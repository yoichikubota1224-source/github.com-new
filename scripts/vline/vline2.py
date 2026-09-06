#!/usr/bin/env python3
"""Vライン条件の測定（人気で厳密に統制する）。

なぜ層別置換なのか:
  Vライン馬は人気馬に偏る。素の複勝率を比べても「人気の効果」を見ているだけになる。
  そこで**単勝人気の値そのもの**を層として、層の中でVラベルだけを入れ替える置換検定を行う。
  これにより人気の効果は帰無仮説側に完全に吸収され、「人気で説明できない上乗せ」だけが残る。
  （層別ROI検定で当方が一度誤った「頭数を無視した一様再割当」と同じ誤りを繰り返さないため）
"""
import json, glob, os, sys, math, random, collections, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vline import load, build, is_vline, band, wilson

MODE = sys.argv[2] if len(sys.argv) > 2 else 'strict'
NPERM = int(os.environ.get("NPERM","20000"))
random.seed(20260901)


def boot_ci(vals, B=4000, seed=20260901):
    """回収率は裾が重いのでWilsonではなくブートストラップで区間を出す。"""
    import random as _r
    rng = _r.Random(seed); n = len(vals)
    if n == 0: return (0.0, 0.0, 0.0)
    out = []
    for _ in range(B):
        out.append(sum(vals[rng.randrange(n)] for _ in range(n)) / n)
    out.sort()
    return (sum(vals)/n, out[int(B*0.025)], out[int(B*0.975)])

def collect(races, hist):
    """馬単位の観測を作る。人気・着順・複勝配当が揃うものだけ。"""
    rows = []
    perday = collections.Counter()
    for r in races:
        if r.get('jump') or r.get('dead_heat'): continue
        D = r['date']
        fp = r.get('pay', {}).get('複勝') or []
        nf = len(fp)
        if nf == 0: continue
        for h in r['horses']:
            hid = h.get('horse_id'); c = h.get('chaku'); pop = h.get('pop')
            if not hid or c is None or pop is None: continue
            v = is_vline(hist, hid, D)
            if v: perday[r['ymd']] += 1
            rows.append({
                'ymd': r['ymd'], 'year': int(r['ymd'][:4]), 'rid': r['race_id'],
                'ns': r.get('n_start'), 'nf': nf,
                'pop': pop, 'band': band(pop), 'chaku': c, 'v': v,
                'win': 1 if c == 1 else 0, 'p3': 1 if c <= nf else 0,
                'tan': (int(h['odds']*100) if (c == 1 and h.get('odds')) else 0),
                'fuku': (fp[c-1] if c <= nf else 0),
            })
    return rows, perday

def stat(rows, sel, key):
    n = 0; s = 0
    for i in sel:
        n += 1; s += rows[i][key]
    return (s/n if n else 0.0), n

def perm_test(rows, key, strat):
    """層内でVラベルを入れ替える置換検定。両側p。"""
    idx = collections.defaultdict(list)
    for i, r in enumerate(rows): idx[strat(r)].append(i)
    vsel = [i for i, r in enumerate(rows) if r['v']]
    nsel = [i for i, r in enumerate(rows) if not r['v']]
    obs_v, nv = stat(rows, vsel, key)
    obs_n, nn = stat(rows, nsel, key)
    obs = obs_v - obs_n
    # 層ごとのV枚数を固定して再割当
    kv = collections.Counter(strat(rows[i]) for i in vsel)
    ge = 0
    vals = {k: [rows[i][key] for i in v] for k, v in idx.items()}
    tot = {k: sum(v) for k, v in vals.items()}
    cnt = {k: len(v) for k, v in vals.items()}
    NV = sum(kv.values()); NN = len(rows) - NV
    for _ in range(NPERM):
        sv = 0
        for k, m in kv.items():
            pool = vals[k]
            sv += sum(random.sample(pool, m)) if m < len(pool) else sum(pool)
        sn = sum(tot.values()) - sv
        d = sv/NV - sn/NN
        if abs(d) >= abs(obs) - 1e-12: ge += 1
    return obs_v, nv, obs_n, nn, obs, (ge+1)/(NPERM+1)

def main():
    races = load()
    hist = build(races, MODE)
    rows, perday = collect(races, hist)
    nv = sum(r['v'] for r in rows)
    print(f'[実] 期間 {races[0]["ymd"]}〜{races[-1]["ymd"]}  レース {len({r["rid"] for r in rows})}R  '
          f'頭数 {len(rows)}  Vライン馬 {nv} ({nv/len(rows)*100:.4f}%)')
    dd = sorted(perday.values())
    if dd:
        print(f'[実] 開催日あたりのVライン馬: 平均 {sum(dd)/len(perday):.2f} 頭 '
              f'中央値 {dd[len(dd)//2]} 最大 {dd[-1]} （V馬が1頭も出ない日 '
              f'{len({r["ymd"] for r in rows}) - len(perday)} 日）')
    print(f'[実] 向こう正面の扱い: {MODE} ／ 置換回数 {NPERM}')

    for sname, sf in (('人気のみ', lambda r: r['pop']),
                      ('人気×出走頭数', lambda r: (r['pop'], r['ns']))):
        print(f'\n===== 層別置換検定 — 層＝{sname} =====')
        print(f'{"指標":<12}{"V群":>11}{"n":>7}{"非V群":>11}{"n":>8}{"差":>11}{"両側p":>9}')
        for key, lab in (('p3','複勝率'), ('win','勝率'), ('fuku','複勝回収'), ('tan','単勝回収')):
            a, na, b, nb, d, p = perm_test(rows, key, sf)
            f = (lambda x: f'{x*100:.4f}%') if key in ('p3','win') else (lambda x: f'{x:.2f}円')
            print(f'{lab:<12}{f(a):>11}{na:>7}{f(b):>11}{nb:>8}{f(d):>11}{p:>9.4f}')

    print('\n===== 人気帯別（素の観測。人気統制なし＝参考） =====')
    print(f'{"帯":<6}{"群":<4}{"n":>7}{"複勝率":>10}{"95%CI":>22}{"複勝回収":>10}{"単勝回収":>10}')
    for b in ('本命','中穴','穴','大穴'):
        for g in (True, False):
            sel = [i for i, r in enumerate(rows) if r['band'] == b and r['v'] == g]
            if not sel: continue
            k = sum(rows[i]['p3'] for i in sel); n = len(sel)
            p, lo, hi = wilson(k, n)
            fk = sum(rows[i]['fuku'] for i in sel)/n
            tk = sum(rows[i]['tan'] for i in sel)/n
            print(f'{b:<6}{"V" if g else "N":<4}{n:>7}{p*100:>9.4f}%   [{lo*100:>7.4f}%,{hi*100:>7.4f}%]'
                  f'{fk:>9.2f}%{tk:>9.2f}%')

    print('\n===== V群の回収率 ブートストラップ95%CI（B=4,000・seed固定） =====')
    print(f'{"帯":<8}{"n":>7}{"単勝回収":>11}{"95%CI":>26}{"複勝回収":>11}{"95%CI":>26}')
    for b in ('ALL','本命','中穴','穴','大穴'):
        sel = [r for r in rows if r['v'] and (b == 'ALL' or r['band'] == b)]
        if len(sel) < 5: continue
        t, tl, th = boot_ci([r['tan'] for r in sel])
        f, fl, fh = boot_ci([r['fuku'] for r in sel])
        print(f'{b:<8}{len(sel):>7}{t:>10.2f}円  [{tl:>7.2f},{th:>7.2f}]{f:>10.2f}円  [{fl:>7.2f},{fh:>7.2f}]')

    print('\n===== 年別（ウォークフォワード。人気層別の差） =====')
    print(f'{"年":<8}{"V頭数":>8}{"複勝率差":>12}{"複勝回収差":>13}')
    for y in sorted({r['year'] for r in rows}):
        sub = [r for r in rows if r['year'] == y]
        vs = [i for i, r in enumerate(sub) if r['v']]
        ns = [i for i, r in enumerate(sub) if not r['v']]
        if len(vs) < 10: 
            print(f'{y:<8}{len(vs):>8}{"[不足]":>12}{"[不足]":>13}'); continue
        a,_ = stat(sub, vs, 'p3'); b,_ = stat(sub, ns, 'p3')
        c,_ = stat(sub, vs, 'fuku'); d,_ = stat(sub, ns, 'fuku')
        print(f'{y:<8}{len(vs):>8}{(a-b)*100:>11.4f}%{c-d:>12.2f}円')

main()
