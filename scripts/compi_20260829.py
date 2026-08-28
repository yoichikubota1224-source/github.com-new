#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""コンピ指数の派生計算(2026-08-29)。定義は凍結スクリプトに一致させる:
- T6 = コンピ上位3頭の指数合計(名称はT6だが凍結定義は上位3合計)
- P区分 = P1≤205 / P2 206-208 / P3 209-211 / P4 212-215 / P5 216-219 / P6≥220
- EP = 指数 − 下位5頭平均、黄金律 = コンピ13〜15位 かつ EP≥+3
- c1/gap12/maxdrop/line46(=指数46以上の頭数)も算出
出典: コンピT6_EP判定_生成.py(Drive 14t8_Mk3sQeBOXoqyox07j9hxv4OgUZ_T)
"""
import csv, json, sys
from collections import defaultdict

CSV, INTEG, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
rows = list(csv.DictReader(open(CSV, 'rb').read().decode('utf-8-sig').splitlines()))
races = defaultdict(list)
for r in rows:
    races[r['racekey']].append((int(r['馬番']), int(r['コンピ順位']), int(r['コンピ指数'])))

def p_kubun(t6):
    if t6 <= 205: return 'P1'
    if t6 <= 208: return 'P2'
    if t6 <= 211: return 'P3'
    if t6 <= 215: return 'P4'
    if t6 <= 219: return 'P5'
    return 'P6'

feat = {}
for rk, v in races.items():
    v.sort(key=lambda z: z[1])              # コンピ順位順
    vals = [x[2] for x in v]
    t6 = sum(vals[:3])
    low5 = sum(vals[-5:]) / 5.0
    ep = {u: round(s - low5, 1) for u, _, s in v}
    gold = [u for u, rank, s in v if 13 <= rank <= 15 and s - low5 >= 3]
    drops = [vals[i] - vals[i+1] for i in range(len(vals)-1)]
    md = max(drops); mdpos = drops.index(md) + 1
    feat[rk] = {'t6': t6, 'pattern': p_kubun(t6), 'c1': vals[0],
                'gap12': vals[0] - vals[1], 'maxdrop': md,
                'drop_pos': f'{mdpos}-{mdpos+1}位間',
                'line46': sum(1 for x in vals if x >= 46),
                'low5': round(low5, 1), 'gold': gold, 'ep': ep,
                'rank': {u: rank for u, rank, _ in v},
                'shisu': {u: s for u, _, s in v}}

D = json.load(open(INTEG))
for R in D:
    f = feat[R['racekey']]
    R['compi'] = {k: f[k] for k in ('t6', 'pattern', 'c1', 'gap12', 'maxdrop',
                                    'drop_pos', 'line46', 'low5', 'gold')}
    for h in R['horses']:
        u = h['uma']
        h['compi_rank'] = f['rank'][u]
        h['compi'] = f['shisu'][u]
        h['EP'] = f['ep'][u]
        h['gold'] = u in f['gold']
json.dump(D, open(OUT, 'w'), ensure_ascii=False, indent=1)

from collections import Counter
print('P区分分布:', dict(Counter(f['pattern'] for f in feat.values())))
print('黄金律該当:', sum(len(f['gold']) for f in feat.values()), '頭')
print('c1範囲:', min(f['c1'] for f in feat.values()), '-', max(f['c1'] for f in feat.values()))
