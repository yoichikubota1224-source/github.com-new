# -*- coding: utf-8 -*-
# 入力の所在(このリポジトリ外):
#   競馬場コース事典2_コース構造_101.csv (zip: 33,424 bytes /
#     SHA-256 5ccd9d8b9eaea8878dde4075d6221976068d65ed043f12cba81992116eb366e1)
#     = 2026-09-10 に添付受領。2026-09-09 の受領確認と8ファイルすべてハッシュ一致。
#   荒れ傾向分析_全レース全頭_20250907-20260906.csv = 受領済み「荒れ傾向分析CSV_過去1年」より
#   読み取りのみ。原本を変更していない。
#
# コース事典の統治(CSV自身が明示):
#   source_role=BOOK_REFERENCE_STATIC 101/101
#   governance_status=REFERENCE_STATIC_ONLY_DIRECT_BUY_USE_PROHIBITED 101/101
#   jra_official_course_verified=NO 101/101
#   geometry_source_status=EXISTING_COURSEMASTER_CANDIDATE 98/101 (出所不明)
#   start_to_first_corner_m は数値0/101で完全欠測 → この列に依存する評価は行わない
# したがって本スクリプトは、前有利度をレースデータから実測し、
# コース事典は構造ラベル(直線長等)の供給にのみ使う。事典の値を正しいものとして扱わない。
"""コース(直線長)を事前条件として、先行型の穴馬が絞れるかの検査.
直線長は事前に既知。先行力は当該レースより前の走りのみ。位置取り(結果)は使わない。
"""
import csv, collections, math, statistics as st
SP="/tmp/claude-0/-home-user-github-com-new/84a20921-3b38-53dd-8669-b122c897a190/scratchpad"
Z=1.96
def wilson(k,n):
    if n==0: return (float('nan'),)*3
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

# 事典: 直線長。重複キー(内/外回り)は最短側を採らず「不定」として除外する
CD=collections.defaultdict(list)
for r in csv.DictReader(open(f"{SP}/course3/x/競馬場コース事典2_コース構造_101.csv",encoding='utf-8-sig')):
    sd='芝' if r['surface'].strip()=='turf' else 'ダ'
    CD[(r['track'].strip(),sd,int(float(r['distance_m'])))].append(r)
AMB={k for k,v in CD.items() if len(v)>1}
def straight(k):
    if k in AMB: return None          # 内回り/外回りを判別できない → 未取得として扱う
    v=CD.get(k)
    return fl(v[0]['straight_length_m']) if v else None

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

def ckey(hs,key):
    d=fl(hs[0]['距離_m']); sd=hs[0]['芝ダ障'].strip()
    if d is None or sd not in ('芝','ダ'): return None
    return (key[1],sd,int(d))

# 直線長の帯
allS=[]
for key,hs in races.items():
    ck=ckey(hs,key)
    if ck is None: continue
    s=straight(ck)
    if s is not None: allS.append(s)
print(f"直線長が判定できたレース = {len(allS)} / {len(races)} ({len(allS)/len(races)*100:.1f}%)")
print(f"  内回り/外回りを判別できず除外したコースキー = {len(AMB)}件 {sorted(AMB)}")
qs=sorted(allS); QQ=[qs[int(len(qs)*f)] for f in (1/3,2/3)]
print(f"  三分位点: {QQ[0]:.1f}m / {QQ[1]:.1f}m")
def sband(s):
    if s is None: return None
    return '短(先行有利側)' if s<QQ[0] else '中' if s<QQ[1] else '長(差し有利側)'

def run(sel, smin, lo=7, hi=12, dates=None):
    k=n=0
    for key,hs in races.items():
        if dates and not (dates[0]<=key[0]<=dates[1]): continue
        ck=ckey(hs,key)
        if ck is None: continue
        if not sel(ck,hs): continue
        for h in hs:
            p=fl(h['人気'])
            if p is None or not (lo<=p<=hi): continue
            s=senkou(h['馬名'],key[0])
            if s is None: continue
            if smin is not None and s<smin: continue
            try: c=int(h['着順'])
            except: continue
            n+=1
            if c<=3: k+=1
    return k,n

print("\n=== 検査K: 直線長帯 × 事前先行力  穴7-12人気の3着内率 (位置取りは使わない) ===")
print(f"{'直線長帯':<16}{'先行力≧0.60':>26}{'しきい値なし':>26}{'差':>30}")
BANDS=['短(先行有利側)','中','長(差し有利側)']
store={}
for b in BANDS:
    sel=lambda ck,hs,b=b: sband(straight(ck))==b
    k1,n1=run(sel,0.60); k0,n0=run(sel,None)
    store[b]=((k1,n1),(k0,n0))
    w1=wilson(k1,n1); w0=wilson(k0,n0); d,l,h=nb(k1,n1,k0,n0)
    print(f"{b:<16}{f'{w1[0]:.2f}% [{w1[1]:.1f},{w1[2]:.1f}] n={n1}':>26}"
          f"{f'{w0[0]:.2f}% [{w0[1]:.1f},{w0[2]:.1f}] n={n0}':>26}"
          f"{f'{d:+.2f}pt [{l:+.2f},{h:+.2f}]':>30}")
(k_s,n_s),_=store['短(先行有利側)']; (k_l,n_l),_=store['長(差し有利側)']
d,l,h=nb(k_s,n_s,k_l,n_l)
print(f"\n  短×先行力≧0.60  −  長×先行力≧0.60 = {d:+.2f}pt  Newcombe 95%CI [{l:+.2f}, {h:+.2f}]pt  → {'0を含まない' if (l>0 or h<0) else '0を含む'}")

print("\n=== 検査L: 芝ダ別に分けても成立するか ===")
for sd in ['芝','ダ']:
    print(f"  --- {sd} ---")
    for b in BANDS:
        sel=lambda ck,hs,b=b,sd=sd: ck[1]==sd and sband(straight(ck))==b
        k1,n1=run(sel,0.60); k0,n0=run(sel,None)
        if n1<30: print(f"      {b:<16} 母数不足 n={n1}"); continue
        w1=wilson(k1,n1); w0=wilson(k0,n0); d,l,h=nb(k1,n1,k0,n0)
        print(f"      {b:<16} 先行力≧0.60 {w1[0]:6.2f}% (n={n1:>4})   全穴 {w0[0]:5.2f}% (n={n0:>4})   差 {d:+.2f}pt [{l:+.2f},{h:+.2f}]")

print("\n=== 検査M: 前後半split ===")
mid='2026-03-01'
for b in BANDS:
    sel=lambda ck,hs,b=b: sband(straight(ck))==b
    a=run(sel,0.60,dates=('2025-09-07',mid)); c=run(sel,0.60,dates=(mid,'2026-09-06'))
    a0=run(sel,None,dates=('2025-09-07',mid)); c0=run(sel,None,dates=(mid,'2026-09-06'))
    print(f"  {b:<16} 前半 {wilson(*a)[0]:6.2f}%(n={a[1]:>4}) / 全穴 {wilson(*a0)[0]:5.2f}%(n={a0[1]:>4})"
          f"    後半 {wilson(*c)[0]:6.2f}%(n={c[1]:>4}) / 全穴 {wilson(*c0)[0]:5.2f}%(n={c0[1]:>4})")

print("\n=== 検査N: 直線長を連続量として。穴7-12×先行力≧0.60 の3着内率をコース単位で相関 ===")
per=collections.defaultdict(lambda:[0,0])
for key,hs in races.items():
    ck=ckey(hs,key)
    if ck is None or straight(ck) is None: continue
    for h in hs:
        p=fl(h['人気']); s=senkou(h['馬名'],key[0])
        if p is None or s is None or s<0.60 or not(7<=p<=12): continue
        try: c=int(h['着順'])
        except: continue
        per[ck][1]+=1
        if c<=3: per[ck][0]+=1
pts=[(straight(k),v[0]/v[1]*100,v[1]) for k,v in per.items() if v[1]>=40]
print(f"  n≧40のコース = {len(pts)}")
if len(pts)>=8:
    xs=[a for a,_,_ in pts]; ys=[b for _,b,_ in pts]
    mx=st.mean(xs); my=st.mean(ys)
    nu=sum((a-mx)*(b-my) for a,b in zip(xs,ys))
    de=math.sqrt(sum((a-mx)**2 for a in xs)*sum((b-my)**2 for b in ys))
    r=nu/de; n=len(xs)
    se=1/math.sqrt(n-3); zf=0.5*math.log((1+r)/(1-r))
    print(f"  直線長 vs 穴×先行型の3着内率  Pearson r={r:+.4f} 95%CI [{math.tanh(zf-Z*se):+.4f}, {math.tanh(zf+Z*se):+.4f}] n={n}")
    for a,b,c in sorted(pts):
        print(f"      直線{a:6.1f}m  3着内率 {b:5.2f}%  (n={c})")
