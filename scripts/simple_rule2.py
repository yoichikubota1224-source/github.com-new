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
"""単純ルールを「事前に使える形」で通す.
穴7-12人気 × 事前先行力 × 条件(芝ダ/馬場/開幕週/当日事前TB) の3着内率。
位置取りは使わない(結果だから)。使うのは事前の先行力のみ。
"""
import csv, collections, math
SP="/tmp/claude-0/-home-user-github-com-new/84a20921-3b38-53dd-8669-b122c897a190/scratchpad"
Z=1.96
def wilson(k,n):
    if n==0: return (float('nan'),float('nan'),float('nan'))
    ph=k/n; d=1+Z*Z/n; c=(ph+Z*Z/(2*n))/d
    m=Z*math.sqrt(ph*(1-ph)/n+Z*Z/(4*n*n))/d
    return ph*100,(c-m)*100,(c+m)*100
def nb(k1,n1,k2,n2):
    def wl(k,n):
        ph=k/n; d=1+Z*Z/n; c=(ph+Z*Z/(2*n))/d
        m=Z*math.sqrt(ph*(1-ph)/n+Z*Z/(4*n*n))/d
        return (c-m,c+m)
    l1,u1=wl(k1,n1); l2,u2=wl(k2,n2); d=k1/n1-k2/n2
    return d*100,(d-math.sqrt((k1/n1-l1)**2+(u2-k2/n2)**2))*100,(d+math.sqrt((u1-k1/n1)**2+(k2/n2-l2)**2))*100
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

# 開幕週
dbv=collections.defaultdict(set)
for r in rows: dbv[r['開催場']].add(r['日付'])
def dn(d): return int(d[:4])*372+int(d[5:7])*31+int(d[8:10])
opening=set()
for v,ds in dbv.items():
    ds=sorted(ds); blocks=[]; cur=[ds[0]]
    for a,b in zip(ds,ds[1:]):
        if dn(b)-dn(a)>14: blocks.append(cur); cur=[b]
        else: cur.append(b)
    blocks.append(cur)
    for bl in blocks:
        for d in bl[:2]: opening.add((v,d))

# 当日事前TB (D_PRE_RACE) を結合
MAP={'1':'札幌','2':'函館','3':'福島','4':'新潟','5':'東京','6':'中山','7':'中京','8':'京都','9':'阪神','10':'小倉'}
pre={}
for r in csv.DictReader(open(f"{SP}/tb/TB日次バイアス_遡及1年_20250801-20260726.csv",encoding='utf-8-sig')):
    v=fl(r['D_PRE_RACE'])
    if v is None: continue
    d=r['date']; d=f"{d[:4]}-{d[4:6]}-{d[6:8]}"
    pre[(d,MAP[r['venue']],r['race'])]=(v,r['sd'])
# 芝ダ内四分位
import statistics as st
byq={}
for sd in ['芝','ダ']:
    vs=sorted(v for (v,s) in pre.values() if s==sd)
    byq[sd]=[vs[int(len(vs)*f)] for f in (0.25,0.5,0.75)]
def tbq(key):
    t=pre.get(key)
    if t is None: return None
    v,sd=t; q=byq[sd]
    return 0 if v<q[0] else 1 if v<q[1] else 2 if v<q[2] else 3

def run(name, racesel, senkou_min, lo=7, hi=12, dates=None):
    k=n=0
    for key,hs in races.items():
        if dates and not (dates[0]<=key[0]<=dates[1]): continue
        if not racesel(key,hs): continue
        for h in hs:
            p=fl(h['人気'])
            if p is None or not (lo<=p<=hi): continue
            s=senkou(h['馬名'],key[0])
            if s is None: continue
            if senkou_min is not None and s<senkou_min: continue
            try: c=int(h['着順'])
            except: continue
            n+=1
            if c<=3: k+=1
    return k,n

ALL=lambda key,hs: True
print("=== 検査E: 穴7-12人気 × 事前先行力  (位置取りは使わない) ===")
print(f"{'先行力しきい値':<16}{'3着内率':>28}")
base=None
for lbl,mn in [('しきい値なし(先行力算出可な全穴馬)',None),('≧0.40',0.40),('≧0.50',0.50),('≧0.60',0.60),('≧0.70',0.70),('≧0.80',0.80)]:
    k,n=run(lbl,ALL,mn); w=wilson(k,n)
    if base is None: base=(k,n)
    ex=""
    if mn is not None:
        d,l,h=nb(k,n,*base); ex=f"  対しきい値なし {d:+.2f}pt CI[{l:+.2f},{h:+.2f}] {'0を含まない' if (l>0 or h<0) else '0を含む'}"
    print(f"{lbl:<16}{f'{w[0]:.2f}% [{w[1]:.1f},{w[2]:.1f}] n={n}':>28}{ex}")

print("\n=== 検査F: 単純ルールの組合せ (穴7-12 × 先行力≧0.60) ===")
CONDS=[
 ('条件なし', ALL),
 ('芝', lambda k,h: h[0]['芝ダ障']=='芝'),
 ('ダート', lambda k,h: h[0]['芝ダ障']=='ダ'),
 ('ダート 良', lambda k,h: h[0]['芝ダ障']=='ダ' and h[0]['馬場状態'].strip()=='良'),
 ('ダート 稍重以上', lambda k,h: h[0]['芝ダ障']=='ダ' and h[0]['馬場状態'].strip() in ('稍重','重','不良')),
 ('ダート 重・不良', lambda k,h: h[0]['芝ダ障']=='ダ' and h[0]['馬場状態'].strip() in ('重','不良')),
 ('開幕週', lambda k,h: (k[1],k[0]) in opening),
 ('開幕週 かつ ダート', lambda k,h: (k[1],k[0]) in opening and h[0]['芝ダ障']=='ダ'),
 ('当日事前TB Q4(前有利側)', lambda k,h: tbq(k)==3),
 ('当日事前TB Q1(前不利側)', lambda k,h: tbq(k)==0),
 ('ダート かつ 当日TB Q4', lambda k,h: h[0]['芝ダ障']=='ダ' and tbq(k)==3),
 ('ダート 重・不良 かつ TB Q4', lambda k,h: h[0]['芝ダ障']=='ダ' and h[0]['馬場状態'].strip() in ('重','不良') and tbq(k)==3),
]
print(f"{'条件':<26}{'先行力≧0.60の穴':>26}{'先行力なし(全穴)':>26}{'差':>30}")
for lbl,sel in CONDS:
    k1,n1=run(lbl,sel,0.60); k0,n0=run(lbl,sel,None)
    if n1<30:
        print(f"{lbl:<26}{f'母数不足 n={n1}':>26}"); continue
    w1=wilson(k1,n1); w0=wilson(k0,n0)
    d,l,h=nb(k1,n1,k0,n0)
    print(f"{lbl:<26}{f'{w1[0]:.2f}% [{w1[1]:.1f},{w1[2]:.1f}] n={n1}':>26}"
          f"{f'{w0[0]:.2f}% [{w0[1]:.1f},{w0[2]:.1f}] n={n0}':>26}"
          f"{f'{d:+.2f}pt [{l:+.2f},{h:+.2f}]':>30}")

print("\n=== 検査G: 前後半split (先行力≧0.60の穴) ===")
mid='2026-03-01'
for lbl,sel in CONDS:
    a=run(lbl,sel,0.60,dates=('2025-09-07',mid))
    b=run(lbl,sel,0.60,dates=(mid,'2026-09-06'))
    if a[1]<25 or b[1]<25:
        print(f"  {lbl:<26} 母数不足 (前半n={a[1]}, 後半n={b[1]})"); continue
    wa=wilson(*a); wb=wilson(*b)
    print(f"  {lbl:<26} 前半 {wa[0]:6.2f}% (n={a[1]:>4})   後半 {wb[0]:6.2f}% (n={b[1]:>4})   差 {wb[0]-wa[0]:+6.2f}pt")
