#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""8/29・8/30・9/5・9/6 を確定人気で統一して再計算する（定義混成の解消）。
荒れ = 1着の確定人気>=5 または 上位3頭の確定人気合計>=18
hit7_12 = 確定7〜12番人気が3着内
"""
import json, os, math, collections
def L(p):
    try: return json.load(open(p,encoding='utf-8'))
    except Exception: return None
def wil(k,n,z=1.96):
    if not n: return (None,None)
    ph=k/n; d=1+z*z/n; c=(ph+z*z/(2*n))/d; hw=z*math.sqrt(ph*(1-ph)/n+z*z/(4*n*n))/d
    return (round(100*(c-hw),1), round(100*(c+hw),1))
def pk(t6): return 'P1' if t6<=205 else 'P2' if t6<=208 else 'P3' if t6<=211 else 'P4' if t6<=215 else 'P5' if t6<=219 else 'P6'
DAYS=['20260829','20260830','20260905','20260906']
OUT={}
for d in DAYS:
    res=L(f'predictions/{d}/results_{d}.json')
    tk=None
    for fn in (f'最終統合_{d}.json', f'toukei_{d}.json'):
        o=L(f'predictions/{d}/{fn}')
        if o: tk=o['races'] if isinstance(o,dict) and 'races' in o else o; break
    if not res or not tk: OUT[d]=dict(err='data missing'); continue
    # race index
    RES={}
    for rc in res:
        for k in (rc.get('race_id'), rc.get('racekey')):
            if k: RES[str(k)]=rc
    rows=[]
    for t in tk:
        rid=str(t.get('race_id') or t.get('racekey')); rc=RES.get(rid)
        if not rc: continue
        for h in rc['horses']:
            if 'chaku' not in h and 'chakujun' in h:
                try: h['chaku']=int(h['chakujun'])
                except (TypeError,ValueError): h['chaku']=None
        hs=[h for h in rc['horses'] if isinstance(h.get('chaku'),int)]
        if not hs: continue
        w=[h for h in hs if h['chaku']==1]
        t3=sorted(hs,key=lambda x:x['chaku'])[:3]
        pops=[h.get('pop') for h in t3 if h.get('pop')]
        if not w or not w[0].get('pop') or len(pops)<3: continue
        haran = (w[0]['pop']>=5) or (sum(pops)>=18)
        hit = any(h.get('pop') and 7<=h['pop']<=12 for h in t3)
        cs=sorted([x['compi'] for x in t.get('horses',[]) if x.get('compi') is not None],reverse=True)
        c1=cs[0] if cs else None; t6=sum(cs[:3]) if len(cs)>=3 else None
        p=pk(t6) if t6 else None
        v21=t.get('v21') or t.get('v21_audit') or {}
        one=None
        if isinstance(v21,dict):
            for kk in ('ONE_HOLE','one_hole','ONE','one'):
                if v21.get(kk) is not None:
                    try: one=float(v21[kk])
                    except (TypeError,ValueError): pass
                    break
        rows.append(dict(rid=rid,ba=t.get('ba'),r=t.get('r'),c1=c1,t6=t6,p=p,one=one,
                         ryo=bool(c1 and t6 and c1<=76 and p in ('P1','P2','P3')),haran=haran,hit=hit))
    def agg(sel,label):
        v=[x for x in rows if sel(x)]
        if not v: return dict(label=label,n=0)
        hk=sum(1 for x in v if x['hit']); hr=sum(1 for x in v if x['haran'])
        return dict(label=label,n=len(v),hit=hk,hit_rate=round(100*hk/len(v),1),hit_ci=wil(hk,len(v)),
                    haran=hr,haran_rate=round(100*hr/len(v),1))
    OUT[d]=dict(n_race=len(rows),
        ALL=agg(lambda x:True,'全R'),
        ryoritsu=agg(lambda x:x['ryo'],'両立(c1<=76∧P1-P3)'),
        P1_P3=agg(lambda x:x['p'] in ('P1','P2','P3'),'P1-P3'),
        P4_P6=agg(lambda x:x['p'] in ('P4','P5','P6'),'P4-P6'),
        ONE_ge63=agg(lambda x:x.get('one') is not None and x['one']>=63,'v21 ONE>=63'),
        ONE_lt63=agg(lambda x:x.get('one') is not None and x['one']<63,'v21 ONE<63'),
        c1_le76=agg(lambda x:x['c1'] is not None and x['c1']<=76,'c1<=76のみ'),
        P1P3only=agg(lambda x:x['p'] in ('P1','P2','P3'),'P1-P3のみ'),
        rows=rows)
print('=== 確定人気で統一した4日比較 [実]')
print(f"{'日':<10} {'R':>3} | {'全R hit7-12':<22} | {'両立 hit7-12':<24} | {'荒れ率(全R)':<10}")
tot_h=tot_n=0; ryo_h=ryo_n=0
for d in DAYS:
    o=OUT[d]
    if 'err' in o: print(d,'データ不足'); continue
    a=o['ALL']; ry=o['ryoritsu']
    tot_h+=a['hit']; tot_n+=a['n']; ryo_h+=ry.get('hit',0); ryo_n+=ry.get('n',0)
    print(f"{d:<10} {a['n']:>3} | {a['hit']}/{a['n']} = {a['hit_rate']:>5}% {str(a['hit_ci']):<14} | {ry.get('hit','-')}/{ry.get('n','-')} = {str(ry.get('hit_rate','-')):>5}% {str(ry.get('hit_ci','')):<14} | {a['haran_rate']}%")
print(f"{'通算':<10} {tot_n:>3} | {tot_h}/{tot_n} = {round(100*tot_h/tot_n,1)}% {wil(tot_h,tot_n)} | {ryo_h}/{ryo_n} = {round(100*ryo_h/ryo_n,1)}% {wil(ryo_h,ryo_n)}")
d=round(100*ryo_h/ryo_n,1)-round(100*tot_h/tot_n,1)
print(f"\n通算で 両立 − 全R = {d:+.1f}pt")
print()
print('=== 他の選別軸（確定人気で統一・4日通算） [実]')
for key,lab in [('ALL','全R(基準)'),('ryoritsu','両立 c1<=76∧P1-P3'),('c1_le76','c1<=76のみ'),('P1P3only','P1-P3のみ'),('ONE_ge63','v21監査 ONE>=63'),('ONE_lt63','v21監査 ONE<63')]:
    h=n=0; hr=0
    for d in DAYS:
        o=OUT[d].get(key)
        if o and o.get('n'): h+=o['hit']; n+=o['n']; hr+=o['haran']
    if n: print(f"  {lab:<24} {h}/{n} = {round(100*h/n,1):>5}% {wil(h,n)}   荒れ率{round(100*hr/n,1)}%")
json.dump({k:{kk:vv for kk,vv in v.items() if kk!='rows'} for k,v in OUT.items()},
          open('predictions/20260906/横断_確定人気統一_20260906.json','w'),ensure_ascii=False,indent=1)
