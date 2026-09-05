# -*- coding: utf-8 -*-
"""2026-09-05 確定結果による事後採点（読み取り専用）。
原本・既報は一切変更しない。買い目・点数・資金配分・購入可否・最終印・軸は出力しない。
"""
import json, os, sys, math
from collections import Counter, defaultdict

BASE = os.path.join(os.path.dirname(__file__), '..', '..')
P = lambda *a: os.path.abspath(os.path.join(BASE, *a))

res   = json.load(open(P('predictions/20260905/results_20260905.json'), encoding='utf-8'))
comp  = json.load(open(P('predictions/20260905/composite.json'), encoding='utf-8'))
touk  = json.load(open(P('predictions/20260905/toukei_20260905.json'), encoding='utf-8'))
unsei = json.load(open(P('predictions/20260905/unsei_20260905.json'), encoding='utf-8'))
chok  = json.load(open(P('predictions/20260905/chokyo_20260905.json'), encoding='utf-8'))
jis   = json.load(open(P('predictions/20260905/jisou905.json'), encoding='utf-8'))
myo   = json.load(open(P('predictions/20260905/myoumi_7R_20260905.json'), encoding='utf-8'))

# ---- race_id -> (ba, r) -------------------------------------------------
rid2br = {t['race_id']: (t['ba'], t['r']) for t in touk}
br2t   = {(t['ba'], t['r']): t for t in touk}

# ---- 結果索引 -----------------------------------------------------------
R = {}          # (ba,r,uma) -> horse result
RACE = {}       # (ba,r) -> race result
for rc in res:
    br = rid2br.get(rc['race_id'])
    if br is None:
        continue
    RACE[br] = rc
    for h in rc['horses']:
        R[(br[0], br[1], h['uma'])] = h

def live(h):
    return h is not None and isinstance(h.get('chaku'), int) and h['chaku'] > 0

# ---- 母集団 -------------------------------------------------------------
POP = [h for h in R.values() if live(h)]
N_POP = len(POP)
def top3(h): return live(h) and h['chaku'] <= 3
def win(h):  return live(h) and h['chaku'] == 1

pop_n   = Counter(h['pop'] for h in POP)
pop_t3  = Counter(h['pop'] for h in POP if top3(h))
pop_w   = Counter(h['pop'] for h in POP if win(h))
POP_RATE = {p: pop_t3[p] / pop_n[p] for p in pop_n}
POP_WRATE= {p: pop_w[p]  / pop_n[p] for p in pop_n}

def expected(hs):
    """同一確定人気の母集団3着内率の和＝人気合わせの期待3着内数"""
    return sum(POP_RATE.get(h['pop'], 0.0) for h in hs)
def expected_w(hs):
    return sum(POP_WRATE.get(h['pop'], 0.0) for h in hs)

def tan_ret(hs):
    """仮定単勝回収率(%)。実購入なし・0円Shadowの仮定計算"""
    if not hs: return None
    got = sum(h['odds'] * 100 for h in hs if win(h) and h['odds'])
    return 100.0 * got / (100 * len(hs))

def summarize(hs, label):
    hs = [h for h in hs if live(h)]
    n = len(hs)
    if n == 0:
        return {'label': label, 'n': 0}
    t = sum(1 for h in hs if top3(h)); w = sum(1 for h in hs if win(h))
    e = expected(hs); ew = expected_w(hs)
    return {'label': label, 'n': n, 'top3': t, 'rate': 100.0*t/n,
            'exp': round(e, 1), 'diff': round(t - e, 1),
            'win': w, 'exp_win': round(ew, 1), 'diff_win': round(w - ew, 1),
            'tan': round(tan_ret(hs), 1)}

def wilson(k, n):
    if n == 0: return (0.0, 0.0)
    z = 1.96; p = k/n
    d = 1 + z*z/n
    c = (p + z*z/(2*n))/d
    s = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))/d
    return (round(100*(c-s), 1), round(100*(c+s), 1))

OUT = {}

# =========================================================================
# 1. 突合
# =========================================================================
ckey = {(x['ba'], x['r'], x['uma']): x for x in comp}
miss_in_res  = [k for k in ckey if k not in R]
miss_in_comp = [k for k in R if k not in ckey]
nonrun = []
for k, h in R.items():
    if not live(h):
        c = ckey.get(k)
        nonrun.append({'ba': k[0], 'r': k[1], 'uma': k[2], 'name': h['name'],
                       'status': h.get('status'),
                       'flags': c['flags'] if c else None,
                       'MB': bool(c and c['MB']), 'UL': bool(c and c['UL']),
                       'jisou': c['jisou'] if c else None})
OUT['join'] = {'n_comp': len(comp), 'n_res_rows': len(R), 'n_live': N_POP,
               'miss_in_res': miss_in_res, 'miss_in_comp': miss_in_comp,
               'nonrun': sorted(nonrun, key=lambda x: (x['ba'], x['r']))}

# =========================================================================
# 2. 母集団
# =========================================================================
OUT['base'] = {'n': N_POP,
               'win': sum(1 for h in POP if win(h)),
               'top3': sum(1 for h in POP if top3(h)),
               'top3_rate': round(100*sum(1 for h in POP if top3(h))/N_POP, 1),
               'tan': round(tan_ret(POP), 1),
               'pop_rate': {str(p): [pop_n[p], pop_t3[p], round(100*POP_RATE[p], 1)]
                            for p in sorted(pop_n)}}

# =========================================================================
# 3. ⑤ マストバイ / ウルトラ
# =========================================================================
mb = [R[(x['ba'], x['r'], x['uma'])] for x in comp if x['MB'] and (x['ba'],x['r'],x['uma']) in R]
ul = [R[(x['ba'], x['r'], x['uma'])] for x in comp if x['UL'] and (x['ba'],x['r'],x['uma']) in R]
mb_rows = sum(len(x['MB']) for x in comp)
OUT['k5'] = {'MB': summarize(mb, 'マストバイ'), 'MB_rows': mb_rows,
             'UL': summarize(ul, 'ウルトラ'),
             'MB_detail': [{'ba': x['ba'], 'r': x['r'], 'uma': x['uma'], 'name': x['name'],
                            'cond': x['MB'],
                            'chaku': R[(x['ba'],x['r'],x['uma'])]['chaku'],
                            'pop': R[(x['ba'],x['r'],x['uma'])]['pop'],
                            'odds': R[(x['ba'],x['r'],x['uma'])]['odds']}
                           for x in comp if x['MB'] and (x['ba'],x['r'],x['uma']) in R],
             'UL_detail': [{'ba': x['ba'], 'r': x['r'], 'uma': x['uma'], 'name': x['name'],
                            'cond': x['UL'],
                            'chaku': R[(x['ba'],x['r'],x['uma'])]['chaku'],
                            'pop': R[(x['ba'],x['r'],x['uma'])]['pop'],
                            'odds': R[(x['ba'],x['r'],x['uma'])]['odds']}
                           for x in comp if x['UL'] and (x['ba'],x['r'],x['uma']) in R]}

# =========================================================================
# 4. ⑭ 次走期待（jisou v1.4）
# =========================================================================
jrows = [(x, R.get((x['ba'], x['r'], x['uma']))) for x in comp if x['jisou']]
jlive = [h for _, h in jrows if live(h)]
OUT['k14'] = {'all': summarize(jlive, '次走期待')}
tier_of  = lambda s: s.split('/')[0]
score_of = lambda s: int(s.split('/sc')[1])
for tier in ['確定枠', '優先高', '優先中']:
    hs = [h for x, h in jrows if live(h) and tier_of(x['jisou']) == tier]
    OUT['k14'][tier] = summarize(hs, tier)
sc_bucket = lambda s: '7-8' if s >= 7 else '5-6' if s >= 5 else '3-4' if s >= 3 else '1-2'
for b in ['7-8', '5-6', '3-4', '1-2']:
    hs = [h for x, h in jrows if live(h) and sc_bucket(score_of(x['jisou'])) == b]
    OUT['k14']['sc' + b] = summarize(hs, 'sc' + b)
OUT['k14']['band'] = {}
jband = {(d['ba'], d['r'], d['uma']): d['band'] for d in jis['hits']}
for b in ['B', 'C', 'D']:
    hs = [h for x, h in jrows if live(h) and jband.get((x['ba'], x['r'], x['uma'])) == b]
    OUT['k14']['band'][b] = summarize(hs, 'band' + b)

# =========================================================================
# 5. 複合係数（flags の本数）
# =========================================================================
OUT['nflag'] = {}
for k in [0, 1, 2, 3, 4]:
    hs = [R[(x['ba'],x['r'],x['uma'])] for x in comp
          if x['nflag'] == k and (x['ba'],x['r'],x['uma']) in R]
    OUT['nflag'][str(k)] = summarize(hs, 'flag%d' % k)
hs = [R[(x['ba'],x['r'],x['uma'])] for x in comp
      if x['nflag'] >= 3 and (x['ba'],x['r'],x['uma']) in R]
OUT['nflag']['3+'] = summarize(hs, 'flag3以上')
OUT['flag_kind'] = {}
for kind in ['穴帯', '次走', '調教', '運勢']:
    hs = [R[(x['ba'],x['r'],x['uma'])] for x in comp
          if kind in x['flags'] and (x['ba'],x['r'],x['uma']) in R]
    OUT['flag_kind'][kind] = summarize(hs, kind)

# =========================================================================
# 6. ⑨ 運勢（記号）
# =========================================================================
OUT['unsei'] = {}
for m in ['◎◎', '◎', '○', '△', '×']:
    hs = [R[(x['ba'],x['r'],x['uma'])] for x in comp
          if x['unsei_j'] == m and (x['ba'],x['r'],x['uma']) in R]
    OUT['unsei'][m] = summarize(hs, m)
OUT['unsei']['未結合'] = summarize(
    [R[(x['ba'],x['r'],x['uma'])] for x in comp
     if x['unsei_j'] is None and (x['ba'],x['r'],x['uma']) in R], '未結合')

# =========================================================================
# 7. ⑥ 調教
# =========================================================================
ck = {}
for k, v in chok['horses'].items():
    a = k.split('|')
    ck[(a[0], int(a[1]), int(a[2]))] = v
zb = lambda z: 'z<=-1.0' if z <= -1.0 else '-1.0<z<=-0.3' if z <= -0.3 else '-0.3<z<=0.3' if z <= 0.3 else 'z>0.3'
buckets = defaultdict(list)
c2b = defaultdict(list)
for x in comp:
    key = (x['ba'], x['r'], x['uma'])
    if key not in R: continue
    v = ck.get(key)
    if not v: continue
    z = v.get('best_z1f')
    if z is not None: buckets[zb(z)].append(R[key])
    c2 = v.get('best_c2')
    if c2: c2b[c2].append(R[key])
OUT['chokyo'] = {k: summarize(v, k) for k, v in buckets.items()}
OUT['chokyo_c2'] = {k: summarize(v, k) for k, v in c2b.items()}

# =========================================================================
# 8. レース単位（荒れ＝1〜3着の確定人気合計≥18 / P区分 / v21監査ONE_HOLE）
# =========================================================================
# テクニカル6 = コンピ上位3頭の合計 / c1 = コンピ最高値 / P区分は8/22以来の閾値
def pattern_of(t6):
    if t6 is None: return None
    for lim, nm in ((205,'P1'), (208,'P2'), (211,'P3'), (215,'P4'), (219,'P5')):
        if t6 <= lim: return nm
    return 'P6'
compi_by_race = defaultdict(list)
for t in touk:
    for h in t['horses']:
        if h.get('compi') is not None:
            compi_by_race[(t['ba'], t['r'])].append(h['compi'])

races = []
for br, rc in RACE.items():
    top = sorted([h for h in rc['horses'] if live(h)], key=lambda h: h['chaku'])[:3]
    if len(top) < 3: continue
    s = sum(h['pop'] for h in top)
    t = br2t[br]
    pay = rc.get('pay') or {}
    pay3t = (pay.get('3連単') or [None])[0]
    cs = sorted(compi_by_race.get(br, []), reverse=True)
    c1 = cs[0] if cs else None
    t6 = sum(cs[:3]) if len(cs) >= 3 else None
    pat = pattern_of(t6)
    # 荒れ = 1着の確定人気>=5 または 上位3頭の確定人気合計>=18（8/29・8/30の採点定義と同一）
    haran = (top[0]['pop'] >= 5) or (s >= 18)
    races.append({'ba': br[0], 'r': br[1], 'race_id': rc['race_id'],
                  'title': t.get('title'), 'sum_pop': s, 'haran': haran,
                  'win_pop': top[0]['pop'], 'win_uma': top[0]['uma'],
                  'win_name': top[0]['name'], 'win_odds': top[0]['odds'],
                  'pay3t': pay3t,
                  'pattern': pat, 'c1': c1, 't6': t6,
                  'ryoritsu': (c1 is not None and c1 <= 76 and pat in ('P1','P2','P3')),
                  'one_audit': (t.get('v21_audit') or {}).get('ONE_HOLE'),
                  'fav_out': (t.get('v21_audit') or {}).get('FAV_OUT'),
                  'multi': (t.get('v21_audit') or {}).get('MULTI_HOLE'),
                  'o1': t.get('o1'), 'n': t.get('n_live'),
                  # P区分ルールの的中定義（8/29・8/30の採点と同一）：
                  # 当日確定7〜12番人気の馬が3着以内に入ったレースを的中とする
                  'hit7_12': any(7 <= h['pop'] <= 12 for h in rc['horses'] if top3(h))})
races.sort(key=lambda x: (x['ba'], x['r']))
OUT['races'] = races
def rgrp(sel, label):
    g = [x for x in races if sel(x)]
    if not g: return {'label': label, 'n': 0}
    h = sum(1 for x in g if x['haran'])
    k = sum(1 for x in g if x['hit7_12'])
    pays = sorted([x['pay3t'] for x in g if x['pay3t']])
    med = pays[len(pays)//2] if pays else None
    return {'label': label, 'n': len(g), 'haran': h, 'rate': round(100*h/len(g), 1),
            'ci': wilson(h, len(g)), 'pay3t_median': med,
            'hit7_12': k, 'hit_rate': round(100*k/len(g), 1), 'hit_ci': wilson(k, len(g))}
OUT['race_groups'] = {
    'ALL':      rgrp(lambda x: True, '全35R'),
    'P1':       rgrp(lambda x: x['pattern'] == 'P1', 'P1'),
    'P1-P3':    rgrp(lambda x: x['pattern'] in ('P1','P2','P3'), 'P1-P3'),
    'P4-P6':    rgrp(lambda x: x['pattern'] in ('P4','P5','P6'), 'P4-P6'),
    'ryoritsu': rgrp(lambda x: x['ryoritsu'] is True, '両立(c1<=76 かつ P1-P3)'),
    'ONE>=63':  rgrp(lambda x: (x['one_audit'] or 0) >= 63, 'v21監査 ONE_HOLE>=63'),
    'ONE<63':   rgrp(lambda x: (x['one_audit'] or 0) < 63, 'v21監査 ONE_HOLE<63'),
    'P1':  rgrp(lambda x: x['pattern'] == 'P1', 'P1'),
    'P2':  rgrp(lambda x: x['pattern'] == 'P2', 'P2'),
    'P3':  rgrp(lambda x: x['pattern'] == 'P3', 'P3'),
    'P4':  rgrp(lambda x: x['pattern'] == 'P4', 'P4'),
    'P5':  rgrp(lambda x: x['pattern'] == 'P5', 'P5'),
    'P6':  rgrp(lambda x: x['pattern'] == 'P6', 'P6'),
}
# 確定7〜12番人気（穴帯・結果側）の馬単位
OUT['ana_band'] = summarize([h for h in POP if 7 <= h['pop'] <= 12], '確定7-12人気')

# =========================================================================
# 10. ⑦ 妙味（既報7R・穴帯＝JRDB基準単勝順位7〜12）
# =========================================================================
mrows = []
for rc in myo['races']:
    for h in rc['rows']:
        if '穴帯' not in (h.get('flags') or []): continue
        k = (rc['ba'], rc['r'], h['uma'])
        if k not in R: continue
        mrows.append((rc, h, R[k]))
def msum(sel, label):
    hs = [rr for rc, h, rr in mrows if live(rr) and sel(h)]
    return summarize(hs, label)
OUT['myoumi'] = {
    'n': len(mrows),
    'all': summarize([rr for _, _, rr in mrows], '穴帯42頭'),
    'kairi>0':  msum(lambda h: (h.get('kairi') or 0) > 0,  '乖離>0'),
    'kairi<=0': msum(lambda h: (h.get('kairi') or 0) <= 0, '乖離<=0'),
    'kairi_idm>0':  msum(lambda h: (h.get('kairi_idm') or 0) > 0,  '乖離IDM>0'),
    'kairi_idm<=0': msum(lambda h: (h.get('kairi_idm') or 0) <= 0, '乖離IDM<=0'),
    'obi<0':  msum(lambda h: (h.get('hosei_resid') or 0) < 0,  '帯調整<0(市場が弱気)'),
    'obi>=0': msum(lambda h: (h.get('hosei_resid') or 0) >= 0, '帯調整>=0'),
    'nsup0-1':  msum(lambda h: h.get('nsup', 0) <= 1, '支持0-1'),
    'nsup2-3':  msum(lambda h: 2 <= h.get('nsup', 0) <= 3, '支持2-3'),
    'nsup4+':   msum(lambda h: h.get('nsup', 0) >= 4, '支持4以上'),
    # 08報で公表した定義：補正差<0 かつ 乖離>0（4頭）
    'cross':    msum(lambda h: (h.get('hosei') or 0) < 0 and (h.get('kairi') or 0) > 0,
                     '二条件クロス(08報の公表定義：補正差<0 かつ 乖離>0)'),
    # 8/30報で使った定義：帯調整<0 かつ 乖離>0（参考・8頭）
    'cross_obi': msum(lambda h: (h.get('hosei_resid') or 0) < 0 and (h.get('kairi') or 0) > 0,
                      '参考(8/30定義：帯調整<0 かつ 乖離>0)'),
}
def _cd(sel):
    return [{'ba': rc['ba'], 'r': rc['r'], 'uma': h['uma'], 'name': h['name'],
             'ninki': h['ninki'], 'hosei': h.get('hosei'), 'obi': h.get('hosei_resid'),
             'kairi': h.get('kairi'), 'kairi_idm': h.get('kairi_idm'), 'nsup': h.get('nsup'),
             'chaku': rr['chaku'], 'pop': rr['pop'], 'odds': rr['odds'],
             'pay3t': next((x['pay3t'] for x in races
                            if x['ba'] == rc['ba'] and x['r'] == rc['r']), None)}
            for rc, h, rr in mrows if sel(h)]
OUT['myoumi']['cross_detail'] = _cd(
    lambda h: (h.get('hosei') or 0) < 0 and (h.get('kairi') or 0) > 0)
OUT['myoumi']['cross_obi_detail'] = _cd(
    lambda h: (h.get('hosei_resid') or 0) < 0 and (h.get('kairi') or 0) > 0)
# 支持係数 vs 当日確定人気 のスピアマン順位相関（既報7Rの全出走馬）
pairs = []
for rc in myo['races']:
    for h in rc['rows']:
        k = (rc['ba'], rc['r'], h['uma'])
        if k in R and live(R[k]):
            pairs.append((h.get('nsup', 0), R[k]['pop']))
def spearman(pairs):
    def rank(v):
        s = sorted(range(len(v)), key=lambda i: v[i]); rk = [0]*len(v); i = 0
        while i < len(s):
            j = i
            while j+1 < len(s) and v[s[j+1]] == v[s[i]]: j += 1
            avg = (i+j)/2 + 1
            for t in range(i, j+1): rk[s[t]] = avg
            i = j+1
        return rk
    a = rank([-p[0] for p in pairs]); b = rank([p[1] for p in pairs])
    n = len(pairs); ma = sum(a)/n; mb = sum(b)/n
    cov = sum((x-ma)*(y-mb) for x, y in zip(a, b))
    va = math.sqrt(sum((x-ma)**2 for x in a)); vb = math.sqrt(sum((y-mb)**2 for y in b))
    return round(cov/(va*vb), 3)
OUT['myoumi']['rho_nsup_pop'] = spearman(pairs)
OUT['myoumi']['rho_n'] = len(pairs)

# 支持係数（既報7Rの全出走馬・帯を問わない）
OUT['nsup_all'] = {}
for lab, sel in [('0-1', lambda v: v <= 1), ('2-3', lambda v: 2 <= v <= 3),
                 ('4', lambda v: v == 4), ('5以上', lambda v: v >= 5)]:
    hs = [R[(rc['ba'], rc['r'], h['uma'])] for rc in myo['races'] for h in rc['rows']
          if sel(h.get('nsup', 0)) and (rc['ba'], rc['r'], h['uma']) in R]
    OUT['nsup_all'][lab] = summarize(hs, '支持' + lab)

# =========================================================================
# 11. ⑦STRIDE total_rank（8/30報の優先「高」対策で主軸に据えると提案した指標）
# =========================================================================
def tr_bucket(v):
    return '1-3位' if v <= 3 else '4-6位' if v <= 6 else '7-10位' if v <= 10 else '11位以下'
tb = defaultdict(list)
for x in comp:
    k = (x['ba'], x['r'], x['uma'])
    if k in R and x.get('total_rank') is not None:
        tb[tr_bucket(x['total_rank'])].append(R[k])
OUT['total_rank'] = {k: summarize(v, k) for k, v in tb.items()}

# =========================================================================
# 9. 荒れレースの1着馬カバー
# =========================================================================
cov = []
for x in races:
    if not x['haran']: continue
    c = ckey.get((x['ba'], x['r'], x['win_uma']))
    cov.append({'ba': x['ba'], 'r': x['r'], 'uma': x['win_uma'], 'name': x['win_name'],
                'pop': x['win_pop'], 'odds': x['win_odds'], 'sum_pop': x['sum_pop'],
                'pay3t': x['pay3t'],
                'flags': c['flags'] if c else [], 'MB': bool(c and c['MB']),
                'UL': bool(c and c['UL']), 'jisou': c['jisou'] if c else None})
OUT['haran_win'] = cov
# 1着馬35頭の材料カバー
# カバー定義（本報で明示）：⑤マストバイ / ⑤ウルトラ / ⑭次走期待 / ⑦妙味の二条件クロス
#   のいずれかに「馬名を挙げて」載っていた馬を「カバーあり」とする。
#   「穴帯(基準単勝順位7〜12)」「運勢記号」「調教」は帯・属性であって推奨ではないので数えない。
#   ⚠ 8/29・8/30の同種表は⑤MB/ULのみが同日成果物だった（⑭は当日結果からの次走監視抽出で
#   同日予想には使っていない）ため、比較は MB/UL のみの系列で行う。
CROSS = {(d['ba'], d['r'], d['uma']) for d in OUT['myoumi']['cross_detail']}
wins = []
for x in races:
    k = (x['ba'], x['r'], x['win_uma'])
    c = ckey.get(k)
    mb, ul = bool(c and c['MB']), bool(c and c['UL'])
    js = c['jisou'] if c else None
    cr = k in CROSS
    wins.append({'ba': x['ba'], 'r': x['r'], 'uma': x['win_uma'], 'name': x['win_name'],
                 'pop': x['win_pop'], 'odds': x['win_odds'], 'haran': x['haran'],
                 'flags': c['flags'] if c else [], 'MB': mb, 'UL': ul, 'jisou': js,
                 'cross': cr,
                 'covered': bool(mb or ul or js or cr),
                 'covered_mbul': bool(mb or ul)})
OUT['wins'] = wins
def cov_stat(sel):
    g = [w for w in wins if sel(w)]
    return {'n': len(g),
            'covered': sum(1 for w in g if w['covered']),
            'covered_mbul': sum(1 for w in g if w['covered_mbul'])}
OUT['coverage'] = {
    '全35R': cov_stat(lambda w: True),
    '荒れ': cov_stat(lambda w: w['haran']),
    '確定7人気以下': cov_stat(lambda w: w['pop'] >= 7),
    '確定5-6人気': cov_stat(lambda w: 5 <= w['pop'] <= 6),
    '確定1-4人気': cov_stat(lambda w: w['pop'] <= 4),
}

# =========================================================================
# 12. 掲載率とリフト（カバー率を頭数の増加と切り分ける）
#     掲載集合 = ⑤MB ∪ ⑤UL ∪ ⑭次走期待 ∪ ⑦二条件クロス（馬名を挙げた馬）
#     リフト  = 荒れ1着馬のカバー率 ÷ 掲載率
# =========================================================================
LIST = set()
for x in comp:
    k = (x['ba'], x['r'], x['uma'])
    if x['MB'] or x['UL'] or x['jisou'] or k in CROSS:
        LIST.add(k)
haran_br = {(x['ba'], x['r']) for x in races if x['haran']}
n_haran_live = n_haran_listed = 0
for br, rc in RACE.items():
    if br not in haran_br: continue
    for h in rc['horses']:
        if live(h):
            n_haran_live += 1
            if (br[0], br[1], h['uma']) in LIST: n_haran_listed += 1
share_all = len(LIST) / N_POP
share_haran = n_haran_listed / n_haran_live
cw = OUT['coverage']['荒れ']['covered'] / OUT['coverage']['荒れ']['n']
cw_all = sum(1 for w in wins if w['covered']) / len(wins)
OUT['lift'] = {'listed': len(LIST), 'live': N_POP, 'share': round(100*share_all, 1),
               'haran_live': n_haran_live, 'haran_listed': n_haran_listed,
               'haran_share': round(100*share_haran, 1),
               'haran_win_cover': round(100*cw, 1),
               'haran_lift': round(cw/share_haran, 2),
               'all_win_cover': round(100*cw_all, 1),
               'all_lift': round(cw_all/share_all, 2)}

json.dump(OUT, open(sys.argv[1] if len(sys.argv) > 1 else '/dev/stdout', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
