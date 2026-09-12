#!/usr/bin/env python3
"""3連複の構成別・選別前後の収支を実測する（再現用）。

用途:
  ChatGPT依頼②③④への対応。羊一様の実際の主戦略である
  「穴＋穴＋本命」「穴＋中穴＋中穴」を、選別前後・期間前後半で比較する。
  前回の「穴＋穴＋穴」は参照用に残す。

実行方法:
  python3 scripts/trifecta_構成別収支.py <荒れ傾向分析_全レース全頭_*.csv>

人気帯の定義（8/16全頭スクリーンと同一）:
  本命帯 = 1-3人気 / 中穴帯 = 4-6人気 / 穴帯 = 7-12人気

母集団の絞り込み:
  平地(障害フラグ=0) ∧ 非新馬(新馬フラグ=0) ∧ 出走頭数>=14

選別条件（前走3着内）:
  馬名×日付順で前走を復元し、前走着順<=3 を満たす馬のみを穴の脚に使う。
  前走がない初出走は除外（False扱いではなく None として不採用）。
  前走結果はレース前に確定している情報なので、事前選別として使える。

購入方式:
  構成を満たす全組合せを1点ずつ購入する理論値。実購入ではない。
  3連複払戻は100円あたりの円単位。回収率 = 払戻合計 / (点数×100)。

【重要な制約】
  - 人気は**確定人気**である。判断時点（前日・直前）の人気は本CSVに存在しない。
    8/16の実測では前日基準と確定の完全一致は10頭(27.0%)のみだったため、
    実運用の数値は本結果と乖離する。よって本結果は事後分析である。
  - **ワイド払戻の列が本CSVに存在しない**ため、ワイドの収支は算出できない
    （的中確率のみ算出可能）。
  - 期間の前後半分割はホールドアウトの代用であり、条件を前半で選んで後半で
    確認する厳密な手続きではない（前走3着内は既知の条件で、探索していない）。
"""
import csv,collections,sys,statistics as st
p=sys.argv[1]
rows=list(csv.DictReader(open(p,encoding='utf-8-sig')))
def i(v):
    try: return int(str(v).strip())
    except: return None
def f(v):
    try: return float(str(v).strip().replace(',',''))
    except: return None
flat=lambda r: (str(r['障害フラグ']).strip() in ('0','','False','false')
            and str(r['新馬フラグ']).strip() in ('0','','False','false'))

# 前走3着内の復元（馬名×日付順。前走がない初出走は False）
hist=collections.defaultdict(list)
for r in rows:
    if i(r['着順']) and str(r['馬名']).strip():
        hist[r['馬名'].strip()].append((r['日付'], i(r['着順']), r['racekey']))
prev={}
for nm,v in hist.items():
    v.sort()
    for k in range(1,len(v)):
        prev[(nm,v[k][2])] = v[k-1][1] <= 3   # 前走3着内か

sel=[r for r in rows if i(r['着順']) and i(r['人気']) and flat(r) and (i(r['出走頭数']) or 0)>=14]
R=collections.defaultdict(lambda:{'h':[], 'pay':None, 'date':None})
for r in sel:
    R[r['racekey']]['h'].append({'pop':i(r['人気']),'ch':i(r['着順']),
        'p3':prev.get((r['馬名'].strip(),r['racekey']), None)})
    R[r['racekey']]['pay']=f(r['3連複払戻']); R[r['racekey']]['date']=r['日付']
races={k:v for k,v in R.items() if len(v['h'])>=14 and v['pay']}

BAND={'本命':(1,3),'中穴':(4,6),'穴':(7,12)}
def legs(hs,b,need_p3=False):
    lo,hi=BAND[b]
    out=[h for h in hs if lo<=h['pop']<=hi]
    if need_p3: out=[h for h in out if h['p3'] is True]
    return out

def run(comp, sel_ana, keys):
    """comp: 帯の並び（重複可）。sel_ana: 穴脚に前走3着内を要求するか"""
    pts=0; hit=0; ret=0.0; pays=[]
    for k in keys:
        d=races[k]; hs=d['h']
        need={b:comp.count(b) for b in set(comp)}
        pools={b:legs(hs,b, sel_ana and b=='穴') for b in need}
        # 購入点数
        c=1
        for b,n in need.items():
            m=len(pools[b])
            if m<n: c=0; break
            num=1
            for x in range(n): num=num*(m-x)//(x+1)
            c*=num
        if not c: continue
        pts+=c
        # 的中判定: 実際の1-3着が構成を満たし、かつ選別条件も満たすか
        top3=[h for h in hs if h['ch']<=3]
        if len(top3)!=3: continue
        ok=True
        for b,n in need.items():
            lo,hi=BAND[b]
            g=[h for h in top3 if lo<=h['pop']<=hi]
            if sel_ana and b=='穴': g=[h for h in g if h['p3'] is True]
            if len(g)!=n: ok=False; break
        if ok:
            hit+=1; ret+=d['pay']/100.0; pays.append(d['pay'])
    roi=ret/pts*100 if pts else 0
    return pts,hit,roi,(st.mean(pays) if pays else 0),(st.median(pays) if pays else 0)

alld=sorted({races[k]['date'] for k in races})
mid=alld[len(alld)//2]
H1=[k for k in races if races[k]['date']<mid]
H2=[k for k in races if races[k]['date']>=mid]
print(f"対象 {len(races):,}R  前半 {len(H1):,}R (〜{mid}) / 後半 {len(H2):,}R ({mid}〜)\n")

COMPS=[('穴+穴+穴',['穴','穴','穴']),('穴+穴+本命',['穴','穴','本命']),('穴+中穴+中穴',['穴','中穴','中穴'])]
for nm,comp in COMPS:
    print(f"■ {nm}")
    print(f"  {'期間':6}{'選別':10}{'点数':>10}{'的中R':>7}{'回収率%':>9}{'的中時平均':>11}{'中央値':>10}")
    for pl,keys in [('全期間',list(races)),('前半',H1),('後半',H2)]:
        for sl,lab in [(False,'なし'),(True,'前走3着内')]:
            pts,hit,roi,mn,md=run(comp,sl,keys)
            print(f"  {pl:6}{lab:10}{pts:>10,}{hit:>7}{roi:>9.2f}{mn:>11,.0f}{md:>10,.0f}")
    print()
