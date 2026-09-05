#!/usr/bin/env python3
"""Vライン条件を当方の一次データへ自前実装する。

出所について:
  Vライン馬は毎日新聞社・松沢一憲氏が提唱した予想法である（Cani自身がそう明記している）。
  Caniはその抽出プログラムを作成し結果を公開している立場。
  当方が使うのは「判定ロジック（着想）」のみであり、先方の集計値は一切使わない（層A）。
  したがって以下の数値はすべて【当方の一次集計】である。

判定ロジック（6条件、すべて過去レースのみを入力とする＝リーク構造なし）:
  対象レース日Dの出走馬Hについて、D-60日 <= 日付 < D のHの過去レースRで
    (1) Rでの着順 <= 10
    (2) Rでの向こう正面順位 <= 10
    (3) Rの3コーナーまたは4コーナーで2つ以上順位を下げた
    (4) Rのゴールでの順位上昇(4角順位-着順)がRの出走馬中で最大
    (5) Rで勝っていない（着順 != 1）
  を満たすものが存在し、かつ
    (6) R以降D未満のHのレースで1着が無い
  ときHをVライン馬とする。

通過順位の解釈（netkeiba の通過列は「通過したコーナーの数」だけ並ぶ）:
  p[-1]=4角, p[-2]=3角, p[-3]=向こう正面（4角レースの2角）
  len(p)==2 のレース（3角4角のみ）は向こう正面が存在しない。
    strict: 除外 / loose: p[0](=3角)を代用   ← 両方を出す
  len(p)==0（新潟千直など直線競走）は判定対象外。
"""
import json, glob, os, sys, math, collections, datetime

FULL = sys.argv[1] if len(sys.argv) > 1 else 'full'

def band(p):
    if p is None: return None
    if p <= 3:  return '本命'
    if p <= 6:  return '中穴'
    if p <= 12: return '穴'
    return '大穴'

def passing(s):
    if not s: return []
    out = []
    for x in s.replace('－', '-').split('-'):
        x = x.strip()
        if not x.isdigit(): return []
        out.append(int(x))
    return out

def load():
    races = []
    for f in sorted(glob.glob(os.path.join(FULL, '*.json'))):
        d = os.path.basename(f)[:8]
        day = datetime.date(int(d[:4]), int(d[4:6]), int(d[6:8]))
        for r in json.load(open(f)):
            r['date'] = day; r['ymd'] = d
            races.append(r)
    races.sort(key=lambda r: (r['date'], r['race_id']))
    return races

def mark_vrace(r, mode):
    """レースr内で「Vライン条件を満たす走り」をした馬の馬番集合を返す。"""
    hs = r['horses']
    gains = {}
    for h in hs:
        p = passing(h.get('passing'))
        if not p or h.get('chaku') is None: continue
        gains[h['uma']] = p[-1] - h['chaku']          # 4角順位 - 着順 = ゴールでの上昇幅
    if not gains: return set()
    gmax = max(gains.values())
    out = set()
    for h in hs:
        c = h.get('chaku'); p = passing(h.get('passing'))
        if c is None or not p: continue
        if c == 1 or c > 10: continue                  # (5)(1)
        if len(p) >= 3:   mukou = p[-3]
        elif mode == 'loose' and len(p) == 2: mukou = p[0]
        else: continue
        if mukou > 10: continue                        # (2)
        drop = -99
        if len(p) >= 3: drop = max(drop, p[-2] - p[-3])
        if len(p) >= 2: drop = max(drop, p[-1] - p[-2])
        if drop < 2: continue                          # (3)
        if gains[h['uma']] != gmax: continue           # (4)
        out.add(h['uma'])
    return out

def build(races, mode):
    """horse_id -> [(date, is_v, is_win)] を時系列で作る。"""
    hist = collections.defaultdict(list)
    for r in races:
        if r.get('jump'): continue
        v = mark_vrace(r, mode)
        for h in r['horses']:
            hid = h.get('horse_id')
            if not hid: continue
            hist[hid].append((r['date'], h['uma'] in v, h.get('chaku') == 1))
    for k in hist: hist[k].sort(key=lambda t: t[0])
    return hist

def is_vline(hist, hid, D):
    """Dの時点でVライン馬か。Dより前のレースだけを見る。"""
    hs = hist.get(hid)
    if not hs: return False
    lo = D - datetime.timedelta(days=60)
    cand = None
    for (d, isv, win) in hs:
        if d >= D: break
        if isv and lo <= d: cand = d          # 直近のV走を採る
    if cand is None: return False
    for (d, isv, win) in hs:                  # (6) V走以降Dまでに勝っていない
        if cand < d < D and win: return False
    return True

def wilson(k, n, z=1.959963985):
    if n == 0: return (0.0, 0.0, 0.0)
    p = k / n; d = 1 + z*z/n
    c = (p + z*z/(2*n)) / d
    hw = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / d
    return (p, max(0.0, c-hw), min(1.0, c+hw))

def main():
    races = load()
    print(f'[実] 読み込み: {len(races)}R  期間 {races[0]["ymd"]}〜{races[-1]["ymd"]}')
    for mode in ('strict', 'loose'):
        hist = build(races, mode)
        print(f'\n===== 向こう正面の扱い: {mode} =====')
        # 集計対象は平地のみ・人気と着順が取れている馬
        agg = collections.defaultdict(lambda: collections.Counter())
        nrace = 0; nvrace = 0
        comp_all = collections.Counter(); comp_v = collections.Counter()
        for r in races:
            if r.get('jump') or r.get('dead_heat'): continue
            D = r['date']
            fuku_pay = r.get('pay', {}).get('複勝') or []
            nf = len(fuku_pay)
            has_v = False
            for h in r['horses']:
                hid = h.get('horse_id'); c = h.get('chaku'); pop = h.get('pop')
                if not hid or c is None or pop is None: continue
                v = is_vline(hist, hid, D)
                if v: has_v = True
                b = band(pop)
                for key in ((mode, 'V' if v else 'N', b), (mode, 'V' if v else 'N', 'ALL')):
                    a = agg[key]
                    a['n'] += 1
                    a['w'] += (c == 1)
                    a['p2'] += (c <= 2)
                    a['p3'] += (c <= 3)
                    if c == 1 and h.get('odds'): a['tan'] += int(h['odds'] * 100)
                    if c <= nf: a['fuku'] += fuku_pay[c-1]
                    a['nf'] += (nf > 0)
            nrace += 1; nvrace += has_v
            # レース単位: 3着以内の人気帯構成
            t3 = sorted([h for h in r['horses'] if h.get('chaku') in (1,2,3) and h.get('pop')],
                        key=lambda h: h['chaku'])
            if len(t3) == 3:
                comp = '＋'.join(sorted([band(h['pop']) for h in t3],
                                        key=lambda b: ['本命','中穴','穴','大穴'].index(b)))
                comp_all[comp] += 1
                if has_v: comp_v[comp] += 1
        print(f'[実] レース数 {nrace} / Vライン馬を含むレース {nvrace} ({nvrace/nrace*100:.4f}%)')
        print(f'\n{"帯":<6}{"群":<4}{"頭数":>8}{"勝率":>9}{"連対":>9}{"複勝":>9}{"複勝95%CI":>22}{"単回収":>9}{"複回収":>9}')
        for b in ('ALL','本命','中穴','穴','大穴'):
            for g in ('V','N'):
                a = agg.get((mode,g,b))
                if not a or a['n'] == 0: continue
                n = a['n']
                p, lo, hi = wilson(a['p3'], n)
                print(f'{b:<6}{g:<4}{n:>8}{a["w"]/n*100:>8.4f}%{a["p2"]/n*100:>8.4f}%'
                      f'{p*100:>8.4f}%   [{lo*100:>7.4f}%,{hi*100:>7.4f}%]'
                      f'{a["tan"]/n:>8.2f}%{(a["fuku"]/a["nf"] if a["nf"] else 0):>8.2f}%')
        print(f'\n[実] 3着以内の帯構成（Vライン馬を含むレース vs 全体）')
        print(f'{"構成":<14}{"全体":>8}{"割合":>10}{"V含":>8}{"割合":>10}{"比":>8}')
        tot = sum(comp_all.values()); totv = sum(comp_v.values())
        for comp, n in comp_all.most_common(8):
            nv = comp_v[comp]
            ra = n/tot*100; rv = (nv/totv*100) if totv else 0
            print(f'{comp:<14}{n:>8}{ra:>9.4f}%{nv:>8}{rv:>9.4f}%{(rv/ra if ra else 0):>8.4f}')
        a_all = comp_all.get('本命＋穴＋穴', 0)
        a_v   = comp_v.get('本命＋穴＋穴', 0)
        print(f'\n[実] A構成(穴＋穴＋本命=正規化後 本命＋穴＋穴): 全体 {a_all}/{tot}={a_all/tot*100:.4f}% '
              f'／ V含 {a_v}/{totv}={(a_v/totv*100 if totv else 0):.4f}%')

main()
