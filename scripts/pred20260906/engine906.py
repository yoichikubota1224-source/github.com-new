#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑤ウルトラ・マストバイ係 該当馬抽出（2026-09-06）。
正本: マイトバス.xlsx（札幌4／中山18／阪神14 = 36条件）／ウルトラ回収率2026.02.22.xlsx（阪神11条件）。
      ⚠ 札幌・中山のウルトラ条件は正本に0件。退避CSV由来の札幌8条件は [要確認:正本外] として別掲のみ。
入力: 正本 DE260906.CSV → shutuba_20260906.json（前走は当方5年DBから horse_id 結合で自前算出）
規約:
  ・[不足]は0・消し・断念に変換しない。判定不能は hit=False ではなく missing に記録する
  ・買い目・点数・資金配分・購入可否・最終印・軸は一切出さない
  ・確定オッズ・確定人気は使用しない
  ・前走値は当方5年DB由来を第一とする（[実]）。DE23/24/25列は突合と欠測時の補完のみ（[推:列同定]）
"""
import json, os, re, csv, collections

D = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'predictions', '20260906')
SP = '/tmp/claude-0/-home-user-github-com-new/47c1892c-ddc4-50e4-8b6f-3403a9782673/scratchpad'

# ---------- 父系統マスタ（[推:系統]。正本に父系列が無いため当方の推定） ----------
KEITO = {
 'ストームキャット系': {'ストームキャット','Storm Cat','ヘネシー','ヘニーヒューズ','アジアエクスプレス',
   'モーニン','ヨハネスブルグ','スキャットダディ','ジャイアンツコーズウェイ','フォレストリー',
   'ディスクリートキャット','ハーランズホリデー','イントゥミスチーフ','ドレフォン','シャンハイボビー',
   'アメリカンペイトリオット','カリフォルニアクローム'},
 'エーピーインディ系': {'エーピーインディ','パルピット','タピット','ベルナルディーニ','マリブムーン',
   'コングラッツ','マジェスティックウォリアー','ベストウォーリア','マインシャフト','カジノドライヴ',
   'パイロ','オールドトリエステ','シニスターミニスター','ラニ','タピザー','カレンブラックヒル'},
 'ディープインパクト系': {'ディープインパクト','キズナ','リアルスティール','サトノダイヤモンド','ミッキーアイル',
   'シルバーステート','フィエールマン','ダノンバラード','ワールドエース','トーセンホマレボシ','アルアイン',
   'ダノンキングリー','サトノアラジン','スピルバーグ','トーセンラー','ディーマジェスティ','リアルインパクト',
   'グレーターロンドン','エイシンヒカリ','マカヒキ','ヴァンセンヌ','サトノクラウン','ダノンシャーク',
   'ロジャーバローズ','ダノンプレミアム','コントレイル','シャフリヤール','グローリーヴェイズ',
   'ヘンリーバローズ','ミッキーグローリー','カデナ','トーセンレーヴ','ワールドプレミア','アドマイヤマーズ',
   'ダノンザキッド','ラウダシオン','サリオス','グレナディアガーズ','ヴァンドギャルド','シャドウディーヴァ'},
 'ロベルト系': {'ロベルト','Roberto','ブライアンズタイム','シンボリクリスエス','エピファネイア',
   'スクリーンヒーロー','モーリス','ゴールドアクター','ダイナフォーマー','リアルシャダイ','タニノギムレット',
   'グラスワンダー','シュヴァルグラン','サートゥルナーリア','ジェネラーレウーノ'},
 'グラスワンダー系': {'グラスワンダー','スクリーンヒーロー','モーリス','ゴールドアクター','ジェネラーレウーノ'},
 'キングカメハメハ系': {'キングカメハメハ','ロードカナロア','ドゥラメンテ','ルーラーシップ','レイデオロ',
   'リオンディーズ','ホッコータルマエ','ベルシャザール','ラブリーデイ','ミッキーロケット','エアスピネル',
   'サートゥルナーリア','タリスマニック','ヤマカツエース','リオンリオン','チュウワウィザード',
   'アドミラブル','ダノンスコーピオン','ダノンスマッシュ','タイセイレジェンド','レイエンダ'},
}
def keito_of(sire, group): return sire in KEITO.get(group, set())

# ---------- 騎手照合（DEは4〜5文字丸め。正本表記→DE表記の候補） ----------
JOCKEY = {
 '武豊':['武豊'], 'M.デムーロ':['Ｍ．デム','M.デム','ミルコ'], 'C.ルメール':['ルメール','Ｃ．ルメ'],
 '横山武史':['横山武史','横山武'], '横山和生':['横山和生','横山和'], '横山典弘':['横山典弘','横山典'],
 '田辺裕信':['田辺裕信','田辺'], '石橋脩':['石橋脩'], '津村明秀':['津村明秀','津村'],
 '三浦皇成':['三浦皇成','三浦'], '岩田望来':['岩田望来','岩田望'], '坂井瑠星':['坂井瑠星','坂井'],
 '川田将雅':['川田将雅','川田'], '松山弘平':['松山弘平','松山'], '藤岡佑介':['藤岡佑介','藤岡佑'],
 '浜中俊':['浜中俊','浜中'],
}
def jk_is(name, rule):
    """DE表記(4〜5文字丸め)と正本のフルネームを照合。前方一致のみ（逆方向は別人を拾う）。"""
    if not name: return False
    n = name.strip()
    for pat in JOCKEY.get(rule, [rule]):
        if n == pat or (pat.startswith(n) and len(n) >= 3): return True
    return False

# ---------- 減量（負担重量の減量の有無） ----------
# 9/5の netkeiba 出馬表の減量表示（☆▲△）から確定した騎手群＝[実:9/5表示]。
GENRYO_ALWAYS = {'上里','井上','佐藤','坂口','大久保','小林美','川端','森田','水沼','永島','河原田','石田','遠藤'}
GENRYO_MIXED  = {'石神道','今村','和田陽','長浜','古川奈','田山'}   # 特別戦等で減量が付かない＝レース単位で判定
def genryo_of(h, race, kin_mode):
    """(True/False/None, タグ, 説明)。None=[不足]。"""
    j = h['jockey']
    hit_always = any(j == k or j.startswith(k) or k.startswith(j[:3]) and len(j) >= 3 and j[:3] == k[:3] for k in GENRYO_ALWAYS)
    hit_mixed  = any(j[:3] == k[:3] for k in GENRYO_MIXED)
    base = kin_mode.get((h['sex'], h['age']))
    if base is not None and h['kin'] < base:
        return True, '[推:斤量差]', f"斤{h['kin']}<同性齢の最頻{base}"
    if base is not None and h['kin'] >= base and not (hit_always or hit_mixed):
        return False, '[実:斤量同値]', f"斤{h['kin']}=同性齢の最頻{base}・非見習"
    if hit_always and base is None:
        return True, '[推:9/5減量表示]', f'{j}は9/5に減量表示'
    if base is not None and h['kin'] >= base and (hit_always or hit_mixed):
        return False, '[推:斤量同値]', f"斤{h['kin']}=同性齢の最頻{base}（見習だが減量なしとみられる）"
    return None, '[不足]', '減量の有無を判定できない'

# ---------- マストバイ 36条件（正本マイトバス.xlsx を1行ずつ転記。9/5と同一・再照合済） ----------
MB = []
def mb(ba, td, dists, uchisoto, kind, target, cond, page, p3, fuku, tan, chaku, fn, need, pre2=None):
    MB.append(dict(ba=ba, td=td, dists=dists, uchisoto=uchisoto, kind=kind, target=target, cond=cond,
                   page=page, p3=p3, fuku=fuku, tan=tan, chaku=chaku, fn=fn, need=need,
                   pre=_pre(target), pre2=(pre2 or (lambda h, r, d: True))))
def _pre(target):
    t = target.strip()
    m = re.match(r'^(?:父[：:]|父が)(.+?)(?:種牡馬)?$', t)
    if m:
        v = m.group(1).strip()
        if v.endswith('系'): return lambda h, r, d: keito_of(h.get('sire'), v)
        return lambda h, r, d: h.get('sire') == v
    m = re.match(r'^(?:鞍上[：:])(.+)$', t) or re.match(r'^(.+?)騎手$', t)
    if m:
        v = m.group(1).strip()
        return lambda h, r, d: jk_is(h.get('jockey'), v)
    return lambda h, r, d: True
# --- 札幌 4 ---
mb('札幌','ダ',[1000,1700],None,'血統','父：ドレフォン','前走の着順が8着以内、かつ、前走の4コーナー通過順が3番手以下','P249',0.552,1.39,0.52,'3-6-7-13/29',
   lambda h,r,d: h['sire']=='ドレフォン' and d['zen_chaku']<=8 and d['corner4']>=3, ['zen_chaku','corner4'])
mb('札幌','ダ',[1000,1700,2400],None,'血統','父：マジェスティックウォリアー','枠番が4〜8枠','P249',0.458,1.48,2.23,'8-7-7-26/48',
   lambda h,r,d: h['sire']=='マジェスティックウォリアー' and 4<=h['waku']<=8, [])
mb('札幌','ダ',[1700],None,'血統','父：ホッコータルマエ','前走の着順が9着以内、かつ、前走の馬体重が440kg以上','P250',0.424,2.08,0.81,'1-6-7-19/33',
   lambda h,r,d: h['sire']=='ホッコータルマエ' and d['zen_chaku']<=9 and d['zen_weight']>=440, ['zen_chaku','zen_weight'])
mb('札幌','ダ',[1700],None,'ジョッキー','鞍上：武豊','無条件','P250',0.522,1.35,2.27,'13-5-6-22/46',
   lambda h,r,d: jk_is(h['jockey'],'武豊'), [])
# --- 中山 18 ---
mb('中山','芝',[1200,1600,1800],{1200:'外',1600:'外',1800:'内'},'血統','父：シルバーステート','枠番が1〜4枠','P053',0.436,1.57,1.82,'11-6-7-31/55',
   lambda h,r,d: h['sire']=='シルバーステート' and 1<=h['waku']<=4, [])
mb('中山','芝',[1600],{1600:'外'},'ジョッキー','鞍上：M.デムーロ','前走のコースが今回と同じ距離か今回より長い距離','P053',0.518,1.36,1.48,'14-5-10-27/56',
   lambda h,r,d: jk_is(h['jockey'],'M.デムーロ') and d['zen_dist']>=r['dist'], ['zen_dist'])
mb('中山','芝',[1600,1800],{1600:'外',1800:'内'},'血統','父：キズナ','前走の馬体重が460kg以上','P054',0.403,1.78,1.36,'8-9-8-37/62',
   lambda h,r,d: h['sire']=='キズナ' and d['zen_weight']>=460, ['zen_weight'])
mb('中山','芝',[1800],{1800:'内'},'血統','父：ディープインパクト系種牡馬','前走の上がり3ハロンタイム順位が3位以内','P054',0.542,1.55,1.00,'13-10-9-27/59',
   lambda h,r,d: keito_of(h['sire'],'ディープインパクト系') and d['agari_rank']<=3, ['agari_rank'])
mb('中山','芝',[1800],{1800:'内'},'ジョッキー','鞍上：横山武史','前走の上がり3ハロンタイム順位が4位以内','P055',0.724,1.40,0.82,'5-8-8-8/29',
   lambda h,r,d: jk_is(h['jockey'],'横山武史') and d['agari_rank']<=4, ['agari_rank'])
mb('中山','芝',[1800,2000],{1800:'内',2000:'内'},'血統','父：リアルスティール','馬番が1〜13番、かつ、負担重量が減量なし','P055',0.441,1.53,1.00,'7-4-4-19/34',
   lambda h,r,d: h['sire']=='リアルスティール' and 1<=h['uma']<=13 and d['genryo'] is False, ['genryo'],
   pre2=lambda h,r,d: 1<=h['uma']<=13)
mb('中山','芝',[2000],{2000:'内'},'血統','父：エピファネイア','馬齢が3歳以下、かつ、性が牡・セン','P056',0.465,1.29,0.53,'7-6-7-23/43',
   lambda h,r,d: h['sire']=='エピファネイア' and h['age']<=3 and h['sex'] in ('牡','セ'), [])
mb('中山','芝',[2000,2200],{2000:'内',2200:'外'},'血統','父：モーリス','前走との間隔が中5週以上、かつ、出走頭数が17頭以下','P056',0.537,1.69,1.52,'10-5-7-19/41',
   lambda h,r,d: h['sire']=='モーリス' and d['naka']>=5 and r['n_entry']<=17, ['naka'], pre2=lambda h,r,d: r['n_entry']<=17)
mb('中山','芝',[2000,2200],{2000:'内',2200:'外'},'ジョッキー','鞍上：田辺裕信','調教師の所属が美浦、かつ、前走のコースが1800m以上','P057',0.457,1.60,2.22,'13-9-10-38/70',
   lambda h,r,d: jk_is(h['jockey'],'田辺裕信') and h['belong']=='美' and d['zen_dist']>=1800, ['zen_dist'],
   pre2=lambda h,r,d: h['belong']=='美')
mb('中山','芝',[2200],{2200:'外'},'血統','父：ディープインパクト系種牡馬','馬齢が4歳以下、かつ、負担重量が減量なし','P057',0.431,1.55,1.85,'11-9-8-37/65',
   lambda h,r,d: keito_of(h['sire'],'ディープインパクト系') and h['age']<=4 and d['genryo'] is False, ['genryo'],
   pre2=lambda h,r,d: h['age']<=4)
mb('中山','ダ',[1200],None,'血統','父：ロードカナロア','前走の馬体重が480kg以上、かつ、前走の4コーナー通過順が12番手以内','P065',0.444,1.69,2.05,'11-10-3-30/54',
   lambda h,r,d: h['sire']=='ロードカナロア' and d['zen_weight']>=480 and d['corner4']<=12, ['zen_weight','corner4'])
mb('中山','ダ',[1200],None,'ジョッキー','鞍上：石橋脩','前走の着順が10着以内、かつ、出走頭数が16頭','P065',0.500,1.29,1.32,'7-13-12-32/64',
   lambda h,r,d: jk_is(h['jockey'],'石橋脩') and d['zen_chaku']<=10 and r['n_entry']==16, ['zen_chaku'],
   pre2=lambda h,r,d: r['n_entry']==16)
mb('中山','ダ',[1200],None,'ジョッキー','鞍上：津村明秀','前走のコースが今回と異なる競馬場、かつ、前走の着順が12着以内','P066',0.441,1.44,2.66,'11-9-10-38/68',
   lambda h,r,d: jk_is(h['jockey'],'津村明秀') and d['zen_ba']!=r['ba'] and d['zen_chaku']<=12, ['zen_ba','zen_chaku'])
mb('中山','ダ',[1200],None,'ジョッキー','鞍上：三浦皇成','馬齢が4歳以上、かつ、前走の着順が13着以内','P066',0.449,1.31,0.46,'8-12-11-38/69',
   lambda h,r,d: jk_is(h['jockey'],'三浦皇成') and h['age']>=4 and d['zen_chaku']<=13, ['zen_chaku'],
   pre2=lambda h,r,d: h['age']>=4)
mb('中山','ダ',[1200],None,'ジョッキー','鞍上：横山武史','前走の着順が5着以下、かつ、前走の4コーナー通過順が12番手以内','P067',0.444,1.42,1.46,'11-8-13-40/72',
   lambda h,r,d: jk_is(h['jockey'],'横山武史') and d['zen_chaku']>=5 and d['corner4']<=12, ['zen_chaku','corner4'])
mb('中山','ダ',[1200,1800],None,'血統','父：イスラボニータ','性が牝、かつ、負担重量が減量なし','P067',0.543,1.23,0.70,'8-5-6-16/35',
   lambda h,r,d: h['sire']=='イスラボニータ' and h['sex']=='牝' and d['genryo'] is False, ['genryo'],
   pre2=lambda h,r,d: h['sex']=='牝')
mb('中山','ダ',[1800],None,'ジョッキー','鞍上：横山和生','前走の馬体重が480kg以上','P068',0.426,1.58,3.33,'7-10-9-35/61',
   lambda h,r,d: jk_is(h['jockey'],'横山和生') and d['zen_weight']>=480, ['zen_weight'])
mb('中山','ダ',[1800,2400],None,'血統','父：シニスターミニスター','前走の着順が9着以内','P068',0.442,1.56,1.28,'12-19-11-53/95',
   lambda h,r,d: h['sire']=='シニスターミニスター' and d['zen_chaku']<=9, ['zen_chaku'])
# --- 阪神 14 ---
mb('阪神','芝',[1200],{1200:'内'},'血統','父：ストームキャット系種牡馬','馬番が1〜9番','P116',0.409,1.55,1.66,'6-5-7-26/44',
   lambda h,r,d: keito_of(h['sire'],'ストームキャット系') and 1<=h['uma']<=9, [])
mb('阪神','芝',[1200,1400,1600,1800],{1200:'内',1400:'内',1600:'外',1800:'外'},'ジョッキー','鞍上：岩田望来','枠番が1〜3枠、かつ、馬齢が4歳以下','P116',0.511,1.70,1.62,'17-13-15-43/88',
   lambda h,r,d: jk_is(h['jockey'],'岩田望来') and 1<=h['waku']<=3 and h['age']<=4, [])
mb('阪神','芝',[1400],{1400:'内'},'血統','父：ディープインパクト系種牡馬','枠番が1〜3枠、かつ、前走の着順が9着以内','P117',0.406,1.74,0.37,'7-8-11-38/64',
   lambda h,r,d: keito_of(h['sire'],'ディープインパクト系') and 1<=h['waku']<=3 and d['zen_chaku']<=9, ['zen_chaku'],
   pre2=lambda h,r,d: 1<=h['waku']<=3)
mb('阪神','芝',[1600],{1600:'外'},'ジョッキー','鞍上：坂井瑠星','馬番が1〜8番','P117',0.533,1.45,2.11,'10-10-4-21/45',
   lambda h,r,d: jk_is(h['jockey'],'坂井瑠星') and 1<=h['uma']<=8, [])
mb('阪神','芝',[1800],{1800:'外'},'血統','父：グラスワンダー系種牡馬','性が牡・セン','P118',0.553,1.50,1.02,'10-6-10-21/47',
   lambda h,r,d: keito_of(h['sire'],'グラスワンダー系') and h['sex'] in ('牡','セ'), [])
mb('阪神','芝',[2000],{2000:'内'},'血統','父：キズナ','馬番が1〜7番','P118',0.410,1.65,4.35,'10-9-6-36/61',
   lambda h,r,d: h['sire']=='キズナ' and 1<=h['uma']<=7, [])
mb('阪神','芝',[2000],{2000:'内'},'ジョッキー','鞍上：川田将雅','出走頭数が12頭以下','P119',0.939,1.26,1.00,'16-6-9-2/33',
   lambda h,r,d: jk_is(h['jockey'],'川田将雅') and r['n_entry']<=12, [])
mb('阪神','芝',[2400,2600,3000,3200],None,'血統','父：キズナ','性が牡・セン、かつ、馬齢が5歳以下','P119',0.600,1.65,1.71,'8-5-2-10/25',
   lambda h,r,d: h['sire']=='キズナ' and h['sex'] in ('牡','セ') and h['age']<=5, [])
mb('阪神','ダ',[1200],None,'血統','父：エーピーインディ系種牡馬','性が牡・セン、かつ、馬齢が3歳以下','P128',0.414,1.24,1.27,'15-10-11-51/87',
   lambda h,r,d: keito_of(h['sire'],'エーピーインディ系') and h['sex'] in ('牡','セ') and h['age']<=3, [])
mb('阪神','ダ',[1400,1800],None,'血統','父：シニスターミニスター','馬齢が4歳以下、かつ、出走頭数が15頭以下','P128',0.500,1.34,1.32,'23-21-17-61/122',
   lambda h,r,d: h['sire']=='シニスターミニスター' and h['age']<=4 and r['n_entry']<=15, [])
mb('阪神','ダ',[1800],None,'ジョッキー','鞍上：武豊','無条件','P129',0.500,1.27,0.97,'18-16-6-40/80',
   lambda h,r,d: jk_is(h['jockey'],'武豊'), [])
mb('阪神','ダ',[1800],None,'ジョッキー','鞍上：藤岡佑介','前走の着順が7着以内','P129',0.442,1.31,1.33,'6-6-11-29/52',
   lambda h,r,d: jk_is(h['jockey'],'藤岡佑介') and d['zen_chaku']<=7, ['zen_chaku'])
mb('阪神','ダ',[1800,2000],None,'血統','父：キズナ','馬齢が3歳以下','P130',0.426,1.34,0.80,'18-24-13-74/129',
   lambda h,r,d: h['sire']=='キズナ' and h['age']<=3, [])
mb('阪神','ダ',[1800,2000],None,'ジョッキー','鞍上：松山弘平','前走の着順が5着以下、かつ、馬番が3〜16番','P130',0.577,1.94,1.26,'10-17-14-30/71',
   lambda h,r,d: jk_is(h['jockey'],'松山弘平') and d['zen_chaku']>=5 and 3<=h['uma']<=16, ['zen_chaku'],
   pre2=lambda h,r,d: 3<=h['uma']<=16)

# ---------- ウルトラ（正本＝阪神11条件のみ。札幌・中山は正本に0件） ----------
UL = []
def ul(no, ba, td, dmin, dmax, uchisoto, c1, c2, p3, tan, fuku, fn, need, pre2=None):
    UL.append(dict(no=no, ba=ba, td=td, dmin=dmin, dmax=dmax, uchisoto=uchisoto, c1=c1, c2=c2,
                   p3=p3, tan=tan, fuku=fuku, fn=fn, need=need, pre=_pre(c1),
                   pre2=(pre2 or (lambda h, r, d: True))))
ul('045','阪神','芝',1200,1200,'内','父がストームキャット系種牡馬','枠番が1～6枠',51.4,126,191,
   lambda h,r,d: keito_of(h['sire'],'ストームキャット系') and 1<=h['waku']<=6, [])
ul('046','阪神','芝',1400,1600,None,'父がハービンジャー','馬齢が4歳以下',39.6,327,209,
   lambda h,r,d: h['sire']=='ハービンジャー' and h['age']<=4, [])
ul('047','阪神','芝',1600,1800,None,'岩田望来騎手','前走馬体重480kg以上',55.6,97,182,
   lambda h,r,d: jk_is(h['jockey'],'岩田望来') and d['zen_weight']>=480, ['zen_weight'])
ul('048','阪神','芝',1800,1800,'外','父がロベルト系種牡馬','前走10着以内',40.0,163,162,
   lambda h,r,d: keito_of(h['sire'],'ロベルト系') and d['zen_chaku']<=10, ['zen_chaku'])
ul('052','阪神','ダ',1400,1800,None,'父がシニスターミニスター','馬番3～16＋関西馬（栗東）',44.5,123,151,
   lambda h,r,d: h['sire']=='シニスターミニスター' and 3<=h['uma']<=16 and h['belong']=='栗', [])
ul('053','阪神','ダ',1400,1800,None,'父がドレフォン','前走上がり（3F順位）4位以内',45.7,101,161,
   lambda h,r,d: h['sire']=='ドレフォン' and d['agari_rank']<=4, ['agari_rank'])
ul('054','阪神','ダ',1800,1800,None,'父がキズナ','3歳以下＋前走馬体重480kg以上',66.0,137,192,
   lambda h,r,d: h['sire']=='キズナ' and h['age']<=3 and d['zen_weight']>=480, ['zen_weight'],
   pre2=lambda h,r,d: h['age']<=3)
ul('055','阪神','ダ',1800,2000,None,'武豊騎手','3歳以下＋性が牡・セ',66.7,153,211,
   lambda h,r,d: jk_is(h['jockey'],'武豊') and h['age']<=3 and h['sex'] in ('牡','セ'), [])
ul('056','阪神','ダ',1800,2000,None,'M.デムーロ騎手','3歳以下',57.7,31,206,
   lambda h,r,d: jk_is(h['jockey'],'M.デムーロ') and h['age']<=3, [])
ul('057','阪神','ダ',1800,2000,None,'横山典弘騎手','馬番1～10＋9頭立て以上',41.5,67,155,
   lambda h,r,d: jk_is(h['jockey'],'横山典弘') and 1<=h['uma']<=10 and r['n_entry']>=9, [])
ul('058','阪神','ダ',2000,2000,None,'松山弘平騎手','前走馬体重520kg未満',65.2,96,160,
   lambda h,r,d: jk_is(h['jockey'],'松山弘平') and d['zen_weight']<520, ['zen_weight'])

# ---------- 札幌ウルトラ（退避CSV由来＝[要確認:正本外]。参考別掲のみ・採用しない） ----------
UL_REF = [
 ('099','札幌','芝',1200,1500,'浜中俊騎手','前走8着以内＋4歳以下',58.6,169,155),
 ('100','札幌','芝',1200,2600,'父がキタサンブラック','前走4角11番手以内',50.9,282,187),
 ('101','札幌','芝',1500,1500,'前走上がり2位以内','前走馬体重460kg未満',45.1,65,155),
 ('102','札幌','芝',2000,2000,'1～2番','3歳以下',36.9,364,209),
 ('103','札幌','芝',2600,2600,'前走上がり1位','1～5枠',50.0,82,159),
 ('104','札幌','ダ',1000,1000,'父がエーピーインディ系種牡馬','3～8枠',48.5,409,166),
 ('105','札幌','ダ',1000,1700,'父がホッコータルマエ','10頭立て以上',46.7,355,166),
 ('106','札幌','ダ',1700,1700,'武豊騎手','牡・セン',56.8,285,150),
]

def main():
    R = json.load(open(os.path.join(D, 'shutuba_20260906.json')))
    mb_hits, ul_hits, missing, ul_ref_hits, shinba_false = [], [], [], [], []
    n_flat = n_horse = 0
    for r in R:
        if r['jump']:
            continue
        n_flat += 1
        kin_mode = {}
        grp = collections.defaultdict(list)
        for h in r['horses']: grp[(h['sex'], h['age'])].append(h['kin'])
        for k, v in grp.items(): kin_mode[k] = collections.Counter(v).most_common(1)[0][0]
        for h in r['horses']:
            n_horse += 1
            g, gtag, gnote = genryo_of(h, r, kin_mode)
            # 前走値: 当方5年DB由来を第一（[実]）。無ければDE列で補完（[推:列同定]）
            src = {}
            def pick(dbv, dev, key, detag='[推:列同定]'):
                if dbv is not None: src[key] = '[実:当方5年DB]'; return dbv
                if dev: src[key] = detag + '(DE補完)'; return dev
                src[key] = '[不足]'; return None
            d = dict(
                zen_chaku = pick(h['zen_chaku'], h['de_zen_chaku'] or None, 'zen_chaku'),
                zen_pop   = pick(h['zen_pop'], h['de_zen_ninki'] or None, 'zen_pop'),
                zen_weight= h['zen_weight'], zen_dist = h['zen_dist'], zen_ba = h['zen_ba'],
                agari_rank= h['zen_agari_rank'], corner4 = h['zen_corner4'],
                naka      = (h['weeks'] - 1 if h['weeks'] else (h['de_zen_kan'] - 1 if h['de_zen_kan'] else None)),
                genryo    = g, genryo_tag = gtag, genryo_note = gnote, src = src)
            for k in ('zen_weight','zen_dist','zen_ba','agari_rank','corner4'):
                src[k] = '[実:当方5年DB]' if d[k] is not None else '[不足]'
            src['naka'] = '[実:当方5年DB]' if h['weeks'] else ('[推:列同定](DE補完)' if h['de_zen_kan'] else '[不足]')
            for C, box, kind in ((MB, mb_hits, 'マストバイ'), (UL, ul_hits, 'ウルトラ')):
                for c in C:
                    if c['ba'] != r['ba'] or c['td'] != r['td']: continue
                    if kind == 'マストバイ':
                        if r['dist'] not in c['dists']: continue
                        want = c['uchisoto'].get(r['dist']) if c['uchisoto'] else None
                    else:
                        if not (c['dmin'] <= r['dist'] <= c['dmax']): continue
                        want = c['uchisoto']
                    if want and r['uchisoto'] and want != r['uchisoto']: continue
                    if want and not r['uchisoto']:
                        missing.append(dict(kind=kind, ba=r['ba'], r=r['r'], uma=h['uma'], name=h['name'],
                                            対象=c.get('target') or c.get('c1'), missing=['内外']))
                        continue
                    if not c['pre'](h, r, d): continue          # 対象(父/鞍上)で確定的に非該当なら[不足]にしない
                    if not c['pre2'](h, r, d): continue
                    lack = [k for k in c['need'] if d.get(k) is None]
                    # 新馬戦かつ出走履歴なし＝前走が存在しない。前走依存条件は[実]で条件不成立とし、
                    # [不足]に水増ししない（2026-08-30に確定した扱い）。
                    if lack and r['shinba'] and h['past_n'] == 0 and any(k.startswith('zen') or k in ('agari_rank','corner4','naka') for k in lack):
                        shinba_false.append(dict(kind=kind, ba=r['ba'], r=r['r'], uma=h['uma'], name=h['name'],
                                                 対象=c.get('target') or c.get('c1'), 条件=c.get('cond') or c.get('c2'),
                                                 理由='新馬=前走なし→[実]条件不成立', 欠測扱いにしない=lack))
                        continue
                    if lack:
                        missing.append(dict(kind=kind, ba=r['ba'], r=r['r'], uma=h['uma'], name=h['name'],
                                            対象=c.get('target') or c.get('c1'), 条件=c.get('cond') or c.get('c2'),
                                            missing=lack, page=c.get('page'), no=c.get('no')))
                        continue
                    try: ok = c['fn'](h, r, d)
                    except Exception as e:
                        missing.append(dict(kind='ERR', err=str(e), ba=r['ba'], r=r['r'], uma=h['uma'])); continue
                    if ok:
                        box.append(dict(ba=r['ba'], r=r['r'], cls=r['cls'],
                            course=f"{r['td']}{r['dist']}{r['uchisoto'] or ''}", n=r['n_entry'],
                            waku=h['waku'], uma=h['uma'], name=h['name'], sire=h['sire'], jockey=h['jockey'],
                            belong=h['belong'], sex=h['sex'], age=h['age'], kin=h['kin'],
                            no=c.get('no'), 種別=c.get('kind'), 対象=c.get('target') or c.get('c1'),
                            条件=c.get('cond') or c.get('c2'), page=c.get('page'),
                            p3=c['p3'], fuku=c['fuku'], tan=c['tan'], chaku=c.get('chaku'),
                            zen=dict(chaku=d['zen_chaku'], pop=d['zen_pop'], weight=d['zen_weight'],
                                     dist=d['zen_dist'], ba=d['zen_ba'], agari=d['agari_rank'],
                                     corner4=d['corner4'], naka=d['naka'], date=h['zen_date']),
                            genryo=d['genryo'], genryo_tag=d['genryo_tag'], src=dict(src)))
            # 札幌ウルトラ（参考・正本外）は「条件①が父/騎手/馬番」のみ機械判定
            for no, ba, td, dmin, dmax, c1, c2, p3, tan, fuku in UL_REF:
                if ba != r['ba'] or td != r['td'] or not (dmin <= r['dist'] <= dmax): continue
                m1 = re.match(r'^父が(.+?)(?:種牡馬)?$', c1); m2 = re.match(r'^(.+?)騎手$', c1)
                m3 = re.match(r'^(\d+)[～~](\d+)番$', c1)
                if m1:
                    v = m1.group(1)
                    ok1 = keito_of(h['sire'], v) if v.endswith('系') else (h['sire'] == v)
                elif m2: ok1 = jk_is(h['jockey'], m2.group(1))
                elif m3: ok1 = int(m3.group(1)) <= h['uma'] <= int(m3.group(2))
                elif c1 == '前走上がり2位以内': ok1 = (d['agari_rank'] is not None and d['agari_rank'] <= 2)
                elif c1 == '前走上がり1位': ok1 = (d['agari_rank'] is not None and d['agari_rank'] == 1)
                else: ok1 = None
                if ok1 is not True: continue
                ul_ref_hits.append(dict(no=no, ba=r['ba'], r=r['r'], course=f"{r['td']}{r['dist']}",
                    uma=h['uma'], waku=h['waku'], name=h['name'], sire=h['sire'], jockey=h['jockey'],
                    c1=c1, c2=c2, p3=p3, tan=tan, fuku=fuku,
                    条件2判定='未評価（正本外のため機械判定を止めた）',
                    zen=dict(chaku=d['zen_chaku'], weight=d['zen_weight'], agari=d['agari_rank'], corner4=d['corner4'])))
    # W該当（同一馬がMBとULの双方）
    mbk = {(x['ba'], x['r'], x['uma']) for x in mb_hits}
    ulk = {(x['ba'], x['r'], x['uma']) for x in ul_hits}
    both = sorted(mbk & ulk)
    json.dump(dict(version='engine906_v1', raceday='20260906', mustbuy=mb_hits, ultra=ul_hits,
                   ultra_ref_sapporo=ul_ref_hits, missing=missing, shinba_false=shinba_false,
                   both=[dict(ba=a, r=b, uma=c) for a, b, c in both],
                   counts=dict(平地R=n_flat, 平地頭数=n_horse, MB=len(mb_hits), UL=len(ul_hits),
                               UL参考=len(ul_ref_hits), 判定不能=len(missing),
                               新馬で条件不成立=len(shinba_false), W該当=len(both))),
              open(os.path.join(D, 'hits_20260906.json'), 'w'), ensure_ascii=False, indent=1)
    print(f'[実] 平地{n_flat}R・{n_horse}頭（中山1R障害7頭は対象外）')
    print(f'[実] マストバイ {len(mb_hits)}頭 / ウルトラ(正本) {len(ul_hits)}頭 / 判定不能[不足] {len(missing)}件 / 新馬で不成立 {len(shinba_false)}件 / W該当 {len(both)}頭')
    print('[実] W該当（マストバイとウルトラの双方）:', [f"{a}{b}R{c}番" for a,b,c in both])
    print('\n=== マストバイ ===')
    for x in sorted(mb_hits, key=lambda x: (x['ba'], x['r'], x['uma'])):
        z = x['zen']
        print(f"  {x['ba']}{x['r']:>2}R {x['course']:<9} {x['uma']:>2}番 {x['name']:<12} 父{x['sire']:<13} 鞍上{x['jockey']:<6} | {x['対象']} / {x['条件']} ({x['page']} 3着内{x['p3']:.1%} 複回{x['fuku']})")
        print(f"        前走: {z['date'] or '—'} {z['ba'] or ''}{z['dist'] or ''}m {z['chaku'] or '—'}着 {z['pop'] or '—'}人気 馬体重{z['weight'] or '—'} 上がり{z['agari'] or '—'}位 4角{z['corner4'] or '—'} 中{z['naka'] if z['naka'] is not None else '—'}週")
    print('\n=== ウルトラ（正本・阪神11条件） ===')
    for x in sorted(ul_hits, key=lambda x: (x['ba'], x['r'], x['uma'])):
        z = x['zen']
        print(f"  No.{x['no']} {x['ba']}{x['r']:>2}R {x['course']:<9} {x['uma']:>2}番 {x['name']:<12} 父{x['sire']:<13} 鞍上{x['jockey']:<6} | {x['対象']} / {x['条件']} (3着内{x['p3']}% 単回{x['tan']} 複回{x['fuku']})")
        print(f"        前走: {z['date'] or '—'} {z['chaku'] or '—'}着 馬体重{z['weight'] or '—'} 上がり{z['agari'] or '—'}位")
    print(f'\n=== 札幌ウルトラ（退避CSV由来＝[要確認:正本外]・参考別掲 {len(ul_ref_hits)}頭）===')
    for x in sorted(ul_ref_hits, key=lambda x: (x['r'], x['uma'])):
        print(f"  No.{x['no']} 札幌{x['r']:>2}R {x['course']:<8} {x['uma']:>2}番 {x['name']:<12} 父{x['sire']:<13} 鞍上{x['jockey']:<6} | ①{x['c1']} ②{x['c2']}")
    print(f'\n=== 新馬戦で前走条件が[実]不成立（[不足]に数えない）{len(shinba_false)}件 ===')
    for m in shinba_false:
        print(f"   {m['ba']}{m['r']}R {m['uma']}番 {m['name']} {m['対象']} / {m['条件']}")
    print('\n=== 判定不能([不足]) ===')
    for k, v in collections.Counter(tuple(m.get('missing', [])) for m in missing).most_common():
        print(f'  {k}: {v}件')
    for m in missing[:20]:
        print(f"   {m.get('ba')}{m.get('r')}R {m.get('uma')}番 {m.get('name')} {m.get('対象')} 欠測={m.get('missing')}")

main()
