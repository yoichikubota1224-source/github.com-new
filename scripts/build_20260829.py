#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2026-08-29 独立再評価の統合ビルド。
5指数CSV(UTF-8 BOM)＋DE出走表(CP932)＋ウルトラ/マストバイ抽出を racekey+馬番 で結合し、
荒れ選定(are_score_v21)と穴馬(基準人気7〜12)候補を出す。
確定オッズ・確定人気は一切使用しない。買い目・点数・資金配分は出力しない。
"""
import csv, json, math, os, sys
from collections import defaultdict, Counter

PACK = sys.argv[1]; DE = sys.argv[2]; MB = sys.argv[3]; UL = sys.argv[4]

def load(name):
    p = os.path.join(PACK, name)
    return list(csv.DictReader(open(p, 'rb').read().decode('utf-8-sig').splitlines()))

def num(x, default=None):
    if x is None: return default
    s = str(x).strip().replace('%', '').replace(' ', '')
    if s in ('', '-', '--', '未', 'null'): return default
    try: return float(s)
    except ValueError: return default

SRC = {'IDM': 'IDM_全35R_20260829.csv', 'TIME': 'タイム指数_全35R_20260829.csv',
       'UMA': 'ウマトク_全35R_20260829.csv', 'STR': 'スライド競馬新聞_全35R_20260829.csv',
       'JRDB': 'JRDB_基準単複オッズ_全35R_20260829.csv'}
D = {k: load(v) for k, v in SRC.items()}
by = {k: {(r['racekey'], int(r['馬番'])): r for r in v} for k, v in D.items()}

# ---- DE出走表(クラス・距離・芝ダ・頭数・父・調教師) ----
de = {}
for r in csv.reader(open(DE, encoding='cp932')):
    de[(r[1], int(r[2]), int(r[3]))] = r

# ---- ⑤ウルトラ・マストバイ(本日抽出済) ----
def hits(path):
    out = defaultdict(list)
    for x in json.load(open(path)):
        rr = x['race']
        for h in x['hits']:
            out[(rr['ba'], rr['r'], h['uma'])].append(h)
    return out
mbh, ulh = hits(MB), hits(UL)

# ---- are_score_v21 (2026-08-02凍結・当方で再実装) ----
O1_T = [(0.0,1.9,15.2,11.7,50.9,8.0),(1.9,2.6,27.3,13.6,55.0,12.3),
        (2.6,3.5,41.2,19.4,61.9,17.1),(3.5,99.0,54.9,31.6,73.8,29.8)]
N_T  = [(8,12,24.8,10.4,46.3,6.2),(12,15,34.7,18.3,62.7,15.1),(15,19,38.0,21.2,63.4,20.3)]
BASE = (34.5,18.3,59.8,16.2)
def _cell(tbl, v, lo_i=0, hi_i=1):
    for row in tbl:
        if row[lo_i] <= v < row[hi_i]: return row
    return tbl[-1]
def _logit(p): p=min(max(p,1e-4),1-1e-4); return math.log(p/(1-p))
def _sig(z): return 1/(1+math.exp(-z))
def are_v21(o1, n):
    """1番人気基準オッズと頭数から p(ONE_HOLE) 等を返す。"""
    if o1 is None or n is None: return None
    a = _cell(O1_T, o1); b = _cell(N_T, n)
    out = {}
    for i, key in enumerate(('FAV_OUT','HEAD_HOLE','ONE_HOLE','MULTI_HOLE')):
        ai = a[2+i] if i < 2 else (a[4] if i == 2 else a[5])
        bi = b[2+i] if i < 2 else (b[4] if i == 2 else b[5])
        z = (_logit(ai/100) + _logit(bi/100)) / 2
        z = _logit(BASE[i]/100) + 1.5*(z - _logit(BASE[i]/100))
        out[key] = round(_sig(z)*100, 1)
    return out

# ---- レース単位に組む ----
races = defaultdict(list)
for k, r in by['IDM'].items():
    races[(r['開催場'], int(r['R']), r['racekey'])].append(k)

out = []
for (ba, rno, rk) in sorted(races, key=lambda z: (z[0], z[1])):
    keys = sorted(races[(ba, rno, rk)], key=lambda z: z[1])
    head_de = de[(ba, rno, keys[0][1])]
    n = int(head_de[26])
    horses = []
    for k in keys:
        u = int(k[1])
        idm, tm, um, st, jd = by['IDM'][k], by['TIME'][k], by['UMA'][k], by['STR'][k], by['JRDB'][k]
        d = de[(ba, rno, u)]
        horses.append({
            # ⚠ IDM CSVの騎手名は3文字丸め＋[替]接尾。運勢結合に使えないためDEを正本とし、
            #    IDM側は乗替フラグの抽出にのみ使う。
            'uma': u, 'name': idm['馬名'], 'jockey': d[10].strip(),
            'jockey_idm': idm['騎手名'].strip(), 'norikae': '[替]' in idm['騎手名'],
            'sire': d[16],
            'trainer': idm['調教師'], 'belong': idm['所属'], 'sex': d[8], 'age': int(d[9]),
            'waku': int(d[22]),
            'kijun_tan': num(jd['基準単勝']), 'kijun_fuku': num(jd['基準複勝']),
            'kijun_ninki': num(um['基準人気']),
            'IDM': num(idm['IDM']), 'idm_mark': idm['IDM印'].strip(), 'kyakusitu': idm['脚質'].strip(),
            'time_max': num(tm['最高指数']), 'time_5avg': num(tm['5走平均']),
            'time_dist': num(tm['距離指数']), 'time_course': num(tm['コース指数']),
            'time_last': num(tm['前走']), 'time_status': tm['source_status'],
            'uma_idx': num(um['馬トク指数']), 'geki': num(um['激走指数']), 'geki_mark': num(um['激印']),
            'haran': um['波乱度'].strip(), 'trust1': um['1番人気信頼度'].strip(), 'myoumi1': um['1番人気妙味度'].strip(),
            'SAV': num(st['SAV']), 'sinrai': st['信頼度'].strip(), 'myoumi': st['妙味度'].strip(),
            'total': num(st['合計値']), 'total_rank': num(st['合計値順位']),
            'tenkai': num(st['展開順位']), 'okure': num(st['出遅率']),
            'chokyo_idx': num(st['調教指数']), 'chokyo_pat': st['調教パターン'].strip(),
            'oikiri': st['最終追切'].strip(), 'jockey_idx': num(st['騎手指数']),
            'omo': st['重適性'].strip(), 'lap': st['ラップ適性'].strip(),
            'MB': mbh.get((ba, rno, u), []), 'UL': ulh.get((ba, rno, u), []),
        })
    o1 = min([h['kijun_tan'] for h in horses if h['kijun_tan'] is not None], default=None)
    v21 = are_v21(o1, n)
    ana = [h for h in horses if h['kijun_ninki'] and 7 <= h['kijun_ninki'] <= 12]
    out.append({'ba': ba, 'r': rno, 'racekey': rk, 'cls': head_de[4], 'td': head_de[5],
                'dist': int(head_de[6]), 'n': n, 'o1': o1, 'v21': v21,
                'time_hold': horses[0]['time_status'] != 'PASS',
                'horses': horses, 'ana': [h['uma'] for h in ana]})

json.dump(out, open(os.path.join(os.path.dirname(MB), '統合_20260829.json'), 'w'),
          ensure_ascii=False, indent=1)
print(f'レース {len(out)} / 頭数 {sum(len(o["horses"]) for o in out)}')
print(f'v21算出可 {sum(1 for o in out if o["v21"])} / タイム指数HOLD {sum(1 for o in out if o["time_hold"])}')
