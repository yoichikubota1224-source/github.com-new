# -*- coding: utf-8 -*-
# 入力の所在(このリポジトリ外):
#   TB日次バイアス_遡及1年_20250801-20260726.csv  = Google Drive より自己取得 (2026-09-10)
#       SHA-256 0bb3783aed94fbd5da7cb9eb188f60fbe8ee4b3e811e40a009318460b5393f1f / 249,763 bytes / 3,308行
#   荒れ傾向分析_全レース全頭_20250907-20260906.csv / レース単位_結果払戻_20250907-20260906.csv
#       = 受領済み「荒れ傾向分析CSV_過去1年」より
#   いずれも読み取りのみ。原本を変更していない。
"""当日事前TB(D_PRE_RACE)が当該レースの結果と関係を持つかの検査.

D_PRE_RACE = 当日・同一場・同一芝ダで「そのレースより前」のflow_r累積平均
             (3308行中2732行で100%一致を確認。各(日,場,芝ダ)の初戦は空欄=576件)
→ as-of。当該レース自身の情報は入っていない。

本スクリプトは検査であり、TB診断・買い目・EVを作らない。
回収率は算出しない(★セル検査の教訓: 配当分散が支配するため率で見る)。
"""
import csv, collections, math, statistics as st

SP = "/tmp/claude-0/-home-user-github-com-new/84a20921-3b38-53dd-8669-b122c897a190/scratchpad"
TB = f"{SP}/tb/TB日次バイアス_遡及1年_20250801-20260726.csv"  # Drive自己取得
UMA = f"{SP}/zx/c/荒れ傾向分析_全レース全頭_20250907-20260906.csv"
RACE = f"{SP}/zx/c/レース単位_結果払戻_20250907-20260906.csv"
Z = 1.96

def wilson(k, n):
    if n == 0: return (0.0, 0.0, 0.0)
    ph = k/n; d = 1 + Z*Z/n
    c = (ph + Z*Z/(2*n))/d
    m = Z*math.sqrt(ph*(1-ph)/n + Z*Z/(4*n*n))/d
    return ph*100, (c-m)*100, (c+m)*100

def fl(v):
    v = (v or '').strip()
    if v=='': return None
    try: return float(v)
    except: return None

# ---------- 1. TB読み込み ----------
tb = []
for r in csv.DictReader(open(TB, encoding='utf-8-sig')):
    tb.append(r)

# ---------- 2. 場コードの対応を実測で確認 ----------
race_rows = list(csv.DictReader(open(RACE, encoding='utf-8-sig')))
dates_by_venue = collections.defaultdict(set)
for r in race_rows:
    dates_by_venue[r['開催場']].add(r['日付'].replace('-',''))
dates_by_code = collections.defaultdict(set)
for r in tb:
    dates_by_code[r['venue']].add(r['date'])

print("=== 場コード対応の実測確認 (共通期間の日付集合のJaccard最大一致) ===")
CAND = ['札幌','函館','福島','新潟','東京','中山','中京','京都','阪神','小倉']
mapping = {}
for code in sorted(dates_by_code, key=lambda x:int(x)):
    dc = dates_by_code[code]
    best = None
    for v in CAND:
        dv = dates_by_venue[v]
        common = dc & dv
        # 共通期間に限定して比較
        lo, hi = '20250907', '20260726'
        dcx = {d for d in dc if lo<=d<=hi}
        dvx = {d for d in dv if lo<=d<=hi}
        if not dcx or not dvx: continue
        j = len(dcx & dvx)/len(dcx | dvx)
        if best is None or j > best[1]: best = (v, j, len(dcx & dvx), len(dcx|dvx))
    mapping[code] = best[0]
    print(f"  venue={code:>2} -> {best[0]}  Jaccard={best[1]:.4f} (共通{best[2]}/合計{best[3]})")
assert len(set(mapping.values()))==10, "対応が一意でない"
print("  → 10場すべて一意に対応。JRA標準の場コード順と一致。")

# ---------- 3. 馬単位データ ----------
uma = collections.defaultdict(list)
for r in csv.DictReader(open(UMA, encoding='utf-8-sig')):
    key = (r['日付'].replace('-',''), r['開催場'], r['R'])
    uma[key].append(r)

rl = {}
for r in race_rows:
    rl[(r['日付'].replace('-',''), r['開催場'], r['R'])] = r

# ---------- 4. 結合 ----------
joined = []
for r in tb:
    pre = fl(r['D_PRE_RACE'])
    key = (r['date'], mapping[r['venue']], r['race'])
    if key not in uma: continue
    horses = uma[key]
    rr = rl.get(key)
    if rr is None: continue
    # 平地・非新馬のみ
    if str(horses[0]['障害フラグ']).strip() not in ('0','','False','false'): continue
    if str(horses[0]['新馬フラグ']).strip() not in ('0','','False','false'): continue
    joined.append((r, pre, horses, rr))

print(f"\n=== 結合結果 ===")
print(f"  TB行 {len(tb)} / 結合成功 {len(joined)} ({len(joined)/len(tb)*100:.2f}%)")
print(f"  うち D_PRE_RACE あり: {sum(1 for x in joined if x[1] is not None)}")
print(f"  ※TB期間 20250801-20260726、レースCSV期間 20250907-20260906 の重なりのみ結合可")

use = [x for x in joined if x[1] is not None]
if not use:
    raise SystemExit("結合0件")

# ---------- 5. D_PRE_RACE の四分位で層化 ----------
pres = sorted(x[1] for x in use)
q = [pres[int(len(pres)*f)] for f in (0.25, 0.50, 0.75)]
print(f"\n  D_PRE_RACE 四分位点: Q1={q[0]:.4f} Q2={q[1]:.4f} Q3={q[2]:.4f}")

def band(p):
    if p < q[0]: return 'Q1(前不利側)'
    if p < q[1]: return 'Q2'
    if p < q[2]: return 'Q3'
    return 'Q4(前有利側)'

def fav3(horses):
    """1番人気の3着内"""
    for h in horses:
        if h['人気']=='1':
            try: return 1 if int(h['着順'])<=3 else 0
            except: return None
    return None

def ana_top3(horses, lo, hi):
    """人気lo..hi の馬のうち3着内に入った頭数と対象頭数"""
    k=n=0
    for h in horses:
        p = fl(h['人気'])
        if p is None or not (lo<=p<=hi): continue
        try: c=int(h['着順'])
        except: continue
        n+=1
        if c<=3: k+=1
    return k,n

def forward_top3(horses):
    """4角(最終取得可能な通過順)で前1/3にいた馬の3着内"""
    pos=[]
    for h in horses:
        last=None
        for c in ['通過順1','通過順2','通過順3','通過順4']:
            v=fl(h[c])
            if v is not None: last=v
        if last is None: continue
        try: chaku=int(h['着順'])
        except: continue
        pos.append((last,chaku))
    if len(pos)<6: return (0,0)
    pos.sort()
    cut=max(1,len(pos)//3)
    k=sum(1 for (_,c) in pos[:cut] if c<=3)
    return k,cut

print("\n=== 検査A: 当日事前TB の四分位別 実測率 (平地・非新馬) ===")
print(f"{'層':<14}{'R数':>6}{'1人気3着内':>26}{'7-12人気3着内':>26}{'前1/3の3着内':>26}{'3連複配当中央値':>16}")
for b in ['Q1(前不利側)','Q2','Q3','Q4(前有利側)']:
    rs=[x for x in use if band(x[1])==b]
    f_k=sum(v for v in (fav3(h) for (_,_,h,_) in rs) if v is not None)
    f_n=sum(1 for (_,_,h,_) in rs if fav3(h) is not None)
    a_k=a_n=0; w_k=w_n=0; pays=[]
    for (_,_,h,rr) in rs:
        k,n=ana_top3(h,7,12); a_k+=k; a_n+=n
        k,n=forward_top3(h); w_k+=k; w_n+=n
        p=fl(rr['3連複_払戻円'])
        if p: pays.append(p)
    f=wilson(f_k,f_n); a=wilson(a_k,a_n); w=wilson(w_k,w_n)
    med=st.median(pays) if pays else 0
    print(f"{b:<14}{len(rs):>6}"
          f"{f'{f[0]:.2f}% [{f[1]:.2f},{f[2]:.2f}] n={f_n}':>26}"
          f"{f'{a[0]:.2f}% [{a[1]:.2f},{a[2]:.2f}] n={a_n}':>26}"
          f"{f'{w[0]:.2f}% [{w[1]:.2f},{w[2]:.2f}] n={w_n}':>26}"
          f"{f'{med:,.0f}円':>16}")

# ---------- 6. 前後半split ----------
print("\n=== 検査B: 前後半split (安定性) ===")
use_s = sorted(use, key=lambda x: x[0]['date'])
half = len(use_s)//2
for label, sub in (('前半', use_s[:half]), ('後半', use_s[half:])):
    print(f"  --- {label} ({sub[0][0]['date']}〜{sub[-1][0]['date']}, {len(sub)}R) ---")
    for b in ['Q1(前不利側)','Q2','Q3','Q4(前有利側)']:
        rs=[x for x in sub if band(x[1])==b]
        w_k=w_n=0; a_k=a_n=0
        for (_,_,h,rr) in rs:
            k,n=forward_top3(h); w_k+=k; w_n+=n
            k,n=ana_top3(h,7,12); a_k+=k; a_n+=n
        w=wilson(w_k,w_n); a=wilson(a_k,a_n)
        print(f"      {b:<14} R={len(rs):>4}  前1/3の3着内={w[0]:>6.2f}% (n={w_n:>5})   7-12人気3着内={a[0]:>5.2f}% (n={a_n:>5})")

# ---------- 7. flow_r の持続性 ----------
print("\n=== 検査C: 事前TBは当該レースのflow_rを予測するか (Pearson) ===")
xs=[x[1] for x in use]; ys=[fl(x[0]['flow_r']) for x in use]
pair=[(a,b) for a,b in zip(xs,ys) if a is not None and b is not None]
n=len(pair)
mx=st.mean([a for a,_ in pair]); my=st.mean([b for _,b in pair])
num=sum((a-mx)*(b-my) for a,b in pair)
den=math.sqrt(sum((a-mx)**2 for a,_ in pair)*sum((b-my)**2 for _,b in pair))
r=num/den
se=1/math.sqrt(n-3); zf=0.5*math.log((1+r)/(1-r))
lo=math.tanh(zf-Z*se); hi=math.tanh(zf+Z*se)
print(f"  n={n}  Pearson r={r:.4f}  95%CI [{lo:.4f}, {hi:.4f}]  r^2={r*r:.4f}")
for sd in ['芝','ダ']:
    p2=[(x[1],fl(x[0]['flow_r'])) for x in use if x[0]['sd']==sd]
    p2=[(a,b) for a,b in p2 if a is not None and b is not None]
    m1=st.mean([a for a,_ in p2]); m2=st.mean([b for _,b in p2])
    nu=sum((a-m1)*(b-m2) for a,b in p2)
    de=math.sqrt(sum((a-m1)**2 for a,_ in p2)*sum((b-m2)**2 for _,b in p2))
    print(f"    {sd}: n={len(p2)}  r={nu/de:.4f}")
