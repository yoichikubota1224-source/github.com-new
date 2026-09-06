#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""中山9R 不良馬場 再検証 v2。v1の重大な欠陥を修正:
 v1の正規表現 r'馬場:(良|稍重|重|不良)' は、当方DBの実表記「良/稍/重/不」のうち
 「稍」「不」にマッチせず、17,319R中3,457R(20.0%)を丸ごと脱落させていた。
 v2は r'馬場:([^\s/]*)' で全表記を取り、良/稍重/重/不良の4区分で集計する。"""
import json, glob, os, re, collections, math
S='/tmp/claude-0/-home-user-github-com-new/47c1892c-ddc4-50e4-8b6f-3403a9782673/scratchpad'
D='predictions/20260906'
MET=re.compile(r'(芝|ダ)(\d+)m'); BAB=re.compile(r'馬場:([^\s/]*)')
NORM={'良':'良','稍':'稍重','重':'重','不':'不良'}
CLS=[('未勝利','未勝利'),('新馬','新馬'),('１勝','1勝'),('2勝',None),('２勝','2勝'),('３勝','3勝'),('オープン','OP'),('(OP)','OP'),('(G','G')]
def klass(t):
    t=t or ''
    if '新馬' in t: return '新馬'
    if '未勝利' in t: return '未勝利'
    if '１勝' in t or '1勝' in t: return '1勝'
    if '２勝' in t or '2勝' in t: return '2勝'
    if '３勝' in t or '3勝' in t: return '3勝'
    return 'OP以上'
def c4(p):
    if not p: return None
    v=[x for x in re.split(r'[-‐−ー]',str(p)) if x.strip().isdigit()]
    return int(v[-1]) if v else None
def wil(k,n,z=1.96):
    if not n: return (None,None)
    ph=k/n; d=1+z*z/n; c=(ph+z*z/(2*n))/d; hw=z*math.sqrt(ph*(1-ph)/n+z*z/(4*n*n))/d
    return (round(100*(c-hw),1), round(100*(c+hw),1))
def fisher(a,b,c_,d):
    """2x2 両側Fisher (SciPyと同じ定義: 観測テーブル以下の確率を持つ表を合算)"""
    from math import comb
    n=a+b+c_+d; r1=a+b; r2=c_+d; c1=a+c_
    def pr(x): return comb(r1,x)*comb(r2,c1-x)/comb(n,c1)
    p0=pr(a); tot=0.0
    lo=max(0,c1-r2); hi=min(r1,c1)
    for x in range(lo,hi+1):
        px=pr(x)
        if px<=p0*(1+1e-9): tot+=px
    return min(1.0,tot)
def z2(k1,n1,k2,n2,pooled=True):
    p1,p2=k1/n1,k2/n2
    if pooled:
        p=(k1+k2)/(n1+n2); se=math.sqrt(p*(1-p)*(1/n1+1/n2))
    else:
        se=math.sqrt(p1*(1-p1)/n1+p2*(1-p2)/n2)
    z=(p1-p2)/se
    return z, 2*(1-0.5*(1+math.erf(abs(z)/math.sqrt(2))))

races=[]
for f in sorted(glob.glob(S+'/k5/full/*.json')):
    for r in json.load(open(f)):
        if r.get('jump'): continue
        m=MET.search(r.get('meta') or ''); b=BAB.search(r.get('meta') or '')
        if not m or not b: continue
        rid=str(r['race_id'])
        races.append(dict(rid=rid,date=os.path.basename(f)[:8],ba=rid[4:6],td=m.group(1),dist=int(m.group(2)),
                          baba=NORM.get(b.group(1),b.group(1)),cls=klass(r.get('title')),horses=r['horses'],title=r.get('title')))
print('平地レース総数(v2)',len(races),'  ※v1は13,368で、稍重・不良を落としていた')
NK=[r for r in races if r['ba']=='06' and r['td']=='ダ' and r['dist']==1200]
print('中山ダ1200 総数',len(NK),' 馬場別',dict(collections.Counter(r['baba'] for r in NK)))
print('  クラス別×馬場:', {k:dict(collections.Counter(r['baba'] for r in NK if r['cls']==k)) for k in ['未勝利','1勝','2勝','3勝','OP以上','新馬']})

def bucket(rs,lo,hi):
    k=n=0
    for r in rs:
        for h in r['horses']:
            p=h.get('pop'); c=h.get('chaku')
            if p and lo<=p<=hi and isinstance(c,int):
                n+=1
                if c<=3: k+=1
    return k,n
def c4b(rs,lo,hi):
    k=n=0
    for r in rs:
        for h in r['horses']:
            v=c4(h.get('passing')); c=h.get('chaku')
            if v and lo<=v<=hi and isinstance(c,int):
                n+=1
                if c<=3: k+=1
    return k,n
G=[r for r in NK if r['baba']=='良']; SO=[r for r in NK if r['baba']=='稍重']
H=[r for r in NK if r['baba']=='重']; B=[r for r in NK if r['baba']=='不良']
DOB=SO+H+B
print('\n=== 中山ダ1200 馬場4区分（[実]・v2）')
for lab,rs in [('良',G),('稍重',SO),('重',H),('不良',B),('道悪計(稍重+重+不良)',DOB)]:
    if not rs: print(f'  {lab}: 0R'); continue
    kf,nf=bucket(rs,1,1); ka,na=bucket(rs,7,12); k9,n9=bucket(rs,9,12); kc,nc=c4b(rs,1,3)
    print(f"  {lab:<22} R={len(rs):>3}  1人気3着内 {100*kf/nf:5.1f}%{wil(kf,nf)}  穴帯7-12 {100*ka/na:5.2f}%(n={na})  9-12 {100*k9/n9:5.2f}%(n={n9})  4角1-3番手 {100*kc/nc:5.1f}%(n={nc})")
print('\n=== 検定（中山ダ1200・9〜12番人気3着内） 良 vs 各区分  [実]')
kg,ng=bucket(G,9,12)
for lab,rs in [('稍重',SO),('重',H),('不良',B),('道悪計',DOB)]:
    if not rs: continue
    kh,nh=bucket(rs,9,12)
    zu,pu=z2(kh,nh,kg,ng,pooled=False); zp,pp=z2(kh,nh,kg,ng,pooled=True)
    pf=fisher(kh,nh-kh,kg,ng-kg)
    print(f"  良 {kg}/{ng}({100*kg/ng:.2f}%) vs {lab} {kh}/{nh}({100*kh/nh:.2f}%)  非プールWald p={pu:.4f} / プールz p={pp:.4f} / Fisher両側 p={pf:.4f}")
json.dump(dict(v='v2', nakayama_d1200=dict(total=len(NK), by_baba=dict(collections.Counter(r['baba'] for r in NK)))),
          open(S+'/baba_v2_summary.json','w'), ensure_ascii=False, indent=1)
