#!/usr/bin/env python3
"""★セル（穴+穴+本命 × 前走6番人気以内）の閾値検査（再現用）。

用途:
  45セルの対応表で唯一「的中二桁・両期間とも保持・的中率の差のCIが0を含まない」
  だった1セルが、偶然か構造かを分ける。3つの検査を行う。

  【A】累積しきい値（前走1/3/6/9/12番人気以内）で単調性が出るか
      → 入れ子なので機械的に単調が出やすい。出なければ強い否定材料
  【B】排他バケット（前走1-3/4-6/7-9/10-12/13+）
      → ただし穴2脚に同一条件を課すため、Aの分解にはならない（注意）
  【C】降格幅（今回人気 − 前走人気）で単調性が出るか
      → 「市場が見限った馬」という仮説の直接の検査
  【感度】上位N本の払戻を除いたときに回収率がどこまで落ちるか
      → 稀な高配当が結果を支配していないかの検査

実行方法:
  python3 scripts/threshold_check_star_cell.py <荒れ傾向分析_全レース全頭_*.csv>

母集団・購入方式・制約は scripts/selection_x_construction.py と同一
（平地・非新馬・出走頭数>=14 / 構成を満たす全組合せを1点ずつ買う理論値 /
 人気は確定人気で判断時点の人気は本CSVに存在しない）。

回収率の単位に注意:
  3連複払戻は100円あたりの円単位。ROI = Σ払戻(円) / (点数 × 100) × 100 [%]
  = Σ払戻(円) / 点数 / 100 × 100。実装時にスケールを間違えやすい。
"""
import csv,collections,sys,datetime as dt,statistics as st,math
p=sys.argv[1]
rows=list(csv.DictReader(open(p,encoding='utf-8-sig')))
def I(v):
    try: return int(str(v).strip())
    except: return None
def F(v):
    try: return float(str(v).strip().replace(',',''))
    except: return None
def D(s): return dt.date.fromisoformat(str(s).strip())
flat=lambda r:(str(r['障害フラグ']).strip() in ('0','','False','false')
           and str(r['新馬フラグ']).strip() in ('0','','False','false'))
byh=collections.defaultdict(list)
for r in rows:
    if I(r['着順']) and str(r['馬名']).strip(): byh[r['馬名'].strip()].append(r)
PREV={}
for nm,v in byh.items():
    v.sort(key=lambda r:(r['日付'],r['racekey']))
    for j in range(1,len(v)):
        PREV[(nm,v[j]['racekey'])]={'pop':I(v[j-1]['人気']),'ch':I(v[j-1]['着順'])}
sel=[r for r in rows if I(r['着順']) and I(r['人気']) and flat(r) and (I(r['出走頭数']) or 0)>=14]
RC=collections.defaultdict(lambda:{'h':[],'pay':None,'date':None})
for r in sel:
    pv=PREV.get((r['馬名'].strip(),r['racekey']))
    RC[r['racekey']]['h'].append({'pop':I(r['人気']),'ch':I(r['着順']),'pv':pv})
    RC[r['racekey']]['pay']=F(r['3連複払戻']); RC[r['racekey']]['date']=r['日付']
races={k:v for k,v in RC.items() if len(v['h'])>=14 and v['pay']}
BAND={'本命':(1,3),'中穴':(4,6),'穴':(7,12)}
COMP=['穴','穴','本命']
def nCk(n,k):
    if n<k: return 0
    r=1
    for x in range(k): r=r*(n-x)//(x+1)
    return r
def wilson(k,n,z=1.96):
    if n==0: return (0,0,0)
    ph=k/n; d=1+z*z/n
    c=(ph+z*z/(2*n))/d; m=z*math.sqrt(ph*(1-ph)/n+z*z/(4*n*n))/d
    return ph,(c-m),(c+m)
def run(cf,keys):
    need=collections.Counter(COMP); pts=hit=0; ret=0.0; pays=[]
    for k in keys:
        d=races[k]; hs=d['h']; pools={}
        for b in need:
            lo,hi=BAND[b]; g=[h for h in hs if lo<=h['pop']<=hi]
            if b=='穴': g=[h for h in g if cf(h)]
            pools[b]=g
        c=1
        for b,n in need.items():
            c*=nCk(len(pools[b]),n)
            if c==0: break
        if not c: continue
        pts+=c
        t3=[h for h in hs if h['ch']<=3]
        if len(t3)!=3: continue
        ok=True
        for b,n in need.items():
            lo,hi=BAND[b]; g=[h for h in t3 if lo<=h['pop']<=hi]
            if b=='穴': g=[h for h in g if cf(h)]
            if len(g)!=n: ok=False;break
        if ok: hit+=1; ret+=d['pay']/100.0; pays.append(d['pay'])
    return pts,hit,(ret/pts*100 if pts else 0),(st.mean(pays) if pays else 0)
alld=sorted({races[k]['date'] for k in races}); mid=alld[len(alld)//2]
H1=[k for k in races if races[k]['date']<mid]; H2=[k for k in races if races[k]['date']>=mid]
K=list(races)
def show(title,items):
    print(f"\n{title}")
    print(f"  {'区分':16}{'点数':>8}{'的中':>5}{'回収率%':>9}{'的中率%':>9}{'的中率95%CI':>20}{'的中時平均':>10} | {'前半%':>8}{'後半%':>8}")
    for lab,cf in items:
        pt,hi,roi,mn=run(cf,K)
        if pt==0: print(f"  {lab:16}{'0':>8}"); continue
        p,lo,up=wilson(hi,pt)
        _,_,r1,_=run(cf,H1); _,_,r2,_=run(cf,H2)
        print(f"  {lab:16}{pt:>8,}{hi:>5}{roi:>9.2f}{p*100:>9.4f}  [{lo*100:6.4f},{up*100:6.4f}]{mn:>10,.0f} | {r1:>8.2f}{r2:>8.2f}")
print(f"対象 {len(races):,}R / 前半 {len(H1):,}R / 後半 {len(H2):,}R")
show("【A】累積しきい値（入れ子・機械的に単調が出やすい）",
 [("なし",lambda h:True)]+[(f"前走{n}番人気以内",(lambda n: (lambda h: bool(h['pv']) and h['pv']['pop'] and h['pv']['pop']<=n))(n)) for n in (1,3,6,9,12)])
show("【B】排他バケット（★本命の検査）",
 [("前走1-3人気",lambda h: bool(h['pv']) and h['pv']['pop'] and 1<=h['pv']['pop']<=3),
  ("前走4-6人気",lambda h: bool(h['pv']) and h['pv']['pop'] and 4<=h['pv']['pop']<=6),
  ("前走7-9人気",lambda h: bool(h['pv']) and h['pv']['pop'] and 7<=h['pv']['pop']<=9),
  ("前走10-12人気",lambda h: bool(h['pv']) and h['pv']['pop'] and 10<=h['pv']['pop']<=12),
  ("前走13人気以下",lambda h: bool(h['pv']) and h['pv']['pop'] and h['pv']['pop']>=13)])
show("【C】降格幅 = 今回人気 − 前走人気（正=人気を落とした）",
 [("−3以下(昇格)",lambda h: bool(h['pv']) and h['pv']['pop'] and (h['pop']-h['pv']['pop'])<=-3),
  ("−2〜+2(横ばい)",lambda h: bool(h['pv']) and h['pv']['pop'] and -2<=(h['pop']-h['pv']['pop'])<=2),
  ("+3〜+5",lambda h: bool(h['pv']) and h['pv']['pop'] and 3<=(h['pop']-h['pv']['pop'])<=5),
  ("+6〜+8",lambda h: bool(h['pv']) and h['pv']['pop'] and 6<=(h['pop']-h['pv']['pop'])<=8),
  ("+9以上(大降格)",lambda h: bool(h['pv']) and h['pv']['pop'] and (h['pop']-h['pv']['pop'])>=9)])
