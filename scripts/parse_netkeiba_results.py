#!/usr/bin/env python3
# netkeiba 結果ページ(サーバサイドレンダリング)をパースして results JSON を作る
import json, os, re, html, sys
SP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(SP, sys.argv[1] if len(sys.argv) > 1 else 'raw23')
OUT = os.path.join(SP, 'derived', sys.argv[2] if len(sys.argv) > 2 else 'results_20260823.json')
tg = {t['race_id']: t for t in json.load(open(os.path.join(SP, 'browser_stage', 'targets.json')))}

def txt(s):
    return html.unescape(re.sub(r'<[^>]+>', '', s)).replace('\xa0', ' ').strip()

def cell_texts(tr):
    return [txt(td) for td in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', tr, re.S)]

def derive_passing(corners, n):
    """コーナー通過順位表から各馬の通過順を復元。
    規則: 括弧内の並走馬は同順位 / '*' 付きの先頭馬のみ1つ上位 / 末尾の半角スペース以降は非出走馬の付記"""
    per = {}
    for ci, raw in enumerate(corners):
        s = raw.split('  ')[0]
        pos = 0
        for tok in re.finditer(r'\(([^)]*)\)|([\d]+)', s):
            if tok.group(1) is not None:
                pos += 1
                for m in re.findall(r'\d+', tok.group(1)):
                    per.setdefault(int(m), {})[ci] = pos
            else:
                pos += 1
                per.setdefault(int(tok.group(2)), {})[ci] = pos
    return {ub: '-'.join(str(v[i]) for i in sorted(v)) for ub, v in per.items()}

races = []
for rid, t in tg.items():
    p = os.path.join(RAW, f'result_{rid}.html')
    raw = open(p, 'rb').read()
    cm0 = re.search(rb'charset=["\']?([\w-]+)', raw[:3000])
    enc = (cm0.group(1).decode() if cm0 else 'utf-8')
    doc = raw.decode(enc, errors='strict')          # 文字化けを黙認しない
    # 結果行は class="HorseList" を持つ。ネストtableで表が切れるのを避け文書全体から拾う
    trs = re.findall(r'<tr[^>]*class="[^"]*HorseList[^"]*"[^>]*>(.*?)</tr>', doc, re.S)
    # 一部の開催日のテンプレートでは、指数・ラップ・脚質の分析ウィジェットも class="HorseList" を使う。
    # それらは列数が結果表と異なる(実測: 結果15列に対し 18/19/21列)ため、
    # 馬リンクを持つ行のうち「最頻の列数」を結果表の行とみなして残す。
    cand = [tr for tr in trs if '/horse/' in tr]
    if cand:
        import collections
        modal = collections.Counter(len(cell_texts(tr)) for tr in cand).most_common(1)[0][0]
        trs = [tr for tr in cand if len(cell_texts(tr)) == modal]
    if not trs:
        print('NO ROWS', rid); continue
    # コーナー通過順位表
    corners = []
    cm = re.search(r'Corner_Num.*?</table>', doc, re.S)
    if cm:
        for tr in re.findall(r'<tr[^>]*>(.*?)</tr>', cm.group(0), re.S):
            c = cell_texts(tr)
            if len(c) >= 2 and re.search(r'\d', c[1]): corners.append(c[1])
    horses = []
    for tr in trs:
        c = cell_texts(tr)
        if len(c) < 12: continue
        rank_s = c[0]
        pos = int(rank_s) if rank_s.isdigit() else None
        status = None if pos else (rank_s or '除外')
        def gi(i): return c[i] if i < len(c) else ''
        hid = None
        hm = re.search(r'/horse/(\d+)', tr)
        if hm: hid = hm.group(1)
        jid = None
        jm = re.search(r'/jockey/result/recent/(\w+)', tr)
        if jm: jid = jm.group(1)
        tid = None
        tm = re.search(r'/trainer/result/recent/(\w+)', tr)
        if tm: tid = tm.group(1)
        def num(x):
            try: return float(x)
            except (ValueError, TypeError): return None
        horses.append({'chakujun': pos, 'status': status, 'waku': gi(1), 'umaban': int(gi(2)),
                       'name': gi(3), 'horse_id': hid, 'sex_age': gi(4), 'kinryo': gi(5),
                       'jockey': gi(6), 'jockey_id': jid, 'time': gi(7), 'diff': gi(8),
                       'pop': int(gi(9)) if gi(9).isdigit() else None, 'odds': num(gi(10)),
                       'last3f': num(gi(11)), 'passing': gi(12) or None,
                       'trainer': gi(14) if len(c) > 14 else '', 'trainer_id': tid,
                       'weight': gi(15) if len(c) > 15 else ''})
    if horses and not any(h.get('passing') for h in horses) and corners:
        dv = derive_passing(corners, len(horses))
        for h in horses:
            h['passing'] = dv.get(h['umaban'])
            h['passing_from'] = 'derived'
    else:
        for h in horses: h.setdefault('passing_from', 'netkeiba')
    dm = re.search(r'<div[^>]*class="RaceData01"[^>]*>(.*?)</div>', doc, re.S)
    meta = txt(dm.group(1)) if dm else ''
    races.append({'racekey': t['racekey'], 'race_id': rid, 'date': '2026-08-30',
                  'venue': t['venue'], 'r': t['race'], 'label': t['label'],
                  'meta': meta, 'head_count': len(horses), 'corners': corners, 'horses': horses})
races.sort(key=lambda r: (r['venue'], r['r']))
json.dump(races, open(OUT, 'w'), ensure_ascii=False)
print('races:', len(races), 'horses:', sum(len(r['horses']) for r in races))
bad = []
for r in races:
    fin = [h for h in r['horses'] if h['chakujun']]
    ch = sorted(h['chakujun'] for h in fin)
    # 同着があると連番にならない。順位は非減少・1始まり・各順位の重複数だけ次順位が飛ぶ、を検査
    okc = ch and ch[0] == 1
    for i in range(1, len(ch)):
        if ch[i] == ch[i-1]: continue
        if ch[i] != ch[:i].count(ch[:i][-1]) + ch[:i].index(ch[:i][-1]) + 1: pass
    from collections import Counter
    cc = Counter(ch); exp = 1
    for k in sorted(cc):
        if k != exp: okc = False; break
        exp = k + cc[k]
    if not okc: bad.append((r['racekey'], 'chaku', ch[:6]))
    if len(fin) + len([h for h in r['horses'] if not h['chakujun']]) != len(r['horses']):
        bad.append((r['racekey'], 'count'))
    ps = [h['pop'] for h in r['horses'] if h['pop']]
    if len(set(ps)) != len(ps): bad.append((r['racekey'], 'pop dup'))
print('整合エラー:', bad if bad else 'なし')
sc = [(r['racekey'], h['umaban'], h['name'], h['status']) for r in races for h in r['horses'] if not h['chakujun']]
print('取消/中止:', len(sc), sc)
