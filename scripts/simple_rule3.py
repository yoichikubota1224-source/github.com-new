# -*- coding: utf-8 -*-
# 入力の所在(このリポジトリ外):
#   荒れ傾向分析_全レース全頭_20250907-20260906.csv = 受領済み「荒れ傾向分析CSV_過去1年」より
#   TB日次バイアス_遡及1年_20250801-20260726.csv    = Google Drive より自己取得 (2026-09-10)
#       SHA-256 0bb3783aed94fbd5da7cb9eb188f60fbe8ee4b3e811e40a009318460b5393f1f
#   読み取りのみ。原本を変更していない。
#
# 先行力指標の定義(リークなし):
#   各馬の「当該レース日より厳密に前」の出走のみを使い、4角(取得できた最後の通過順)で
#   前1/3に入った割合。過去3走未満はNoneとして除外し、0や推定値で埋めない。
"""希釈の原因に直接当てる: 同型(先行型)が他に何頭いるか.
先行力指標から事前に数えられる。位置取りは使わない。
"""
import csv, collections, math
SP="/tmp/claude-0/-home-user-github-com-new/84a20921-3b38-53dd-8669-b122c897a190/scratchpad"
Z=1.96
def wilson(k,n):
    if n==0: return (float('nan'),)*3
    ph=k/n; d=1+Z*Z/n; c=(ph+Z*Z/(2*n))/d
    m=Z*math.sqrt(ph*(1-ph)/n+Z*Z/(4*n*n))/d
    return ph*100,(c-m)*100,(c+m)*100
def fl(v):
    v=(v or '').strip()
    if v=='': return None
    try: return float(v)
    except: return None
rows=[r for r in csv.DictReader(open(f"{SP}/zx/c/荒れ傾向分析_全レース全頭_20250907-20260906.csv",encoding='utf-8-sig'))
      if str(r['障害フラグ']).strip() in ('0','','False','false')
      and str(r['新馬フラグ']).strip() in ('0','','False','false')]
races=collections.defaultdict(list)
for r in rows: races[(r['日付'],r['開催場'],r['R'])].append(r)
def lc(h):
    last=None
    for c in ['通過順1','通過順2','通過順3','通過順4']:
        v=fl(h[c])
        if v is not None: last=v
    return last
posmap={}
for key,hs in races.items():
    kn=[(lc(h),h) for h in hs]; kn=[(p,h) for p,h in kn if p is not None]
    if len(kn)<6: continue
    kn.sort(key=lambda t:t[0]); n=len(kn); c1=max(1,n//3); c2=max(c1+1,2*n//3)
    for i,(p,h) in enumerate(kn): posmap[id(h)]='前' if i<c1 else ('中' if i<c2 else '後')
hist=collections.defaultdict(list)
for key,hs in races.items():
    for h in hs:
        g=posmap.get(id(h))
        if g is None: continue
        hist[h['馬名']].append((key[0],1 if g=='前' else 0))
for k in hist: hist[k].sort()
def senkou(name,date):
    v=[f for (d,f) in hist.get(name,[]) if d<date]
    if len(v)<3: return None
    return sum(v)/len(v)

# レースごとに「先行力≧0.60の頭数」と「先行力を算出できた頭数」
rinfo={}
for key,hs in races.items():
    ss=[(h, senkou(h['馬名'],key[0])) for h in hs]
    known=[(h,s) for h,s in ss if s is not None]
    n60=sum(1 for h,s in known if s>=0.60)
    rinfo[key]=(n60, len(known), len(hs))
cov=[k for k,(a,b,c) in rinfo.items() if b>=c*0.6]
print(f"全レース {len(races)} / 先行力を6割以上の馬で算出できたレース {len(cov)} ({len(cov)/len(races)*100:.1f}%)")

print("\n=== 検査H: 事前先行力≧0.60 の穴馬 × 同型(自分以外の先行力≧0.60)の頭数 ===")
print("   ※先行力の算出可能率が6割以上のレースに限定(頭数の数え落ちを抑える)")
tab=collections.defaultdict(lambda:[0,0])
tab_pos=collections.defaultdict(lambda:[0,0])
for key in cov:
    hs=races[key]
    n60,nk,nh=rinfo[key]
    for h in hs:
        p=fl(h['人気']); s=senkou(h['馬名'],key[0])
        if p is None or s is None or s<0.60: continue
        if not (7<=p<=12): continue
        others=n60-1
        b='0頭' if others==0 else '1頭' if others==1 else '2頭' if others==2 else '3頭以上'
        try: c=int(h['着順'])
        except: continue
        t=tab[b]; t[1]+=1
        if c<=3: t[0]+=1
        g=posmap.get(id(h))
        if g is not None:
            u=tab_pos[b]; u[1]+=1
            if g=='前': u[0]+=1
print(f"{'同型の数':<10}{'穴7-12の3着内率':>26}{'実際に前1/3で運べた率':>28}")
for b in ['0頭','1頭','2頭','3頭以上']:
    k,n=tab[b]; w=wilson(k,n)
    k2,n2=tab_pos[b]; w2=wilson(k2,n2)
    print(f"{b:<10}{f'{w[0]:.2f}% [{w[1]:.1f},{w[2]:.1f}] n={n}':>26}{f'{w2[0]:.2f}% [{w2[1]:.1f},{w2[2]:.1f}] n={n2}':>28}")

# 前後半split
print("\n=== 前後半split ===")
mid='2026-03-01'
for lab,rng in (('前半',('2025-09-07',mid)),('後半',(mid,'2026-09-06'))):
    t=collections.defaultdict(lambda:[0,0])
    for key in cov:
        if not (rng[0]<=key[0]<=rng[1]): continue
        hs=races[key]; n60,_,_=rinfo[key]
        for h in hs:
            p=fl(h['人気']); s=senkou(h['馬名'],key[0])
            if p is None or s is None or s<0.60 or not(7<=p<=12): continue
            others=n60-1
            b='0頭' if others==0 else '1頭' if others==1 else '2頭' if others==2 else '3頭以上'
            try: c=int(h['着順'])
            except: continue
            t[b][1]+=1
            if c<=3: t[b][0]+=1
    print(f"  {lab}: " + "  ".join(f"{b}={wilson(*t[b])[0]:5.2f}%(n={t[b][1]:>3})" for b in ['0頭','1頭','2頭','3頭以上']))

# 参考: 全穴(先行力しきい値なし)での同型数別
print("\n=== 参考: 穴7-12全体(先行力しきい値なし) × レース内の先行型頭数 ===")
t=collections.defaultdict(lambda:[0,0])
for key in cov:
    hs=races[key]; n60,_,_=rinfo[key]
    b='0頭' if n60==0 else '1頭' if n60==1 else '2頭' if n60==2 else '3-4頭' if n60<=4 else '5頭以上'
    for h in hs:
        p=fl(h['人気'])
        if p is None or not(7<=p<=12): continue
        try: c=int(h['着順'])
        except: continue
        t[b][1]+=1
        if c<=3: t[b][0]+=1
for b in ['0頭','1頭','2頭','3-4頭','5頭以上']:
    k,n=t[b]; w=wilson(k,n)
    print(f"  レース内の先行型 {b:<8} 穴7-12の3着内率 {w[0]:5.2f}% [{w[1]:.1f},{w[2]:.1f}] n={n}")
