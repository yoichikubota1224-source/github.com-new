#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ウルトラ該当馬抽出(新潟/中京/札幌)。
⚠ 条件表の出所は _archive の退避CSV。正本WB(ウルトラ回収率2026.02.22.xlsx)には
   No.059以降が収録されておらず、退避理由の「xlsxへ統合済み」記載と実態が食い違う。
   よって本抽出は全件 [要確認:正本外] であり、昇格には羊一様の承認が要る。
"""
import csv, re, sys, json
sys.path.insert(0, '/home/user/github.com-new/scripts')
from ultra_mb_extract import (D_BA, D_R, D_UMA, D_CLS, D_TD, D_DIST, D_NAME, D_SEX,
                              D_AGE, D_JOCKEY, D_KIN, D_TRAINER, D_BELONG, D_SIRE,
                              D_WAKU, D_ATAMA, D_ZEN_KAN, D_ZEN_NIN, D_ZEN_CHAKU,
                              D_PRIZE1, D_PRIZE2,
                              norm_jockey, jockey_match, sire_rule_match, iz)

# 退避CSVのOCR由来と思われる表記ゆれ → 実在騎手名
JOCKEY_FIX = {'億野極': '荻野極', '高杉吏麒': '高杉史麒', '鮫島-克駿': '鮫島克駿'}

def parse_course(s):
    """『新潟芝1200～1600m』→ (場, 芝ダ, lo, hi, 内外注記)"""
    m = re.match(r'(新潟|中京|札幌|東京|京都|阪神|中山|小倉|福島|函館)(芝|ダ)(.+)', s)
    if not m:
        return None
    ba, td, rest = m.group(1), m.group(2), m.group(3)
    naigai = ''.join(ch for ch in rest if ch in '内外直')
    nums = [int(x) for x in re.findall(r'\d{3,4}', rest)]
    if not nums:
        return None
    return ba, td, min(nums), max(nums), naigai

def eval_cond(c, h, race):
    c = c.strip()
    if not c or c in ('-',):
        return (True, '[実]', '無条件')
    m = re.search(r'(\d+)[〜～](\d+)番', c)
    if m:
        lo, hi = sorted((int(m.group(1)), int(m.group(2))))
        return (lo <= h['uma'] <= hi, '[実]', f'馬番{h["uma"]}∈{lo}-{hi}')
    m = re.search(r'(\d+)[〜～](\d+)枠', c)
    if m:
        lo, hi = sorted((int(m.group(1)), int(m.group(2))))
        return (lo <= h['waku'] <= hi, '[実]', f'枠{h["waku"]}∈{lo}-{hi}')
    m = re.search(r'(\d+)歳以下', c)
    if m and '前走' not in c:
        return (h['age'] <= int(m.group(1)), '[実]', f'{h["age"]}歳≤{m.group(1)}')
    m = re.search(r'(\d+)頭立て以上', c)
    if m and '前走' not in c:
        return (race['atama'] >= int(m.group(1)), '[実]', f'{race["atama"]}頭≥{m.group(1)}')
    m = re.search(r'(\d+)頭立て以下', c)
    if m and '前走' not in c:
        return (race['atama'] <= int(m.group(1)), '[実]', f'{race["atama"]}頭≤{m.group(1)}')
    m = re.search(r'負担重量([\d.]+)kg以下', c)
    if m:
        return (h['kin'] <= float(m.group(1)), '[実]', f'斤{h["kin"]}≤{m.group(1)}')
    if '牡・セン' in c or '牡・セ' in c:
        return (h['sex'] in ('牡', 'セ'), '[実]', f'性{h["sex"]}')
    if '関西馬' in c:
        return (h['belong'] == '栗', '[実]', f'所属{h["belong"]}')
    if '調教師美浦' in c or '美浦' in c:
        return (h['belong'] == '美', '[実]', f'所属{h["belong"]}')
    if '前走' in c:
        if race['shinba']:
            return (False, '[実]', '新馬=前走なし→条件不成立')
        if h.get('zen_missing'):
            # ⚠ 2026-08-30 訂正: DE23/24/25=0/0/0 は「未出走」ではなく
            #   「前走情報が取得できていない」。タイム指数CSVとの交差検証で、
            #   0/0/0の9頭中4頭(中京9R8番・新潟5R2番/14番・札幌9R3番)に
            #   前走の実測タイム指数が存在した[実]。よって0を不成立に変換しない。
            return (None, '[不足]', 'DE23/24/25が全て0=前走情報なし(未出走とは断定しない)')
        m = re.search(r'前走(\d+)着以内', c)
        if m and h.get('zen_chaku'):
            k = int(m.group(1))
            return (h['zen_chaku'] <= k, '[推:列同定]', f'前走{h["zen_chaku"]}着≤{k}着')
        m = re.search(r'前走(\d+)番?人気以内', c)
        if m and h.get('zen_ninki'):
            k = int(m.group(1))
            return (h['zen_ninki'] <= k, '[推:列同定]', f'前走{h["zen_ninki"]}人気≤{k}人気')
        m = re.search(r'前走(?:から)?中(\d+)週以上', c)
        if m and h.get('zen_kan'):
            k = int(m.group(1))
            return (h['zen_kan'] >= k + 1, '[推:中週換算]',
                    f'前走から{h["zen_kan"]}週(中{max(h["zen_kan"]-1,0)}週)≥中{k}週')
        m = re.search(r'前走(?:から)?中(\d+)週以内', c)
        if m and h.get('zen_kan'):
            k = int(m.group(1))
            return (h['zen_kan'] <= k + 1, '[推:中週換算]',
                    f'前走から{h["zen_kan"]}週(中{max(h["zen_kan"]-1,0)}週)≤中{k}週')
        return (None, '[不足]', c + '=DE33列に該当項目なし')
    return (None, '[要確認]', c)

def main():
    de_path, tmpl_path = sys.argv[1], sys.argv[2]
    rows = [r for r in csv.reader(open(de_path, encoding='cp932'))]
    trows = [r for r in csv.reader(open(tmpl_path, encoding='cp932'))]
    venues = {r[D_BA] for r in rows}

    rules = []
    for r in trows:
        pc = parse_course(r[1])
        if not pc or pc[0] not in venues:
            continue
        ba, td, lo, hi, naigai = pc
        rules.append({'no': r[0], 'course': r[1], 'ba': ba, 'td': td, 'lo': lo, 'hi': hi,
                      'naigai': naigai, 'c1': r[2], 'c2': r[3], 'chaku': r[4],
                      'p3': r[7], 'tan': r[8], 'fuku': r[9], 'ken': r[10]})

    races = {}
    for r in rows:
        races.setdefault((r[D_BA], int(r[D_R])), []).append(r)

    out = []
    for key in sorted(races, key=lambda k: (k[0], k[1])):
        rs = races[key]; head = rs[0]
        race = {'ba': key[0], 'r': key[1], 'cls': head[D_CLS], 'td': head[D_TD],
                'dist': int(head[D_DIST]), 'atama': int(head[D_ATAMA]),
                'shinba': '新馬' in head[D_CLS], 'jump': '障害' in head[D_CLS]}
        hits, applicable, undecided = [], [], []
        for ru in rules:
            if ru['ba'] != race['ba'] or ru['td'] != race['td']:
                continue
            if not (ru['lo'] <= race['dist'] <= ru['hi']):
                continue
            applicable.append(ru)
            # 条件①が対象(騎手/血統/馬番枠/前走場)、条件②が付帯条件
            c1 = ru['c1'].strip()
            for r in rs:
                h = {'uma': int(r[D_UMA]), 'waku': int(r[D_WAKU]), 'name': r[D_NAME],
                     'sex': r[D_SEX], 'age': int(r[D_AGE]), 'jockey': r[D_JOCKEY],
                     'sire': r[D_SIRE], 'belong': r[D_BELONG], 'kin': float(r[D_KIN]),
                     'zen_kan': iz(r[D_ZEN_KAN]), 'zen_ninki': iz(r[D_ZEN_NIN]),
                     'zen_chaku': iz(r[D_ZEN_CHAKU])}
                h['zen_missing'] = (h['zen_kan'] == 0 and h['zen_ninki'] == 0
                                    and h['zen_chaku'] == 0)
                base_tag, base_note = '[実]', ''
                jm = re.match(r'(.+?)騎手$', c1)
                sm = re.match(r'父が?(.+)$', c1)
                if jm:
                    nm = JOCKEY_FIX.get(jm.group(1), jm.group(1))
                    if not jockey_match(h['jockey'], nm):
                        continue
                    base_note = f'鞍上:{norm_jockey(h["jockey"])}'
                    if jm.group(1) in JOCKEY_FIX:
                        base_note += f'(表記ゆれ {jm.group(1)}→{nm})'
                elif sm:
                    ok, base_tag, base_note = sire_rule_match(h['sire'], sm.group(1))
                    if ok is False:
                        continue
                    if ok is None:
                        undecided.append({'no': ru['no'], 'course': ru['course'],
                                          'uma': h['uma'], 'name': h['name'], 'sire': h['sire'],
                                          'jockey': norm_jockey(h['jockey']),
                                          'c1': ru['c1'], 'c2': ru['c2'],
                                          'base_tag': base_tag, 'base_note': base_note})
                        continue
                else:
                    v, t, n = eval_cond(c1, h, race)
                    if v is False:
                        continue
                    if v is None:
                        # [不足]/[要確認]を無言で0に変換しない。別枠へ退避。
                        undecided.append({'no': ru['no'], 'course': ru['course'],
                                          'uma': h['uma'], 'name': h['name'], 'sire': h['sire'],
                                          'jockey': norm_jockey(h['jockey']),
                                          'c1': ru['c1'], 'c2': ru['c2'],
                                          'base_tag': t, 'base_note': n})
                        continue
                    base_tag, base_note = t, n
                conds = [c for c in re.split(r'[＋+]', ru['c2']) if c.strip()]
                results = [eval_cond(c, h, race) for c in conds] or [(True, '[実]', '無条件')]
                if any(v is False for v, _, _ in results):
                    continue
                hits.append({'no': ru['no'], 'course': ru['course'], 'uma': h['uma'],
                             'waku': h['waku'], 'name': h['name'],
                             'jockey': norm_jockey(h['jockey']), 'sire': h['sire'],
                             'c1': ru['c1'], 'c2': ru['c2'], 'p3': ru['p3'],
                             'tan': ru['tan'], 'fuku': ru['fuku'], 'ken': ru['ken'],
                             'chaku': ru['chaku'], 'base_tag': base_tag, 'base_note': base_note,
                             'naigai': ru['naigai'],
                             'conds': [{'text': c, 'ok': v, 'tag': t, 'note': n}
                                       for c, (v, t, n) in zip(conds or ['無条件'], results)]})
        out.append({'race': race, 'applicable_rules': len(applicable), 'hits': hits,
                    'base_undecided': undecided})
    print(json.dumps(out, ensure_ascii=False, indent=1))

if __name__ == '__main__':
    main()
