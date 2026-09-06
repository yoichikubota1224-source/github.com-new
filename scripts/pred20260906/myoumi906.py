#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2026-09-06 オッズ妙味分析（全35Rを計算し、荒れ選定レースを報告に使う）。9/5 myoumi905 と同じ手法。
- 市場p3   : JRDB基準複勝の逆数をレース内でΣ=3.0に正規化（控除率を剥がす）。基準複勝は前日の予想オッズであり実オッズではない
- 較正p3   : 人気別3着内率（8/22-23の自前標本・ドリフト補正後 predictions/20260829/人気別3着内率_ドリフト補正後.json）をΣ=3.0に正規化。9/5用の再較正はしていない
- 補正差   : 100×(市場p3 − 較正p3)。＋=市場が強気／−=市場が弱気
- 帯調整   : 補正差から当日35Rの同一基準人気の平均を引いた残差。z=帯内標準化。診断であって補正ではない
- 乖離     : コンピ順位 − 新聞合計値順位(同値は平均順位)。＋=指数が市場より高評価（8/30と同定義）
- 乖離IDM  : 基準単勝順位 − IDM順位(同値は平均順位)。＋=IDMが市場より高評価（本報で追加。合計値=IDM+3+調教指数−C_r の依存を避けIDM単独で見る）
- 支持係数 : 8/30定義から黄金律・厩舎ROI（9/5未取得）を除いた本数。基準人気とρ≈+0.7で連動するため絶対値で穴を判定しない
⚠ are_score_v21 の4出力は意思決定利用HOLDのため使わない。買い目・点数・資金配分・購入可否・最終印・軸は出さない。運勢×は消し根拠にしない。
"""
import json, csv, os, math, statistics as st, collections
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
D = os.path.join(REPO, 'predictions', '20260906')
SP = '/tmp/claude-0/-home-user-github-com-new/47c1892c-ddc4-50e4-8b6f-3403a9782673/scratchpad'
PACK = os.environ.get('PACK906', os.path.join(SP, 'd0906', 'pack.json'))
T = json.load(open(os.path.join(D, 'toukei_20260906.json')))['races']
C = json.load(open(os.path.join(D, 'chokyo_20260906.json')))['horses']
U = json.load(open(os.path.join(D, 'unsei_20260906.json')))['horses']
CM = {(x['ba'], x['r'], x['uma']): x for x in json.load(open(os.path.join(D, 'composite.json')))['rows']}
J = {(x['ba'], x['r'], x['uma']): x for x in json.load(open(os.path.join(D, 'jisou906.json')))['hits']}
DRIFT = {int(k): v for k, v in json.load(open(os.path.join(REPO, 'predictions', '20260829', '人気別3着内率_ドリフト補正後.json'))).items()}
P = json.load(open(PACK))
UM = {(r['race_id'], int(r['馬番'])): r for r in P['ウマトク']}   # 波乱度・1番人気信頼度・妙味度は英字のため toukei では None になっている（build905 v3.2 の num() が落とす）＝訂正候補
H5 = json.load(open(os.path.join(SP, 'hist5y.json')))
import sys
SEL = [tuple(x.split(':')) for x in os.environ.get('SEL906', '').split(',') if x]
SEL = [(b, int(r)) for b, r in SEL]   # 荒れ選定レース（環境変数で受ける。空なら全35R）
MYOUMI_GOOD = ('Ｓ', 'ＡＡ', 'Ａ', 'S', 'AA', 'A')   # 8/30 と同じ

def avg_rank(hs, key, rev=True):
    v = sorted([(h['uma'], h[key]) for h in hs if h.get(key) is not None], key=lambda z: -z[1] if rev else z[1])
    rk, i = {}, 0
    while i < len(v):
        j = i
        while j + 1 < len(v) and v[j+1][1] == v[i][1]: j += 1
        for k in range(i, j+1): rk[v[k][0]] = (i + j) / 2 + 1
        i = j + 1
    return rk

def pkubun(t6):
    return 'P1' if t6 <= 205 else 'P2' if t6 <= 208 else 'P3' if t6 <= 211 else 'P4' if t6 <= 215 else 'P5' if t6 <= 219 else 'P6'

out = []
for rc in T:
    hs = [h for h in rc['horses'] if not h['scratched']]
    n = len(hs); third = max(1, round(n / 3))   # 8/30 と同じ定義
    s = sum(1/h['kijun_fuku'] for h in hs if h.get('kijun_fuku'))
    mkt = {h['uma']: (1/h['kijun_fuku'])*3/s for h in hs if h.get('kijun_fuku')}
    cal_sum = sum(DRIFT[min(int(h['kijun_ninki']), 16)] for h in hs if h.get('kijun_ninki'))
    cal_k = 3.0/cal_sum if cal_sum else 1.0
    r_tot = avg_rank(hs, 'total'); r_idm = avg_rank(hs, 'IDM'); r_time = avg_rank(hs, 'time_max'); r_last = avg_rank(hs, 'time_1')
    r_ten = avg_rank(hs, 'tenkai', rev=False); r_dist = avg_rank(hs, 'time_dist'); r_crs = avg_rank(hs, 'time_course'); r_geki = avg_rank(hs, 'geki')
    cz = {h['uma']: ((C.get(f"{rc['ba']}|{rc['r']}|{h['uma']}", {}).get('last_d2') or {}).get('z1f')) for h in hs}
    r_cho = avg_rank([dict(uma=u, z=z) for u, z in cz.items() if z is not None], 'z', rev=False)
    cs = sorted([h['compi'] for h in hs if h['compi'] is not None], reverse=True)
    c1, t6 = (cs[0] if cs else None), (sum(cs[:3]) if len(cs) >= 3 else None)
    um0 = UM.get((rc['race_id'], hs[0]['uma']), {})
    rows = []
    for h in hs:
        u = h['uma']; nin = h.get('kijun_ninki'); key = f"{rc['ba']}|{rc['r']}|{u}"
        cal_raw = DRIFT.get(min(int(nin), 16)) if nin else None
        cal = cal_raw*cal_k if cal_raw is not None else None
        hosei = 100*(mkt[u]-cal) if (u in mkt and cal is not None) else None
        cr, tr = h.get('compi_rank'), r_tot.get(u)
        uu = U.get(key, {}); cm = CM.get((rc['ba'], rc['r'], u), {}); c = C.get(key, {}); j = J.get((rc['ba'], rc['r'], u))
        unsei = uu.get('jockey_mark_usable')
        sup = []
        if r_idm.get(u) and r_idm[u] <= third: sup.append(f"⑧IDM{r_idm[u]:g}位")
        if r_time.get(u) and r_time[u] <= third: sup.append(f"⑧タイム{r_time[u]:g}位")
        elif r_last.get(u) and r_last[u] <= third: sup.append(f"⑧前走時計{r_last[u]:g}位")
        if cr and cr <= third: sup.append(f"④コンピ{cr:g}位")
        if unsei in ('◎◎', '◎'): sup.append(f"⑨運勢{unsei}")
        if r_ten.get(u) and r_ten[u] <= third and (h.get('deokure') is not None and h['deokure'] <= 20): sup.append(f"⑬展開{r_ten[u]:g}位/出遅{h['deokure']:.0f}%")
        if r_cho.get(u) and r_cho[u] <= third: sup.append(f"⑥調教z{r_cho[u]:g}位")
        if (tr and tr <= 3) or (h.get('myoumi') in MYOUMI_GOOD): sup.append(f"⑦新聞(合計{tr if tr else '-'}位/妙味{h.get('myoumi') or '-'})")
        if h.get('MB') or h.get('UL'): sup.append('⑤' + '+'.join([x for x in (f"MB{len(h['MB'])}" if h.get('MB') else '', f"UL{len(h['UL'])}" if h.get('UL') else '') if x]))
        gm = None
        try: gm = float(h.get('geki_mark')) if h.get('geki_mark') not in (None, '') else None
        except ValueError: gm = None
        if (gm or 0) >= 2 or (r_geki.get(u) and r_geki[u] <= 3): sup.append(f"激走(印{h.get('geki_mark') or 0}/指数{r_geki.get(u, '-')}位)")
        if (r_dist.get(u) and r_dist[u] <= third) or (r_crs.get(u) and r_crs[u] <= third): sup.append('①適性')
        hist = sorted(H5.get(h['name'], []), key=lambda x: x['date'], reverse=True)[:3]
        rows.append(dict(uma=u, name=h['name'], jockey=h['jockey'], ninki=nin, tan=h['kijun_tan'], fuku=h['kijun_fuku'],
            mkt_p3=round(100*mkt[u], 1) if u in mkt else None, cal_p3=round(100*cal, 1) if cal is not None else None, cal_k=round(cal_k, 4),
            hosei=round(hosei, 1) if hosei is not None else None,
            compi_rank=cr, total_rank=tr, idm_rank=r_idm.get(u), time_rank=r_time.get(u),
            kairi=(cr - tr) if (cr is not None and tr is not None) else None,
            kairi_idm=(nin - r_idm[u]) if (nin and r_idm.get(u)) else None,
            kairi_time=(nin - r_time[u]) if (nin and r_time.get(u)) else None,
            nsup=len(sup), support=sup, IDM=h['IDM'], compi=h['compi'], uma_idx=h['uma_idx'], time_max=h['time_max'], time_5avg=h['time_5avg'], time_course=h['time_course'],
            tenkai=h['tenkai'], okure=h['deokure'], kyaku=h['kyakushitsu'], kin=h['kin'], rotation=h['rotation'], zen3f=h['zen3f_rank'], shobu=h['shobu_rank'], gmae=h['gmae_rank'],
            oikiri=h['saishu_oikiri'], chokyo_status=c.get('status'), chokyo_c2=c.get('best_c2'), chokyo_z=cz.get(u), chokyo_z_rank=r_cho.get(u),
            unsei=unsei, unsei_raw=uu.get('jockey_mark'), unsei_kubun=uu.get('jockey_kubun'), myoumi=h.get('myoumi'), sinrai=h.get('sinrai'), geki_mark=h.get('geki_mark'),
            flags=cm.get('flags'), jisou=(f"{j['tier']}/sc{j['score']}" if j else None),
            jisou_prev=(f"{j['zen_date']} {j['zen_ba']}{j['zen_course']} {j['zen_pop']}人気{j['zen_chaku']}着 上がり{j['zen_l3rank']}位" if j else None),
            hist=[f"{x['date'][4:6]}/{x['date'][6:]} {x['td']}{x['dist']} {x['chaku']}着 L3F{x['last3f']}" for x in hist],
            hist_gap=('[不足] 直近走(' + str(h['rotation']) + ')が当方5年DBに無い' if (h['rotation'] in ('連闘', '中1週', '中2週') and hist and hist[0]['date'] < '20260815') else None)))
    out.append(dict(ba=rc['ba'], r=rc['r'], title=rc['title'], meta=rc['meta'], td=rc['td'], dist=rc['dist'], n=n, third=third, o1=rc['o1'],
        c1=c1, t6=t6, pattern=(pkubun(t6) if t6 else None), ryoritsu=(bool(c1 and t6) and c1 <= 76 and pkubun(t6) in ('P1', 'P2', 'P3')),
        haran=um0.get('波乱度') or None, fav_sinrai=um0.get('1番人気信頼度') or None, fav_myoumi=um0.get('1番人気妙味度') or None,
        v21='HOLD（4出力とも意思決定利用停止）', rows=rows))
# 帯調整（当日35R）
band = collections.defaultdict(list)
for o in out:
    for h in o['rows']:
        if h['ninki'] and h['hosei'] is not None: band[h['ninki']].append(h['hosei'])
mu = {k: sum(v)/len(v) for k, v in band.items()}; sd = {k: (st.pstdev(v) if len(v) > 1 else 1.0) or 1.0 for k, v in band.items()}
for o in out:
    for h in o['rows']:
        if h['ninki'] and h['hosei'] is not None:
            h['hosei_resid'] = round(h['hosei'] - mu[h['ninki']], 2); h['hosei_z'] = round((h['hosei'] - mu[h['ninki']])/sd[h['ninki']], 2)
        else: h['hosei_resid'] = h['hosei_z'] = None
# 補正差と基準人気の連動（診断）
xs = [(h['ninki'], h['hosei']) for o in out for h in o['rows'] if h['ninki'] and h['hosei'] is not None]
def spearman(a, b):
    def rk(v):
        s_ = sorted(range(len(v)), key=lambda i: v[i]); r = [0]*len(v); i = 0
        while i < len(s_):
            j = i
            while j+1 < len(s_) and v[s_[j+1]] == v[s_[i]]: j += 1
            for k in range(i, j+1): r[s_[k]] = (i+j)/2+1
            i = j+1
        return r
    ra, rb = rk(a), rk(b); n_ = len(a); ma, mb = sum(ra)/n_, sum(rb)/n_
    cov = sum((x-ma)*(y-mb) for x, y in zip(ra, rb)); va = sum((x-ma)**2 for x in ra); vb = sum((y-mb)**2 for y in rb)
    return cov/math.sqrt(va*vb) if va and vb else 0.0
rho = spearman([x[0] for x in xs], [x[1] for x in xs])
diag = dict(n_horses=len(xs), rho_ninki_hosei=round(rho, 3), band_mean={k: round(v, 2) for k, v in sorted(mu.items())}, band_n={k: len(v) for k, v in sorted(band.items())})
sel = [o for o in out if (not SEL) or ((o['ba'], o['r']) in SEL)]
DEF_VERSION = {'穴帯': '基準人気7〜12 (v1 2026-08-29〜)', '補正差': '100×(市場p3−較正p3)・両者Σ=3.0正規化 (v2 2026-08-30〜)', '帯調整': '補正差−当日35Rの同人気平均 (v1 2026-08-30〜)',
    '乖離': 'コンピ順位 − 合計値の当方順位（合計値が同値の馬は平均順位）(v1 2026-08-29〜9/6同一実装)。＋＝指数(新聞合計)が市場(コンピ)より高評価。⚠紙面の合計値順位(同順なし1..n)とは同値馬で差が出る(9/6は483頭中138頭・符号反転11頭)。定義は動かさず、紙面順位は total_rank_paper として併記', '乖離IDM': '基準単勝順位−IDM順位 (v1 2026-09-05〜。9/5結果で符号逆＝採用保留)',
    '二条件クロス': 'v2 = 穴帯 ∧ 補正差<0 ∧ 乖離>0 (2026-09-05〜) / 参考v1 = 穴帯 ∧ 帯調整<0 ∧ 乖離>0 (8/29-8/30。8/30は穴帯6〜14)',
    '支持係数': 'nsup v2 = 8/30定義から黄金律・厩舎ROIを除いた本数 (2026-09-05〜)。序列に使わない（ρ≈+0.72で人気の写し）'}
res = dict(version='myoumi906_v1', raceday='20260906', def_version=DEF_VERSION, method=__doc__, diag=diag, selected=[list(x) for x in SEL], races=sel, races_all=out)
json.dump(res, open(os.path.join(D, 'myoumi_20260906.json'), 'w'), ensure_ascii=False, indent=1)
# CSV（7R全頭）
cols = ['ba', 'r', 'uma', 'name', 'jockey', 'ninki', 'tan', 'fuku', 'mkt_p3', 'cal_p3', 'hosei', 'hosei_resid', 'hosei_z', 'compi_rank', 'total_rank', 'idm_rank', 'time_rank', 'kairi', 'kairi_idm', 'kairi_time', 'nsup', 'support', 'okure', 'tenkai', 'kyaku', 'rotation', 'zen3f', 'shobu', 'gmae', 'chokyo_c2', 'chokyo_z', 'unsei', 'unsei_kubun', 'myoumi', 'sinrai', 'flags', 'jisou', 'jisou_prev', 'hist', 'hist_gap']
with open(os.path.join(D, '03_オッズ妙味_選定R_20260906.csv'), 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f, lineterminator='\n'); w.writerow(['target_date'] + cols + ['v21', 'decision'])
    for o in sel:
        for h in o['rows']:
            w.writerow(['2026-09-06'] + [(' / '.join(x) if isinstance(x, list) else ('・'.join(x) if False else x)) if k != 'support' and k != 'hist' and k != 'flags' else (' / '.join(x) if x else '') for k, x in ((k, (o[k] if k in ('ba', 'r') else h.get(k))) for k in cols)] + ['HOLD', '買い目・印・軸なし'])
print('diag', diag)
for o in sel:
    print(f"\n=== {o['ba']}{o['r']}R {o['title']} {o['td']}{o['dist']} n={o['n']} third={o['third']} c1={o['c1']:g} T6={o['t6']:g} {o['pattern']} 両立={o['ryoritsu']} 波乱度={o['haran']} 1人気信頼={o['fav_sinrai']} 1人気妙味={o['fav_myoumi']} o1={o['o1']}")
    print(f"{'馬':>2} {'馬名':<10} {'人':>2} {'単':>5} {'複':>4} {'市p3':>5} {'較p3':>5} {'補正':>5} {'帯調':>6} {'z':>5} {'乖離':>5} {'乖IDM':>5} {'乖T':>5} {'支':>2} {'出遅':>4} {'z3/sh/gm':>8} {'調z':>6} {'運':>3} {'妙':>2} 支持")
    for h in o['rows']:
        f = lambda v, w=5: (f"{v:>{w}.1f}" if isinstance(v, (int, float)) and v is not None else f"{'—':>{w}}")
        print(f"{h['uma']:>2} {h['name']:<10} {h['ninki'] or 0:>2} {h['tan'] or 0:>5} {h['fuku'] or 0:>4} {f(h['mkt_p3'])} {f(h['cal_p3'])} {f(h['hosei'])} {f(h['hosei_resid'],6)} {f(h['hosei_z'])} {f(h['kairi'])} {f(h['kairi_idm'])} {f(h['kairi_time'])} {h['nsup']:>2} {h['okure'] if h['okure'] is not None else '—':>4} {str(h['zen3f'] or '')+'/'+str(h['shobu'] or '')+'/'+str(h['gmae'] or ''):>8} {f(h['chokyo_z'],6)} {h['unsei'] or '—':>3} {h['myoumi'] or '—':>2} {' / '.join(h['support'])}")
print('\n=== 二条件クロス(基準7〜12・補正差<0・乖離>0) ===')
for o in sel:
    for h in o['rows']:
        if h['ninki'] and 7 <= h['ninki'] <= 12 and h['hosei'] is not None and h['hosei'] < 0 and (h['kairi'] or 0) > 0:
            print(f"  {o['ba']}{o['r']}R {h['uma']:>2} {h['name']:<10} 人気{h['ninki']} 補正{h['hosei']:+.1f} 帯調{h['hosei_resid']:+.2f} z{h['hosei_z']:+.2f} 乖離{h['kairi']:+.1f} 乖IDM{h['kairi_idm']:+.1f} 支持{h['nsup']} 出遅{h['okure']} 調z{h['chokyo_z']} 運勢{h['unsei']} {h['hist_gap'] or ''}")
print('\n=== 帯調整後に市場が最も弱気(基準7〜12・z昇順・上位12) ===')
cand = sorted([(o, h) for o in sel for h in o['rows'] if h['ninki'] and 7 <= h['ninki'] <= 12 and h['hosei_z'] is not None], key=lambda x: x[1]['hosei_z'])[:12]
for o, h in cand: print(f"  {o['ba']}{o['r']}R {h['uma']:>2} {h['name']:<10} 人気{h['ninki']} 帯調{h['hosei_resid']:+.2f} z{h['hosei_z']:+.2f} 乖離{h['kairi']} 乖IDM{h['kairi_idm']} 支持{h['nsup']} 出遅{h['okure']} 運勢{h['unsei']}")
print('\n=== 帯外参考(基準6・13〜14)で 補正差<0 かつ 乖離>0 ===')
for o in sel:
    for h in o['rows']:
        if h['ninki'] in (6, 13, 14) and h['hosei'] is not None and h['hosei'] < 0 and (h['kairi'] or 0) > 0:
            print(f"  {o['ba']}{o['r']}R {h['uma']:>2} {h['name']:<10} 人気{h['ninki']} 補正{h['hosei']:+.1f} 帯調{h['hosei_resid']:+.2f} 乖離{h['kairi']:+.1f} 乖IDM{h['kairi_idm']:+.1f} 支持{h['nsup']} 出遅{h['okure']} 運勢{h['unsei']}")
print('\n=== 各レースの1番人気(基準)の補正差 ===')
for o in sel:
    h=next(x for x in o['rows'] if x['ninki']==1); print(f"  {o['ba']}{o['r']}R 1人気 {h['uma']} {h['name']} 単{h['tan']} 補正{h['hosei']:+.1f} 帯調{h['hosei_resid']:+.2f} 支持{h['nsup']} ウマトク信頼度{o['fav_sinrai']}/妙味{o['fav_myoumi']} 波乱度{o['haran']} T6={o['t6']:g}{o['pattern']} c1={o['c1']:g}")
print('\n=== 乖離IDM>0 かつ 補正差<0 (基準7〜12) ===')
for o in sel:
    for h in o['rows']:
        if h['ninki'] and 7 <= h['ninki'] <= 12 and h['hosei'] is not None and h['hosei'] < 0 and (h['kairi_idm'] or 0) > 0:
            print(f"  {o['ba']}{o['r']}R {h['uma']:>2} {h['name']:<10} 人気{h['ninki']} 補正{h['hosei']:+.1f} 乖IDM{h['kairi_idm']:+.1f} IDM順{h['idm_rank']} 乖離{h['kairi']} 支持{h['nsup']}")
