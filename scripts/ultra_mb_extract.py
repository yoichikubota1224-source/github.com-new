#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑤ウルトラ・マストバイ係 該当馬抽出。
正本: マイトバス.xlsx(場別シート＋まとめ_All) / ウルトラ回収率2026.02.22.xlsx。
DE出走表CSV(CP932・33列・ヘッダ無し)を入力に、条件を1つずつ評価して出所タグを付ける。
[不足]は0/消し/断念に変換しない。買い目・点数・資金配分は一切出さない。
"""
import csv, re, sys, json, os
import openpyxl

# ---- DE出走表 列定義(実測による) ----
D_DATE, D_BA, D_R, D_UMA, D_CLS, D_TD, D_DIST = 0, 1, 2, 3, 4, 5, 6
D_NAME, D_SEX, D_AGE, D_JOCKEY, D_KIN, D_TRAINER, D_BELONG = 7, 8, 9, 10, 11, 12, 13
D_SIRE, D_DAM, D_KETTO, D_BMS, D_WAKU, D_ATAMA = 16, 17, 18, 20, 22, 26
# 23,24,25 は内容未同定(値域0〜125)。前走着順とは一致しないため使用しない=[要確認]

# 騎手名: DEは4〜5文字に丸められる。正本のフルネームとの対応表(DE表記→正本表記)
JOCKEY_ALIAS = {
    'ルメール': 'C.ルメール', 'Ｍ．デム': 'M.デムーロ', 'ミシェル': 'ミシェル',
    '河原田菜': '河原田菜々', '古川奈穂': '古川奈穂', '大久保友': '大久保友雅',
    '小牧加矢': '小牧加矢太', '永島まな': '永島まなみ', '野中悠太': '野中悠太郎',
    '小野寺祐': '小野寺祐太', '吉村誠之': '吉村誠之助', '柴田裕一': '柴田裕一郎',
}

def norm_jockey(de_name):
    de_name = de_name.strip()
    return JOCKEY_ALIAS.get(de_name, de_name)

def jockey_match(de_name, rule_name):
    """正本の騎手名とDE短縮表記の照合。前方一致＋別名表で判定。"""
    de = norm_jockey(de_name)
    rn = rule_name.strip().replace('鞍上：', '').replace('鞍上:', '').strip()
    if de == rn:
        return True
    # M.デムーロ / C.ルメール のような接頭辞つき
    rn_core = re.sub(r'^[A-ZＭＣ][\.．]', '', rn)
    de_core = re.sub(r'^[A-ZＭＣ][\.．]', '', de)
    if de_core and rn_core and (de_core == rn_core):
        return True
    # DE側が丸められている場合の前方一致(3文字以上必須)
    raw = de_name.strip()
    if len(raw) >= 3 and rn_core.startswith(raw):
        return True
    return False

# ---- 父系統マスタ ----
# 正本WBに父系列は無い(READMEが『入力_出走馬』の『父系(任意)』列にユーザ入力を求めている)。
# 以下は当方が付す推定であり [推:系統] タグ固定。確定には羊一様/Excel側の確認が要る。
KEITO = {
  'キングカメハメハ系': {'キングカメハメハ','ロードカナロア','ドゥラメンテ','ルーラーシップ','レイデオロ',
      'リオンディーズ','ホッコータルマエ','ベルシャザール','ラブリーデイ','ミッキーロケット','エアスピネル',
      'サートゥルナーリア','レイデオロ','タリスマニック','ヤマカツエース','リオンリオン','チュウワウィザード',
      'アドミラブル','ホウオウリアリティ','ダノンスコーピオン','グローリーヴェイズ'},
  'ディープインパクト系': {'ディープインパクト','キズナ','リアルスティール','サトノダイヤモンド','ミッキーアイル',
      'シルバーステート','フィエールマン','ダノンバラード','ワールドエース','トーセンホマレボシ','アルアイン',
      'ダノンキングリー','サトノアラジン','スピルバーグ','トーセンラー','ディーマジェスティ','リアルインパクト',
      'グレーターロンドン','サトノクラウン','ダノンシャーク','エイシンヒカリ','シャドウディーヴァ',
      'マカヒキ','ヴァンドギャルド','アドマイヤマーズ','コントレイル','グレナディアガーズ','シャフリヤール',
      'ダノンザキッド','ラウダシオン','ロジャーバローズ','サリオス'},
  'ステイゴールド系': {'ステイゴールド','オルフェーヴル','ゴールドシップ','ドリームジャーニー','ナカヤマフェスタ',
      'ウインブライト','インディチャンプ','フェノーメノ','レインボーライン','オジュウチョウサン','マイネルフロスト'},
  'グラスワンダー系': {'グラスワンダー','スクリーンヒーロー','モーリス','ゴールドアクター','ジェニュイン'},
}

# 「父がサンデーサイレンス系以外」条件の判定に使う。SS系の主要種牡馬(当方推定)。
SS_KEI = set()
for _k in ('ディープインパクト系', 'ステイゴールド系'):
    SS_KEI |= KEITO[_k]
SS_KEI |= {'サンデーサイレンス','ハーツクライ','ダイワメジャー','ゴールドアリュール','ネオユニヴァース',
    'マンハッタンカフェ','ステイゴールド','ヴィクトワールピサ','キングヘイロー','スペシャルウィーク',
    'ダノンシャンティ','ジャスタウェイ','エピファネイア','キタサンブラック','ブラックタイド','ドゥラメンテ',
    'シニスターミニスター'}  # ※シニスターミニスターは非SS。下で除外
SS_KEI -= {'シニスターミニスター','ドゥラメンテ'}
# 明確に非SS系と判断できる種牡馬(米国系・欧州系・キンカメ系・グラスワンダー系など)
NON_SS = set()
for _k in ('キングカメハメハ系', 'グラスワンダー系'):
    NON_SS |= KEITO[_k]
NON_SS |= {'ヘニーヒューズ','シニスターミニスター','ドレフォン','マジェスティックウォリアー','モーニン',
    'アジアエクスプレス','パイロ','カジノドライヴ','クロフネ','ゴールドアリュール'} - {'ゴールドアリュール'}
NON_SS |= {'サウスヴィグラス','ホッコータルマエ','スマートファルコン','エスポワールシチー','ロージズインメイ',
    'キンシャサノキセキ','アドマイヤムーン','スクリーンヒーロー','ハービンジャー','フランケル','ロードカナロア',
    'サンダースノー','ミスチヴィアスアレックス','ニューイヤーズデイ','マインドユアビスケッツ','ブリックスアンドモルタル',
    'ダイワメジャー'} - {'ダイワメジャー'}

def ss_kei_gai(sire):
    """「父がサンデーサイレンス系以外」の判定。(True/False/None, タグ, 説明)"""
    if sire in SS_KEI:
        return (False, '[推:系統]', f'父{sire}=SS系(当方推定)')
    if sire in NON_SS:
        return (True, '[推:系統]', f'父{sire}=非SS系(当方推定・要確認)')
    return (None, '[要確認]', f'父{sire}の系統マスタ未提供')

def sire_rule_match(sire, target):
    """(判定, タグ, 説明) を返す。"""
    t = target.strip().replace('父：', '').replace('父:', '').strip()
    if t.endswith('系種牡馬'):
        kei = t[:-3]            # 「○○系種牡馬」→「○○系」
    elif t.endswith('系'):
        kei = t
    else:
        kei = None
    if kei:
        members = KEITO.get(kei)
        if members is None:
            return (None, '[要確認]', f'{kei}の系統マスタ未提供')
        if sire in members:
            return (True, '[推:系統]', f'父{sire}→{kei}(当方推定・要確認)')
        return (False, '[推:系統]', '')
    return (sire == t, '[実]', '')

# ---- 条件パーサ ----
COND_SPLIT = re.compile(r'、かつ、|、また、')
KANSUJI = {'牡':'牡','牝':'牝','セ':'セ'}

def eval_cond(c, h, race):
    """1条件を評価。戻り値 (True/False/None, タグ, 表示文)。None=判定不能。"""
    c = c.strip().strip('（）()')
    if c in ('無条件', ''):
        return (True, '[実]', '無条件')
    m = re.search(r'馬番が(\d+)[〜～](\d+)番', c)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        return (lo <= h['uma'] <= hi, '[実]', f'馬番{h["uma"]}∈{lo}-{hi}')
    m = re.search(r'枠番が(\d+)[〜～](\d+)枠', c)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        return (lo <= h['waku'] <= hi, '[実]', f'枠{h["waku"]}∈{lo}-{hi}')
    m = re.search(r'最内枠', c)
    if m:
        return (h['waku'] == 1, '[実]', f'枠{h["waku"]}')
    m = re.search(r'馬齢が(\d+)歳以下', c)
    if m:
        return (h['age'] <= int(m.group(1)), '[実]', f'{h["age"]}歳≤{m.group(1)}')
    m = re.search(r'馬齢が(\d+)歳以上', c)
    if m:
        return (h['age'] >= int(m.group(1)), '[実]', f'{h["age"]}歳≥{m.group(1)}')
    m = re.search(r'出走頭数が(\d+)頭以下', c)
    if m:
        return (race['atama'] <= int(m.group(1)), '[実]', f'{race["atama"]}頭≤{m.group(1)}')
    m = re.search(r'出走頭数が(\d+)頭以上', c)
    if m:
        return (race['atama'] >= int(m.group(1)), '[実]', f'{race["atama"]}頭≥{m.group(1)}')
    if '性が牡・セン' in c or '性が牡・セ' in c:
        return (h['sex'] in ('牡', 'セ'), '[実]', f'性{h["sex"]}')
    m = re.search(r'調教師の所属が(栗東|美浦)', c)
    if m:
        want = '栗' if m.group(1) == '栗東' else '美'
        return (h['belong'] == want, '[実]', f'所属{h["belong"]}')
    if '父がサンデーサイレンス系以外' in c:
        return ss_kei_gai(h['sire'])
    if '前走' in c:
        if race['shinba']:
            return (False, '[実]', '新馬=前走なし→条件不成立')
        return (None, '[不足]', c + '=DEに前走情報なし')
    return (None, '[要確認]', c)

def parse_dist(s):
    """距離セルを数値集合と内外注記に分解。"""
    s = str(s)
    nums = set(int(x) for x in re.findall(r'\d{3,4}', s))
    naigai = bool(re.search(r'[内外直]', s))
    return nums, naigai

def load_rules(path, sheets):
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rules = []
    for sh in sheets:
        ws = wb[sh]
        rows = [r for r in ws.iter_rows(values_only=True)]
        hdr = rows[0]
        for r in rows[1:]:
            if not r[0]:
                continue
            d = dict(zip(hdr, r))
            rules.append({
                'sheet': sh, 'ba': d['競馬場'], 'td': d['芝ダ'],
                'dist_raw': d['距離'], 'naigai': d['内外等'], 'kind': d['種別'],
                'target': str(d['対象']), 'cond': str(d['条件'] or ''),
                'p3': d['3着内率'], 'fukukai': d['複勝回収率'], 'tankai': d['単勝回収率'],
                'chaku': d['着別度数'], 'page': d['ページ'],
            })
    wb.close()
    return rules

def main():
    de_path = sys.argv[1]; mb_path = sys.argv[2]
    rows = [r for r in csv.reader(open(de_path, encoding='cp932'))]
    races = {}
    for r in rows:
        key = (r[D_BA], int(r[D_R]))
        races.setdefault(key, []).append(r)

    venues = sorted({r[D_BA] for r in rows})
    sheets = [f'{v}_マストバイ' for v in venues]
    rules = load_rules(mb_path, sheets)

    out = []
    for key in sorted(races, key=lambda k: (k[0], k[1])):
        rs = races[key]
        head = rs[0]
        race = {'ba': key[0], 'r': key[1], 'cls': head[D_CLS], 'td': head[D_TD],
                'dist': int(head[D_DIST]), 'atama': int(head[D_ATAMA]),
                'jump': ('障害' in head[D_CLS]), 'shinba': ('新馬' in head[D_CLS])}
        hits = []
        applicable = []
        for ru in rules:
            if ru['ba'] != race['ba'] or ru['td'] != race['td']:
                continue
            dn, naigai = parse_dist(ru['dist_raw'])
            if race['dist'] not in dn:
                continue
            applicable.append(ru)
            for r in rs:
                h = {'uma': int(r[D_UMA]), 'waku': int(r[D_WAKU]), 'name': r[D_NAME],
                     'sex': r[D_SEX], 'age': int(r[D_AGE]), 'jockey': r[D_JOCKEY],
                     'sire': r[D_SIRE], 'trainer': r[D_TRAINER], 'belong': r[D_BELONG]}
                if ru['kind'] == 'ジョッキー':
                    if not jockey_match(h['jockey'], ru['target']):
                        continue
                    base_tag, base_note = '[実]', f'鞍上:{norm_jockey(h["jockey"])}'
                else:
                    ok, base_tag, base_note = sire_rule_match(h['sire'], ru['target'])
                    if ok is not True:
                        continue
                conds = [c for c in COND_SPLIT.split(ru['cond']) if c.strip()]
                results = [eval_cond(c, h, race) for c in conds] or [(True, '[実]', '無条件')]
                if any(v is False for v, _, _ in results):
                    continue                      # 条件を明確に外す馬は落とす
                hits.append({
                    'uma': h['uma'], 'waku': h['waku'], 'name': h['name'],
                    'jockey': norm_jockey(h['jockey']), 'sire': h['sire'],
                    'sex': h['sex'], 'age': h['age'], 'belong': h['belong'],
                    'rule': f"{ru['kind']}／{ru['target']}", 'rule_cond': ru['cond'],
                    'p3': ru['p3'], 'fuku': ru['fukukai'], 'tan': ru['tankai'],
                    'chaku': ru['chaku'], 'page': ru['page'], 'base_tag': base_tag,
                    'base_note': base_note,
                    'conds': [{'text': c, 'ok': v, 'tag': t, 'note': n}
                              for c, (v, t, n) in zip(conds or ['無条件'], results)],
                    'naigai': ru['naigai'], 'dist_raw': ru['dist_raw'],
                })
        # --- W該当判定: 同一馬が血統ルールとジョッキールールの双方に該当 ---
        by_uma = {}
        for hh in hits:
            by_uma.setdefault(hh['uma'], []).append(hh)
        for uma, hs in by_uma.items():
            kinds = {x['rule'].split('／')[0] for x in hs}
            if '血統' in kinds and 'ジョッキー' in kinds:
                fk = [float(x['fuku']) for x in hs]
                both100 = all(v >= 1.00 for v in fk)
                clean = all(c['ok'] is True for x in hs for c in x['conds'])
                w = 'W該当' if (both100 and clean) else ('W判定保留' if both100 else '該当外')
                for x in hs:
                    x['W'] = w
        for hh in hits:
            hh.setdefault('W', '')
        out.append({'race': race, 'applicable_rules': len(applicable), 'hits': hits,
                    'shinba': race['shinba'], 'jump': race['jump']})
    print(json.dumps(out, ensure_ascii=False, indent=1))

if __name__ == '__main__':
    main()
