#!/usr/bin/env python3
"""選別条件別 × 3連複構成別の対応表を作る（再現用）。

用途:
  「どの選別条件が、どの構成で効くか」を1枚の表にする。
  9/10の実測で「同じ前走3着内が構成によって逆方向に働く」ことが判明したため、
  条件を9種・構成を5種へ広げて全45セルを測る。

実行方法:
  python3 scripts/selection_x_construction.py <荒れ傾向分析_全レース全頭_*.csv>

人気帯（8/16全頭スクリーンと同一）: 本命=1-3 / 中穴=4-6 / 穴=7-12
母集団: 平地(障害フラグ=0) ∧ 非新馬(新馬フラグ=0) ∧ 出走頭数>=14

選別条件（すべて事前確定情報。穴の脚にのみ適用）:
  なし / 前走3着内 / 前走5着内 / 前走6番人気以内 / 前走7番人気以下 /
  前走上がり3F上位3 / 騎手直近3着内20%+ / 距離短縮 / 前走前3番手
  - 前走は馬名×日付順で復元。前走がない初出走は不採用（None）
  - 前走上がり3F順位はそのレース内の順位
  - 騎手直近3着内率は当該日より前の180日のみ・最低50騎乗（リークなし）

購入方式: 構成を満たす全組合せを1点ずつ買う理論値。実購入ではない
         3連複払戻は100円あたり。回収率 = 払戻合計 / (点数×100)

【制約】
  - 人気は確定人気。判断時点の人気は本CSVに存在しない（8/16実測では前日基準との
    完全一致は10頭27.0%のみ）。よって本結果は事後分析である
  - ワイド払戻の列が本CSVに無いため、ワイドの収支は算出できない
  - 45セルの多重比較。有意水準5%なら偶然の当たりは期待値2.25セル
  - 前後半分割はホールドアウトの代用（条件は既知で前半で探索していない）
"""
import csv,collections,sys,datetime as dt,statistics as st
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

# ---- 各馬の走破履歴（日付順）から前走の属性を作る ----
byhorse=collections.defaultdict(list)
for r in rows:
    if I(r['着順']) and str(r['馬名']).strip():
        byhorse[r['馬名'].strip()].append(r)
# 前走上がり3F順位のため、レース内の上がり3F順位を先に作る
ag=collections.defaultdict(list)
for r in rows:
    a=F(r['上がり3F_秒'])
    if a: ag[r['racekey']].append((a,r['馬名'].strip()))
agrank={}
for k,v in ag.items():
    for i,(a,nm) in enumerate(sorted(v),1): agrank[(k,nm)]=i

PREV={}
for nm,v in byhorse.items():
    v.sort(key=lambda r:(r['日付'], r['racekey']))
    for j in range(1,len(v)):
        pr=v[j-1]; cu=v[j]
        PREV[(nm,cu['racekey'])]={
          'ch':I(pr['着順']), 'pop':I(pr['人気']),
          'agr':agrank.get((pr['racekey'],nm)),
          'pass1':I(pr['通過順1']),
          'dist':I(pr['距離_m']),
          'days':(D(cu['日付'])-D(pr['日付'])).days,
        }

# ---- 騎手の直近180日3着内率（当該日より前のみ＝リークなし） ----
jk=collections.defaultdict(list)
for r in rows:
    if I(r['着順']) and str(r['騎手']).strip():
        jk[r['騎手'].strip()].append((D(r['日付']), I(r['着順'])<=3))
for k in jk: jk[k].sort()
def jrate(name,d):
    v=jk.get(name)
    if not v: return None
    w=[t for (dd,t) in v if 0 < (d-dd).days <= 180]
    if len(w)<50: return None
    return sum(w)/len(w)

sel=[r for r in rows if I(r['着順']) and I(r['人気']) and flat(r) and (I(r['出走頭数']) or 0)>=14]
RC=collections.defaultdict(lambda:{'h':[],'pay':None,'date':None})
for r in sel:
    nm=r['馬名'].strip(); k=r['racekey']; pv=PREV.get((nm,k))
    d=D(r['日付'])
    RC[k]['h'].append({'pop':I(r['人気']),'ch':I(r['着順']),'pv':pv,
                       'dist':I(r['距離_m']),'jr':jrate(r['騎手'].strip(),d)})
    RC[k]['pay']=F(r['3連複払戻']); RC[k]['date']=r['日付']
races={k:v for k,v in RC.items() if len(v['h'])>=14 and v['pay']}

# ---- 選別条件（すべて事前確定情報） ----
def c_none(h): return True
def c_p3(h):   return bool(h['pv']) and h['pv']['ch'] is not None and h['pv']['ch']<=3
def c_p5(h):   return bool(h['pv']) and h['pv']['ch'] is not None and h['pv']['ch']<=5
def c_pop16(h):return bool(h['pv']) and h['pv']['pop'] is not None and h['pv']['pop']<=6
def c_pop7(h): return bool(h['pv']) and h['pv']['pop'] is not None and h['pv']['pop']>=7
def c_ag3(h):  return bool(h['pv']) and h['pv']['agr'] is not None and h['pv']['agr']<=3
def c_jk20(h): return h['jr'] is not None and h['jr']>=0.20
def c_short(h):return bool(h['pv']) and h['pv']['dist'] and h['dist'] and h['dist']<h['pv']['dist']
def c_fwd(h):  return bool(h['pv']) and h['pv']['pass1'] is not None and h['pv']['pass1']<=3
COND=[('なし',c_none),('前走3着内',c_p3),('前走5着内',c_p5),('前走6番人気以内',c_pop16),
      ('前走7番人気以下',c_pop7),('前走上がり3F上位3',c_ag3),('騎手直近3着内20%+',c_jk20),
      ('距離短縮',c_short),('前走前3番手',c_fwd)]

BAND={'本命':(1,3),'中穴':(4,6),'穴':(7,12)}
COMPS=[('穴+穴+穴',['穴','穴','穴']),('穴+穴+本命',['穴','穴','本命']),
       ('穴+中穴+中穴',['穴','中穴','中穴']),('穴+中穴+本命',['穴','中穴','本命']),
       ('穴+本命+本命',['穴','本命','本命'])]

def nCk(n,k):
    if n<k: return 0
    r=1
    for x in range(k): r=r*(n-x)//(x+1)
    return r

def run(comp,cf,keys):
    need=collections.Counter(comp); pts=0;hit=0;ret=0.0;pays=[]
    for k in keys:
        d=races[k]; hs=d['h']
        pools={}
        for b in need:
            lo,hi=BAND[b]
            g=[h for h in hs if lo<=h['pop']<=hi]
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
            lo,hi=BAND[b]
            g=[h for h in t3 if lo<=h['pop']<=hi]
            if b=='穴': g=[h for h in g if cf(h)]
            if len(g)!=n: ok=False;break
        if ok: hit+=1;ret+=d['pay']/100.0;pays.append(d['pay'])
    return pts,hit,(ret/pts*100 if pts else 0),(st.mean(pays) if pays else 0)

alld=sorted({races[k]['date'] for k in races}); mid=alld[len(alld)//2]
H1=[k for k in races if races[k]['date']<mid]; H2=[k for k in races if races[k]['date']>=mid]
print(f"対象 {len(races):,}R / 前半 {len(H1):,}R (〜{mid}) / 後半 {len(H2):,}R")
print(f"セル数 {len(COMPS)}構成 × {len(COND)}条件 = {len(COMPS)*len(COND)}\n")

for nm,comp in COMPS:
    print(f"■ {nm}")
    print(f"  {'条件':20}{'点数':>9}{'的中':>5}{'回収率%':>9}{'的中時平均':>10} | {'前半%':>8}{'的中':>4} {'後半%':>8}{'的中':>4}")
    for cn,cf in COND:
        pt,hi,roi,mn=run(comp,cf,list(races))
        p1,h1,r1,_=run(comp,cf,H1); p2,h2,r2,_=run(comp,cf,H2)
        print(f"  {cn:20}{pt:>9,}{hi:>5}{roi:>9.2f}{mn:>10,.0f} | {r1:>8.2f}{h1:>4} {r2:>8.2f}{h2:>4}")
    print()
