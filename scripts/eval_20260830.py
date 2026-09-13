#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2026-08-29 独立再評価: 穴馬(基準人気7〜12)候補の材料集計。
「支持係数」は材料が何本重なったかを数えるだけで、買い判断・印・買い目ではない。
運勢×は減点に使わない(押し上げの欠如としてのみ扱う)。[不足]は0に変換しない。
"""
import json, sys
from collections import Counter

INTEG, UNSEI, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
D = json.load(open(INTEG)); U = json.load(open(UNSEI))['map']

def rank_of(hs, key, reverse=True):
    """値のある馬だけで順位。値なしはNone。"""
    vals = [(h['uma'], h[key]) for h in hs if h[key] is not None]
    vals.sort(key=lambda z: -z[1] if reverse else z[1])
    return {u: i + 1 for i, (u, _) in enumerate(vals)}, len(vals)

MYOUMI_GOOD = {'Ｓ', 'ＡＡ', 'Ａ', 'S', 'AA', 'A'}

for R in D:
    hs = R['horses']; n = len(hs)
    third = max(1, round(n / 3))
    r_idm, n_idm       = rank_of(hs, 'IDM')
    r_time, n_time     = rank_of(hs, 'time_max')
    r_last, n_last     = rank_of(hs, 'time_last')
    r_tot, n_tot       = rank_of(hs, 'total')
    r_cho, n_cho       = rank_of(hs, 'chokyo_idx')
    r_ten, n_ten       = rank_of(hs, 'tenkai', reverse=False)
    r_geki, n_geki     = rank_of(hs, 'geki')
    r_dist, _          = rank_of(hs, 'time_dist')
    r_crs, _           = rank_of(hs, 'time_course')
    r_sav, _           = rank_of(hs, 'SAV')
    for h in hs:
        u = h['uma']
        f = U.get(h['jockey'])
        h['unsei'] = f['m30'] if f else None
        h['unsei_roi'] = f['roi'] if f else None
        h['unsei_note'] = f['note'] if f else None
        s = []
        if r_idm.get(u) and r_idm[u] <= third: s.append(f"⑧IDM{r_idm[u]}位")
        if r_time.get(u) and r_time[u] <= third: s.append(f"⑧タイム{r_time[u]}位")
        elif r_last.get(u) and r_last[u] <= third: s.append(f"⑧前走時計{r_last[u]}位")
        if (r_tot.get(u) and r_tot[u] <= 3) or h['myoumi'] in MYOUMI_GOOD:
            s.append(f"⑦STRIDE(合計{r_tot.get(u,'-')}位/妙味{h['myoumi'] or '-'})")
        if r_cho.get(u) and r_cho[u] <= third: s.append(f"⑥調教{r_cho[u]}位")
        if r_ten.get(u) and r_ten[u] <= third and (h['okure'] is not None and h['okure'] <= 20):
            s.append(f"⑬展開{r_ten[u]}位/出遅{h['okure']:.0f}%")
        if h['MB'] or h['UL']:
            tags = []
            if h['MB']: tags.append(f"MB{len(h['MB'])}")
            if h['UL']: tags.append(f"UL{len(h['UL'])}")
            s.append("⑤" + "+".join(tags))
        if h['unsei'] in ('◎◎', '◎'): s.append(f"運勢{h['unsei']}")
        if (h['geki_mark'] or 0) >= 2 or (r_geki.get(u) and r_geki[u] <= 3):
            s.append(f"ウマトク(激印{h['geki_mark'] or 0}/激走{r_geki.get(u,'-')}位)")
        if (r_dist.get(u) and r_dist[u] <= third) or (r_crs.get(u) and r_crs[u] <= third):
            s.append("①適性")
        h['support'] = s
        h['nsup'] = len(s)
        h['ranks'] = {'IDM': r_idm.get(u), 'time': r_time.get(u), 'total': r_tot.get(u),
                      'chokyo': r_cho.get(u), 'tenkai': r_ten.get(u), 'SAV': r_sav.get(u)}
    R['third'] = third
    R['n_time_ok'] = n_time

json.dump(D, open(OUT, 'w'), ensure_ascii=False, indent=1)

ana = [(R, h) for R in D for h in R['horses'] if h['kijun_ninki'] and 7 <= h['kijun_ninki'] <= 12]
print(f'全35R / 穴帯(基準人気7〜12)候補 {len(ana)}頭')
print('支持係数分布:', dict(sorted(Counter(h['nsup'] for _, h in ana).items())))
print()
print('■ 支持4本以上の穴馬（v2.1荒れ順で並べ替え）')
order = {(R['ba'], R['r']): i for i, R in enumerate(sorted(D, key=lambda x: -x['v21']['ONE_HOLE']))}
top = sorted([x for x in ana if x[1]['nsup'] >= 4], key=lambda z: (order[(z[0]['ba'], z[0]['r'])], -z[1]['nsup']))
for R, h in top:
    print(f"{R['ba']}{R['r']:>2}R(荒れ{order[(R['ba'],R['r'])]+1:>2}位/ONE{R['v21']['ONE_HOLE']}) "
          f"{h['uma']:>2} {h['name']:<12} {h['jockey']:<5} 基準人気{int(h['kijun_ninki']):>2} "
          f"単{h['kijun_tan']} 複{h['kijun_fuku']} 支持{h['nsup']}")
    print(f"      {' / '.join(h['support'])}")
