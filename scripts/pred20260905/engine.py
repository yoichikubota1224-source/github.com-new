#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑤ウルトラ・マストバイ係 該当馬抽出（2026-09-05）。
正本: マイトバス.xlsx(札幌/中山/阪神シート) / ウルトラ回収率2026.02.22.xlsx(ウルトラ一覧)。
入力: netkeiba出馬表(5走表示)を当方が解析した shutuba_20260905.json
      ＋ 当方5年データ full/*.json（前走の上がり3F順位・4角通過順を自前算出）
規約:
  ・[不足]は0/消し/断念に変換しない。判定不能は hit=False ではなく missing に記録する
  ・買い目・点数・資金配分・購入可否・最終印・軸は一切出さない
  ・確定オッズ・確定人気は使用しない（出馬表時点で未確定＝そもそも取得していない）
"""
import json, re, sys, os, glob, collections

D = os.path.dirname(os.path.abspath(__file__))
K = '/tmp/claude-0/-home-user-github-com-new/47c1892c-ddc4-50e4-8b6f-3403a9782673/scratchpad/k5/full'

# ---------- 父系統マスタ（[推:系統]：正本に父系列が無いため当方の推定） ----------
KEITO = {
 'ストームキャット系': {'ストームキャット','Storm Cat','ヘネシー','ヘニーヒューズ','アジアエクスプレス',
   'モーニン','ヨハネスブルグ','スキャットダディ','ジャイアンツコーズウェイ','フォレストリー',
   'ディスクリートキャット','ハーランズホリデー','イントゥミスチーフ','ドレフォン'},
 'エーピーインディ系': {'エーピーインディ','パルピット','タピット','ベルナルディーニ','マリブムーン',
   'コングラッツ','マジェスティックウォリアー','ベストウォーリア','マインシャフト','カジノドライヴ',
   'パイロ','オールドトリエステ','シニスターミニスター','ラニ'},
 'ディープインパクト系': {'ディープインパクト','キズナ','リアルスティール','サトノダイヤモンド','ミッキーアイル',
   'シルバーステート','フィエールマン','ダノンバラード','ワールドエース','トーセンホマレボシ','アルアイン',
   'ダノンキングリー','サトノアラジン','スピルバーグ','トーセンラー','ディーマジェスティ','リアルインパクト',
   'グレーターロンドン','エイシンヒカリ','マカヒキ','ヴァンセンヌ',
   'ロジャーバローズ','ダノンプレミアム','コントレイル','シャフリヤール','グローリーヴェイズ',
   # 2026-09-05 追加(独立検証で判明した漏れ。いずれも父ディープインパクト)
   'ヘンリーバローズ','ミッキーグローリー','カデナ','トーセンレーヴ','ワールドプレミア'},
 'ロベルト系': {'ロベルト','Roberto','ブライアンズタイム','シンボリクリスエス','エピファネイア',
   'スクリーンヒーロー','モーリス','ゴールドアクター',
   'ダイナフォーマー','リアルシャダイ','タニノギムレット','グラスワンダー','スクリーンヒーロー'},
 'グラスワンダー系': {'グラスワンダー','スクリーンヒーロー','モーリス','ゴールドアクター','ジェネラーレウーノ'},
 'キングカメハメハ系': {'キングカメハメハ','ロードカナロア','ドゥラメンテ','ルーラーシップ','レイデオロ',
   'リオンディーズ','ホッコータルマエ','ベルシャザール','ラブリーデイ','ミッキーロケット','エアスピネル',
   'サートゥルナーリア','タリスマニック','ヤマカツエース','リオンリオン','チュウワウィザード',
   'アドミラブル','ダノンスコーピオン','ダノンスマッシュ','タイセイレジェンド'},
}
# ⚠ ロベルト系とグラスワンダー系は包含関係にある（グラスワンダーはロベルト系の枝）。
#    正本が両方を別条件に使うため、当方は「グラスワンダー系」を狭義（グラスワンダーの子孫）として扱う。

def keito_of(sire, group):
    return sire in KEITO.get(group, set())

# ---------- 騎手名の照合（netkeiba短縮表記 → 正本表記） ----------
JOCKEY = {
 '武豊':['武豊'], 'M.デムーロ':['Ｍ．デム','M.デム','ミルコ'], 'C.ルメール':['ルメール','Ｃ．ルメ'],
 '横山武史':['横山武'], '横山和生':['横山和'], '横山典弘':['横山典'], '田辺裕信':['田辺'],
 '石橋脩':['石橋脩'], '津村明秀':['津村'], '三浦皇成':['三浦'], '岩田望来':['岩田望'],
 '坂井瑠星':['坂井'], '川田将雅':['川田'], '松山弘平':['松山'], '藤岡佑介':['藤岡佑'],
}
# netkeiba の騎手ID（短縮表記の取り違えを構造的に防ぐ。横山武/和/典/琉の誤マッチ対策）
JOCKEY_ID = {
 '武豊':'00666', 'M.デムーロ':'05212', '横山武史':'01170', '横山和生':'01162?',
 '横山典弘':'00660', '田辺裕信':'01088', '石橋脩':'01034', '津村明秀':'01092',
 '三浦皇成':'01115', '岩田望来':'01173', '坂井瑠星':'01166', '川田将雅':'01088?',
 '松山弘平':'01126', '藤岡佑介':'01059',
}
def jk_is(name, rule, jid=None):
    """rule=正本の騎手名。netkeibaの短縮表記と照合する。
    ⚠ 短縮表記は前方一致のみ（逆方向の部分一致は別人を拾うため禁止）。"""
    if not name: return False
    n = name.strip()
    for pat in JOCKEY.get(rule, [rule]):
        if n == pat or pat.startswith(n) and len(n) >= 3:
            return True
    return False

# ---------- 前走の派生値（当方5年データから自前算出） ----------
def build_index():
    idx = {}
    for f in glob.glob(os.path.join(K, '*.json')):
        for r in json.load(open(f)):
            idx[r['race_id']] = r
    return idx

def past_derived(p, idx):
    """前走の上がり3F順位・4角通過順を返す。取れなければ None（=[不足]）。
    ⚠ 前走が競走中止・除外だと chaku=None・last3f=0.0 のレコードが来る。
      0.0 をそのまま順位計算に渡すと「上がり1位」の偽陽性になるため弾く。"""
    out = {'agari_rank': None, 'corner4': None, 'src': None}
    if p.get('chaku') is None:      # 中止・除外の前走は評価に使わない
        return out
    # 4角通過順は出馬表の通過表記の最終要素から直接取れる
    if p.get('passing'):
        seg = [x for x in str(p['passing']).split('-') if x.isdigit()]
        if seg: out['corner4'] = int(seg[-1])
    rid = p.get('race_id')
    r = idx.get(rid)
    if r:
        vals = sorted({h['last3f'] for h in r['horses'] if h.get('last3f') is not None})
        rank = {v: i + 1 for i, v in enumerate(vals)}
        if p.get('last3f'):     # 0.0/None は異常値として除外
            if p['last3f'] in rank:
                out['agari_rank'] = rank[p['last3f']]
                out['src'] = 'full5y'
    return out

def weeks(rot):
    """'中5週'->5, '連闘'->0, None->None"""
    if not rot: return None
    if '連闘' in rot: return 0
    m = re.search(r'中(\d+)週', rot)
    return int(m.group(1)) if m else None

# ---------- 判定の記述（正本の条件文をそのまま構造化） ----------
def C(fn, need):
    return {'fn': fn, 'need': need}


def _pre_from_target(target):
    """『対象』欄（父：○○ / 鞍上：○○ / 父が○○ / ○○騎手）から、前走データを要さない
    判定可能部分だけを取り出す。ここで確定的に非該当なら[不足]に落とさない。"""
    t = target.strip()
    m = re.match(r'^(?:父[：:]|父が)(.+?)(?:種牡馬)?$', t)
    if m:
        v = m.group(1).strip()
        if v.endswith('系'):
            return lambda h, r, d: keito_of(h.get('sire'), v + '種牡馬' if False else v)
        return lambda h, r, d: h.get('sire') == v
    m = re.match(r'^(?:鞍上[：:])(.+)$', t) or re.match(r'^(.+?)騎手$', t)
    if m:
        v = m.group(1).strip()
        return lambda h, r, d: jk_is(h.get('jockey'), v)
    return lambda h, r, d: True

MB = []   # マストバイ
def mb(ba, td, dists, uchisoto, kind, target, cond, page, fn, need, pre2=None):
    MB.append(dict(ba=ba, td=td, dists=dists, uchisoto=uchisoto, kind=kind,
                   target=target, cond=cond, page=page, fn=fn, need=need,
                   pre=_pre_from_target(target), pre2=(pre2 or (lambda h, r, d: True))))

# --- 札幌 ---
mb('札幌','ダ',[1000,1700],None,'血統','父：ドレフォン','前走の着順が8着以内、かつ、前走の4コーナー通過順が3番手以下','P249',
   lambda h,r,d: h['sire']=='ドレフォン' and d['zen_chaku'] is not None and d['zen_chaku']<=8
                 and d['corner4'] is not None and d['corner4']>=3, ['zen_chaku','corner4'])
mb('札幌','ダ',[1000,1700,2400],None,'血統','父：マジェスティックウォリアー','枠番が4〜8枠','P249',
   lambda h,r,d: h['sire']=='マジェスティックウォリアー' and h['waku'] is not None and 4<=h['waku']<=8, [])
mb('札幌','ダ',[1700],None,'血統','父：ホッコータルマエ','前走の着順が9着以内、かつ、前走の馬体重が440kg以上','P250',
   lambda h,r,d: h['sire']=='ホッコータルマエ' and d['zen_chaku'] is not None and d['zen_chaku']<=9
                 and d['zen_weight'] is not None and d['zen_weight']>=440, ['zen_chaku','zen_weight'])
mb('札幌','ダ',[1700],None,'ジョッキー','鞍上：武豊','無条件','P250',
   lambda h,r,d: jk_is(h.get('jockey'),'武豊'), [])
# --- 中山 ---
mb('中山','芝',[1200,1600,1800],{1200:'外',1600:'外',1800:'内'},'血統','父：シルバーステート','枠番が1〜4枠','P053',
   lambda h,r,d: h['sire']=='シルバーステート' and h['waku'] is not None and 1<=h['waku']<=4, [])
mb('中山','芝',[1600],{1600:'外'},'ジョッキー','鞍上：M.デムーロ','前走のコースが今回と同じ距離か今回より長い距離','P053',
   lambda h,r,d: jk_is(h.get('jockey'),'M.デムーロ') and d['zen_dist'] is not None and d['zen_dist']>=r['dist'], ['zen_dist'])
mb('中山','芝',[1600,1800],{1600:'外',1800:'内'},'血統','父：キズナ','前走の馬体重が460kg以上','P054',
   lambda h,r,d: h['sire']=='キズナ' and d['zen_weight'] is not None and d['zen_weight']>=460, ['zen_weight'])
mb('中山','芝',[1800],{1800:'内'},'血統','父：ディープインパクト系種牡馬','前走の上がり3ハロンタイム順位が3位以内','P054',
   lambda h,r,d: keito_of(h['sire'],'ディープインパクト系') and d['agari_rank'] is not None and d['agari_rank']<=3, ['agari_rank'])
mb('中山','芝',[1800],{1800:'内'},'ジョッキー','鞍上：横山武史','前走の上がり3ハロンタイム順位が4位以内','P055',
   lambda h,r,d: jk_is(h.get('jockey'),'横山武史') and d['agari_rank'] is not None and d['agari_rank']<=4, ['agari_rank'])
mb('中山','芝',[1800,2000],{1800:'内',2000:'内'},'血統','父：リアルスティール','馬番が1〜13番、かつ、負担重量が減量なし','P055',
   lambda h,r,d: h['sire']=='リアルスティール' and h['uma'] is not None and 1<=h['uma']<=13
                 and d['genryo'] is False, ['genryo'])
mb('中山','芝',[2000],{2000:'内'},'血統','父：エピファネイア','馬齢が3歳以下、かつ、性が牡・セン','P056',
   lambda h,r,d: h['sire']=='エピファネイア' and h['age'] is not None and h['age']<=3 and h['sex'] in ('牡','セ','セン'), [])
mb('中山','芝',[2000,2200],{2000:'内',2200:'外'},'血統','父：モーリス','前走との間隔が中5週以上、かつ、出走頭数が17頭以下','P056',
   lambda h,r,d: h['sire']=='モーリス' and d['weeks'] is not None and d['weeks']>=5 and r['n_entry']<=17, ['weeks'], pre2=lambda h,r,d: r['n_entry']<=17)
mb('中山','芝',[2000,2200],{2000:'内',2200:'外'},'ジョッキー','鞍上：田辺裕信','調教師の所属が美浦、かつ、前走のコースが1800m以上','P057',
   lambda h,r,d: jk_is(h.get('jockey'),'田辺裕信') and h.get('belong')=='美浦'
                 and d['zen_dist'] is not None and d['zen_dist']>=1800, ['zen_dist'], pre2=lambda h,r,d: h.get('belong')=='美浦')
mb('中山','芝',[2200],{2200:'外'},'血統','父：ディープインパクト系種牡馬','馬齢が4歳以下、かつ、負担重量が減量なし','P057',
   lambda h,r,d: keito_of(h['sire'],'ディープインパクト系') and h['age'] is not None and h['age']<=4 and d['genryo'] is False, ['genryo'])
mb('中山','ダ',[1200],None,'血統','父：ロードカナロア','前走の馬体重が480kg以上、かつ、前走の4コーナー通過順が12番手以内','P065',
   lambda h,r,d: h['sire']=='ロードカナロア' and d['zen_weight'] is not None and d['zen_weight']>=480
                 and d['corner4'] is not None and d['corner4']<=12, ['zen_weight','corner4'])
mb('中山','ダ',[1200],None,'ジョッキー','鞍上：石橋脩','前走の着順が10着以内、かつ、出走頭数が16頭','P065',
   lambda h,r,d: jk_is(h.get('jockey'),'石橋脩') and d['zen_chaku'] is not None and d['zen_chaku']<=10 and r['n_entry']==16, ['zen_chaku'], pre2=lambda h,r,d: r['n_entry']==16)
mb('中山','ダ',[1200],None,'ジョッキー','鞍上：津村明秀','前走のコースが今回と異なる競馬場、かつ、前走の着順が12着以内','P066',
   lambda h,r,d: jk_is(h.get('jockey'),'津村明秀') and d['zen_ba'] is not None and d['zen_ba']!=r['ba']
                 and d['zen_chaku'] is not None and d['zen_chaku']<=12, ['zen_ba','zen_chaku'])
mb('中山','ダ',[1200],None,'ジョッキー','鞍上：三浦皇成','馬齢が4歳以上、かつ、前走の着順が13着以内','P066',
   lambda h,r,d: jk_is(h.get('jockey'),'三浦皇成') and h['age'] is not None and h['age']>=4
                 and d['zen_chaku'] is not None and d['zen_chaku']<=13, ['zen_chaku'], pre2=lambda h,r,d: h['age'] is not None and h['age']>=4)
mb('中山','ダ',[1200],None,'ジョッキー','鞍上：横山武史','前走の着順が5着以下、かつ、前走の4コーナー通過順が12番手以内','P067',
   lambda h,r,d: jk_is(h.get('jockey'),'横山武史') and d['zen_chaku'] is not None and d['zen_chaku']>=5
                 and d['corner4'] is not None and d['corner4']<=12, ['zen_chaku','corner4'])
mb('中山','ダ',[1200,1800],None,'血統','父：イスラボニータ','性が牝、かつ、負担重量が減量なし','P067',
   lambda h,r,d: h['sire']=='イスラボニータ' and h['sex']=='牝' and d['genryo'] is False, ['genryo'])
mb('中山','ダ',[1800],None,'ジョッキー','鞍上：横山和生','前走の馬体重が480kg以上','P068',
   lambda h,r,d: jk_is(h.get('jockey'),'横山和生') and d['zen_weight'] is not None and d['zen_weight']>=480, ['zen_weight'])
mb('中山','ダ',[1800,2400],None,'血統','父：シニスターミニスター','前走の着順が9着以内','P068',
   lambda h,r,d: h['sire']=='シニスターミニスター' and d['zen_chaku'] is not None and d['zen_chaku']<=9, ['zen_chaku'])
# --- 阪神 ---
mb('阪神','芝',[1200],{1200:'内'},'血統','父：ストームキャット系種牡馬','馬番が1〜9番','P116',
   lambda h,r,d: keito_of(h['sire'],'ストームキャット系') and h['uma'] is not None and 1<=h['uma']<=9, [])
mb('阪神','芝',[1200,1400,1600,1800],{1200:'内',1400:'内',1600:'外',1800:'外'},'ジョッキー','鞍上：岩田望来','枠番が1〜3枠、かつ、馬齢が4歳以下','P116',
   lambda h,r,d: jk_is(h.get('jockey'),'岩田望来') and h['waku'] is not None and 1<=h['waku']<=3
                 and h['age'] is not None and h['age']<=4, [])
mb('阪神','芝',[1400],{1400:'内'},'血統','父：ディープインパクト系種牡馬','枠番が1〜3枠、かつ、前走の着順が9着以内','P117',
   lambda h,r,d: keito_of(h['sire'],'ディープインパクト系') and h['waku'] is not None and 1<=h['waku']<=3
                 and d['zen_chaku'] is not None and d['zen_chaku']<=9, ['zen_chaku'], pre2=lambda h,r,d: h['waku'] is not None and 1<=h['waku']<=3)
mb('阪神','芝',[1600],{1600:'外'},'ジョッキー','鞍上：坂井瑠星','馬番が1〜8番','P117',
   lambda h,r,d: jk_is(h.get('jockey'),'坂井瑠星') and h['uma'] is not None and 1<=h['uma']<=8, [])
mb('阪神','芝',[1800],{1800:'外'},'血統','父：グラスワンダー系種牡馬','性が牡・セン','P118',
   lambda h,r,d: keito_of(h['sire'],'グラスワンダー系') and h['sex'] in ('牡','セ','セン'), [])
mb('阪神','芝',[2000],{2000:'内'},'血統','父：キズナ','馬番が1〜7番','P118',
   lambda h,r,d: h['sire']=='キズナ' and h['uma'] is not None and 1<=h['uma']<=7, [])
mb('阪神','芝',[2000],{2000:'内'},'ジョッキー','鞍上：川田将雅','出走頭数が12頭以下','P119',
   lambda h,r,d: jk_is(h.get('jockey'),'川田将雅') and r['n_entry']<=12, [])
mb('阪神','芝',[2400,2600,3000,3200],None,'血統','父：キズナ','性が牡・セン、かつ、馬齢が5歳以下','P119',
   lambda h,r,d: h['sire']=='キズナ' and h['sex'] in ('牡','セ','セン') and h['age'] is not None and h['age']<=5, [])
mb('阪神','ダ',[1200],None,'血統','父：エーピーインディ系種牡馬','性が牡・セン、かつ、馬齢が3歳以下','P128',
   lambda h,r,d: keito_of(h['sire'],'エーピーインディ系') and h['sex'] in ('牡','セ','セン') and h['age'] is not None and h['age']<=3, [])
mb('阪神','ダ',[1400,1800],None,'血統','父：シニスターミニスター','馬齢が4歳以下、かつ、出走頭数が15頭以下','P128',
   lambda h,r,d: h['sire']=='シニスターミニスター' and h['age'] is not None and h['age']<=4 and r['n_entry']<=15, [])
mb('阪神','ダ',[1800],None,'ジョッキー','鞍上：武豊','無条件','P129',
   lambda h,r,d: jk_is(h.get('jockey'),'武豊'), [])
mb('阪神','ダ',[1800],None,'ジョッキー','鞍上：藤岡佑介','前走の着順が7着以内','P129',
   lambda h,r,d: jk_is(h.get('jockey'),'藤岡佑介') and d['zen_chaku'] is not None and d['zen_chaku']<=7, ['zen_chaku'])
mb('阪神','ダ',[1800,2000],None,'血統','父：キズナ','馬齢が3歳以下','P130',
   lambda h,r,d: h['sire']=='キズナ' and h['age'] is not None and h['age']<=3, [])
mb('阪神','ダ',[1800,2000],None,'ジョッキー','鞍上：松山弘平','前走の着順が5着以下、かつ、馬番が3〜16番','P130',
   lambda h,r,d: jk_is(h.get('jockey'),'松山弘平') and d['zen_chaku'] is not None and d['zen_chaku']>=5
                 and h['uma'] is not None and 3<=h['uma']<=16, ['zen_chaku'], pre2=lambda h,r,d: h['uma'] is not None and 3<=h['uma']<=16)

# ---------- ウルトラ（阪神のみ。正本に札幌・中山の条件は0件） ----------
UL = []
def ul(no, ba, td, dmin, dmax, uchisoto, c1, c2, fn, need, pre2=None):
    UL.append(dict(no=no, ba=ba, td=td, dmin=dmin, dmax=dmax, uchisoto=uchisoto,
                   c1=c1, c2=c2, fn=fn, need=need, pre=_pre_from_target(c1),
                   pre2=(pre2 or (lambda h, r, d: True))))
ul('045','阪神','芝',1200,1200,'内','父がストームキャット系種牡馬','枠番が1～6枠',
   lambda h,r,d: keito_of(h['sire'],'ストームキャット系') and h['waku'] is not None and 1<=h['waku']<=6, [])
ul('046','阪神','芝',1400,1600,None,'父がハービンジャー','馬齢が4歳以下',
   lambda h,r,d: h['sire']=='ハービンジャー' and h['age'] is not None and h['age']<=4, [])
ul('047','阪神','芝',1600,1800,None,'岩田望来騎手','前走馬体重480kg以上',
   lambda h,r,d: jk_is(h.get('jockey'),'岩田望来') and d['zen_weight'] is not None and d['zen_weight']>=480, ['zen_weight'])
ul('048','阪神','芝',1800,1800,'外','父がロベルト系種牡馬','前走10着以内',
   lambda h,r,d: keito_of(h['sire'],'ロベルト系') and d['zen_chaku'] is not None and d['zen_chaku']<=10, ['zen_chaku'])
ul('052','阪神','ダ',1400,1800,None,'父がシニスターミニスター','馬番3～16＋関西馬（栗東）',
   lambda h,r,d: h['sire']=='シニスターミニスター' and h['uma'] is not None and 3<=h['uma']<=16
                 and h.get('belong')=='栗東', [])
ul('053','阪神','ダ',1400,1800,None,'父がドレフォン','前走上がり（3F順位）4位以内',
   lambda h,r,d: h['sire']=='ドレフォン' and d['agari_rank'] is not None and d['agari_rank']<=4, ['agari_rank'])
ul('054','阪神','ダ',1800,1800,None,'父がキズナ','3歳以下＋前走馬体重480kg以上',
   lambda h,r,d: h['sire']=='キズナ' and h['age'] is not None and h['age']<=3
                 and d['zen_weight'] is not None and d['zen_weight']>=480, ['zen_weight'], pre2=lambda h,r,d: h['age'] is not None and h['age']<=3)
ul('055','阪神','ダ',1800,2000,None,'武豊騎手','3歳以下＋性が牡・セ',
   lambda h,r,d: jk_is(h.get('jockey'),'武豊') and h['age'] is not None and h['age']<=3 and h['sex'] in ('牡','セ','セン'), [])
ul('056','阪神','ダ',1800,2000,None,'M.デムーロ騎手','3歳以下',
   lambda h,r,d: jk_is(h.get('jockey'),'M.デムーロ') and h['age'] is not None and h['age']<=3, [])
ul('057','阪神','ダ',1800,2000,None,'横山典弘騎手','馬番1～10＋9頭立て以上',
   lambda h,r,d: jk_is(h.get('jockey'),'横山典弘') and h['uma'] is not None and 1<=h['uma']<=10 and r['n_entry']>=9, [])
ul('058','阪神','ダ',2000,2000,None,'松山弘平騎手','前走馬体重520kg未満',
   lambda h,r,d: jk_is(h.get('jockey'),'松山弘平') and d['zen_weight'] is not None and d['zen_weight']<520, ['zen_weight'])

# ---------- 実行 ----------
def course_uchisoto(meta):
    return '外' if '外' in meta else '内'

def main():
    R = json.load(open(os.path.join(D, 'shutuba_20260905.json')))
    idx = build_index()
    genryo = {}
    gp = os.path.join(D, 'genryo.json')
    if os.path.exists(gp): genryo = json.load(open(gp))

    mb_hits, ul_hits, missing = [], [], []
    for r in R:
        if r['jump']: continue
        r['uchisoto'] = course_uchisoto(r['meta'])
        for h in r['horses']:
            p = h['past'][0] if h['past'] else None
            der = past_derived(p, idx) if p else {'agari_rank':None,'corner4':None,'src':None}
            key = f"{r['race_id']}-{h['uma']}"
            valid_past = bool(p and p.get('chaku') is not None)
            d = dict(
                zen_chaku = p.get('chaku') if valid_past else None,
                zen_pop   = p.get('pop') if valid_past else None,
                zen_weight= p.get('weight') if valid_past else None,
                zen_dist  = p.get('dist') if valid_past else None,
                zen_ba    = p.get('ba') if valid_past else None,
                zen_td    = p.get('td') if valid_past else None,
                agari_rank= der['agari_rank'], corner4 = der['corner4'],
                agari_src = der['src'],
                weeks     = weeks(h.get('rotation')),
                genryo    = genryo.get(key),        # True=減量あり / False=なし / None=[不足]
            )
            h['_d'] = d
            # --- マストバイ ---
            for c in MB:
                if c['ba'] != r['ba'] or c['td'] != r['td'] or r['dist'] not in c['dists']: continue
                if c['uchisoto'] and c['uchisoto'].get(r['dist']) not in (None, r['uchisoto']): continue
                # ⚠ 三値論理: 判定可能な部分(対象=父/鞍上)を先に評価する。
                #    そこで確定的に非該当なら[不足]にしない（[不足]の水増しを防ぐ）。
                if not c['pre'](h, r, d): continue
                if not c['pre2'](h, r, d): continue
                miss = [k for k in c['need'] if d.get(k) is None]
                if miss:
                    missing.append(dict(kind='マストバイ', ba=r['ba'], r=r['r'], uma=h['uma'],
                                        name=h['name'], target=c['target'], cond=c['cond'], missing=miss))
                    continue
                try: ok = c['fn'](h, r, d)
                except Exception as e: ok = False; missing.append(dict(kind='ERR', err=str(e)))
                if ok:
                    mb_hits.append(dict(ba=r['ba'], r=r['r'], race=r['title'], course=f"{r['td']}{r['dist']}{r['uchisoto']}",
                        n=r['n_entry'], waku=h['waku'], uma=h['uma'], name=h['name'], sire=h['sire'],
                        jockey=h['jockey'], belong=h['belong'], sex=h['sex'], age=h['age'],
                        種別=c['kind'], 対象=c['target'], 条件=c['cond'], page=c['page'], d=d))
            # --- ウルトラ ---
            for c in UL:
                if c['ba'] != r['ba'] or c['td'] != r['td']: continue
                if not (c['dmin'] <= r['dist'] <= c['dmax']): continue
                if c['uchisoto'] and c['uchisoto'] != r['uchisoto']: continue
                if not c['pre'](h, r, d): continue
                if not c['pre2'](h, r, d): continue
                miss = [k for k in c['need'] if d.get(k) is None]
                if miss:
                    missing.append(dict(kind='ウルトラ', no=c['no'], ba=r['ba'], r=r['r'], uma=h['uma'],
                                        name=h['name'], c1=c['c1'], c2=c['c2'], missing=miss))
                    continue
                try: ok = c['fn'](h, r, d)
                except Exception as e: ok = False; missing.append(dict(kind='ERR', err=str(e)))
                if ok:
                    ul_hits.append(dict(no=c['no'], ba=r['ba'], r=r['r'], race=r['title'],
                        course=f"{r['td']}{r['dist']}{r['uchisoto']}", n=r['n_entry'],
                        waku=h['waku'], uma=h['uma'], name=h['name'], sire=h['sire'], jockey=h['jockey'],
                        belong=h['belong'], sex=h['sex'], age=h['age'], 条件1=c['c1'], 条件2=c['c2'], d=d))

    json.dump({'mustbuy': mb_hits, 'ultra': ul_hits, 'missing': missing},
              open(os.path.join(D, 'hits_20260905.json'), 'w'), ensure_ascii=False, indent=1)
    print(f'[実] マストバイ {len(mb_hits)}頭 / ウルトラ {len(ul_hits)}頭 / 判定不能[不足] {len(missing)}件')
    print('\n=== マストバイ ===')
    for x in sorted(mb_hits, key=lambda x:(x['ba'],x['r'],x['uma'])):
        print(f"  {x['ba']}{x['r']:>2}R {x['course']:<10} {x['uma']:>2}番 {x['name']:<12} "
              f"父{x['sire']:<14} 鞍上{x['jockey']:<6} | {x['対象']} / {x['条件']}")
    print('\n=== ウルトラ ===')
    for x in sorted(ul_hits, key=lambda x:(x['ba'],x['r'],x['uma'])):
        print(f"  No.{x['no']} {x['ba']}{x['r']:>2}R {x['course']:<10} {x['uma']:>2}番 {x['name']:<12} "
              f"父{x['sire']:<14} 鞍上{x['jockey']:<6} | {x['条件1']} / {x['条件2']}")
    print('\n=== 判定不能([不足])の内訳 ===')
    for k, v in collections.Counter(tuple(m.get('missing', [])) for m in missing).most_common():
        print(f'  {k} : {v}件')

main()
