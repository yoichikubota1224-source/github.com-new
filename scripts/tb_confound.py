# -*- coding: utf-8 -*-
# 入力の所在(このリポジトリ外):
#   TB日次バイアス_遡及1年_20250801-20260726.csv  = Google Drive より自己取得 (2026-09-10)
#       SHA-256 0bb3783aed94fbd5da7cb9eb188f60fbe8ee4b3e811e40a009318460b5393f1f / 249,763 bytes / 3,308行
#   荒れ傾向分析_全レース全頭_20250907-20260906.csv / レース単位_結果払戻_20250907-20260906.csv
#       = 受領済み「荒れ傾向分析CSV_過去1年」より
#   いずれも読み取りのみ。原本を変更していない。
"""指示書§6手順3の要求: TB以外で説明できるかの点検.
候補交絡: 出走頭数 / 馬場状態 / 芝ダ / 開催場 / 距離
"""
import csv, collections, math, statistics as st
SP="/tmp/claude-0/-home-user-github-com-new/84a20921-3b38-53dd-8669-b122c897a190/scratchpad"
Z=1.96
def wilson(k,n):
    if n==0: return (float('nan'),0,0)
    ph=k/n; d=1+Z*Z/n; c=(ph+Z*Z/(2*n))/d
    m=Z*math.sqrt(ph*(1-ph)/n+Z*Z/(4*n*n))/d
    return ph*100,(c-m)*100,(c+m)*100
def fl(v):
    v=(v or '').strip()
    if v=='': return None
    try: return float(v)
    except: return None
MAP={'1':'札幌','2':'函館','3':'福島','4':'新潟','5':'東京','6':'中山','7':'中京','8':'京都','9':'阪神','10':'小倉'}
tb=list(csv.DictReader(open(f"{SP}/tb/TB日次バイアス_遡及1年_20250801-20260726.csv"  # Drive自己取得,encoding='utf-8-sig')))
uma=collections.defaultdict(list)
for r in csv.DictReader(open(f"{SP}/zx/c/荒れ傾向分析_全レース全頭_20250907-20260906.csv",encoding='utf-8-sig')):
    uma[(r['日付'].replace('-',''),r['開催場'],r['R'])].append(r)
use=[]
for r in tb:
    pre=fl(r['D_PRE_RACE'])
    if pre is None: continue
    hs=uma.get((r['date'],MAP[r['venue']],r['race']))
    if not hs: continue
    if str(hs[0]['障害フラグ']).strip() not in ('0','','False','false'): continue
    if str(hs[0]['新馬フラグ']).strip() not in ('0','','False','false'): continue
    use.append((r,pre,hs))
pres=sorted(x[1] for x in use); q=[pres[int(len(pres)*f)] for f in (0.25,0.50,0.75)]
def band(p): return 0 if p<q[0] else 1 if p<q[1] else 2 if p<q[2] else 3
BN=['Q1(前不利側)','Q2','Q3','Q4(前有利側)']
def posgroup(hs):
    pos=[]
    for h in hs:
        last=None
        for c in ['通過順1','通過順2','通過順3','通過順4']:
            v=fl(h[c])
            if v is not None: last=v
        pos.append((last,h))
    kn=[(p,h) for p,h in pos if p is not None]
    if len(kn)<6: return {}
    kn.sort(key=lambda t:t[0]); n=len(kn); c1=max(1,n//3); c2=max(c1+1,2*n//3)
    return {id(h):('前' if i<c1 else '中' if i<c2 else '後') for i,(p,h) in enumerate(kn)}

print("=== 交絡候補の分布: TB四分位ごと ===")
print(f"{'層':<14}{'R数':>6}{'平均出走頭数':>14}{'良馬場率':>10}{'芝率':>8}{'平均距離':>10}")
for b in range(4):
    rs=[x for x in use if band(x[1])==b]
    hd=[fl(x[2][0]['出走頭数']) for x in rs]; hd=[v for v in hd if v]
    good=sum(1 for x in rs if x[2][0]['馬場状態'].strip()=='良')
    shiba=sum(1 for x in rs if x[0]['sd']=='芝')
    dist=[fl(x[2][0]['距離_m']) for x in rs]; dist=[v for v in dist if v]
    print(f"{BN[b]:<14}{len(rs):>6}{st.mean(hd):>14.2f}{good/len(rs)*100:>9.1f}%{shiba/len(rs)*100:>7.1f}%{st.mean(dist):>10.0f}")

def cross(sub, lo, hi, gsel):
    out=[]
    for b in range(4):
        k=n=0
        for (r,pre,hs) in sub:
            if band(pre)!=b: continue
            pg=posgroup(hs)
            if not pg: continue
            for h in hs:
                if pg.get(id(h))!=gsel: continue
                p=fl(h['人気'])
                if p is None or not (lo<=p<=hi): continue
                try: c=int(h['着順'])
                except: continue
                n+=1
                if c<=3: k+=1
        out.append((k,n))
    return out

def show(title, sub):
    if len(sub)<80:
        print(f"  {title:<26} R={len(sub):>5}  → 母数不足のため出力しない")
        return
    f=cross(sub,7,12,'前'); r=cross(sub,7,12,'後')
    fs=" ".join(f"{BN[i][:2]}={wilson(*f[i])[0]:5.2f}%(n={f[i][1]:>4})" for i in range(4))
    mono = all(f[i][1] and f[i+1][1] and f[i][0]/f[i][1] <= f[i+1][0]/f[i+1][1]+1e-12 for i in range(3))
    gaps=[]
    for i in range(4):
        if f[i][1] and r[i][1]: gaps.append(f[i][0]/f[i][1]*100 - r[i][0]/r[i][1]*100)
        else: gaps.append(float('nan'))
    gmono = all(gaps[i] <= gaps[i+1]+1e-12 for i in range(3))
    print(f"  {title:<26} R={len(sub):>5}  {fs}")
    print(f"  {'':<26}   差(前-後)= " + " ".join(f"{g:+6.2f}pt" for g in gaps)
          + f"   前1/3単調={'YES' if mono else 'no'} 差単調={'YES' if gmono else 'no'}")

print("\n=== 検査F: 穴7-12人気×前1/3 の3着内率 — 交絡を固定しても単調か ===")
show("全体", use)
print()
for cond in ['良','稍重','重','不良']:
    show(f"馬場状態={cond}", [x for x in use if x[2][0]['馬場状態'].strip()==cond])
print()
for sd in ['芝','ダ']:
    show(f"芝ダ={sd}", [x for x in use if x[0]['sd']==sd])
print()
for lo,hi,lbl in [(5,11,'出走頭数 5-11'),(12,14,'出走頭数 12-14'),(15,18,'出走頭数 15-18')]:
    show(lbl, [x for x in use if (fl(x[2][0]['出走頭数']) or 0)>=lo and (fl(x[2][0]['出走頭数']) or 0)<=hi])
print()
for lo,hi,lbl in [(0,1400,'距離 -1400m'),(1401,1800,'距離 1401-1800m'),(1801,9999,'距離 1801m-')]:
    show(lbl, [x for x in use if lo<=(fl(x[2][0]['距離_m']) or 0)<=hi])
