#!/usr/bin/env python3
"""過去5年 上位3着の人気構成 × 3連複 — 【正本4帯】版。
定義出典: Obsidian『穴馬抽出マニュアル_7-12番人気_次走期待好走馬_Claude依頼用_v1.0_20260818』§2.1
  本命 = 確定 1〜3番人気
  中穴 = 確定 4〜6番人気
  穴   = 確定 7〜12番人気        ← 上限あり(12)。第12報の「7以下・青天井」は誤り
  大穴 = 確定 13番人気以下        ← マニュアルは「対象外・別集計」。本報では独立の帯として集計
帯サイズ(EXPECTED_COUNT の考え方を踏襲):
  本命 min(3, ns) / 中穴 min(3, max(0, ns-3))
  穴   max(0, min(ns,12) - 6)    ← 12頭未満なら7番人気〜最下位まで
  大穴 max(0, ns - 12)
障害除外。[不足]は0で埋めない。統治: 印・軸・買い目の推奨は出さない。"""
import json, os, math, collections, statistics as st
from math import comb

BANDS = ['本命', '中穴', '穴', '大穴']
def band(p):
    if p <= 3:  return '本命'
    if p <= 6:  return '中穴'
    if p <= 12: return '穴'
    return '大穴'
def key(bs):
    c = collections.Counter(bs)
    return '＋'.join(sum(([b]*c[b] for b in BANDS), []))
def sizes(ns):
    return {'本命': min(3, ns), '中穴': min(3, max(0, ns-3)),
            '穴': max(0, min(ns, 12) - 6), '大穴': max(0, ns - 12)}
def points(comp, ns):
    sz = sizes(ns); t = 1
    for b, k in collections.Counter(comp.split('＋')).items():
        if sz[b] < k: return 0
        t *= comb(sz[b], k)
    return t
def wilson(k, n, z=1.96):
    if n == 0: return (0.0, 0.0)
    p = k/n; d = 1+z*z/n; c = p+z*z/(2*n); m = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))
    return ((c-m)/d*100, (c+m)/d*100)

def load(d='days2'):
    R, skip = [], collections.Counter()
    for f in sorted(os.listdir(d)):
        if not f.endswith('.json'): continue
        for r in json.load(open(os.path.join(d, f))):
            if r['jump']: skip['障害'] += 1; continue
            t = r['top3']
            if r.get('dead_heat') or len(t) != 3:
                skip['同着で上位3着が3頭にならない'] += 1; continue
            if any(h['pop'] is None for h in t): skip['人気欠測'] += 1; continue
            ns = r.get('n_start') or 0
            if ns < 3: skip['出走頭数不明'] += 1; continue
            p3 = r['pay'].get('3連複')
            if not p3: skip['3連複が未発売/欠測'] += 1
            R.append(dict(day=f[:-5], rid=r['race_id'], ns=ns,
                          comp=key([band(h['pop']) for h in t]),
                          pops=sorted(h['pop'] for h in t),
                          san=p3[0] if (p3 and len(p3) == 1) else None))
    return R, skip

if __name__ == '__main__':
    R, skip = load(); N = len(R)
    days = sorted(set(r['day'] for r in R))
    print(f'■ 母集団 {N:,}R  {days[0]}〜{days[-1]}  開催{len(days)}日   除外:{dict(skip)}')
    # 健全性: 20構成の点数合計 = C(ns,3)
    allc = sorted({key(list(c)) for c in
                   __import__('itertools').combinations_with_replacement(BANDS, 3)})
    bad = sum(1 for r in R if sum(points(c, r['ns']) for c in allc) != comb(r['ns'], 3))
    print(f'  点数式の健全性: Σ(全{len(allc)}構成の点数)=C(n,3) の不一致 {bad}件')
    pv = [(r['san'], comb(r['ns'], 3)) for r in R if r['san']]
    base = sum(p for p, _ in pv)/sum(c*100 for _, c in pv)*100
    print(f'  無差別基準線(全C(n,3)組合せ購入) {base:.2f}%\n')
    by = collections.defaultdict(list)
    for r in R: by[r['comp']].append(r)
    inv = {c: sum(points(c, r['ns'])*100 for r in R) for c in allc}
    print(f'{"構成":<22s}{"件数":>7s}{"出現率":>8s}{"  95%CI":>16s}{"配当中央":>10s}{"配当平均":>11s}{"全通り":>8s}{"平均点":>8s}')
    rows = []
    for c in sorted(allc, key=lambda c: -len(by.get(c, []))):
        rs = by.get(c, []); k = len(rs)
        pay = [r['san'] for r in rs if r['san']]
        lo, hi = wilson(k, N)
        ret = sum(pay)/inv[c]*100 if inv[c] and pay else None
        apt = st.mean([points(c, r['ns']) for r in R])
        rows.append((c, k, k/N*100, lo, hi, st.median(pay) if pay else None,
                     st.mean(pay) if pay else None, max(pay) if pay else None, ret, apt, len(pay)))
        print(f'{c:<22s}{k:>7,}{k/N*100:>7.2f}%[{lo:>5.2f},{hi:>5.2f}]'
              f'{(st.median(pay) if pay else 0):>10,.0f}{(st.mean(pay) if pay else 0):>11,.0f}'
              f'{(f"{ret:.1f}%" if ret else "-"):>8s}{apt:>8.1f}')
    print(f'\n  合計 {sum(r[1] for r in rows):,}R  出現率計 {sum(r[2] for r in rows):.2f}%')
    json.dump({'N': N, 'base': base, 'rows': rows, 'skip': dict(skip),
               'period': [days[0], days[-1]], 'days': len(days)},
              open('final4.json', 'w'), ensure_ascii=False, indent=1)
