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
"""最も単純な形: 直線長だけで穴帯が動くか(先行力を要求しない=母数最大)."""
import csv, collections, math, statistics as st
SP="/tmp/claude-0/-home-user-github-com-new/84a20921-3b38-53dd-8669-b122c897a190/scratchpad"
Z=1.96
def wilson(k,n):
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
CD=collections.defaultdict(list)
for r in csv.DictReader(open(f"{SP}/course3/x/競馬場コース事典2_コース構造_101.csv",encoding='utf-8-sig')):
    sd='芝' if r['surface'].strip()=='turf' else 'ダ'
    CD[(r['track'].strip(),sd,int(float(r['distance_m'])))].append(r)
AMB={k for k,v in CD.items() if len(v)>1}
def straight(k):
    if k in AMB: return None
    v=CD.get(k)
    return fl(v[0]['straight_length_m']) if v else None
rows=[r for r in csv.DictReader(open(f"{SP}/zx/c/荒れ傾向分析_全レース全頭_20250907-20260906.csv",encoding='utf-8-sig'))
      if str(r['障害フラグ']).strip() in ('0','','False','false')
      and str(r['新馬フラグ']).strip() in ('0','','False','false')]
races=collections.defaultdict(list)
for r in rows: races[(r['日付'],r['開催場'],r['R'])].append(r)
def ckey(hs,key):
    d=fl(hs[0]['距離_m']); sd=hs[0]['芝ダ障'].strip()
    if d is None or sd not in ('芝','ダ'): return None
    return (key[1],sd,int(d))
allS=[]
for key,hs in races.items():
    ck=ckey(hs,key)
    if ck and straight(ck) is not None: allS.append(straight(ck))
qs=sorted(allS); QQ=[qs[int(len(qs)*f)] for f in (1/3,2/3)]
def sband(s):
    if s is None: return None
    return '短' if s<QQ[0] else '中' if s<QQ[1] else '長'
def run(band, lo, hi, dates=None, sd=None):
    k=n=0
    for key,hs in races.items():
        if dates and not (dates[0]<=key[0]<=dates[1]): continue
        ck=ckey(hs,key)
        if ck is None: continue
        if sd and ck[1]!=sd: continue
        if sband(straight(ck))!=band: continue
        for h in hs:
            p=fl(h['人気'])
            if p is None or not(lo<=p<=hi): continue
            try: c=int(h['着順'])
            except: continue
            n+=1
            if c<=3: k+=1
    return k,n
print(f"三分位点 {QQ[0]:.1f}m / {QQ[1]:.1f}m")
print("\n=== 検査O: 直線長帯だけ。人気帯ごとの3着内率(先行力を要求しない=母数最大) ===")
print(f"{'人気帯':<14}{'短(<310m)':>26}{'中':>26}{'長(≧358.7m)':>26}{'短−長':>28}")
for lbl,lo,hi in [('本命1-3',1,3),('中穴4-6',4,6),('穴7-12',7,12),('大穴13-',13,99)]:
    cells={}
    for b in ['短','中','長']:
        cells[b]=run(b,lo,hi)
    d,l,h=nb(*cells['短'],*cells['長'])
    line=""
    for b in ['短','中','長']:
        k,n=cells[b]; w=wilson(k,n)
        line+=f"{f'{w[0]:.2f}% [{w[1]:.1f},{w[2]:.1f}] n={n}':>26}"
    print(f"{lbl:<14}{line}{f'{d:+.2f}pt [{l:+.2f},{h:+.2f}]':>28}  {'0を含まない' if (l>0 or h<0) else '0を含む'}")
print("\n=== 芝ダ別 (穴7-12) ===")
for sd in ['芝','ダ']:
    cells={b:run(b,7,12,sd=sd) for b in ['短','中','長']}
    d,l,h=nb(*cells['短'],*cells['長'])
    line="".join(f"{f'{wilson(*cells[b])[0]:.2f}% (n={cells[b][1]})':>22}" for b in ['短','中','長'])
    print(f"  {sd}{line}   短−長 {d:+.2f}pt [{l:+.2f},{h:+.2f}]  {'0を含まない' if (l>0 or h<0) else '0を含む'}")
print("\n=== 前後半split (穴7-12) ===")
mid='2026-03-01'
for lab,rng in (('前半',('2025-09-07',mid)),('後半',(mid,'2026-09-06'))):
    cells={b:run(b,7,12,dates=rng) for b in ['短','中','長']}
    d,_,_=nb(*cells['短'],*cells['長'])
    line="".join(f"{f'{wilson(*cells[b])[0]:.2f}% (n={cells[b][1]})':>22}" for b in ['短','中','長'])
    print(f"  {lab}{line}   短−長 {d:+.2f}pt")
