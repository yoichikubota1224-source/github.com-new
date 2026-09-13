#!/usr/bin/env python3
# §12 事後検証(先行実施) — 基準単勝オッズの「基準比」に信号があるかを、既存データで測る。
#
# ⚠ 現在オッズ(前日・中間・直前)は未取得のため、ここでは **確定単勝オッズ** を用いる。
#    これは依頼書が想定する「現在オッズ」ではない。確定は締切までの全資金を含むため、
#    前日オッズでの乖離とは別物である。本検証は「上限の目安」として読むこと。
#    §11の「確定人気を事前分析へ混入しない」に抵触しないよう、これは事後検証としてのみ行う。
#
# 統治: SHADOW_ONLY / RULE_PROMOTION=NONE / PURCHASE_ALLOWED=NO
import json, glob, math, os, collections, random

SP = '/tmp/claude-0/-home-user-github-com-new/47c1892c-ddc4-50e4-8b6f-3403a9782673/scratchpad'
GH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MISSING = '[不足]'


def load_kijun():
    """ウマトク kijtanodds / STRIDE standard_odds から基準単勝を集める。両者は一致を確認済み。"""
    out = {}
    for day in ('20260822', '20260823'):
        for pat, kod, kpop in (('umatoku_*.json', 'kijtanodds', 'kijtanninki'),
                               ('stride_*.json', 'standard_odds', 'popularity')):
            for p in glob.glob(f'{SP}/race_day_{day}/browser_stage*/{pat}'):
                try:
                    d = json.load(open(p))
                except Exception:
                    continue
                if not isinstance(d, dict) or 'horses' not in d:
                    continue
                for h in d['horses']:
                    try:
                        u = int(str(h['umaban']).strip())
                        o = float(str(h.get(kod) or '').strip())
                        r = int(float(str(h.get(kpop) or '').strip()))
                    except (ValueError, TypeError, KeyError):
                        continue
                    if o <= 0:
                        continue
                    out.setdefault((d['date'], d['venue'], int(d['race']), u), (o, r))
    return out


def load_results():
    rows = []
    for day, path in (('2026-08-22', f'{GH}/predictions/20260823/results_20260822.json'),
                      ('2026-08-23', f'{GH}/predictions/20260823/results_20260823.json')):
        j = json.load(open(path))
        for x in (j if isinstance(j, list) else list(j.values())):
            for h in x['horses']:
                if h.get('chakujun') is None or not h.get('odds') or not h.get('pop'):
                    continue
                rows.append(dict(day=day, venue=x['venue'], race=x['r'], umaban=h['umaban'],
                                 name=h['name'], chaku=h['chakujun'], odds=float(h['odds']),
                                 pop=int(h['pop'])))
    return rows


def wilson(k, n, z=1.96):
    if not n:
        return (0.0, 1.0)
    p, d = k / n, 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def race_boot(groups, sel, B=600, seed=31):
    keys = list(groups)
    rnd = random.Random(seed)
    out = []
    for _ in range(B):
        st = rt = 0
        for _ in range(len(keys)):
            for h in groups[rnd.choice(keys)]:
                if sel(h):
                    st += 1
                    rt += h['odds'] if h['chaku'] == 1 else 0.0
        if st:
            out.append(100 * rt / st)
    out.sort()
    return (out[int(.025 * len(out))], out[int(.975 * len(out))]) if out else (MISSING, MISSING)


def main():
    K = load_kijun()
    R = load_results()
    rows, miss = [], 0
    for r in R:
        k = K.get((r['day'], r['venue'], r['race'], r['umaban']))
        if not k:
            miss += 1
            continue
        base, brank = k
        r = dict(r, kijun=base, kijun_rank=brank,
                 ratio=round(r['odds'] / base, 3),
                 rank_diff=r['pop'] - brank)
        rows.append(r)
    print(f'結果 {len(R)}頭 / 基準オッズ結合 {len(rows)}頭 ({100*len(rows)/len(R):.1f}%) / 未結合 {miss}頭')
    print(f'⚠ 「現在オッズ」ではなく**確定単勝オッズ**を用いた事後検証である\n')

    groups = collections.defaultdict(list)
    for r in rows:
        groups[(r['day'], r['venue'], r['race'])].append(r)

    def rep(label, sub, ind=''):
        n = len(sub)
        if not n:
            print(f'{ind}{label:<26} n=   0'); return
        w = sum(1 for x in sub if x['chaku'] == 1)
        k3 = sum(1 for x in sub if x['chaku'] <= 3)
        roi = sum(x['odds'] for x in sub if x['chaku'] == 1) / n * 100
        lo, hi = wilson(k3, n)
        ids = {id(x) for x in sub}
        bl, bh = race_boot(groups, lambda h: id(h) in ids)
        print(f'{ind}{label:<26} n={n:>4}  勝{w:>3}({100*w/n:>4.1f}%)  3着内{k3:>4}({100*k3/n:>4.1f}%)'
              f' CI[{100*lo:>4.1f},{100*hi:>5.1f}]  単回収{roi:>6.1f}%')

    print('=== ① 基準比(確定単勝÷基準単勝)の五分位 ===')
    srt = sorted(rows, key=lambda r: r['ratio'])
    for i in range(5):
        a, b = i * len(srt) // 5, (i + 1) * len(srt) // 5
        q = srt[a:b]
        rep(f'Q{i+1} 比{q[0]["ratio"]:.2f}〜{q[-1]["ratio"]:.2f}', q)

    print('\n=== ② 確定7〜12番人気帯に限定 ===')
    band = [r for r in rows if 7 <= r['pop'] <= 12]
    rep('7〜12人気 全体', band)
    s2 = sorted(band, key=lambda r: r['ratio'])
    for i in range(3):
        a, b = i * len(s2) // 3, (i + 1) * len(s2) // 3
        q = s2[a:b]
        rep(f'  比 {q[0]["ratio"]:.2f}〜{q[-1]["ratio"]:.2f}', q, '  ')

    print('\n=== ③ 基準人気順位差(確定人気 − 基準人気) ===')
    for lab, f in (('市場が大きく買った (差≤−3)', lambda r: r['rank_diff'] <= -3),
                   ('やや買った (−2〜−1)', lambda r: -2 <= r['rank_diff'] <= -1),
                   ('基準どおり (0)', lambda r: r['rank_diff'] == 0),
                   ('やや売れ残り (+1〜+2)', lambda r: 1 <= r['rank_diff'] <= 2),
                   ('大きく売れ残り (差≥+3)', lambda r: r['rank_diff'] >= 3)):
        rep(lab, [r for r in rows if f(r)])

    print('\n=== ④ 基準人気そのものの精度(基準人気帯別) ===')
    for lo, hi, lab in ((1, 3, '基準1〜3人気'), (4, 6, '基準4〜6人気'),
                        (7, 12, '基準7〜12人気'), (13, 99, '基準13人気以下')):
        rep(lab, [r for r in rows if lo <= r['kijun_rank'] <= hi])

    print('\n=== ⑤ 基準人気 vs 確定人気 の一致度 ===')
    same = sum(1 for r in rows if r['rank_diff'] == 0)
    w1 = sum(1 for r in rows if abs(r['rank_diff']) <= 1)
    w3 = sum(1 for r in rows if abs(r['rank_diff']) >= 3)
    print(f'  完全一致 {same}/{len(rows)} = {100*same/len(rows):.1f}%')
    print(f'  ±1以内   {w1}/{len(rows)} = {100*w1/len(rows):.1f}%')
    print(f'  3段階以上のズレ {w3}/{len(rows)} = {100*w3/len(rows):.1f}%')
    rr = [r['ratio'] for r in rows]
    rr.sort()
    print(f'  基準比の分布: 最小{rr[0]:.2f} / 25%{rr[len(rr)//4]:.2f} / 中央{rr[len(rr)//2]:.2f}'
          f' / 75%{rr[3*len(rr)//4]:.2f} / 最大{rr[-1]:.2f}')

    print('\n```text\nSTATUS                   = SHADOW_ONLY\nPREDICTIVE_EFFECTIVENESS = NOT_EVALUATED\n'
          'RULE_PROMOTION           = NONE\nPURCHASE_ALLOWED         = NO\n```')


if __name__ == '__main__':
    main()
