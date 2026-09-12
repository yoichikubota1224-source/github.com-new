# -*- coding: utf-8 -*-
# 入力の所在(このリポジトリ外):
#   TB日次バイアス_遡及1年_20250801-20260726.csv  = Google Drive より自己取得 (2026-09-10)
#       SHA-256 0bb3783aed94fbd5da7cb9eb188f60fbe8ee4b3e811e40a009318460b5393f1f / 249,763 bytes / 3,308行
#   荒れ傾向分析_全レース全頭_20250907-20260906.csv / レース単位_結果払戻_20250907-20260906.csv
#       = 受領済み「荒れ傾向分析CSV_過去1年」より
#   いずれも読み取りのみ。原本を変更していない。
"""TB日次バイアス_遡及1年 の独立整合性検査.
列定義は未提供のため、値の関係から定義を推定し、
「as-of(事前)」を名乗る列に当該レース自身の情報が混入していないかを検査する。
検査であり、TB診断の作成ではない。
"""
import csv, collections, statistics as st

P = "TB日次バイアス_遡及1年_20250801-20260726.csv"  # Drive自己取得
rows = []
with open(P, encoding='utf-8-sig') as f:
    for r in csv.DictReader(f):
        rows.append(r)

print(f"行数 = {len(rows)}")
cols = list(rows[0].keys())
print("列 =", cols)

def fl(v):
    v = (v or '').strip()
    if v == '': return None
    try: return float(v)
    except: return None

# 欠測
print("\n--- 欠測件数 ---")
for c in cols:
    miss = sum(1 for r in rows if (r[c] or '').strip()=='')
    print(f"  {c}: {miss} ({miss/len(rows)*100:.2f}%)")

# 値域
print("\n--- 値域 ---")
for c in ['N','flow_r','D_POSTDAY_LOO','D_PRE_RACE']:
    vs=[fl(r[c]) for r in rows]; vs=[v for v in vs if v is not None]
    print(f"  {c}: n={len(vs)} min={min(vs):.4f} max={max(vs):.4f} mean={st.mean(vs):.4f} median={st.median(vs):.4f}")

# 開催日×場 の構造
days = collections.Counter((r['date'], r['venue']) for r in rows)
print(f"\n開催日×場 = {len(days)}組 / 日付 = {len(set(r['date'] for r in rows))}日 / 場コード = {sorted(set(r['venue'] for r in rows))}")
print(f"1組あたりレース数: min={min(days.values())} max={max(days.values())}")

# 芝ダ
print("sd値 =", collections.Counter(r['sd'] for r in rows))

# ---- 検査1: D_PRE_RACE は「直前レースの flow_r」か? ----
by = collections.defaultdict(list)
for i,r in enumerate(rows):
    by[(r['date'], r['venue'])].append(r)

eq_prev_any = eq_prev_sd = eq_self_loo = 0
tested_pre = 0
first_race_pre_filled = 0
for k, rs in by.items():
    rs.sort(key=lambda r: int(r['race']))
    for j, r in enumerate(rs):
        pre = fl(r['D_PRE_RACE'])
        if pre is None: continue
        tested_pre += 1
        if j == 0: first_race_pre_filled += 1
        # 直前レース(全体)のflow_r
        if j>0 and fl(rs[j-1]['flow_r']) is not None and abs(pre - fl(rs[j-1]['flow_r']))<1e-9:
            eq_prev_any += 1
        # 同一sdの直前レースのflow_r
        prev_sd = [x for x in rs[:j] if x['sd']==r['sd']]
        if prev_sd and fl(prev_sd[-1]['flow_r']) is not None and abs(pre - fl(prev_sd[-1]['flow_r']))<1e-9:
            eq_prev_sd += 1
        # 自レースのLOO値と一致(=当日全体から自レースを除いた値。事前ではない)
        loo = fl(r['D_POSTDAY_LOO'])
        if loo is not None and abs(pre-loo)<1e-9:
            eq_self_loo += 1

print(f"\n--- 検査1: D_PRE_RACE の正体 (検査対象 {tested_pre}行) ---")
print(f"  直前レース(全体)のflow_rと一致      : {eq_prev_any} ({eq_prev_any/tested_pre*100:.2f}%)")
print(f"  同一sdの直前レースのflow_rと一致    : {eq_prev_sd} ({eq_prev_sd/tested_pre*100:.2f}%)")
print(f"  自レースのD_POSTDAY_LOOと一致        : {eq_self_loo} ({eq_self_loo/tested_pre*100:.2f}%)")
print(f"  第1レースでD_PRE_RACEが埋まっている  : {first_race_pre_filled}")

# ---- 検査2: D_PRE_RACE は 当日それまでの flow_r の累積平均か? ----
eq_cum_any = eq_cum_sd = 0
for k, rs in by.items():
    rs.sort(key=lambda r: int(r['race']))
    for j, r in enumerate(rs):
        pre = fl(r['D_PRE_RACE'])
        if pre is None or j==0: continue
        prevs=[fl(x['flow_r']) for x in rs[:j]]; prevs=[v for v in prevs if v is not None]
        if prevs and abs(pre - st.mean(prevs))<1e-9: eq_cum_any += 1
        p2=[fl(x['flow_r']) for x in rs[:j] if x['sd']==r['sd']]; p2=[v for v in p2 if v is not None]
        if p2 and abs(pre - st.mean(p2))<1e-9: eq_cum_sd += 1
print(f"\n--- 検査2: 累積平均か ---")
print(f"  当日それまで(全体)の累積平均と一致  : {eq_cum_any}")
print(f"  当日それまで(同sd)の累積平均と一致  : {eq_cum_sd}")

# ---- 検査3: D_POSTDAY_LOO は当日flow_rのLOO平均か? ----
eq_loo_any = eq_loo_sd = 0; tested_loo=0
for k, rs in by.items():
    for r in rs:
        loo = fl(r['D_POSTDAY_LOO'])
        if loo is None: continue
        tested_loo += 1
        others=[fl(x['flow_r']) for x in rs if x is not r]; others=[v for v in others if v is not None]
        if others and abs(loo - st.mean(others))<1e-9: eq_loo_any += 1
        o2=[fl(x['flow_r']) for x in rs if x is not r and x['sd']==r['sd']]; o2=[v for v in o2 if v is not None]
        if o2 and abs(loo - st.mean(o2))<1e-9: eq_loo_sd += 1
print(f"\n--- 検査3: D_POSTDAY_LOO の正体 (検査対象 {tested_loo}行) ---")
print(f"  当日(全体)LOO平均と一致 : {eq_loo_any} ({eq_loo_any/tested_loo*100:.2f}%)")
print(f"  当日(同sd)LOO平均と一致 : {eq_loo_sd} ({eq_loo_sd/tested_loo*100:.2f}%)")
