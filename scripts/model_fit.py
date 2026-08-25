#!/usr/bin/env python3
# §6 主解析。ロジスティック回帰 + レース単位クラスターロバスト標準誤差 + レース単位ブートストラップ
# + 日付順ウォークフォワード検証。numpy/scipy が無い環境のため全て純Pythonで実装する。
import json, math, os, glob, collections, random, csv

GH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.environ.get('CHOKYO_WORK', '/tmp/chokyo_work')


# ---------- 線形代数(最小限) ----------
def matinv(A):
    n = len(A)
    M = [row[:] + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(A)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(M[r][c]))
        if abs(M[piv][c]) < 1e-12:
            raise ValueError('特異行列(説明変数が共線)')
        M[c], M[piv] = M[piv], M[c]
        d = M[c][c]
        M[c] = [v / d for v in M[c]]
        for r in range(n):
            if r != c and M[r][c] != 0.0:
                f = M[r][c]
                M[r] = [a - f * b for a, b in zip(M[r], M[c])]
    return [row[n:] for row in M]


def logistic_irls(X, y, iters=60):
    n, k = len(X), len(X[0])
    b = [0.0] * k
    for _ in range(iters):
        p = []
        for xi in X:
            z = sum(bj * xj for bj, xj in zip(b, xi))
            z = max(-30.0, min(30.0, z))
            p.append(1.0 / (1.0 + math.exp(-z)))
        XtWX = [[0.0] * k for _ in range(k)]
        Xtr = [0.0] * k
        for xi, yi, pi in zip(X, y, p):
            w = max(pi * (1 - pi), 1e-9)
            r = yi - pi
            for a in range(k):
                Xtr[a] += xi[a] * r
                for c in range(a, k):
                    XtWX[a][c] += w * xi[a] * xi[c]
        for a in range(k):
            for c in range(a):
                XtWX[a][c] = XtWX[c][a]
        step = matinv(XtWX)
        delta = [sum(step[a][c] * Xtr[c] for c in range(k)) for a in range(k)]
        b = [bj + dj for bj, dj in zip(b, delta)]
        if max(abs(dj) for dj in delta) < 1e-9:
            break
    return b, XtWX


def cluster_robust_se(X, y, b, XtWX, clusters):
    k = len(b)
    p = []
    for xi in X:
        z = max(-30.0, min(30.0, sum(bj * xj for bj, xj in zip(b, xi))))
        p.append(1.0 / (1.0 + math.exp(-z)))
    g = collections.defaultdict(lambda: [0.0] * k)
    for xi, yi, pi, cl in zip(X, y, p, clusters):
        r = yi - pi
        for a in range(k):
            g[cl][a] += xi[a] * r
    meat = [[0.0] * k for _ in range(k)]
    for s in g.values():
        for a in range(k):
            for c in range(k):
                meat[a][c] += s[a] * s[c]
    bread = matinv(XtWX)
    V = [[sum(bread[a][m] * meat[m][q] for m in range(k)) for q in range(k)] for a in range(k)]
    V = [[sum(V[a][m] * bread[m][c] for m in range(k)) for c in range(k)] for a in range(k)]
    G, N = len(g), len(X)
    corr = (G / max(1, G - 1)) * ((N - 1) / max(1, N - k))
    return [math.sqrt(max(0.0, V[a][a] * corr)) for a in range(k)]


def normcdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


# ---------- データ ----------
def build():
    joined = json.load(open(f'{GH}/reports/joined_strict.json'))
    ch = json.load(open(f'{WORK}/chokyo_raw.json'))
    zk = {}
    for x in ch:
        if x['z1f'] is not None:
            zk[(x['name'], x['date'], x['surface'])] = x['z1f']
    rows = []
    for r in joined:
        z = zk.get((r['name'], r['last_date'], r['last_course']))
        if z is None or not r['pop']:
            continue
        import datetime
        rd = datetime.date(*map(int, r['day'].split('-')))
        wd = datetime.date(int(r['last_date'][:4]), int(r['last_date'][4:6]), int(r['last_date'][6:]))
        rows.append(dict(day=r['day'], race=f"{r['day']}|{r['venue']}|{r['race']}", venue=r['venue'],
                         y=1 if r['chaku'] <= 3 else 0, z=z, pop=r['pop'], odds=r['odds'],
                         gap=(rd - wd).days, course=r['last_course'], name=r['name'], chaku=r['chaku']))
    fs = collections.Counter(r['race'] for r in rows)
    for r in rows:
        r['field'] = fs[r['race']]
    return rows


def fit(rows, spec, label):
    names, build_x = spec
    X = [[1.0] + build_x(r) for r in rows]
    y = [r['y'] for r in rows]
    cl = [r['race'] for r in rows]
    b, XtWX = logistic_irls(X, y)
    se = cluster_robust_se(X, y, b, XtWX, cl)
    print(f'\n--- {label}  n={len(rows)}  レース(クラスタ)={len(set(cl))} ---')
    print(f'{"変数":<26}{"係数":>9}{"クラスタ頑健SE":>14}{"z":>8}{"p":>9}   95%CI')
    for nm, bb, ss in zip(['(切片)'] + names, b, se):
        zz = bb / ss if ss > 0 else float('nan')
        pp = 2 * (1 - normcdf(abs(zz)))
        star = ' *' if pp < 0.05 else ''
        print(f'{nm:<26}{bb:>9.4f}{ss:>14.4f}{zz:>8.2f}{pp:>9.4f}   '
              f'[{bb-1.96*ss:>7.4f},{bb+1.96*ss:>8.4f}]{star}')
    return b, se, names


def boot_race(rows, spec, B=200, seed=17):
    """レース単位ブートストラップ(レースごと丸ごと再抽出)。"""
    names, build_x = spec
    byrace = collections.defaultdict(list)
    for r in rows:
        byrace[r['race']].append(r)
    keys = list(byrace)
    rnd = random.Random(seed)
    out = []
    for _ in range(B):
        samp = []
        for _ in range(len(keys)):
            samp.extend(byrace[rnd.choice(keys)])
        try:
            X = [[1.0] + build_x(r) for r in samp]
            bb, _ = logistic_irls([x for x in X], [r['y'] for r in samp], iters=12)
            out.append(bb[1])
        except Exception:
            pass
    out.sort()
    return out[int(.025 * len(out))], out[int(.975 * len(out))], len(out)


if __name__ == '__main__':
    rows = build()
    print(f'解析対象 {len(rows)}頭 / {len(set(r["race"] for r in rows))}レース / '
          f'{len(set(r["day"] for r in rows))}開催日')
    venues = sorted({r['venue'] for r in rows})[1:]      # 基準カテゴリを1つ落とす

    A = (['調教z', 'log(人気)', '頭数', '調教→出走日数'] + [f'場:{v}' for v in venues],
         lambda r: [r['z'], math.log(r['pop']), r['field'], r['gap']]
                   + [1.0 if r['venue'] == v else 0.0 for v in venues])
    fit(rows, A, 'モデルA: 全標本・人気で統制')
    lo, hi, nb = boot_race(rows, A)
    print(f'  調教zの係数 レース単位ブートストラップ95%CI = [{lo:.4f}, {hi:.4f}]  (成功 {nb}回)')

    sub = [r for r in rows if r['odds']]
    if sub:
        vsub = sorted({r['venue'] for r in sub})[1:]
        B = (['調教z', 'log(市場推定確率)', '頭数', '調教→出走日数'] + [f'場:{v}' for v in vsub],
             lambda r: [r['z'], math.log(1.0 / r['odds']), r['field'], r['gap']]
                       + [1.0 if r['venue'] == v else 0.0 for v in vsub])
        fit(sub, B, 'モデルB: オッズがある部分標本・市場推定確率で統制')
        lo, hi, nb = boot_race(sub, B)
        print(f'  調教zの係数 レース単位ブートストラップ95%CI = [{lo:.4f}, {hi:.4f}]  (成功 {nb}回)')

    # ---------- 日付順ウォークフォワード ----------
    print('\n=== §6 日付順ウォークフォワード検証 ===')
    print('  過去の開催日だけで学習し、次の開催日を予測する。人気のみのモデルに調教zを足して改善するか。')
    days = sorted({r['day'] for r in rows})
    wf = []
    for i in range(3, len(days)):
        tr = [r for r in rows if r['day'] < days[i]]
        te = [r for r in rows if r['day'] == days[i]]
        if len(te) < 20:
            continue
        def ll(spec, tr, te):
            names, bx = spec
            Xtr = [[1.0] + bx(r) for r in tr]; ytr = [r['y'] for r in tr]
            try:
                b, _ = logistic_irls(Xtr, ytr, iters=40)
            except Exception:
                return None
            tot = 0.0
            for r in te:
                x = [1.0] + bx(r)
                z = max(-30.0, min(30.0, sum(bj*xj for bj, xj in zip(b, x))))
                pr = 1/(1+math.exp(-z))
                pr = min(max(pr, 1e-9), 1-1e-9)
                tot += math.log(pr) if r['y'] else math.log(1-pr)
            return tot/len(te)
        base = (['log(人気)', '頭数'], lambda r: [math.log(r['pop']), r['field']])
        full = (['log(人気)', '頭数', '調教z'], lambda r: [math.log(r['pop']), r['field'], r['z']])
        lb, lf = ll(base, tr, te), ll(full, tr, te)
        if lb is None or lf is None:
            continue
        wf.append(dict(test_day=days[i], n_train=len(tr), n_test=len(te),
                       logloss_base=round(-lb, 5), logloss_with_z=round(-lf, 5),
                       improvement=round(lb - lf, 5)))
        print(f"  {days[i]}  学習{len(tr):>4}頭 → 検証{len(te):>3}頭   "
              f"対数損失 人気のみ {-lb:.5f} / +調教z {-lf:.5f}   改善 {lb-lf:+.5f}")
    if wf:
        imp = [w['improvement'] for w in wf]
        better = sum(1 for v in imp if v > 0)
        print(f"\n  改善した開催日 {better}/{len(wf)}  平均改善 {sum(imp)/len(imp):+.5f}")
        print(f"  → 調教zを足しても予測が良くなる保証は無い(改善が正の日と負の日が混在)"
              if better < len(wf) else "  → 全日で改善")
        with open(f'{GH}/reports/walkforward_results.csv', 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=list(wf[0].keys())); w.writeheader(); w.writerows(wf)
        print(f'  reports/walkforward_results.csv に {len(wf)}行')
