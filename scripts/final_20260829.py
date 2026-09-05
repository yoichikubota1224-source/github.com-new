#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2026-08-29 14係 最終統合。コンピ＋ROIを追記し、支持係数を再計算する。
- ③ROI: 厩舎別回収率(5年実測・20260802凍結)。結合は調教師名の完全一致→3文字前方一致(一意時のみ)。
  未収載は[不足]HOLDのまま保持(0に変換しない)。
- ②荒れ: 凍結v2.1(基準オッズ×頭数) と コンピP区分 を併記。
- 買い目・点数・資金配分・購入可否は出力しない。運勢×は減点しない。
"""
import csv, json, sys
from collections import defaultdict, Counter

EVAL, ROI, DE, OUT = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
D = json.load(open(EVAL))

roi_rows = list(csv.DictReader(open(ROI, 'rb').read().decode('utf-8-sig').splitlines()))
roi = {}
for r in roi_rows:
    n5 = float(r['n_5年'] or 0)
    if n5 <= 0:
        continue                       # 室井潔・柴田卓は全0行=データ無し
    roi[r['調教師'].strip()] = {'tan5': float(r['単回_5年']), 'fuku5': float(r['複回_5年']),
                                'n5': int(n5)}

de_tr = {}
for r in csv.reader(open(DE, encoding='cp932')):
    de_tr[(r[1], int(r[2]), int(r[3]))] = r[12].strip()

def find_roi(name):
    if name in roi:
        return roi[name], '[実]'
    pre = [k for k in roi if k.startswith(name[:3])] if len(name) >= 3 else []
    if len(pre) == 1:
        return roi[pre[0]], '[実:前方一致]'
    return None, '[不足]HOLD'

MYOUMI_GOOD = {'Ｓ', 'ＡＡ', 'Ａ', 'S', 'AA', 'A'}
def rank_of(hs, key, reverse=True):
    vals = [(h['uma'], h[key]) for h in hs if h.get(key) is not None]
    vals.sort(key=lambda z: -z[1] if reverse else z[1])
    return {u: i+1 for i, (u, _) in enumerate(vals)}

nj = 0
for R in D:
    hs = R['horses']; n = len(hs); third = max(1, round(n/3))
    r_idm = rank_of(hs, 'IDM'); r_time = rank_of(hs, 'time_max'); r_last = rank_of(hs, 'time_last')
    r_tot = rank_of(hs, 'total'); r_cho = rank_of(hs, 'chokyo_idx')
    r_ten = rank_of(hs, 'tenkai', reverse=False); r_geki = rank_of(hs, 'geki')
    r_dist = rank_of(hs, 'time_dist'); r_crs = rank_of(hs, 'time_course')
    for h in hs:
        u = h['uma']
        tr = de_tr[(R['ba'], R['r'], u)]
        rv, tag = find_roi(tr)
        h['roi'] = rv; h['roi_tag'] = tag
        if rv: nj += 1
        s = []
        # 優先順位: 能力 > 運勢 > 回収率 > 展開馬場 > 調教 > 補強 > オッズ
        if r_idm.get(u) and r_idm[u] <= third: s.append(f"⑧IDM{r_idm[u]}位")
        if r_time.get(u) and r_time[u] <= third: s.append(f"⑧タイム{r_time[u]}位")
        elif r_last.get(u) and r_last[u] <= third: s.append(f"⑧前走時計{r_last[u]}位")
        if h.get('compi_rank') and h['compi_rank'] <= third: s.append(f"④コンピ{h['compi_rank']}位")
        if h.get('gold'): s.append(f"②黄金律(EP+{h['EP']})")
        if h.get('unsei') in ('◎◎', '◎'): s.append(f"運勢{h['unsei']}")
        if rv and (rv['tan5'] >= 100 or rv['fuku5'] >= 100):
            s.append(f"③厩舎ROI(単{rv['tan5']:.0f}/複{rv['fuku5']:.0f})")
        if r_ten.get(u) and r_ten[u] <= third and (h.get('okure') is not None and h['okure'] <= 20):
            s.append(f"⑬展開{r_ten[u]}位/出遅{h['okure']:.0f}%")
        if r_cho.get(u) and r_cho[u] <= third: s.append(f"⑥調教{r_cho[u]}位")
        if (r_tot.get(u) and r_tot[u] <= 3) or h.get('myoumi') in MYOUMI_GOOD:
            s.append(f"⑦STRIDE(合計{r_tot.get(u,'-')}位/妙味{h.get('myoumi') or '-'})")
        if h.get('MB') or h.get('UL'):
            t = []
            if h.get('MB'): t.append(f"MB{len(h['MB'])}")
            if h.get('UL'): t.append(f"UL{len(h['UL'])}")
            s.append("⑤" + "+".join(t))
        if (h.get('geki_mark') or 0) >= 2 or (r_geki.get(u) and r_geki[u] <= 3):
            s.append(f"激走(印{h.get('geki_mark') or 0}/指数{r_geki.get(u,'-')}位)")
        if (r_dist.get(u) and r_dist[u] <= third) or (r_crs.get(u) and r_crs[u] <= third):
            s.append("①適性")
        h['support'] = s; h['nsup'] = len(s)
    R['third'] = third

json.dump(D, open(OUT, 'w'), ensure_ascii=False, indent=1)
ana = [(R, h) for R in D for h in R['horses'] if h['kijun_ninki'] and 7 <= h['kijun_ninki'] <= 12]
print('ROI結合', nj, '/482頭')
print('穴帯202頭の支持分布:', dict(sorted(Counter(h['nsup'] for _, h in ana).items())))
print('支持5本以上:', sum(1 for _, h in ana if h['nsup'] >= 5), '頭')
