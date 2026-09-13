#!/usr/bin/env python3
# 調教データ(スライド競馬新聞)を確定結果に結合し、入着率・回収率を統計的に測る。
# 目的は「独自理論の確立」の土台づくり。現時点の標本で何が言えて何が言えないかを分離する。
import csv, io, json, math, os, re, collections

SP22 = '/tmp/claude-0/-home-user-github-com-new/47c1892c-ddc4-50e4-8b6f-3403a9782673/scratchpad/race_day_20260822'
SP23 = '/tmp/claude-0/-home-user-github-com-new/47c1892c-ddc4-50e4-8b6f-3403a9782673/scratchpad/race_day_20260823'
GH = '/home/user/github.com-new/predictions'
DAYS = [
    ('8/22', f'{SP22}/out/スライド競馬新聞_全35R_20260822.csv', f'{GH}/20260823/results_20260822.json'),
    ('8/23', f'{SP23}/out/stride.csv', f'{GH}/20260823/results_20260823.json'),
]


def rd(p):
    return list(csv.DictReader(io.StringIO(open(p, encoding='utf-8').read())))


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def wilson(k, n, z=1.96):
    if not n:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


rows = []
join_stat = collections.Counter()
for lbl, sp, rp in DAYS:
    res = json.load(open(rp))
    races = res if isinstance(res, list) else list(res.values())
    idx = {}
    for x in races:
        for h in x['horses']:
            idx[(x['venue'], x['r'], h['umaban'])] = h
    heads = collections.Counter((x['venue'], x['r']) for x in races for _ in x['horses'])
    for r in rd(sp):
        key0 = list(r.keys())[0]                      # BOM付きの「日付」
        v, rr, u = r.get('開催場'), num(r.get('R')), num(r.get('馬番'))
        if not v or rr is None or u is None:
            join_stat['キー欠損'] += 1
            continue
        res_h = idx.get((v, int(rr), int(u)))
        if res_h is None:
            join_stat['結果に無し'] += 1
            continue
        if res_h.get('chakujun') is None:
            join_stat['取消/中止'] += 1
            continue
        if res_h['name'] != r.get('馬名'):
            join_stat['馬名不一致'] += 1
            continue
        fin = re.match(r'(\d+)\((.+)\)', (r.get('最終追切') or '').strip())
        wk1 = re.match(r'(\d+)\((.+)\)', (r.get('1週前追切') or '').strip())
        pat = (r.get('調教パターン') or '').strip()
        m = re.match(r'(坂路|コース|併用)(.*)', pat)
        rows.append({
            'day': lbl, 'venue': v, 'r': int(rr), 'umaban': int(u), 'name': r['馬名'],
            'pop': res_h.get('pop'), 'odds': res_h.get('odds') or 0.0,
            'chaku': res_h['chakujun'], 'last3f': res_h.get('last3f'),
            'field': heads[(v, int(rr))],
            'chokyo_idx': num(r.get('調教指数')), 'shiage_idx': num(r.get('仕上指数')),
            'fin_idx': num(fin.group(1)) if fin else None,
            'fin_course': fin.group(2) if fin else None,
            'wk1_idx': num(wk1.group(1)) if wk1 else None,
            'wk1_course': wk1.group(2) if wk1 else None,
            'pattern': pat or None,
            'surface': m.group(1) if m else None,          # 坂路 / コース(ウッド) / 併用
            'emphasis': (m.group(2) or None) if m else None,  # 平均 / 終い重点 / テン重点 / 中重点
        })
        join_stat['結合成功'] += 1

print('=== 結合 ===')
for k, v in join_stat.most_common():
    print(f'  {k}: {v}')
print(f'  → 解析対象 {len(rows)}頭 ({DAYS[0][0]}+{DAYS[1][0]})\n')


def rep(name, sub, indent=''):
    n = len(sub)
    if n == 0:
        print(f'{indent}{name:<26} n=  0'); return
    w = sum(1 for x in sub if x['chaku'] == 1)
    k3 = sum(1 for x in sub if x['chaku'] <= 3)
    ret = sum(x['odds'] for x in sub if x['chaku'] == 1)
    lo, hi = wilson(k3, n)
    print(f'{indent}{name:<26} n={n:>4}  勝{w:>3}({100*w/n:>4.1f}%)  '
          f'3着内{k3:>3}({100*k3/n:>4.1f}%) CI[{100*lo:>4.1f},{100*hi:>5.1f}]  単回収{100*ret/n:>6.1f}%')


base = rows
print('=== 全体(基準) ===')
rep('全馬', base)

print('\n=== ① 調教コース種別(調教パターン) ===')
for s in ('坂路', 'コース', '併用'):
    rep(s, [x for x in base if x['surface'] == s])
rep('[不足](パターン無し)', [x for x in base if x['surface'] is None])

print('\n=== ② 重点区分 ===')
for e in ('平均', '終い重点', 'テン重点', '中重点'):
    rep(e, [x for x in base if x['emphasis'] == e])

print('\n=== ③ コース種別 × 終い重点 ===')
for s in ('坂路', 'コース', '併用'):
    for e in ('平均', '終い重点'):
        rep(f'{s}・{e}', [x for x in base if x['surface'] == s and x['emphasis'] == e], '  ')

print('\n=== ④ 最終追切の実施コース ===')
cc = collections.Counter(x['fin_course'] for x in base if x['fin_course'])
for c, _ in cc.most_common():
    sub = [x for x in base if x['fin_course'] == c]
    if len(sub) >= 15:
        rep(c, sub)

print('\n=== ⑤ 調教指数(レース内順位) ===')
byrace = collections.defaultdict(list)
for x in base:
    if x['chokyo_idx'] is not None:
        byrace[(x['day'], x['venue'], x['r'])].append(x)
for g in byrace.values():
    g.sort(key=lambda h: -h['chokyo_idx'])
    for i, h in enumerate(g, 1):
        h['ck_rank'] = i
        h['ck_frac'] = i / len(g)
ranked = [x for x in base if x.get('ck_rank')]
rep('調教指数1位', [x for x in ranked if x['ck_rank'] == 1])
rep('同2〜3位', [x for x in ranked if 2 <= x['ck_rank'] <= 3])
rep('同 上位1/3', [x for x in ranked if x['ck_frac'] <= 1/3])
rep('同 中位1/3', [x for x in ranked if 1/3 < x['ck_frac'] <= 2/3])
rep('同 下位1/3', [x for x in ranked if x['ck_frac'] > 2/3])

print('\n=== ⑥ 最終追切が1週前より上昇したか(上昇量) ===')
both = [x for x in base if x['fin_idx'] is not None and x['wk1_idx'] is not None]
rep('上昇 +5以上', [x for x in both if x['fin_idx'] - x['wk1_idx'] >= 5])
rep('上昇 +1〜+4', [x for x in both if 1 <= x['fin_idx'] - x['wk1_idx'] <= 4])
rep('横ばい 0', [x for x in both if x['fin_idx'] == x['wk1_idx']])
rep('下降 -1〜-4', [x for x in both if -4 <= x['fin_idx'] - x['wk1_idx'] <= -1])
rep('下降 -5以下', [x for x in both if x['fin_idx'] - x['wk1_idx'] <= -5])
rep('1週前が[不足]', [x for x in base if x['wk1_idx'] is None])

json.dump(rows, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'joined.json'), 'w'),
          ensure_ascii=False)
print(f'\n書き出し: joined.json ({len(rows)}頭)')
