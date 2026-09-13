#!/usr/bin/env python3
"""結果ページから「上位3着の確定人気」と「払戻」を取り出す。
規約(parse_day.py 踏襲):
  - 文字化けを黙認しない / [不足]を0で埋めない
  - 結果表の行は「列数の最頻値」で同定する
    ⚠ 2025年1月以降のページは、同じ class="HorseList" を持つ拡張テーブル(24〜27列)が
      追加されており、列数で切らないと幽霊行が混入する(馬番欄に馬名が入る行がある)
  - 人気/オッズは列位置ではなくCSSクラスで同定
    人気 = class に Odds と Txt_C / 単勝オッズ = Odds と Txt_R (2021年〜2026年で共通)
  - 同着で上位3着が3頭にならない場合は捨てずに dead_heat=True で明示する"""
import re, html, sys, json, os, collections

def txt(s): return html.unescape(re.sub(r'<[^>]+>', '', s)).replace('\xa0', ' ').strip()

def parse(doc, rid):
    o = {'race_id': rid}
    dm = re.search(r'<div[^>]*class="RaceData01"[^>]*>(.*?)</div>', doc, re.S)
    tt = re.search(r'<title>(.*?)</title>', doc, re.S)
    meta = txt(dm.group(1)) if dm else ''
    title = (txt(tt.group(1)) if tt else '').split('|')[0].strip()
    o['meta'] = meta; o['title'] = title
    o['jump'] = ('障' in meta) or ('障害' in title)

    raw = []
    for tr in re.findall(r'<tr[^>]*class="[^"]*HorseList[^"]*"[^>]*>(.*?)</tr>', doc, re.S):
        c = [(re.search(r'class="([^"]*)"', a).group(1) if 'class="' in a else '', txt(v))
             for _t, a, v in re.findall(r'<(t[dh])([^>]*)>(.*?)</\1>', tr, re.S)]
        raw.append(c)
    if not raw: return {**o, 'n_rows': 0, 'n_start': 0, 'top3': [], 'pay': {}, 'dead_heat': False}
    mode = collections.Counter(len(c) for c in raw).most_common(1)[0][0]
    rows = [c for c in raw if len(c) == mode]
    o['n_rows_all'] = len(raw); o['mode_cols'] = mode

    horses = []
    for c in rows:
        def iv(s): return int(s) if re.fullmatch(r'\d+', (s or '').strip()) else None
        uma = iv(c[2][1]) if len(c) > 2 else None
        if uma is None: continue                     # 馬番が整数でない行は結果行ではない
        chaku = iv(c[0][1]); pop = odds = None
        for cls, v in c:
            if 'Odds' in cls and 'Txt_C' in cls and pop is None: pop = iv(v)
            elif 'Odds' in cls and 'Txt_R' in cls and odds is None:
                try: odds = float(v)
                except ValueError: pass
        horses.append({'chaku': chaku, 'uma': uma, 'pop': pop, 'odds': odds,
                       'status': None if chaku is not None else c[0][1].strip()})
    o['n_rows'] = len(horses)
    o['n_start'] = sum(1 for h in horses if h['chaku'] is not None or h['status'] == '中止')
    top = sorted([h for h in horses if h['chaku'] in (1, 2, 3)], key=lambda h: h['chaku'])
    o['dead_heat'] = len(top) != 3
    o['top3'] = [{'chaku': h['chaku'], 'uma': h['uma'], 'pop': h['pop'], 'odds': h['odds']} for h in top]

    pays = {}
    for mm in re.finditer(r'<tr[^>]*>\s*<th[^>]*>([^<]+)</th>(.*?)</tr>', doc, re.S):
        nm = txt(mm.group(1)); py = re.search(r'<td class="Payout">(.*?)</td>', mm.group(2), re.S)
        if not py: continue
        vals = []
        for y in re.split(r'<br\s*/?>', py.group(1)):
            y = txt(y).replace(',', '').replace('円', '').strip()
            if re.fullmatch(r'\d+', y): vals.append(int(y))
        if vals: pays[nm] = vals
    o['pay'] = pays
    return o

if __name__ == '__main__':
    src, dst = sys.argv[1], sys.argv[2]
    res = [parse(open(os.path.join(src, f), encoding='utf-8', errors='strict').read(), f[:-5])
           for f in sorted(os.listdir(src)) if f.endswith('.html')]
    json.dump(res, open(dst, 'w'), ensure_ascii=False)
    print(len(res), '->', dst)
