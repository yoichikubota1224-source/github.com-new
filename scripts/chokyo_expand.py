#!/usr/bin/env python3
# 拡大標本での再検定。
#
# 第5報は 8/22・8/23 の2開催日(589頭)だけで、補正後zの3着内率に p=0.0996 を得た。
# そこでの必要標本の見積り「1群 n≈534」は **人気を統制しない比較** に対するもので、
# それが正しい目標だったのかを、標本を12開催日に広げて確かめる。
#
# 結果の出所は2系統:
#   A. data/results/official_results_*.csv … JRA公式サイト由来。オッズ列が無いので回収率は出せない
#   B. predictions/*/results*.json          … netkeiba由来。オッズあり
import csv, io, json, math, os, collections, datetime, glob

HERE = os.path.dirname(os.path.abspath(__file__))
GH = os.path.dirname(HERE)
WORK = os.environ.get('CHOKYO_WORK', '/tmp/chokyo_work')
chokyo = json.load(open(f'{WORK}/chokyo_raw.json'))


def window(dstr):
    """レース日から遡って直近の月〜金を本追切の窓とする。"""
    d = datetime.date(*map(int, dstr.split('-')))
    mon = d - datetime.timedelta(days=d.weekday())
    return {(mon + datetime.timedelta(days=i)).strftime('%Y%m%d') for i in range(5)}


def best_work(win):
    """窓の中で最も遅い日の追切。同日複数は最長距離を採る。"""
    best = {}
    for x in chokyo:
        if x['date'] not in win or x['z1f'] is None:
            continue
        rank = (x['date'], 1 if x['f4'] else 0, 1 if x['f3'] else 0)
        if x['name'] not in best or rank > best[x['name']][0]:
            best[x['name']] = (rank, x)
    return {k: v[1] for k, v in best.items()}


rows, miss = [], collections.Counter()

for p in sorted(glob.glob(f'{GH}/data/results/official_results_*.csv')):
    for r in csv.DictReader(io.StringIO(open(p, encoding='utf-8-sig').read())):
        if r['status'] != 'COMPLETED':
            miss['取消・中止・除外'] += 1
            continue
        rows.append(dict(day=r['date'], venue=r['track'], r=int(r['race_no']), name=r['horse_name'],
                         chaku=int(float(r['finish_numeric'])),
                         pop=int(float(r['popularity'])) if r['popularity'] else None, odds=None))

for day, path in [('2026-08-16', f'{GH}/predictions/20260816/results確定_20260816.json'),
                  ('2026-08-22', f'{GH}/predictions/20260823/results_20260822.json'),
                  ('2026-08-23', f'{GH}/predictions/20260823/results_20260823.json')]:
    d = json.load(open(path))
    for x in (d if isinstance(d, list) else list(d.values())):
        for h in x['horses']:
            if h.get('chakujun') is None:
                miss['取消・中止・除外'] += 1
                continue
            rows.append(dict(day=day, venue=x['venue'], r=x['r'], name=h['name'],
                             chaku=h['chakujun'], pop=h.get('pop'), odds=h.get('odds')))

byday = collections.defaultdict(list)
for x in rows:
    byday[x['day']].append(x)
joined = []
for day, hs in byday.items():
    w = best_work(window(day))
    for h in hs:
        k = w.get(h['name'])
        if k is None:
            miss['追切データに無し'] += 1
            continue
        h['z1f'] = k['z1f']
        joined.append(h)

print(f'開催日 {len(byday)}日 / 結果 {len(rows)}頭 / 結合 {len(joined)}頭 ({100*len(joined)/len(rows):.1f}%)')
print('  除外:', dict(miss))

byrace = collections.defaultdict(list)
for x in joined:
    byrace[(x['day'], x['venue'], x['r'])].append(x)
for g in byrace.values():
    g.sort(key=lambda h: h['z1f'])
    for i, h in enumerate(g, 1):
        h['zfrac'] = i / len(g)


def wilson(k, n, z=1.96):
    if not n:
        return (0.0, 1.0)
    p, d = k / n, 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def lch(n, k):
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def fisher(a, b, c, d):
    n = a + b + c + d
    if not n:
        return float('nan')
    p0 = math.exp(lch(a + b, a) + lch(c + d, c) - lch(n, a + c))
    t = 0.0
    for i in range(max(0, a + c - (c + d)), min(a + b, a + c) + 1):
        p = math.exp(lch(a + b, i) + lch(c + d, a + c - i) - lch(n, a + c))
        if p <= p0 * (1 + 1e-9):
            t += p
    return min(1.0, t)


def nreq(p1, p2, alpha=0.05, power=0.8):
    za, zb = 1.959963985, 0.8416212336
    if p1 == p2:
        return float('inf')
    pb = (p1 + p2) / 2
    return math.ceil((za * math.sqrt(2 * pb * (1 - pb))
                      + zb * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2 / (p1 - p2) ** 2)


up = [x for x in joined if x['zfrac'] <= 1/3]
mid = [x for x in joined if 1/3 < x['zfrac'] <= 2/3]
lo = [x for x in joined if x['zfrac'] > 2/3]

print('\n=== ① 補正後z 3分割(人気を統制しない・第5報と同じ切り方) ===')
for lab, sub in [('上位1/3', up), ('中位1/3', mid), ('下位1/3', lo)]:
    k3 = sum(1 for x in sub if x['chaku'] <= 3)
    a, b = wilson(k3, len(sub))
    print(f'  {lab}  n={len(sub):>4}  3着内 {k3:>4} ({100*k3/len(sub):>4.1f}%)  CI[{100*a:>4.1f},{100*b:>5.1f}]')
ka, kb = sum(1 for x in up if x['chaku'] <= 3), 0
kb = len(up) - ka
kc = sum(1 for x in lo if x['chaku'] <= 3)
kd = len(lo) - kc
print(f'  上位1/3 vs 下位1/3  Fisher両側 p={fisher(ka, kb, kc, kd):.4f}')

print('\n=== ② ⚠ その差は人気の差ではないか ===')
for lab, sub in [('z上位1/3', up), ('z中位1/3', mid), ('z下位1/3', lo)]:
    p = [x for x in sub if x['pop']]
    b = collections.Counter('1-3' if x['pop'] <= 3 else '4-6' if x['pop'] <= 6
                            else '7-12' if x['pop'] <= 12 else '13-' for x in p)
    n = len(p)
    print(f'  {lab}  平均人気 {sum(x["pop"] for x in p)/n:4.1f}   '
          + ' '.join(f'{k}:{100*b[k]/n:4.1f}%' for k in ('1-3', '4-6', '7-12', '13-')))

print('\n=== ③ 人気帯の中だけで z上位1/3 vs z下位1/3 ===')
print('  人気帯        z上位1/3             z下位1/3            Fisher p   必要n/群')
for lab, f in [('1〜3人気', lambda p: p <= 3), ('4〜6人気', lambda p: 4 <= p <= 6),
               ('7〜12人気', lambda p: 7 <= p <= 12), ('13人気以下', lambda p: p >= 13)]:
    band = [x for x in joined if x['pop'] and f(x['pop'])]
    u = [x for x in band if x['zfrac'] <= 1/3]
    l = [x for x in band if x['zfrac'] > 2/3]
    if not u or not l:
        continue
    ku, kl = sum(1 for x in u if x['chaku'] <= 3), sum(1 for x in l if x['chaku'] <= 3)
    p = fisher(ku, len(u) - ku, kl, len(l) - kl)
    n = nreq(ku / len(u), kl / len(l))
    print(f'  {lab:<10} {ku:>4}/{len(u):<4}={100*ku/len(u):>5.1f}%    '
          f'{kl:>4}/{len(l):<4}={100*kl/len(l):>5.1f}%    p={p:.4f}   n≈{n}')

print('\n=== ④ 結合できなかった馬に偏りはあるか ===')
jk = {(x['day'], x['venue'], x['r'], x['name']) for x in joined}
un = [x for x in rows if (x['day'], x['venue'], x['r'], x['name']) not in jk]
for lab, v in [('結合できた', joined), ('結合できず', un)]:
    p = [x for x in v if x['pop']]
    k3 = sum(1 for x in v if x['chaku'] <= 3)
    print(f'  {lab}: n={len(v):>4}  平均人気 {sum(x["pop"] for x in p)/len(p):4.1f}  3着内 {100*k3/len(v):4.1f}%')

wo = [x for x in joined if x['odds']]
print(f'\n=== ⑤ 単勝回収率 ===\n  オッズを持つのは {len(wo)}/{len(joined)}頭。'
      f'JRA公式結果CSVにオッズ列が無いため、拡大標本の回収率は [不足]。')
