#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2026-09-06 オッズ妙味分析（羊一様ご指定の7R: 阪神2R/11R・札幌6R/7R/11R・中山9R/11R）。
myoumi906_v1 の定義は動かさない。本スクリプトが足すのは次の4点（いずれも診断・参考であり規則の昇格ではない）。
 (a) 全出走馬（穴帯に限らない）を対象にした妙味表
 (b) 基準単複が同値の馬の扱い: 較正p3をタイ平均にした参考値 hosei_tie（順位の割り方で生じる差を分離する）
 (c) 乖離の紙面順位版 kairi_paper = コンピ順位 − 新聞「合計値順位」(同順なし1..n)
 (d) 較正表(8/22-23標本)の鮮度検査: 8/29・8/30・9/5 の実績で基準人気別3着内率を測り、較正値と比べる
⚠ 実オッズ・確定人気は使わない。買い目・スコア配分・資金配分・購入可否・最終印・軸は出さない。運勢×は消し根拠にしない。
"""
import json, csv, os, math, collections, statistics as st

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
D = os.path.join(REPO, 'predictions', '20260906')
TARGET = [('阪神', 2), ('札幌', 6), ('札幌', 7), ('中山', 9), ('札幌', 11), ('阪神', 11), ('中山', 11)]
DRIFT = {int(k): v for k, v in json.load(open(os.path.join(REPO, 'predictions', '20260829', '人気別3着内率_ドリフト補正後.json'))).items()}

M = json.load(open(os.path.join(D, 'myoumi_20260906.json')))
T = {(r['ba'], r['r']): r for r in json.load(open(os.path.join(D, 'toukei_20260906.json')))['races']}
ALL = {(r['ba'], r['r']): r for r in M['races_all']}

# ---------- (d) 較正表の鮮度検査 ----------
def kijun_map(day):
    """(ba, r, uma) -> 基準人気 を、その日の統合ファイルから取る。"""
    out = {}
    for fn in (f'最終統合_{day}.json', f'toukei_{day}.json'):
        p = os.path.join(REPO, 'predictions', day, fn)
        if not os.path.exists(p): continue
        o = json.load(open(p))
        races = o['races'] if isinstance(o, dict) and 'races' in o else (o if isinstance(o, list) else [])
        for rc in races:
            ba = rc.get('ba') or rc.get('venue'); r = rc.get('r')
            rid = rc.get('race_id')
            for h in rc.get('horses', []):
                u = h.get('uma') or h.get('umaban')
                k = h.get('kijun_ninki')
                if u and k:
                    if ba and r: out[(ba, int(r), int(u))] = int(k)
                    if rid: out[(str(rid), int(u))] = int(k)
        if out: return out, fn
    return out, None

drift_chk, drift_note = [], []
tally = collections.defaultdict(lambda: [0, 0])   # 基準人気 -> [3着内, 母数]
for day in ('20260829', '20260830', '20260905'):
    km, src = kijun_map(day)
    R = json.load(open(os.path.join(REPO, 'predictions', day, f'results_{day}.json')))
    if not km:
        drift_note.append(f'{day}: 基準人気の台帳が見つからず未測定＝[不足]'); continue
    n_join = n_miss = 0
    for rc in R:
        ba = rc.get('venue') or (rc.get('meta') or '')[:2]
        r = rc.get('r') or int(str(rc.get('race_id'))[-2:])
        for h in rc['horses']:
            u = h.get('uma') or h.get('umaban'); ch = h.get('chaku') or h.get('chakujun')
            if u is None: continue
            k = km.get((str(rc.get('race_id')), int(u))) or km.get((ba, int(r), int(u)))
            if k is None: n_miss += 1; continue
            n_join += 1
            try: c = int(str(ch))
            except (TypeError, ValueError): c = None
            if k <= 16:
                tally[k][1] += 1
                if c is not None and c <= 3: tally[k][0] += 1
    drift_note.append(f'{day}: {src} と結合 {n_join}頭・未結合 {n_miss}頭')
for k in sorted(tally):
    hit, nn = tally[k]
    drift_chk.append(dict(ninki=k, n=nn, hit3=hit, rate=round(hit/nn, 4) if nn else None,
                          cal=DRIFT.get(k), diff=(round(hit/nn - DRIFT[k], 4) if nn and k in DRIFT else None)))

# ---------- 本体 ----------
def band_of(n):
    return '穴帯(7-12)' if n and 7 <= n <= 12 else ('上位帯(1-6)' if n and n <= 6 else '下位帯(13-)')

races, rows_csv, cross_all, ties_all = [], [], [], []
for key in TARGET:
    rc = ALL[key]; tk = T[key]
    tpaper = {h['uma']: h.get('total_rank_paper') for h in tk['horses'] if not h['scratched']}
    hs = rc['rows']
    # タイ群（基準単勝・基準複勝が同値）
    grp = collections.defaultdict(list)
    for h in hs: grp[(h['tan'], h['fuku'])].append(h)
    cal_k = hs[0]['cal_k']
    tie_groups = []
    for (tan, fuku), g in sorted(grp.items(), key=lambda z: z[0][0] if z[0][0] else 0):
        if len(g) < 2: continue
        ninkis = [h['ninki'] for h in g]
        cal_tie = sum(DRIFT[min(n, 16)] for n in ninkis) / len(ninkis) * cal_k
        for h in g:
            h['hosei_tie'] = round(100 * (h['mkt_p3'] / 100 - cal_tie), 1)
        tie_groups.append(dict(tan=tan, fuku=fuku, umas=[h['uma'] for h in g], names=[h['name'] for h in g],
                               ninkis=ninkis, hosei=[h['hosei'] for h in g],
                               hosei_tie=round(100 * (g[0]['mkt_p3'] / 100 - cal_tie), 1),
                               spread=round(max(h['hosei'] for h in g) - min(h['hosei'] for h in g), 1)))
    ties_all += [dict(ba=key[0], r=key[1], **t) for t in tie_groups]
    for h in hs:
        h.setdefault('hosei_tie', h['hosei'])
        h['kairi_paper'] = (h['compi_rank'] - tpaper[h['uma']]) if (h['compi_rank'] and tpaper.get(h['uma'])) else None
        h['band'] = band_of(h['ninki'])
        h['cross'] = bool(h['hosei'] is not None and h['hosei'] < 0 and h['kairi'] is not None and h['kairi'] > 0)
        h['cross_paper'] = bool(h['hosei'] is not None and h['hosei'] < 0 and h['kairi_paper'] is not None and h['kairi_paper'] > 0)
        h['cross_tie'] = bool(h['hosei_tie'] is not None and h['hosei_tie'] < 0 and h['kairi'] is not None and h['kairi'] > 0)
        if h['cross']: cross_all.append(dict(ba=key[0], r=key[1], **{k2: h[k2] for k2 in ('uma','name','ninki','band','hosei','hosei_tie','kairi','kairi_paper','kairi_idm','idm_rank','time_rank','nsup','okure','chokyo_c2','chokyo_z','unsei','flags','jisou')}))
        rows_csv.append(dict(場=key[0], R=key[1], 馬番=h['uma'], 馬名=h['name'], 騎手=h['jockey'], 帯=h['band'],
            基準人気=h['ninki'], 基準単勝=h['tan'], 基準複勝=h['fuku'], 市場p3=h['mkt_p3'], 較正p3=h['cal_p3'],
            補正差=h['hosei'], 補正差タイ平均=h['hosei_tie'], 帯調整=h['hosei_resid'], 帯調整z=h['hosei_z'],
            コンピ順位=h['compi_rank'], 合計値順位_当方=h['total_rank'], 合計値順位_紙面=tpaper.get(h['uma']),
            乖離=h['kairi'], 乖離_紙面=h['kairi_paper'], 乖離IDM=h['kairi_idm'], IDM=h['IDM'], IDM順位=h['idm_rank'],
            タイム最高=h['time_max'], タイム5走平均=h['time_5avg'], タイム順位=h['time_rank'],
            前3F順位=h['zen3f'], 勝負所順位=h['shobu'], G前順位=h['gmae'], 出遅率=h['okure'], 脚質=h['kyaku'],
            調教status=h['chokyo_status'], 調教C2=h['chokyo_c2'], 調教z=h['chokyo_z'], 運勢=h['unsei'],
            支持本数=h['nsup'], 係印=h['flags'], 次走=h['jisou'], ローテ=h['rotation'],
            クロスv2=h['cross'], クロス_紙面=h['cross_paper'], クロス_タイ平均=h['cross_tie']))
    ok = [h for h in hs if h['hosei'] is not None]
    top3 = sorted(hs, key=lambda h: h['ninki'] or 99)[:3]
    races.append(dict(ba=key[0], r=key[1], title=rc['title'], meta=rc['meta'], td=rc['td'], dist=rc['dist'], n=rc['n'],
        c1=rc['c1'], t6=rc['t6'], pattern=rc['pattern'], ryoritsu=rc['ryoritsu'], haran=rc['haran'],
        fav_sinrai=rc['fav_sinrai'], fav_myoumi=rc['fav_myoumi'], o1=rc['o1'],
        mkt_top3=round(sum(h['mkt_p3'] for h in top3), 1), hosei_fav=top3[0]['hosei'],
        hosei_min=min(h['hosei'] for h in ok), hosei_max=max(h['hosei'] for h in ok),
        hosei_sd=round(st.pstdev([h['hosei'] for h in ok]), 2),
        n_cross=sum(1 for h in hs if h['cross']), n_cross_ana=sum(1 for h in hs if h['cross'] and h['band'].startswith('穴帯')),
        n_tie_groups=len(tie_groups), chokyo_missing=sum(1 for h in hs if h['chokyo_status'] != '[実]'),
        rows=hs))

OUT = dict(version='myoumi7R906_v1', raceday='20260906', generated_utc_note='当方生成時刻はrun_log参照',
           target=[f'{b}{r}R' for b, r in TARGET],
           note_scope='羊一様ご指定の7R。中山8R・新馬2R(中山5R/6R)はご指定外のため本書では扱わない（材料は02報に残る）',
           def_added=dict(
             hosei_tie='基準単複が同値の馬は較正p3をタイ群の平均にして補正差を再計算した参考値。定義(myoumi906_v1)は動かしていない',
             kairi_paper='コンピ順位 − 新聞「合計値順位」(同順なし1..n)。当方実装の乖離(同値は平均順位)と併記',
             cross='補正差<0 ∧ 乖離>0。02報§4-1は穴帯に限定したが、本書は帯を外して全出走馬で数える',
             deokure='新聞CSV「出遅率」列。母数・期間はCSVに記載がなく[不足]。確率としては扱わない'),
           calibration=dict(table='predictions/20260829/人気別3着内率_ドリフト補正後.json（8/22-23標本）',
                            check=drift_chk, join_note=drift_note,
                            caution='本検査は基準人気で統一して測った。確定人気で測ると別の値になる（9/5第9報の定義混成と同根）'),
           races=races, cross_all=cross_all, ties=ties_all)
json.dump(OUT, open(os.path.join(D, 'myoumi7R_20260906.json'), 'w'), ensure_ascii=False, indent=1)
with open(os.path.join(D, '04_オッズ妙味_7R_20260906.csv'), 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=list(rows_csv[0].keys())); w.writeheader(); w.writerows(rows_csv)


# ---------- (d2) 較正の鮮度を使った感度検査（規則の昇格ではない。参考値） ----------
def wilson(k, n, z=1.96):
    if not n: return (None, None)
    ph = k/n; d = 1 + z*z/n
    c = (ph + z*z/(2*n))/d; hw = z*math.sqrt(ph*(1-ph)/n + z*z/(4*n*n))/d
    return (round(100*(c-hw), 1), round(100*(c+hw), 1))
EMP = {x['ninki']: x['rate'] for x in drift_chk if x['n'] >= 20}
for x in drift_chk:
    lo, hi = wilson(x['hit3'], x['n']); x['ci95'] = [lo, hi]
    x['cal_in_ci'] = bool(lo is not None and lo <= 100*x['cal'] <= hi) if x['cal'] else None
sens = []
for rc in races:
    hs = rc['rows']
    ok = [h for h in hs if h['ninki'] and h['ninki'] in EMP]
    ssum = sum(EMP[h['ninki']] for h in ok)
    k2 = 3.0/ssum if ssum else 1.0
    for h in hs:
        if h['ninki'] in EMP and h['mkt_p3'] is not None:
            h['cal_p3_3day'] = round(100*EMP[h['ninki']]*k2, 1)
            h['hosei_3day'] = round(h['mkt_p3'] - h['cal_p3_3day'], 1)
            h['hosei_shift'] = round(h['hosei_3day'] - h['hosei'], 1)
        else:
            h['cal_p3_3day'] = h['hosei_3day'] = h['hosei_shift'] = None
    ch = [h for h in hs if h['hosei_3day'] is not None]
    rc['n_cross_3day'] = sum(1 for h in ch if h['hosei_3day'] < 0 and h['kairi'] is not None and h['kairi'] > 0)
    rc['n_cross_3day_ana'] = sum(1 for h in ch if h['hosei_3day'] < 0 and h['kairi'] is not None and h['kairi'] > 0 and h['band'].startswith('穴帯'))
    sens.append(dict(ba=rc['ba'], r=rc['r'], cross=rc['n_cross'], cross_3day=rc['n_cross_3day'],
                     cross_ana=rc['n_cross_ana'], cross_3day_ana=rc['n_cross_3day_ana'],
                     ana_hosei=[(h['uma'], h['hosei'], h['hosei_3day']) for h in hs if h['band'].startswith('穴帯')]))
OUT['calibration']['empirical_3day'] = {str(k): v for k, v in EMP.items()}
OUT['calibration']['sensitivity_note'] = ('8/29・8/30・9/5の実測(基準人気別3着内率・105R)でΣ=3.0正規化し直した参考値 hosei_3day を併記。'
    '各帯 n≈105 で95%CIは±8〜10ptあり、これ自体を新しい較正表に昇格させない（RULE_PROMOTION: NONE）')
OUT['calibration']['sensitivity'] = sens
for rw in rows_csv:
    h = [x for x in ALL[(rw['場'], rw['R'])]['rows'] if x['uma'] == rw['馬番']][0]
    rw['較正p3_3日'] = h.get('cal_p3_3day'); rw['補正差_3日較正'] = h.get('hosei_3day'); rw['補正差の動き'] = h.get('hosei_shift')
json.dump(OUT, open(os.path.join(D, 'myoumi7R_20260906.json'), 'w'), ensure_ascii=False, indent=1)
with open(os.path.join(D, '04_オッズ妙味_7R_20260906.csv'), 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=list(rows_csv[0].keys())); w.writeheader(); w.writerows(rows_csv)
print('--- sensitivity (クロス頭数: 8/22-23較正 → 3日実測較正)')
for x in sens: print(f"{x['ba']}{x['r']}R クロス {x['cross']}→{x['cross_3day']} (穴帯 {x['cross_ana']}→{x['cross_3day_ana']})")
print('--- drift CI'); [print(x) for x in drift_chk]

print('races', len(races), 'horses', len(rows_csv), 'cross', len(cross_all), 'tie_groups', len(ties_all))
for r in races:
    print(f"{r['ba']}{r['r']}R n={r['n']} c1={r['c1']} T6={r['t6']}/{r['pattern']} 波乱度={r['haran']} 1人気補正差={r['hosei_fav']} 補正差sd={r['hosei_sd']} 市場top3={r['mkt_top3']} クロス={r['n_cross']}(穴帯{r['n_cross_ana']}) タイ群={r['n_tie_groups']} 調教欠={r['chokyo_missing']}/{r['n']}")
print('--- drift'); [print(x) for x in drift_chk]; [print(x) for x in drift_note]
print('--- ties'); [print(t) for t in ties_all]
