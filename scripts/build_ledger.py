#!/usr/bin/env python3
# 累積成績台帳: 日ごとの上下でなく、標本を積み上げて中長期で判断するための集計。
# 「その日どうだったか」ではなく「今の標本で何が言えて、何がまだ言えないか」を出す。
import json, math, os, collections

CUM = os.environ.get('LEDGER_DIR', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GH = '/home/user/github.com-new/predictions'

# (日付, 印データのパス, 結果データのパス, 予想対象の絞り込みがあるか)
DAYS = [
    ('2026-08-16', f'{GH}/20260816/results_20260816.json', f'{CUM}/derived/results_20260816.json', None),
    ('2026-08-22', f'{GH}/20260822/results_20260822.json', f'{GH}/20260823/results_20260822.json', None),
    ('2026-08-23', f'{GH}/20260823/00_Claude独立再評価_20260823.md', f'{GH}/20260823/results_20260823.json', 'selected'),
]
MARKS = [('main', '◎'), ('rival', '○'), ('third', '▲'), ('sub', '△'), ('long', '☆'), ('hoshi', '☆')]


def load_results(path):
    r = json.load(open(path))
    rows = r if isinstance(r, list) else list(r.values())
    idx = {}
    for x in rows:
        for h in x['horses']:
            idx[(x['venue'], x['r'], h['umaban'])] = h
    return rows, idx


def marks_from_eval(path):
    """8/16・8/22形式(係JSON)から (venue, r, mark, umaban) を取り出す"""
    out = []
    for x in json.load(open(path)):
        rc, f = x['race'], x.get('final') or {}
        for key, m in MARKS:
            v = f.get(key)
            if not v:
                continue
            for h in (v if isinstance(v, list) else [v]):
                if isinstance(h, dict) and h.get('umaban'):
                    out.append((rc['venue'], rc['r'], m, h['umaban']))
    return out


def marks_0823():
    """8/23は分析JSONに印×結果が展開済み"""
    ana = json.load(open(f'{GH}/20260823/分析_20260823.json'))
    return [(d['venue'], d['r'], d['mark'], d['umaban']) for d in ana['detail']]


def is_chaotic(race):
    hs = sorted([h for h in race['horses'] if h.get('chakujun') and h.get('pop')],
                key=lambda h: h['chakujun'])[:3]
    if len(hs) < 3:
        return None
    return hs[0]['pop'] >= 5 or sum(h['pop'] for h in hs) >= 18


def wilson(k, n, z=1.96):
    """Wilson score 区間。小標本でも破綻しない二項比率の信頼区間"""
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


days, per_day = [], {}
for date, mpath, rpath, scope in DAYS:
    races, idx = load_results(rpath)
    marks = marks_0823() if date == '2026-08-23' else marks_from_eval(mpath)
    agg = collections.defaultdict(lambda: {'n': 0, 'w': 0, 'p2': 0, 'p3': 0, 'ret': 0.0, 'unresolved': 0})
    for v, r, m, u in marks:
        h = idx.get((v, r, u))
        if h is None:
            continue
        a = agg[m]
        a['n'] += 1
        c = h.get('chakujun')
        if c is None:                       # 競走中止・除外は着順不明として分母から外さず別計上
            a['unresolved'] += 1
            continue
        if c == 1:
            a['w'] += 1
            a['ret'] += h.get('odds') or 0.0
        if c <= 2:
            a['p2'] += 1
        if c <= 3:
            a['p3'] += 1
    ch = [is_chaotic(x) for x in races]
    ch = [c for c in ch if c is not None]
    per_day[date] = {'agg': {k: dict(v) for k, v in agg.items()},
                     'races': len(races), 'chaotic': sum(ch),
                     'horses': sum(len(x['horses']) for x in races)}
    days.append(date)

# 累積
cum = collections.defaultdict(lambda: {'n': 0, 'w': 0, 'p2': 0, 'p3': 0, 'ret': 0.0, 'unresolved': 0})
for d in days:
    for m, a in per_day[d]['agg'].items():
        for k in cum[m]:
            cum[m][k] += a[k]

report = {'days': days, 'per_day': per_day, 'cumulative': {k: dict(v) for k, v in cum.items()}}
json.dump(report, open(f'{CUM}/derived/累積成績台帳.json', 'w'), ensure_ascii=False, indent=1)

print('=== 日別 ===')
print(f"{'日付':12} {'R':>3} {'頭':>4} {'荒れ':>5}  " + '  '.join(f'{m:>16}' for m in '◎○▲'))
for d in days:
    p = per_day[d]
    cells = []
    for m in '◎○▲':
        a = p['agg'].get(m, {'n': 0, 'w': 0, 'p3': 0})
        cells.append(f"n{a['n']:>3} 勝{a['w']:>2} 複{a['p3']:>2}" if a['n'] else ' ' * 16)
    print(f"{d:12} {p['races']:>3} {p['horses']:>4} {p['chaotic']:>2}/{p['races']:<2}  " + '  '.join(cells))

print('\n=== 累積(3日) ===')
print(f"{'印':>2} {'頭数':>4} {'勝':>3} {'連対':>4} {'複勝':>4} {'勝率':>7} {'複勝率':>7} {'単回収':>8} {'複勝率95%CI':>16}")
for m in '◎○▲△☆':
    a = cum.get(m)
    if not a or not a['n']:
        continue
    dec = a['n'] - a['unresolved']
    lo, hi = wilson(a['p3'], dec)
    print(f"{m:>2} {a['n']:>4} {a['w']:>3} {a['p2']:>4} {a['p3']:>4} "
          f"{100*a['w']/dec:>6.1f}% {100*a['p3']/dec:>6.1f}% {100*a['ret']/dec:>7.1f}% "
          f"  [{100*lo:>4.1f}%, {100*hi:>4.1f}%]")

# ◎と○の差が標本で分離できているか
a, b = cum['◎'], cum['○']
da, db = a['n'] - a['unresolved'], b['n'] - b['unresolved']
la, ha = wilson(a['p3'], da)
lb, hb = wilson(b['p3'], db)
sep = (ha < lb) or (hb < la)
print(f"\n◎複勝率 {100*a['p3']/da:.1f}% [{100*la:.1f}, {100*ha:.1f}]  vs"
      f"  ○複勝率 {100*b['p3']/db:.1f}% [{100*lb:.1f}, {100*hb:.1f}]")
print('区間が重なる → 現標本では差を主張できない' if not sep else '区間が分離 → 差を主張できる')


def n_needed(p1, p2, power=0.8, alpha=0.05):
    """2つの比率の差を検出するのに必要な1群あたりの標本数(正規近似)"""
    if p1 == p2:
        return None
    za, zb = 1.959964, 0.8416212
    pbar = (p1 + p2) / 2
    num = (za * math.sqrt(2 * pbar * (1 - pbar)) + zb * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2
    return math.ceil(num / (p1 - p2) ** 2)


p1, p2 = a['p3'] / da, b['p3'] / db
need = n_needed(p1, p2)
print(f"\n観測差({100*p1:.1f}% vs {100*p2:.1f}%)を有意に検出するには 1印あたり約{need}頭が必要。"
      f"現在{da}頭 / {db}頭。")
avg = da / len(days)
print(f"1日あたり◎は平均{avg:.1f}頭なので、あと約{math.ceil((need-da)/avg)}開催日ぶんの積み上げが要る。")
print('\n書き出し:', f'{CUM}/derived/累積成績台帳.json')
