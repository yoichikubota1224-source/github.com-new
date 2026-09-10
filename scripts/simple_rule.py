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
"""単純ルールの実測検査.
検査する前提:
  A. 重・不良のダートは先行有利か
  B. 開幕週は先行有利か
  C. 午前中の傾向(当日事前TB)は使えるか  ← 既に確認済み、再掲
そして最大の欠落を埋める:
  D. 「先行できそう」を事前に決める指標 = 過去走の4角前1/3率 (当該レースより前のみ)

先行力はリークなし: 各馬の当該レース日より厳密に前の出走のみを使う。
回収率は算出しない。率と差のみ。
"""
import csv, collections, math, statistics as st
SP="/tmp/claude-0/-home-user-github-com-new/84a20921-3b38-53dd-8669-b122c897a190/scratchpad"
Z=1.96
def wilson(k,n):
    if n==0: return (float('nan'),float('nan'),float('nan'))
    ph=k/n; d=1+Z*Z/n; c=(ph+Z*Z/(2*n))/d
    m=Z*math.sqrt(ph*(1-ph)/n+Z*Z/(4*n*n))/d
    return ph*100,(c-m)*100,(c+m)*100
def fl(v):
    v=(v or '').strip()
    if v=='': return None
    try: return float(v)
    except: return None

rows=list(csv.DictReader(open(f"{SP}/zx/c/荒れ傾向分析_全レース全頭_20250907-20260906.csv",encoding='utf-8-sig')))
# 平地・非新馬
rows=[r for r in rows
      if str(r['障害フラグ']).strip() in ('0','','False','false')
      and str(r['新馬フラグ']).strip() in ('0','','False','false')]
print(f"平地・非新馬の行数 = {len(rows)}")

races=collections.defaultdict(list)
for r in rows:
    races[(r['日付'],r['開催場'],r['R'])].append(r)
print(f"レース数 = {len(races)}")

def last_corner(h):
    last=None
    for c in ['通過順1','通過順2','通過順3','通過順4']:
        v=fl(h[c])
        if v is not None: last=v
    return last

# レースごとに 前/中/後 を割り当て
posmap={}
for key,hs in races.items():
    kn=[(last_corner(h),h) for h in hs]
    kn=[(p,h) for p,h in kn if p is not None]
    if len(kn)<6: continue
    kn.sort(key=lambda t:t[0]); n=len(kn); c1=max(1,n//3); c2=max(c1+1,2*n//3)
    for i,(p,h) in enumerate(kn):
        posmap[id(h)]='前' if i<c1 else ('中' if i<c2 else '後')

# ---------- D. リークのない先行力: 過去走の前1/3率 ----------
hist=collections.defaultdict(list)   # 馬名 -> [(日付, 前1/3か)]
for key,hs in races.items():
    for h in hs:
        g=posmap.get(id(h))
        if g is None: continue
        hist[h['馬名']].append((key[0], 1 if g=='前' else 0))
for k in hist: hist[k].sort()

def senkou(name, date):
    """当該レース日より厳密に前の出走のみで前1/3率を返す。3走未満はNone"""
    v=[f for (d,f) in hist.get(name,[]) if d < date]
    if len(v)<3: return None, len(v)
    return sum(v)/len(v), len(v)

# ---------- B. 開幕週の判定 ----------
days_by_venue=collections.defaultdict(set)
for r in rows: days_by_venue[r['開催場']].add(r['日付'])
opening=set()   # (開催場, 日付) が開幕週(開催ブロックの最初2日)
for v,ds in days_by_venue.items():
    ds=sorted(ds)
    blocks=[]; cur=[ds[0]]
    for a,b in zip(ds, ds[1:]):
        gap=(int(b[:4])*372+int(b[5:7])*31+int(b[8:10])) - (int(a[:4])*372+int(a[5:7])*31+int(a[8:10]))
        if gap>14: blocks.append(cur); cur=[b]
        else: cur.append(b)
    blocks.append(cur)
    for bl in blocks:
        for d in bl[:2]: opening.add((v,d))
print(f"開催ブロックの最初2日 = {len(opening)} (場×日)")

# ---------- 検査A/B: 前1/3の3着内率 ----------
def rate(sel, gsel='前', lo=1, hi=99, need_senkou=None):
    """sel: レースキーの述語。need_senkou: (下限, ) で先行力しきい値"""
    k=n=0
    for key,hs in races.items():
        if not sel(key,hs): continue
        for h in hs:
            if gsel and posmap.get(id(h))!=gsel: continue
            p=fl(h['人気'])
            if p is None or not (lo<=p<=hi): continue
            if need_senkou is not None:
                s,_=senkou(h['馬名'], key[0])
                if s is None or s < need_senkou: continue
            try: c=int(h['着順'])
            except: continue
            n+=1
            if c<=3: k+=1
    return k,n

print("\n=== 検査A: 馬場状態×芝ダ 別  「実際に前1/3で運んだ馬」の3着内率 ===")
print(f"{'条件':<16}{'全馬':>24}{'穴7-12人気':>24}{'R数':>7}")
for sd in ['芝','ダ']:
    for cond in ['良','稍重','重','不良']:
        sel=lambda key,hs,sd=sd,cond=cond: hs[0]['芝ダ障']==sd and hs[0]['馬場状態'].strip()==cond
        nr=sum(1 for key,hs in races.items() if sel(key,hs))
        if nr<40:
            print(f"{sd}{cond:<14}{'母数不足':>24}{'':>24}{nr:>7}"); continue
        k1,n1=rate(sel); k2,n2=rate(sel,lo=7,hi=12)
        w1=wilson(k1,n1); w2=wilson(k2,n2)
        print(f"{sd+cond:<16}{f'{w1[0]:.2f}% [{w1[1]:.1f},{w1[2]:.1f}] n={n1}':>24}"
              f"{f'{w2[0]:.2f}% [{w2[1]:.1f},{w2[2]:.1f}] n={n2}':>24}{nr:>7}")

print("\n=== 検査B: 開幕週(開催ブロック初2日) vs それ以降 ===")
print(f"{'条件':<20}{'前1/3全馬':>24}{'前1/3の穴7-12':>24}{'R数':>7}")
for sd in ['芝','ダ']:
    for lbl,f in [('開幕週', True), ('それ以降', False)]:
        sel=lambda key,hs,sd=sd,f=f: hs[0]['芝ダ障']==sd and (((key[1],key[0]) in opening)==f)
        nr=sum(1 for key,hs in races.items() if sel(key,hs))
        k1,n1=rate(sel); k2,n2=rate(sel,lo=7,hi=12)
        w1=wilson(k1,n1); w2=wilson(k2,n2)
        print(f"{sd+' '+lbl:<20}{f'{w1[0]:.2f}% [{w1[1]:.1f},{w1[2]:.1f}] n={n1}':>24}"
              f"{f'{w2[0]:.2f}% [{w2[1]:.1f},{w2[2]:.1f}] n={n2}':>24}{nr:>7}")

# ---------- 検査D: 先行力(事前)は当該レースで前に行けるか ----------
print("\n=== 検査D: 事前の先行力(過去3走以上の前1/3率)は、当該レースの位置取りを当てるか ===")
buckets=collections.defaultdict(lambda:[0,0])  # 先行力帯 -> [前1/3だった数, 該当数]
for key,hs in races.items():
    for h in hs:
        g=posmap.get(id(h))
        if g is None: continue
        s,nprev=senkou(h['馬名'], key[0])
        if s is None: continue
        b = '0.00-0.20' if s<0.2 else '0.20-0.40' if s<0.4 else '0.40-0.60' if s<0.6 else '0.60-0.80' if s<0.8 else '0.80-1.00'
        t=buckets[b]; t[1]+=1
        if g=='前': t[0]+=1
print(f"{'事前の先行力':<14}{'当該レースで前1/3だった率':>30}")
for b in ['0.00-0.20','0.20-0.40','0.40-0.60','0.60-0.80','0.80-1.00']:
    k,n=buckets[b]; w=wilson(k,n)
    print(f"{b:<14}{f'{w[0]:.2f}% [{w[1]:.1f},{w[2]:.1f}] n={n}':>30}")
