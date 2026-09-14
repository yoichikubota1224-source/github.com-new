# -*- coding: utf-8 -*-
# 入力の所在(このリポジトリ外):
#   TB日次バイアス_遡及1年_20250801-20260726.csv  = Google Drive より自己取得 (2026-09-10)
#       SHA-256 0bb3783aed94fbd5da7cb9eb188f60fbe8ee4b3e811e40a009318460b5393f1f / 249,763 bytes / 3,308行
#   荒れ傾向分析_全レース全頭_20250907-20260906.csv / レース単位_結果払戻_20250907-20260906.csv
#       = 受領済み「荒れ傾向分析CSV_過去1年」より
#   いずれも読み取りのみ。原本を変更していない。
"""期待値のクロス: 当日事前TB × 人気帯 × 実際の位置取り.

注意: 通過順は結果である。事前の選別条件ではない。
      本検査は「機構の確認」であり、そのまま事前フィルタにはできない。
      事前化には先行力の推定(展開係の担当)が必要 → 不足として明記する。
"""
import csv, collections, math, statistics as st
SP="/tmp/claude-0/-home-user-github-com-new/84a20921-3b38-53dd-8669-b122c897a190/scratchpad"
Z=1.96
def wilson(k,n):
    if n==0: return (0.0,0.0,0.0,0)
    ph=k/n; d=1+Z*Z/n; c=(ph+Z*Z/(2*n))/d
    m=Z*math.sqrt(ph*(1-ph)/n+Z*Z/(4*n*n))/d
    return ph*100,(c-m)*100,(c+m)*100,n
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
    k=(r['date'],MAP[r['venue']],r['race'])
    hs=uma.get(k)
    if not hs: continue
    if str(hs[0]['障害フラグ']).strip() not in ('0','','False','false'): continue
    if str(hs[0]['新馬フラグ']).strip() not in ('0','','False','false'): continue
    use.append((r,pre,hs))

pres=sorted(x[1] for x in use)
q=[pres[int(len(pres)*f)] for f in (0.25,0.50,0.75)]
def band(p):
    return 'Q1(前不利側)' if p<q[0] else 'Q2' if p<q[1] else 'Q3' if p<q[2] else 'Q4(前有利側)'

def posgroup(hs):
    """各馬に 前/中/後 の3分位を割り当てる(4角=最終取得可能な通過順)"""
    pos=[]
    for h in hs:
        last=None
        for c in ['通過順1','通過順2','通過順3','通過順4']:
            v=fl(h[c])
            if v is not None: last=v
        pos.append((last,h))
    known=[(p,h) for p,h in pos if p is not None]
    if len(known)<6: return {}
    known.sort(key=lambda t:t[0])
    n=len(known); c1=max(1,n//3); c2=max(c1+1,2*n//3)
    out={}
    for i,(p,h) in enumerate(known):
        out[id(h)] = '前' if i<c1 else ('中' if i<c2 else '後')
    return out

print("=== 検査D: 期待値のクロス  当日事前TB × 人気帯 × 4角位置 の3着内率 ===")
print("   (平地・非新馬。通過順は結果であり事前条件ではない)\n")
BANDS=['Q1(前不利側)','Q2','Q3','Q4(前有利側)']
POPS=[('本命 1-3人気',1,3),('中穴 4-6人気',4,6),('穴 7-12人気',7,12)]
tab=collections.defaultdict(lambda:[0,0])
for (r,pre,hs) in use:
    b=band(pre); pg=posgroup(hs)
    if not pg: continue
    for h in hs:
        g=pg.get(id(h))
        if g is None: continue
        p=fl(h['人気'])
        if p is None: continue
        try: c=int(h['着順'])
        except: continue
        for lbl,lo,hi in POPS:
            if lo<=p<=hi:
                t=tab[(b,lbl,g)]; t[1]+=1
                if c<=3: t[0]+=1
for lbl,lo,hi in POPS:
    print(f"--- {lbl} ---")
    print(f"   {'':<14}{'前(4角上位1/3)':>28}{'中':>28}{'後(4角下位1/3)':>28}")
    for b in BANDS:
        cells=[]
        for g in ['前','中','後']:
            k,n=tab[(b,lbl,g)]
            w=wilson(k,n)
            cells.append(f"{w[0]:.2f}% [{w[1]:.1f},{w[2]:.1f}] n={n}")
        print(f"   {b:<14}{cells[0]:>28}{cells[1]:>28}{cells[2]:>28}")
    # 前-後 差
    print(f"   {'差(前-後)':<14}", end='')
    for b in BANDS:
        k1,n1=tab[(b,lbl,'前')]; k2,n2=tab[(b,lbl,'後')]
        if n1 and n2:
            print(f"  {b}: {k1/n1*100-k2/n2*100:+.2f}pt", end='')
    print("\n")

# ---- 穴帯の「前」に絞った層別の単調性 + 前後半split ----
print("=== 検査E: 穴7-12人気 かつ 4角前1/3 の3着内率 (単調性と安定性) ===")
use_s=sorted(use,key=lambda x:x[0]['date'])
half=len(use_s)//2
for label,sub in (('全期間',use_s),('前半',use_s[:half]),('後半',use_s[half:])):
    line=[]
    for b in BANDS:
        k=n=0
        for (r,pre,hs) in sub:
            if band(pre)!=b: continue
            pg=posgroup(hs)
            if not pg: continue
            for h in hs:
                if pg.get(id(h))!='前': continue
                p=fl(h['人気'])
                if p is None or not (7<=p<=12): continue
                try: c=int(h['着順'])
                except: continue
                n+=1
                if c<=3: k+=1
        w=wilson(k,n)
        line.append(f"{b}={w[0]:.2f}% (n={n})")
    print(f"  {label:<6} " + "  ".join(line))

# ---- Newcombe: Q4前 vs Q1前 (穴帯) ----
def nb(k1,n1,k2,n2):
    def wl(k,n):
        ph=k/n; d=1+Z*Z/n; c=(ph+Z*Z/(2*n))/d
        m=Z*math.sqrt(ph*(1-ph)/n+Z*Z/(4*n*n))/d
        return (c-m,c+m)
    l1,u1=wl(k1,n1); l2,u2=wl(k2,n2)
    d=k1/n1-k2/n2
    lo=d-math.sqrt((k1/n1-l1)**2+(u2-k2/n2)**2)
    hi=d+math.sqrt((u1-k1/n1)**2+(k2/n2-l2)**2)
    return d*100,lo*100,hi*100
for lbl,lo_,hi_ in POPS:
    k4,n4=tab[('Q4(前有利側)',lbl,'前')]; k1_,n1_=tab[('Q1(前不利側)',lbl,'前')]
    if n4 and n1_:
        d,l,h=nb(k4,n4,k1_,n1_)
        sig = "0を含まない" if (l>0 or h<0) else "0を含む"
        print(f"\n  {lbl} 前1/3: Q4-Q1 差 = {d:+.2f}pt  Newcombe 95%CI [{l:+.2f}, {h:+.2f}]pt → {sig}")
