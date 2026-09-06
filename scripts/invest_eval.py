#!/usr/bin/env python3
# §7 投資評価 / §8 レース単位を考慮した必要標本。
# ⚠ 本スクリプトは事後評価であり、買い目・資金配分を提案するものではない。
import json, math, os, collections, random, csv

GH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.environ.get('CHOKYO_WORK', '/tmp/chokyo_work')


def load():
    joined = json.load(open(f'{GH}/reports/joined_strict.json'))
    ch = json.load(open(f'{WORK}/chokyo_raw.json'))
    zk = {(x['name'], x['date'], x['surface']): x['z1f'] for x in ch if x['z1f'] is not None}
    rows = []
    for r in joined:
        z = zk.get((r['name'], r['last_date'], r['last_course']))
        if z is None or not r['pop']:
            continue
        rows.append(dict(day=r['day'], race=f"{r['day']}|{r['venue']}|{r['race']}",
                         y3=1 if r['chaku'] <= 3 else 0, win=1 if r['chaku'] == 1 else 0,
                         z=z, pop=r['pop'], odds=r['odds']))
    byrace = collections.defaultdict(list)
    for r in rows:
        byrace[r['race']].append(r)
    for g in byrace.values():
        g.sort(key=lambda h: h['z'])
        for i, h in enumerate(g, 1):
            h['zfrac'] = i / len(g)
        g.sort(key=lambda h: h['pop'])
        for i, h in enumerate(g, 1):
            h['pfrac'] = i / len(g)
    return rows


def wilson(k, n, z=1.96):
    if not n:
        return (0.0, 1.0)
    p, d = k / n, 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def race_boot(byrace, pick, B=2000, seed=23):
    """レース単位で再抽出した単勝回収率の95%CI。"""
    keys = list(byrace)
    rnd = random.Random(seed)
    out = []
    for _ in range(B):
        stake = ret = 0
        for _ in range(len(keys)):
            for h in byrace[rnd.choice(keys)]:
                if pick(h):
                    stake += 1
                    ret += h['odds'] if h['win'] else 0.0
        if stake:
            out.append(100 * ret / stake)
    out.sort()
    return out[int(.025 * len(out))], out[int(.975 * len(out))]


def evaluate(rows, pick, label):
    sel = [r for r in rows if pick(r)]
    n = len(sel)
    if not n:
        print(f'{label}: 該当なし')
        return
    k3 = sum(r['y3'] for r in sel)
    kw = sum(r['win'] for r in sel)
    ret = sum(r['odds'] for r in sel if r['win'])
    lo3, hi3 = wilson(k3, n)
    low, hiw = wilson(kw, n)
    avg = sum(r['odds'] for r in sel) / n
    byrace = collections.defaultdict(list)
    for r in rows:
        byrace[r['race']].append(r)
    blo, bhi = race_boot(byrace, pick)
    # レース単位の損益と最大ドローダウン(1点1単位)
    pnl = []
    for k in sorted(byrace):
        s = [h for h in byrace[k] if pick(h)]
        if s:
            pnl.append(sum(h['odds'] if h['win'] else 0.0 for h in s) - len(s))
    cum, peak, dd = 0.0, 0.0, 0.0
    for v in pnl:
        cum += v
        peak = max(peak, cum)
        dd = min(dd, cum - peak)
    print(f'\n{label}  n={n}  ({len(pnl)}レース)')
    print(f'  的中率(単勝)   {100*kw/n:>6.2f}%  Wilson95%CI [{100*low:.2f}, {100*hiw:.2f}]')
    print(f'  3着内率        {100*k3/n:>6.2f}%  Wilson95%CI [{100*lo3:.2f}, {100*hi3:.2f}]')
    print(f'  平均オッズ     {avg:>6.2f}倍')
    print(f'  単勝回収率     {100*ret/n:>6.1f}%  レース単位ブートストラップ95%CI [{blo:.1f}, {bhi:.1f}]')
    print(f'  最終損益       {cum:>+7.1f}単位 / 最大ドローダウン {dd:>+7.1f}単位')
    q = sorted(pnl)
    print(f'  レース損益分布 最小{q[0]:+.1f} / 25%{q[len(q)//4]:+.1f} / 中央{q[len(q)//2]:+.1f} '
          f'/ 75%{q[3*len(q)//4]:+.1f} / 最大{q[-1]:+.1f}')
    print(f'  ⚠ 複勝回収率: [不足] — 複勝払戻データがどの結果ソースにも無い')


def sample_size_sim(rows, B=3000, seed=29):
    """§8 レース単位・同一馬反復を考慮した必要標本のシミュレーション。
    観測された効果量を保ったままレースごと再抽出し、開催日数を増やしたとき
    7〜12人気帯の Fisher 検定が有意になる割合(検出力)を求める。"""
    band = [r for r in rows if 7 <= r['pop'] <= 12]
    byrace = collections.defaultdict(list)
    for r in band:
        byrace[r['race']].append(r)
    keys = list(byrace)
    days = len({r['day'] for r in rows})
    per_day = len(keys) / days

    def lch(n, k):
        return math.lgamma(n+1) - math.lgamma(k+1) - math.lgamma(n-k+1)

    def fisher(a, b, c, d):
        n = a+b+c+d
        if not n:
            return 1.0
        p0 = math.exp(lch(a+b, a) + lch(c+d, c) - lch(n, a+c))
        t = 0.0
        for i in range(max(0, a+c-(c+d)), min(a+b, a+c)+1):
            p = math.exp(lch(a+b, i) + lch(c+d, a+c-i) - lch(n, a+c))
            if p <= p0*(1+1e-9):
                t += p
        return min(1.0, t)

    print('\n=== §8 レース単位シミュレーションによる必要開催日数 ===')
    print(f'  7〜12人気帯: {len(band)}頭 / {len(keys)}レース / {days}開催日 '
          f'(1開催日あたり約{per_day:.0f}レース)')
    print('  開催日数  検出力(有意になった割合)')
    rnd = random.Random(seed)
    for extra_days in (12, 24, 36, 48, 72, 96):
        nrace = int(per_day * extra_days)
        hit = 0
        for _ in range(B):
            u = l = uk = lk = 0
            for _ in range(nrace):
                for h in byrace[rnd.choice(keys)]:
                    if h['zfrac'] <= 1/3:
                        u += 1; uk += h['y3']
                    elif h['zfrac'] > 2/3:
                        l += 1; lk += h['y3']
            if u and l and fisher(uk, u-uk, lk, l-lk) < 0.05:
                hit += 1
        print(f'  {extra_days:>6}日  {100*hit/B:>6.1f}%')
    print('  ※ 観測された効果量が真であると仮定した場合の値。効果が無ければ検出力は5%に留まる。')


if __name__ == '__main__':
    rows = load()
    odds_rows = [r for r in rows if r['odds']]
    print(f'全結合 {len(rows)}頭 / うちオッズあり {len(odds_rows)}頭'
          f'({len({r["day"] for r in odds_rows})}開催日)')
    print('⚠ 回収率の評価はオッズがある部分標本に限られる。JRA公式結果CSVにオッズ列が無い。')
    evaluate(odds_rows, lambda r: r['zfrac'] <= 1/3, '① 調教z上位1/3を単勝で買った場合')
    evaluate(odds_rows, lambda r: r['pfrac'] <= 1/3, '② 比較: 人気上位1/3を単勝で買った場合')
    evaluate(odds_rows, lambda r: 7 <= r['pop'] <= 12 and r['zfrac'] <= 1/3,
             '③ 7〜12人気かつ調教z上位1/3')
    evaluate(odds_rows, lambda r: 7 <= r['pop'] <= 12, '④ 比較: 7〜12人気すべて')
    sample_size_sim(rows)
