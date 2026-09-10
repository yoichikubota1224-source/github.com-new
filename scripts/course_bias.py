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
"""コース別の前有利度を実測し、コース事典の構造列が説明できるかを検証.

設計:
  前有利度 = レースデータからの実測(場×芝ダ×距離)。コース事典は使わない。
  コース事典 = 構造ラベル(直線長・高低差・回り・内外回り)の供給のみ。
              jra_official_course_verified=NO 101/101、98/101が出所不明の既存CourseMaster由来。
              値そのものを正しいものとして扱わない。
  start_to_first_corner_m は数値0/101で完全欠測 → この列に依存する評価は行わない。
"""
import csv, collections, math, statistics as st
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

# ---- コース事典 ----
CD={}
dup=collections.Counter()
for r in csv.DictReader(open(f"{SP}/course3/x/競馬場コース事典2_コース構造_101.csv",encoding='utf-8-sig')):
    sd='芝' if r['surface'].strip()=='turf' else 'ダ'
    key=(r['track'].strip(), sd, int(float(r['distance_m'])))
    dup[key]+=1
    CD.setdefault(key,[]).append(r)
print("=== 結合キー(場,芝ダ,距離)の重複 ===")
d2={k:v for k,v in dup.items() if v>1}
print(f"  重複キー {len(d2)}件: {sorted(d2.items())[:8]}")
for k in sorted(d2):
    print(f"    {k}: " + " / ".join(f"{x['course_section']}(直線{x['straight_length_m']}m)" for x in CD[k]))

# ---- レースデータ ----
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

# ---- コース別 実測 ----
agg=collections.defaultdict(lambda: {'R':0,'zen':[0,0],'ushiro':[0,0],'ana_zen':[0,0],'ana_ushiro':[0,0]})
for key,hs in races.items():
    d=fl(hs[0]['距離_m']); sd=hs[0]['芝ダ障'].strip()
    if d is None or sd not in ('芝','ダ'): continue
    ck=(key[1], sd, int(d))
    a=agg[ck]; a['R']+=1
    for h in hs:
        g=posmap.get(id(h))
        if g is None: continue
        p=fl(h['人気'])
        try: c=int(h['着順'])
        except: continue
        hit=1 if c<=3 else 0
        if g=='前': a['zen'][1]+=1; a['zen'][0]+=hit
        if g=='後': a['ushiro'][1]+=1; a['ushiro'][0]+=hit
        if p is not None and 7<=p<=12:
            if g=='前': a['ana_zen'][1]+=1; a['ana_zen'][0]+=hit
            if g=='後': a['ana_ushiro'][1]+=1; a['ana_ushiro'][0]+=hit

print(f"\n=== レースデータ側のコース数 = {len(agg)} / 事典側 = {len(CD)} ===")
matched=[k for k in agg if k in CD]
print(f"  事典と結合できたコース = {len(matched)}")
print(f"  事典にないコース = {len([k for k in agg if k not in CD])} 例: {sorted(k for k in agg if k not in CD)[:10]}")
print(f"  事典にありデータにないコース = {len([k for k in CD if k not in agg])}")

# 30R以上のコースだけ
sel=[k for k in matched if agg[k]['R']>=30]
print(f"  30R以上かつ結合できたコース = {len(sel)}")

print("\n=== 検査I: コース別の前有利度(実測) 上位・下位 ===")
res=[]
for k in sel:
    a=agg[k]
    z=a['zen']; u=a['ushiro']
    if z[1]<30 or u[1]<30: continue
    gap=z[0]/z[1]*100 - u[0]/u[1]*100
    res.append((gap,k,z,u,a))
res.sort(reverse=True)
print(f"{'コース':<20}{'R':>5}{'前1/3の3着内':>22}{'後1/3の3着内':>22}{'差':>10}")
for gap,k,z,u,a in res[:10]:
    wz=wilson(*z); wu=wilson(*u)
    print(f"{k[0]+k[1]+str(k[2]):<20}{a['R']:>5}{f'{wz[0]:.1f}% (n={z[1]})':>22}{f'{wu[0]:.1f}% (n={u[1]})':>22}{gap:>+9.1f}pt")
print("   … 中略 …")
for gap,k,z,u,a in res[-10:]:
    wz=wilson(*z); wu=wilson(*u)
    print(f"{k[0]+k[1]+str(k[2]):<20}{a['R']:>5}{f'{wz[0]:.1f}% (n={z[1]})':>22}{f'{wu[0]:.1f}% (n={u[1]})':>22}{gap:>+9.1f}pt")
gaps=[g for g,_,_,_,_ in res]
print(f"\n  コース数={len(res)}  差の範囲 {min(gaps):+.1f}pt 〜 {max(gaps):+.1f}pt  中央値 {st.median(gaps):+.1f}pt  標準偏差 {st.pstdev(gaps):.1f}pt")

# ---- 構造列との対応 ----
print("\n=== 検査J: 事典の構造列は実測の前有利度を説明するか ===")
def corr(xs,ys):
    n=len(xs)
    if n<8: return None
    mx=st.mean(xs); my=st.mean(ys)
    nu=sum((a-mx)*(b-my) for a,b in zip(xs,ys))
    de=math.sqrt(sum((a-mx)**2 for a in xs)*sum((b-my)**2 for b in ys))
    if de==0: return None
    r=nu/de
    se=1/math.sqrt(n-3); zf=0.5*math.log((1+r)/(1-r))
    return r, math.tanh(zf-Z*se), math.tanh(zf+Z*se), n
for col,lbl in [('straight_length_m','直線長(m)'),('elevation_difference_m','高低差(m)'),('distance_m','距離(m)')]:
    xs=[];ys=[]
    for gap,k,z,u,a in res:
        v=fl(CD[k][0][col])
        if v is None: continue
        xs.append(v); ys.append(gap)
    c=corr(xs,ys)
    if c: print(f"  {lbl:<14} vs 差(前-後)   Pearson r={c[0]:+.4f} 95%CI [{c[1]:+.4f}, {c[2]:+.4f}]  n={c[3]}  {'0を含まない' if (c[1]>0 or c[2]<0) else '0を含む'}")
print()
for col in ['turn_direction','course_section']:
    grp=collections.defaultdict(list)
    for gap,k,z,u,a in res:
        grp[CD[k][0][col].strip()].append(gap)
    print(f"  --- {col} 別の差(前-後) ---")
    for g,v in sorted(grp.items(), key=lambda t:-st.mean(t[1])):
        print(f"      {g:<8} n={len(v):>3}コース  平均 {st.mean(v):+.1f}pt  中央値 {st.median(v):+.1f}pt  範囲 {min(v):+.1f}〜{max(v):+.1f}")
