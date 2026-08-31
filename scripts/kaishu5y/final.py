#!/usr/bin/env python3
"""過去5年 上位3頭の人気構成 × 3連複 — 出現率と回収率。
定義(20260823 第11報 §2 踏襲): 本命=1〜3人気 / 中穴=4〜6人気 / 穴=7人気以下。順不同。
障害除外。[不足]は0で埋めず母数から外す。
統治: SHADOW_ONLY / 印・軸・買い目の推奨は出さない。
      「全通り買い回収率」は構成の市場価格特性を測る機械的指標であり、購入推奨ではない。"""
import json, os, math, collections, statistics as st
from math import comb

def band(p): return '本命' if p<=3 else ('中穴' if p<=6 else '穴')
ORDER=['本命','中穴','穴']
def key(bs):
    c=collections.Counter(bs); return '＋'.join(sum(([b]*c[b] for b in ORDER),[]))
def wilson(k,n,z=1.96):
    if n==0: return (0.0,0.0)
    p=k/n; d=1+z*z/n; c=p+z*z/(2*n); m=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))
    return ((c-m)/d*100,(c+m)/d*100)
def sizes(ns): return {'本命':min(3,ns),'中穴':min(3,max(0,ns-3)),'穴':max(0,ns-6)}
def points(comp,ns):
    sz=sizes(ns); t=1
    for b,k in collections.Counter(comp.split('＋')).items():
        if sz[b]<k: return 0
        t*=comb(sz[b],k)
    return t

def load(d='days2'):
    R,skip=[],collections.Counter()
    for f in sorted(os.listdir(d)):
        if not f.endswith('.json'): continue
        for r in json.load(open(os.path.join(d,f))):
            if r['jump']: skip['障害']+=1; continue
            t=r['top3']
            if r.get('dead_heat') or len(t)!=3:
                skip['同着で上位3着が3頭にならない']+=1; continue
            if any(h['pop'] is None for h in t): skip['人気欠測']+=1; continue
            ns=r.get('n_start') or 0
            if ns<3: skip['出走頭数不明']+=1; continue
            p3=r['pay'].get('3連複')
            if p3 and len(p3)>1: skip['3連複が同着で複数']+=1
            if not p3: skip['3連複が未発売/欠測']+=1
            R.append(dict(day=f[:-5],rid=r['race_id'],ns=ns,
                          comp=key([band(h['pop']) for h in t]),
                          pops=sorted(h['pop'] for h in t),
                          san=p3[0] if (p3 and len(p3)==1) else None))
    return R,skip

def trim(v,k):
    v=sorted(v,reverse=True); return st.mean(v[k:]) if len(v)>k else None

if __name__=='__main__':
    R,skip=load(); N=len(R)
    days=sorted(set(r['day'] for r in R))
    print(f'■ 母集団  {N:,}R  {days[0]}〜{days[-1]}  開催{len(days)}日')
    print(f'  除外・注記: {dict(skip)}')
    # 無差別基準線: 全組合せ購入(必ず的中)
    pv=[(r['san'],comb(r['ns'],3)) for r in R if r['san'] and r['ns']>=3]
    base=sum(p for p,_ in pv)/sum(c*100 for _,c in pv)*100
    print(f'  無差別基準線(全C(n,3)組合せ購入・必ず的中): {base:.2f}%   ※JRA3連複払戻率75%は等確率時のみ到達する上限')
    print(f'  ⚠ 75%を下回るのは本命偏重(結果が上位人気に集中)による構造的なもので、異常値ではない\n')

    by=collections.defaultdict(list)
    for r in R: by[r['comp']].append(r)
    inv={c:sum(points(c,r['ns'])*100 for r in R) for c in by}
    print('■ 上位3頭の人気構成 — 全10通り')
    print(f'{"構成":<18s}{"件数":>7s}{"出現率":>8s}{"  95%CI":>15s}{"配当中央":>10s}{"配当平均":>10s}{"最大":>11s}{"全通り買い":>10s}{"平均点":>8s}')
    tab=[]
    for comp,rs in sorted(by.items(),key=lambda x:-len(x[1])):
        k=len(rs); pay=[r['san'] for r in rs if r['san']]; lo,hi=wilson(k,N)
        ret=sum(pay)/inv[comp]*100 if inv[comp] else None
        apt=st.mean([points(comp,r['ns']) for r in R])
        tab.append(dict(comp=comp,k=k,rate=k/N*100,lo=lo,hi=hi,npay=len(pay),
                        med=st.median(pay) if pay else None, mean=st.mean(pay) if pay else None,
                        mx=max(pay) if pay else None, ret=ret, apt=apt,
                        t1=trim(pay,1), t3=trim(pay,3)))
        print(f'{comp:<18s}{k:>7,}{k/N*100:>7.2f}%[{lo:>5.2f},{hi:>5.2f}]{st.median(pay):>10,.0f}'
              f'{st.mean(pay):>10,.0f}{max(pay):>11,}{ret:>9.1f}%{apt:>8.1f}')
    print(f'\n  合計 {sum(t["k"] for t in tab):,}R  出現率計 {sum(t["rate"] for t in tab):.2f}%')

    TARGET=[('穴＋穴＋本命','本命＋穴＋穴'),('穴＋中穴＋中穴','中穴＋中穴＋穴')]
    for label,comp in TARGET:
        rs=by[comp]; pay=[r['san'] for r in rs if r['san']]; k=len(rs)
        print(f'\n{"="*76}\n■ {label}（当方表記: {comp}）  n={k:,} / {N:,}R')
        lo,hi=wilson(k,N)
        print(f'  出現率 {k/N*100:.2f}%  95%CI[{lo:.2f}, {hi:.2f}]   約{N/k:.0f}レースに1回')
        q=st.quantiles(pay,n=4)
        print(f'  3連複配当: 中央値{st.median(pay):,.0f}円  平均{st.mean(pay):,.0f}円  '
              f'Q1 {q[0]:,.0f} / Q3 {q[2]:,.0f}  最大{max(pay):,}円')
        print(f'  全通り買い回収率 {sum(pay)/inv[comp]*100:.1f}%  (平均{st.mean([points(comp,r["ns"]) for r in R]):.1f}点/レース)')
        for kk in (1,3,5,10):
            s=sorted(pay,reverse=True)
            print(f'    上位{kk:>2}件の高配当を除くと {(sum(s[kk:]))/inv[comp]*100:>5.1f}%')
        print('  年次:')
        for y in sorted(set(d[:4] for d in days)):
            ry=[r for r in R if r['day'][:4]==y]; ky=[r for r in ry if r['comp']==comp]
            if not ry: continue
            py=[r['san'] for r in ky if r['san']]; iy=sum(points(comp,r['ns'])*100 for r in ry)
            l2,h2=wilson(len(ky),len(ry))
            print(f'    {y}  n={len(ry):>5,}  出現{len(ky):>4}件 {len(ky)/len(ry)*100:>5.2f}% [{l2:>4.2f},{h2:>5.2f}]  '
                  f'中央{st.median(py) if py else 0:>8,.0f}円  全通り{sum(py)/iy*100 if iy else 0:>5.1f}%')
        print('  出走頭数帯:')
        for lo_,hi_ in ((3,9),(10,12),(13,14),(15,16),(17,18)):
            rb=[r for r in R if lo_<=r['ns']<=hi_]; kb=[r for r in rb if r['comp']==comp]
            if len(rb)<50: continue
            pb=[r['san'] for r in kb if r['san']]; ib=sum(points(comp,r['ns'])*100 for r in rb)
            l3,h3=wilson(len(kb),len(rb))
            print(f'    {lo_:>2}〜{hi_:>2}頭  n={len(rb):>5,}  出現{len(kb):>4}件 {len(kb)/len(rb)*100:>5.2f}% [{l3:>4.2f},{h3:>5.2f}]  '
                  f'中央{st.median(pb) if pb else 0:>8,.0f}円  全通り{sum(pb)/ib*100 if ib else 0:>5.1f}%  {points(comp,(lo_+hi_)//2):>4d}点')
    json.dump({'N':N,'skip':dict(skip),'base':base,'table':tab,
               'period':[days[0],days[-1]],'days':len(days)},
              open('final.json','w'),ensure_ascii=False,indent=1)
