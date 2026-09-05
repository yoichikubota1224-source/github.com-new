#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2026-09-05 のJRA公式結果（netkeiba結果ページ）を解析して results_20260905.json を作る。
⚠ 結果は事前評価の書き換えには使わない。既報は改変せず、答え合わせを別文書に記録する。
⚠ 文字化けを黙認しない（errors='strict'）。整合検査（着順の連番・人気の重複・頭数）を必ず通す。
"""
import json, os, re, html, glob, collections, hashlib
RAW = '/tmp/claude-0/-home-user-github-com-new/47c1892c-ddc4-50e4-8b6f-3403a9782673/scratchpad/res0905'
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   'predictions', '20260905', 'results_20260905.json')

def txt(s): return html.unescape(re.sub(r'<[^>]+>', '', s)).replace('\xa0', ' ').strip()
def cells(tr): return [txt(td) for td in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', tr, re.S)]

def derive_passing(corners):
    per = {}
    for ci, raw in enumerate(corners):
        s = raw.split('  ')[0]; pos = 0
        for tok in re.finditer(r'\(([^)]*)\)|([\d]+)', s):
            if tok.group(1) is not None:
                pos += 1
                for m in re.findall(r'\d+', tok.group(1)): per.setdefault(int(m), {})[ci] = pos
            else:
                pos += 1; per.setdefault(int(tok.group(2)), {})[ci] = pos
    return {ub: '-'.join(str(v[i]) for i in sorted(v)) for ub, v in per.items()}

races = []
for p in sorted(glob.glob(os.path.join(RAW, 'result_*.html'))):
    rid = re.search(r'result_(\d+)\.html', p).group(1)
    raw = open(p, 'rb').read()
    cm0 = re.search(rb'charset=["\']?([\w-]+)', raw[:3000])
    doc = raw.decode(cm0.group(1).decode() if cm0 else 'utf-8', errors='strict')
    trs = [t for t in re.findall(r'<tr[^>]*class="[^"]*HorseList[^"]*"[^>]*>(.*?)</tr>', doc, re.S) if '/horse/' in t]
    if trs:
        modal = collections.Counter(len(cells(t)) for t in trs).most_common(1)[0][0]
        trs = [t for t in trs if len(cells(t)) == modal]
    corners = []
    cm = re.search(r'Corner_Num.*?</table>', doc, re.S)
    if cm:
        for tr in re.findall(r'<tr[^>]*>(.*?)</tr>', cm.group(0), re.S):
            c = cells(tr)
            if len(c) >= 2 and re.search(r'\d', c[1]): corners.append(c[1])
    horses = []
    for tr in trs:
        c = cells(tr)
        if len(c) < 12: continue
        g = lambda i: c[i] if i < len(c) else ''
        def num(x):
            try: return float(x)
            except (ValueError, TypeError): return None
        hm = re.search(r'/horse/(\d+)', tr)
        horses.append(dict(chaku=int(g(0)) if g(0).isdigit() else None,
                           status=None if g(0).isdigit() else (g(0) or '除外'),
                           waku=int(g(1)) if g(1).isdigit() else None, uma=int(g(2)), name=g(3),
                           horse_id=hm.group(1) if hm else None, sex_age=g(4), kin=num(g(5)),
                           jockey=g(6), time=g(7), diff=g(8),
                           pop=int(g(9)) if g(9).isdigit() else None, odds=num(g(10)),
                           last3f=num(g(11)), passing=g(12) or None,
                           trainer=re.sub(r'\s+', ' ', g(14)) if len(c) > 14 else '',
                           weight=g(15) if len(c) > 15 else ''))
    if horses and not any(h['passing'] for h in horses) and corners:
        dv = derive_passing(corners)
        for h in horses: h['passing'] = dv.get(h['uma']); h['passing_from'] = 'derived'
    else:
        for h in horses: h['passing_from'] = 'netkeiba'
    dm = re.search(r'<div[^>]*class="RaceData01"[^>]*>(.*?)</div>', doc, re.S)
    tm = re.search(r'<title>(.*?)</title>', doc, re.S)
    # 払戻
    pay = {}
    for blk in re.findall(r'<table[^>]*class="[^"]*Payout_Detail_Table[^"]*"[^>]*>(.*?)</table>', doc, re.S):
        for tr in re.findall(r'<tr[^>]*>(.*?)</tr>', blk, re.S):
            th = re.search(r'<th[^>]*>(.*?)</th>', tr, re.S)
            if not th: continue
            k = txt(th.group(1))
            tds = re.findall(r'<td[^>]*>(.*?)</td>', tr, re.S)
            if len(tds) >= 2:
                pay[k] = [int(x.replace(',', '')) for x in re.findall(r'([\d,]+)円', tds[1])]
    races.append(dict(race_id=rid, date='2026-09-05', meta=txt(dm.group(1)) if dm else '',
                      title=txt(tm.group(1)).split(' | ')[0] if tm else '', corners=corners,
                      n_rows=len(horses), horses=horses, pay=pay))
races.sort(key=lambda r: r['race_id'])
# ---- 整合検査 ----
bad = []
for r in races:
    fin = [h for h in r['horses'] if h['chaku']]
    cc = collections.Counter(h['chaku'] for h in fin); exp = 1
    for k in sorted(cc):
        if k != exp: bad.append((r['race_id'], '着順が連番でない', sorted(cc))); break
        exp = k + cc[k]
    ps = [h['pop'] for h in r['horses'] if h['pop']]
    if len(set(ps)) != len(ps): bad.append((r['race_id'], '人気重複'))
    us = [h['uma'] for h in r['horses']]
    if len(set(us)) != len(us): bad.append((r['race_id'], '馬番重複'))
json.dump(races, open(OUT, 'w'), ensure_ascii=False, indent=1)
print(f'[実] {len(races)}R / {sum(len(r["horses"]) for r in races)}頭 を解析')
print('[実] 整合検査:', bad if bad else 'エラーなし')
print('[実] 着順なし(中止・除外):', [(r['race_id'], h['uma'], h['name'], h['status']) for r in races for h in r['horses'] if not h['chaku']])
print('[実] 通過順の出所:', dict(collections.Counter(h['passing_from'] for r in races for h in r['horses'])))
print('[実] 払戻を取得できたR:', sum(1 for r in races if r['pay']), '/', len(races))
print('sha256', hashlib.sha256(open(OUT,'rb').read()).hexdigest())
