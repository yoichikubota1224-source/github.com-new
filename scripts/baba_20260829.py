#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""新潟 馬場適正オーバーレイ(2026-08-29 小雨・芝稍重/ダ稍重)。
[実] STRIDE重適性 / 騎手の重馬場ROI(運勢シート記載)
[推] 父系の重巧者傾向・稍重の一般的な傾向(当方の較正標本70Rは全て良馬場=検証不能)
買い目・点数・資金配分は出力しない。"""
import json, re, sys, csv
import openpyxl

XLSX, EVAL, DE, OUT = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]

# ---- 運勢シートから騎手別の重馬場ROIを抽出 ----
wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
ws = wb['2026.08.29']
wet = {}
for row in ws.iter_rows(values_only=True):
    c = [('' if x is None else str(x)) for x in row]
    if len(c) < 4 or not c[0] or '青字' in c[0] or c[0] == '2026年':
        continue
    # 「102田辺（新・OP✖）、101北村友一（札・凾・阪・京○）」の形を1件ずつ切る
    for m in re.finditer(r'(\d{2,3})?\s*([^\d、,\n（(]+)\s*(?:[（(]([^）)]*)[）)])?', c[3]):
        nm = (m.group(2) or '').strip()
        note = (m.group(3) or '')
        if len(nm) < 2:
            continue
        found = {}
        for mm in re.finditer(r'(芝ダ重|芝・ダ重|芝重|ダ重|ﾀﾞ重|ﾀ重|重)\s*([0-9]{2,3}|[◎○×✖△])', note):
            found[mm.group(1)] = mm.group(2)
        if found:
            wet[nm] = {'note': note, 'wet': found, 'roi': int(m.group(1)) if m.group(1) else None}
wb.close()

# 表記ゆれ: 運勢シート側 → DE側の騎手名
ALIAS = {'秋山稔': '秋山稔樹', '小沢': '小沢大仁', '松岡': None, '鷲頭虎太': None,
         '鮫島駿': '鮫島克駿', '西村太': '西村太一', '佐々木': None, '小林美駒': '小林美駒',
         '吉田豊': '吉田豊', '丸山': '丸山元気', '斎藤新': '斎藤新', '小幡育': '木幡育也',
         '泉谷': '泉谷楓真', '石川': '石川倭', '津村': '津村明秀', '横山典': '横山典弘',
         '大野拓': '大野拓弥', '菊沢': '菊沢一樹', '松若': '松若風馬', '横山和': '横山和生',
         '国分恭': '国分恭介', '江田照': '江田照男', '石橋脩': '石橋脩', '高倉': '高倉稜'}

D = json.load(open(EVAL))
nii = [R for R in D if R['ba'] == '新潟']
jockeys = {h['jockey'] for R in nii for h in R['horses']}

def wet_for(j):
    for k, v in wet.items():
        cand = ALIAS.get(k, k)
        if cand == j or (len(k) >= 3 and j.startswith(k[:3])):
            return k, v
    return None, None

# ---- 稍重での方向づけ ----
# STRIDE重適性を主、騎手重ROIを従。脚質は[推]の補助。
OMO_W = {'◎': 2, '○': 1, '△': -1, '': 0, None: 0}

out = []
for R in sorted(nii, key=lambda x: x['r']):
    surface = R['td']
    rows = []
    for h in R['horses']:
        jk, jv = wet_for(h['jockey'])
        # 騎手の当該馬場の重ROI([実]・数値のみ採用)
        jroi = None
        if jv:
            keys = ['芝重', '芝ダ重', '芝・ダ重'] if surface == '芝' else ['ダ重', 'ﾀﾞ重', 'ﾀ重', '芝ダ重', '芝・ダ重']
            for k in keys:
                if k in jv['wet'] and jv['wet'][k].isdigit():
                    jroi = int(jv['wet'][k]); break
        rows.append({
            'uma': h['uma'], 'name': h['name'], 'jockey': h['jockey'],
            'ninki': int(h['kijun_ninki']) if h['kijun_ninki'] else None,
            'tan': h['kijun_tan'], 'fuku': h['kijun_fuku'],
            'omo': h.get('omo') or '', 'omo_w': OMO_W.get(h.get('omo') or '', 0),
            'kyakusitu': h.get('kyakusitu') or '', 'okure': h.get('okure'),
            'sire': h.get('sire'), 'nsup': h['nsup'], 'unsei': h.get('unsei'),
            'jockey_wet_roi': jroi, 'jockey_wet_note': (jv['note'] if jv else None),
            'lap': h.get('lap') or '',
        })
    out.append({'r': R['r'], 'cls': R['cls'], 'td': surface, 'dist': R['dist'],
                'n': R['n'], 'c1': R['compi']['c1'], 'pattern': R['compi']['pattern'],
                'one': R['v21']['ONE_HOLE'], 'haran': R['horses'][0]['haran'], 'rows': rows})

json.dump(out, open(OUT, 'w'), ensure_ascii=False, indent=1)
tot = sum(len(o['rows']) for o in out)
jr = sum(1 for o in out for r in o['rows'] if r['jockey_wet_roi'] is not None)
om = sum(1 for o in out for r in o['rows'] if r['omo'])
print(f'新潟 {len(out)}R / {tot}頭')
print(f'  STRIDE重適性あり  : {om}/{tot}頭  ([不足] {tot-om}頭)')
print(f'  騎手の重馬場ROI取得: {jr}/{tot}頭  ([不足] {tot-jr}頭)')
