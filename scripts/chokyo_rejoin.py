#!/usr/bin/env python3
# 自前で作った馬場差補正(z化した終い1F)を確定結果に結合し、
# 第2報「生タイムは情報を持たない(p=1.0000)」を補正後に再検定する。
import json, math, os, collections, random
import os
# 中間成果物の置き場。作業領域が変わる場合は CHOKYO_WORK で上書きする。
WORK = os.environ.get("CHOKYO_WORK", "/tmp/claude-0/-home-user-github-com-new/47c1892c-ddc4-50e4-8b6f-3403a9782673/scratchpad/rev")
os.makedirs(WORK, exist_ok=True)
SC = WORK
GH = '/home/user/github.com-new/predictions/20260823'
WINDOW = {'20260815', '20260816', '20260817', '20260818', '20260819', '20260820', '20260821'}

chokyo = json.load(open(f'{SC}/chokyo_raw.json'))

# 本追切 = 8/15〜8/21 のうち最も遅い日の追切。同日複数は最長距離(4F>3F>2F)を採る。
best = {}
for x in chokyo:
    if x['date'] not in WINDOW or x['z1f'] is None:
        continue
    rank = (x['date'], 1 if x['f4'] else 0, 1 if x['f3'] else 0)
    k = x['name']
    if k not in best or rank > best[k][0]:
        best[k] = (rank, x)
work = {k: v[1] for k, v in best.items()}
print(f'本追切が特定できた馬 {len(work)}頭 (8/15〜8/21)')

rows = []
miss = collections.Counter()
for day, rp in [('8/22', f'{GH}/results_20260822.json'), ('8/23', f'{GH}/results_20260823.json')]:
    res = json.load(open(rp))
    races = res if isinstance(res, list) else list(res.values())
    for r in races:
        n = len(r['horses'])
        for h in r['horses']:
            if h.get('chakujun') is None:
                miss['取消/中止'] += 1
                continue
            w = work.get(h['name'])
            if w is None:
                miss['追切データに無し'] += 1
                continue
            rows.append(dict(day=day, venue=r['venue'], r=r['r'], name=h['name'], field=n,
                             chaku=h['chakujun'], pop=h.get('pop'), odds=h.get('odds') or 0.0,
                             z1f=w['z1f'], f1=w['f1'], surface=w['surface'],
                             place=w['place'], wdate=w['date']))
            miss['結合成功'] += 1
print('結合:', dict(miss))
print(f'→ 解析対象 {len(rows)}頭\n')


def wilson(k, n, z=1.96):
    if not n:
        return (0.0, 1.0)
    p, d = k / n, 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0, c - h), min(1, c + h))


def boot_roi(sub, B=4000, seed=7):
    if not sub:
        return (0.0, 0.0)
    rnd = random.Random(seed)
    pay = [x['odds'] if x['chaku'] == 1 else 0.0 for x in sub]
    n = len(pay)
    o = sorted(sum(rnd.choice(pay) for _ in range(n)) / n * 100 for _ in range(B))
    return (o[int(.025 * B)], o[int(.975 * B)])


def lchoose(n, k):
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def fisher(a, b, c, d):
    """2x2 両側 Fisher 正確検定。"""
    n = a + b + c + d
    p0 = math.exp(lchoose(a + b, a) + lchoose(c + d, c) - lchoose(n, a + c))
    tot = 0.0
    for i in range(max(0, a + c - (c + d)), min(a + b, a + c) + 1):
        p = math.exp(lchoose(a + b, i) + lchoose(c + d, a + c - i) - lchoose(n, a + c))
        if p <= p0 * (1 + 1e-9):
            tot += p
    return min(1.0, tot)


def rep(name, sub, ind=''):
    n = len(sub)
    if not n:
        print(f'{ind}{name:<24} n=   0'); return
    w = sum(1 for x in sub if x['chaku'] == 1)
    k3 = sum(1 for x in sub if x['chaku'] <= 3)
    roi = sum(x['odds'] for x in sub if x['chaku'] == 1) / n * 100
    lo, hi = wilson(k3, n)
    blo, bhi = boot_roi(sub)
    print(f'{ind}{name:<24} n={n:>4}  勝{w:>3}({100*w/n:>4.1f}%)  3着内{k3:>3}({100*k3/n:>4.1f}%) '
          f'CI[{100*lo:>4.1f},{100*hi:>5.1f}]  単回収{roi:>6.1f}% CI[{blo:>5.1f},{bhi:>6.1f}]')


# レース内でz順位を出す(相対評価)。zは小さいほど速い。
byrace = collections.defaultdict(list)
for x in rows:
    byrace[(x['day'], x['venue'], x['r'])].append(x)
for g in byrace.values():
    g.sort(key=lambda h: h['z1f'])
    for i, h in enumerate(g, 1):
        h['zrank'] = i
        h['zfrac'] = i / len(g)

print('=== 全体(基準) ===')
rep('全馬', rows)

print('\n=== ① 補正後の終い1F(z) 絶対水準 ===')
for lab, f in [('z <= -1.5 (かなり速い)', lambda x: x['z1f'] <= -1.5),
               ('-1.5 < z <= -0.5', lambda x: -1.5 < x['z1f'] <= -0.5),
               ('-0.5 < z <= +0.5', lambda x: -0.5 < x['z1f'] <= 0.5),
               ('z > +0.5 (遅い)', lambda x: x['z1f'] > 0.5)]:
    rep(lab, [x for x in rows if f(x)])

print('\n=== ② 補正後の終い1F レース内順位(3分割) ===')
t = [x for x in rows if x.get('zfrac')]
up = [x for x in t if x['zfrac'] <= 1/3]
mid = [x for x in t if 1/3 < x['zfrac'] <= 2/3]
lo3 = [x for x in t if x['zfrac'] > 2/3]
rep('補正後 上位1/3', up); rep('補正後 中位1/3', mid); rep('補正後 下位1/3', lo3)
a, b = sum(1 for x in up if x['chaku'] <= 3), len(up) - sum(1 for x in up if x['chaku'] <= 3)
c, d = sum(1 for x in lo3 if x['chaku'] <= 3), len(lo3) - sum(1 for x in lo3 if x['chaku'] <= 3)
print(f'  上位1/3 vs 下位1/3 の3着内率: Fisher両側 p={fisher(a,b,c,d):.4f}')

print('\n=== ③ 比較: 補正前(生タイム)のレース内順位(3分割) ===')
for g in byrace.values():
    g.sort(key=lambda h: h['f1'])
    for i, h in enumerate(g, 1):
        h['rawfrac'] = i / len(g)
rup = [x for x in t if x['rawfrac'] <= 1/3]
rlo = [x for x in t if x['rawfrac'] > 2/3]
rep('補正前 上位1/3', rup)
rep('補正前 中位1/3', [x for x in t if 1/3 < x['rawfrac'] <= 2/3])
rep('補正前 下位1/3', rlo)
a2, b2 = sum(1 for x in rup if x['chaku'] <= 3), len(rup) - sum(1 for x in rup if x['chaku'] <= 3)
c2, d2 = sum(1 for x in rlo if x['chaku'] <= 3), len(rlo) - sum(1 for x in rlo if x['chaku'] <= 3)
print(f'  上位1/3 vs 下位1/3 の3着内率: Fisher両側 p={fisher(a2,b2,c2,d2):.4f}')

print('\n=== ④ 交絡の直接確認: コース別 ===')
for s in ('坂路', 'ウッド'):
    sub = [x for x in rows if x['surface'] == s]
    rep(s, sub)
    raw11 = sum(1 for x in sub if x['f1'] < 12.0)
    print(f'     └ 生の終い1Fが11秒台の割合: {raw11}/{len(sub)} = {100*raw11/max(1,len(sub)):.1f}%')

json.dump(rows, open(f'{SC}/joined_z.json', 'w'), ensure_ascii=False)
print(f'\n書き出し: joined_z.json ({len(rows)}頭)')
