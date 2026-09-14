#!/usr/bin/env python3
"""期待値の基準値を荒れ傾向分析CSVから算出する（再現用）。

用途:
  ChatGPT依頼②「主要数値を再現できる材料」への対応。本スクリプト単体で
  人気帯別の勝率・3着内率・単複回収率、穴帯の同時入着率（ワイド/3連複の
  的中確率）、および機械的購入の回収率を再現する。

実行方法:
  python3 scripts/ev_baseline.py <荒れ傾向分析_全レース全頭_*.csv>

入力（当方は未コミット。所在は predictions/ops_review/ の受領確認docを参照）:
  荒れ傾向分析CSV 過去1年 20250907-20260906 / 全レース全頭 48,274行62列
  必要列: racekey, 人気, 着順, 単勝, 複勝, 3連複払戻, 障害フラグ, 新馬フラグ, 出走頭数

母集団の絞り込み（次走期待好走馬docと同一条件）:
  平地(障害フラグ=0) ∧ 非新馬(新馬フラグ=0) ∧ 出走頭数>=14

購入方式の前提:
  全頭均等1点購入を仮定した事後研究の理論値。実購入ではない。
  払戻列は100円あたりの円単位。回収率は 払戻合計 / (点数×100) 。

信頼区間の方法:
  Wilson score interval（z=1.96）。比率にのみ適用し、回収率には付けない
  （回収率は稀な高配当が分散を支配し、正規近似が妥当でないため）。
"""
import csv, sys, math, collections, statistics as st

Z = 1.96

def to_int(v):
    try: return int(str(v).strip())
    except Exception: return None

def to_float(v):
    try: return float(str(v).strip().replace(',', ''))
    except Exception: return None

def wilson(k, n, z=Z):
    """比率のWilson score interval。戻り値は百分率 (点推定, 下限, 上限)。"""
    if n == 0:
        return (0.0, 0.0, 0.0)
    ph = k / n
    d = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / d
    m = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / d
    return ph * 100, (c - m) * 100, (c + m) * 100

def is_flat_nonmaiden(r):
    return (str(r['障害フラグ']).strip() in ('0', '', 'False', 'false')
            and str(r['新馬フラグ']).strip() in ('0', '', 'False', 'false'))

def load(path):
    rows = list(csv.DictReader(open(path, encoding='utf-8-sig')))
    sel = [r for r in rows
           if to_int(r['着順']) and to_int(r['人気'])
           and is_flat_nonmaiden(r)
           and (to_int(r['出走頭数']) or 0) >= 14]
    return rows, sel

def band_table(sel):
    """人気帯別の勝率・3着内率・単複回収率。"""
    print(f"\n{'人気帯':12}{'n':>8}{'勝率%':>8}{'勝率95%CI':>18}"
          f"{'3着内率%':>10}{'単回収%':>9}{'複回収%':>9}")
    print("-" * 76)
    out = []
    for lab, lo, hi in [("1番人気", 1, 1), ("1-3人気", 1, 3), ("4-6人気", 4, 6),
                        ("7-12人気", 7, 12), ("13人気以下", 13, 99)]:
        g = [r for r in sel if lo <= to_int(r['人気']) <= hi]
        if not g:
            continue
        w = sum(1 for r in g if to_int(r['着順']) == 1)
        t3 = sum(1 for r in g if to_int(r['着順']) <= 3)
        tan = sum((to_float(r['単勝']) or 0) for r in g if to_int(r['着順']) == 1)
        fuku = sum((to_float(r['複勝']) or 0) for r in g)
        wp, wl, wh = wilson(w, len(g))
        tp, _, _ = wilson(t3, len(g))
        print(f"{lab:12}{len(g):>8,}{wp:>8.2f}  [{wl:5.2f}, {wh:5.2f}]"
              f"{tp:>10.2f}{tan/len(g):>9.1f}{fuku/len(g):>9.1f}")
        out.append((lab, len(g), wp, tp, tan/len(g), fuku/len(g)))
    return out

def joint_rates(sel, lo=7, hi=12):
    """穴帯の同時入着率。単純積との比を出す（積の向きは事前に決まらない）。"""
    byrace = collections.defaultdict(dict)
    for r in sel:
        byrace[r['racekey']][to_int(r['人気'])] = to_int(r['着順'])
    races = [d for d in byrace.values() if len(d) >= 14]

    n1 = t1 = 0
    for d in races:
        for k, ch in d.items():
            if lo <= k <= hi:
                n1 += 1
                t1 += (ch <= 3)
    p1 = t1 / n1

    npair = tpair = 0
    ntri = ttri = 0
    for d in races:
        ks = sorted(k for k in d if lo <= k <= hi)
        for a in range(len(ks)):
            for b in range(a + 1, len(ks)):
                npair += 1
                tpair += (d[ks[a]] <= 3 and d[ks[b]] <= 3)
                for c in range(b + 1, len(ks)):
                    ntri += 1
                    ttri += (d[ks[a]] <= 3 and d[ks[b]] <= 3 and d[ks[c]] <= 3)
    pj = tpair / npair
    pt = ttri / ntri
    print(f"\n【同時入着率 {lo}-{hi}人気帯】対象 {len(races):,}R")
    print(f"  単頭3着内率        {p1*100:8.2f}%   (n={n1:,})")
    print(f"  2頭ともに3着内(実測){pj*100:8.4f}%   (ペア n={npair:,})")
    print(f"    単純積 p^2        {p1*p1*100:8.4f}%   実測/積 = {pj/(p1*p1):.3f}倍"
          f"  → 積は{'過小' if pj > p1*p1 else '過大'}")
    print(f"  3頭で1-3着(実測)   {pt*100:8.5f}%   (三つ組 n={ntri:,})")
    print(f"    単純積 p^3        {p1**3*100:8.5f}%   実測/積 = {pt/(p1**3):.3f}倍"
          f"  → 積は{'過小' if pt > p1**3 else '過大'}")
    return races, p1, pj, pt

def mechanical_trifecta(races_full, lo=7, hi=12):
    """穴帯から3頭の全組合せを1点ずつ買った場合の回収率（理論値）。"""
    combos = hits = 0
    ret = 0.0
    for d in races_full:
        if not d['pay']:
            continue
        ks = [k for k in d['h'] if lo <= k <= hi]
        n = len(ks)
        combos += n * (n - 1) * (n - 2) // 6
        top3 = {k for k in d['h'] if d['h'][k] <= 3}
        if len([k for k in ks if k in top3]) == 3:
            hits += 1
            ret += d['pay'] / 100.0
    print(f"\n【戦略A: {lo}-{hi}人気から3頭の全組合せを1点ずつ購入】")
    print(f"  購入点数 {combos:,}点 / 的中 {hits}R")
    print(f"  的中率 {hits/combos*100:.5f}%   回収率 {ret/combos*100:.2f}%")
    if hits:
        print(f"  的中時の平均払戻 {ret/hits*100:,.0f}円/100円")
    print(f"  ※3連複の設定払戻率は75.0%。これを下回るのは穴帯が過剰に買われていることを示す")
    return combos, hits, ret / combos * 100

def payout_split(races_full, lo=7):
    """3着内に穴を含むか否かで3連複払戻を分ける。"""
    hp = [d for d in races_full if d['pay']]
    inc = [d for d in hp if any(k >= lo for k in d['h'] if d['h'][k] <= 3)]
    noinc = [d for d in hp if not any(k >= lo for k in d['h'] if d['h'][k] <= 3)]
    print(f"\n【3着内に{lo}番人気以下を含むか】払戻あり {len(hp):,}R")
    print(f"  含む   {len(inc):,}R ({len(inc)/len(hp)*100:.1f}%)  "
          f"3連複 中央値 {st.median([d['pay'] for d in inc]):>9,.0f}円  "
          f"平均 {st.mean([d['pay'] for d in inc]):>9,.0f}円")
    print(f"  含まない {len(noinc):,}R ({len(noinc)/len(hp)*100:.1f}%)  "
          f"3連複 中央値 {st.median([d['pay'] for d in noinc]):>9,.0f}円")

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    path = sys.argv[1]
    rows, sel = load(path)
    nr = len({r['racekey'] for r in sel})
    print(f"入力 {path}")
    print(f"全行 {len(rows):,} → 絞り込み後 {len(sel):,}頭 / {nr:,}R"
          f"（平地・非新馬・出走頭数>=14）")

    # 1番人気（絞り込みなし・全レース）
    fin = [r for r in rows if to_int(r['着順']) and to_int(r['人気'])]
    fav = [r for r in fin if to_int(r['人気']) == 1]
    w = sum(1 for r in fav if to_int(r['着順']) == 1)
    p, lo_, hi_ = wilson(w, len(fav))
    print(f"\n【1番人気・全レース】n={len(fav):,}")
    print(f"  勝率       {p:6.2f}%  95%CI [{lo_:.2f}, {hi_:.2f}]")
    print(f"  負ける確率 {100-p:6.2f}%  95%CI [{100-hi_:.2f}, {100-lo_:.2f}]")

    band_table(sel)

    byrace = collections.defaultdict(lambda: {'h': {}, 'pay': None})
    for r in sel:
        byrace[r['racekey']]['h'][to_int(r['人気'])] = to_int(r['着順'])
        if byrace[r['racekey']]['pay'] is None:
            byrace[r['racekey']]['pay'] = to_float(r['3連複払戻'])
    races_full = [d for d in byrace.values() if len(d['h']) >= 14]

    joint_rates(sel)
    mechanical_trifecta(races_full)
    payout_split(races_full)

if __name__ == '__main__':
    main()
