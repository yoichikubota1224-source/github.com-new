#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2026-08-30 荒れレース選定と穴馬抽出。
- 荒れ選定: are_score_v21(凍結) と コンピ c1≤76∧P1-P3(70R実測 78.6%) の併記
- 穴馬: 支持係数 / 乖離(コンピ順位−総合順位・同順位は平均順位) /
        補正差(市場p3 − ドリフト補正後較正p3) / 斤量・展開順位・先行力・出遅率
- 買い目・点数・資金配分・購入可否・最終印・軸は出力しない。
"""
import csv, io, json, sys
from collections import defaultdict

FIN, SLIDE, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
DRIFT = {int(k): v for k, v in
         json.load(open('predictions/20260829/人気別3着内率_ドリフト補正後.json')).items()}
F = json.load(open(FIN))
sl = {(r['開催場'], int(r['R']), int(r['馬番'])): r
      for r in csv.DictReader(io.open(SLIDE, encoding='utf-8-sig'))}

def avg_rank(hs, key='total', rev=True):
    v = sorted([(h['uma'], h[key]) for h in hs if h.get(key) is not None],
               key=lambda z: -z[1] if rev else z[1])
    rk, i = {}, 0
    while i < len(v):
        j = i
        while j + 1 < len(v) and v[j+1][1] == v[i][1]:
            j += 1
        a = (i + j) / 2 + 1
        for k in range(i, j+1):
            rk[v[k][0]] = a
        i = j + 1
    return rk

def num(x, d=None):
    s = str(x or '').strip()
    if s in ('', '-', '未'): return d
    try: return float(s)
    except ValueError: return d

out = []
for x in F:
    hs = x['horses']
    tr = avg_rank(hs)
    s = sum(1/h['kijun_fuku'] for h in hs if h.get('kijun_fuku'))
    mkt = {h['uma']: (1/h['kijun_fuku'])*3/s for h in hs if h.get('kijun_fuku')}
    rows = []
    for h in hs:
        u = h['uma']
        nin = int(h['kijun_ninki']) if h.get('kijun_ninki') else None
        cal = DRIFT.get(min(nin, 16)) if nin else None
        hosei = 100*(mkt[u] - cal) if (u in mkt and cal is not None) else None
        cr, t = h.get('compi_rank'), tr.get(u)
        s_ = sl.get((x['ba'], x['r'], u), {})
        rows.append({
            'uma': u, 'name': h['name'], 'jockey': h['jockey'], 'ninki': nin,
            'tan': h.get('kijun_tan'), 'fuku': h.get('kijun_fuku'),
            'nsup': h['nsup'], 'support': h.get('support', []),
            'compi_rank': cr, 'total_rank': t,
            'kairi': (cr - t) if (cr is not None and t is not None) else None,
            'hosei': hosei, 'unsei': h.get('unsei'), 'roi': h.get('roi'),
            'kin': num(s_.get('斤量')), 'tenkai': num(s_.get('展開順位')),
            'senkou': (s_.get('先行力') or '').strip(), 'okure': num(s_.get('出遅率', '').replace('%','')),
            'omo': h.get('omo'), 'kyakusitu': h.get('kyakusitu'), 'sav': h.get('SAV'),
            'chokyo_z': h.get('chokyo_z'), 'geki_mark': h.get('geki_mark'),
            'myoumi': h.get('myoumi'), 'MB': len(h.get('MB', [])), 'UL': len(h.get('UL', [])),
        })
    c = x['compi']
    out.append({'ba': x['ba'], 'r': x['r'], 'cls': x['cls'], 'td': x['td'], 'dist': x['dist'],
                'n': x['n'], 'o1': x['o1'], 'one': x['v21']['ONE_HOLE'],
                'haran': hs[0]['haran'], 'c1': c['c1'], 't6': c['t6'], 'pattern': c['pattern'],
                'ryoritsu': (c['c1'] <= 76 and c['pattern'] in ('P1','P2','P3')),
                'shinba': '新馬' in x['cls'], 'rows': rows})
json.dump(out, open(OUT, 'w'), ensure_ascii=False, indent=1)
print(f"{len(out)}R / {sum(len(o['rows']) for o in out)}頭  両立{sum(1 for o in out if o['ryoritsu'])}R")
