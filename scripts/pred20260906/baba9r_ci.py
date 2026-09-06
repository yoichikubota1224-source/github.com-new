#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, glob, os, re, collections, math
S='/tmp/claude-0/-home-user-github-com-new/47c1892c-ddc4-50e4-8b6f-3403a9782673/scratchpad'
D='predictions/20260906'
MET=re.compile(r'(芝|ダ)(\d+)m'); BAB=re.compile(r'馬場:(良|稍重|重|不良)')
def c4(p):
    if not p: return None
    v=[x for x in re.split(r'[-‐−ー]',str(p)) if x.strip().isdigit()]
    return int(v[-1]) if v else None
def wil(k,n,z=1.96):
    if not n: return (None,None)
    ph=k/n; d=1+z*z/n; c=(ph+z*z/(2*n))/d; hw=z*math.sqrt(ph*(1-ph)/n+z*z/(4*n*n))/d
    return (round(100*(c-hw),1), round(100*(c+hw),1))
def diffci(k1,n1,k2,n2,z=1.96):
    p1,p2=k1/n1,k2/n2; d=p1-p2
    se=math.sqrt(p1*(1-p1)/n1+p2*(1-p2)/n2)
    return round(100*d,1), (round(100*(d-z*se),1), round(100*(d+z*se),1))

races=[]
for f in sorted(glob.glob(S+'/k5/full/*.json')):
    for r in json.load(open(f)):
        if r.get('jump'): continue
        m=MET.search(r.get('meta') or ''); b=BAB.search(r.get('meta') or '')
        if not m or not b: continue
        rid=str(r['race_id'])
        races.append(dict(rid=rid, date=os.path.basename(f)[:8], ba=rid[4:6], td=m.group(1), dist=int(m.group(2)), baba=b.group(1), horses=r['horses']))
NK=[r for r in races if r['ba']=='06' and r['td']=='ダ' and r['dist']==1200]
G=[r for r in NK if r['baba']=='良']; H=[r for r in NK if r['baba'] in ('重','不良')]
def bucket(rs, lo, hi):
    k=n=0
    for r in rs:
        for h in r['horses']:
            p=h.get('pop'); c=h.get('chaku')
            if p and lo<=p<=hi and isinstance(c,int):
                n+=1
                if c<=3: k+=1
    return k,n
def c4b(rs, lo, hi):
    k=n=0
    for r in rs:
        for h in r['horses']:
            v=c4(h.get('passing')); c=h.get('chaku')
            if v and lo<=v<=hi and isinstance(c,int):
                n+=1
                if c<=3: k+=1
    return k,n
def l3b(rs):
    k=n=0
    for r in rs:
        hs=[h for h in r['horses'] if h.get('last3f') and isinstance(h.get('chaku'),int)]
        if not hs: continue
        mn=min(h['last3f'] for h in hs)
        for h in hs:
            if h['last3f']==mn:
                n+=1
                if h['chaku']<=3: k+=1
    return k,n
print('=== 中山ダ1200 良(%d R) vs 重・不良(%d R)  差と95%%CI [実]'%(len(G),len(H)))
for lab,(kg,ng),(kh,nh) in [
  ('1番人気3着内', bucket(G,1,1), bucket(H,1,1)),
  ('2-3番人気3着内', bucket(G,2,3), bucket(H,2,3)),
  ('4-6番人気3着内', bucket(G,4,6), bucket(H,4,6)),
  ('穴帯7-12番人気3着内', bucket(G,7,12), bucket(H,7,12)),
  ('うち7-8番人気', bucket(G,7,8), bucket(H,7,8)),
  ('うち9-12番人気', bucket(G,9,12), bucket(H,9,12)),
  ('13番人気以下', bucket(G,13,18), bucket(H,13,18)),
  ('4角1-3番手3着内', c4b(G,1,3), c4b(H,1,3)),
  ('4角4-8番手3着内', c4b(G,4,8), c4b(H,4,8)),
  ('4角9番手以降3着内', c4b(G,9,18), c4b(H,9,18)),
  ('上がり最速の3着内', l3b(G), l3b(H)),
]:
    d,ci=diffci(kh,nh,kg,ng)
    sig='**有意**' if (ci[0]>0 or ci[1]<0) else '有意でない'
    print(f"  {lab:<22} 良 {100*kg/ng:5.1f}% (n={ng:>5})  重 {100*kh/nh:5.1f}% (n={nh:>4}) {wil(kh,nh)}  差 {d:+5.1f}pt CI[{ci[0]:+.1f},{ci[1]:+.1f}] {sig}")

# 同一条件(中山ダ1200・重/不良)の各馬実績
T={(r['ba'],r['r']):r for r in json.load(open(os.path.join(D,'toukei_20260906.json')))['races']}
_s=json.load(open(os.path.join(D,'shutuba_20260906.json'))); SH={(r['ba'],r['r']):r for r in (_s['races'] if isinstance(_s,dict) else _s)}
rc=T[('中山',9)]; hid={h['uma']:h.get('horse_id') for h in SH[('中山',9)]['horses']}
same=collections.defaultdict(list)
for r in H:
    for h in r['horses']:
        if h.get('horse_id'): same[h['horse_id']].append((r['date'],h.get('chaku'),h.get('pop'),c4(h.get('passing'))))
print('\n=== 中山ダ1200・重/不良の同一条件実績 [実]')
for h in sorted(rc['horses'], key=lambda x:x['kijun_ninki']):
    v=same.get(hid.get(h['uma']),[])
    if v: print(f"  {h['uma']:>2} {h['name']}({h['kijun_ninki']}人気): " + ' / '.join(f"{d[:4]}/{d[4:6]}/{d[6:]} {c}着({p}人)4角{k}" for d,c,p,k in sorted(v,reverse=True)))
print('  ※上記以外の馬は中山ダ1200・重の走歴なし＝[不足]')

print('\n=== 頑健性: より大きい標本で再現するか [実]')
def z_of(k1,n1,k2,n2):
    p1,p2=k1/n1,k2/n2
    se=math.sqrt(p1*(1-p1)/n1+p2*(1-p2)/n2)
    return (p1-p2)/se, se
DS=[r for r in races if r['td']=='ダ' and 1000<=r['dist']<=1400]
DG=[r for r in DS if r['baba']=='良']; DH=[r for r in DS if r['baba'] in ('重','不良')]
DA=[r for r in races if r['td']=='ダ']
AG=[r for r in DA if r['baba']=='良']; AH=[r for r in DA if r['baba'] in ('重','不良')]
tests=[('中山ダ1200', G,H), ('全場ダ1000-1400', DG,DH), ('全場ダート全距離', AG,AH)]
for lab,g,h in tests:
    kg,ng=bucket(g,9,12); kh,nh=bucket(h,9,12)
    z,se=z_of(kh,nh,kg,ng); d=100*(kh/nh-kg/ng)
    p=2*(1-0.5*(1+math.erf(abs(z)/math.sqrt(2))))
    print(f"  9-12番人気3着内  {lab:<16} 良 {100*kg/ng:5.2f}%(n={ng:>5}) 重 {100*kh/nh:5.2f}%(n={nh:>5}) 差{d:+5.2f}pt z={z:+.2f} p={p:.4f}")
    kg,ng=l3b(g); kh,nh=l3b(h)
    z,se=z_of(kh,nh,kg,ng); d=100*(kh/nh-kg/ng)
    p=2*(1-0.5*(1+math.erf(abs(z)/math.sqrt(2))))
    print(f"  上がり最速3着内  {lab:<16} 良 {100*kg/ng:5.2f}%(n={ng:>5}) 重 {100*kh/nh:5.2f}%(n={nh:>5}) 差{d:+5.2f}pt z={z:+.2f} p={p:.4f}")
print('  ※中山ダ1200での11比較のうち有意2件。Bonferroni補正の閾値は α=0.05/11=0.0045')
