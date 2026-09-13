#!/usr/bin/env python3
"""結果ページから【全出走馬】を取り出す（extract.py の上位互換）。
extract.py との違い:
  - top3 だけでなく全馬を horses[] に保持
  - 通過順位(PassageRate)・上がり3F・馬名・horse_id・枠番・騎手・厩舎・馬体重・斤量を追加
規約（extract.py を踏襲）:
  - 文字化けを黙認しない / [不足]を0で埋めない（取れなければ None）
  - 結果表の行は「列数の最頻値」で同定（2025-01以降の拡張テーブル混入対策）
  - 列は**位置ではなくCSSクラス**で同定
  - 同着で上位3着が3頭にならない場合は dead_heat=True で明示
"""
import re, html, sys, json, os, collections, gzip

def txt(s): return html.unescape(re.sub(r'<[^>]+>', '', s)).replace('\xa0', ' ').strip()
def iv(s):
    s = (s or '').strip()
    return int(s) if re.fullmatch(r'\d+', s) else None
def fv(s):
    s = (s or '').strip()
    try: return float(s)
    except (TypeError, ValueError): return None

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
        cells = []
        for _t, attr, val in re.findall(r'<(t[dh])([^>]*)>(.*?)</\1>', tr, re.S):
            m = re.search(r'class="([^"]*)"', attr)
            cells.append((m.group(1) if m else '', val))   # ← 生HTMLも保持(hrefが要る)
        raw.append(cells)
    if not raw:
        return {**o, 'n_rows': 0, 'n_start': 0, 'horses': [], 'top3': [], 'pay': {}, 'dead_heat': False}
    mode = collections.Counter(len(c) for c in raw).most_common(1)[0][0]
    rows = [c for c in raw if len(c) == mode]
    o['n_rows_all'] = len(raw); o['mode_cols'] = mode

    horses = []
    for c in rows:
        get = lambda pred: next((v for cls, v in c if pred(cls)), None)
        uma = iv(txt(get(lambda k: 'Num' in k and 'Txt_C' in k) or ''))
        if uma is None: continue          # 馬番が整数でない行は結果行ではない
        chaku_raw = txt(c[0][1]) if c else ''
        times = [txt(v) for cls, v in c if cls.split() and cls.split()[0] == 'Time']
        hi = get(lambda k: k.strip() == 'Horse_Info')
        hid = None
        if hi:
            mh = re.search(r'/horse/(\w+)', hi)
            if mh: hid = mh.group(1)
        h = {
            'chaku'   : iv(chaku_raw),
            'status'  : None if iv(chaku_raw) is not None else (chaku_raw or None),
            'uma'     : uma,
            'waku'    : iv(txt(get(lambda k: 'Num' in k and 'Waku' in k) or '')),
            'name'    : txt(hi or '') or None,
            'horse_id': hid,
            'sex_age' : txt(get(lambda k: 'Horse_Info' in k and 'Txt_C' in k) or '') or None,
            'kinryo'  : fv(txt(get(lambda k: 'Jockey_Info' in k) or '')),
            'jockey'  : txt(get(lambda k: k.strip() == 'Jockey') or '') or None,
            'time'    : (times[0] or None) if times else None,
            'diff'    : (times[1] or None) if len(times) > 1 else None,
            'pop'     : iv(txt(get(lambda k: 'Odds' in k and 'Txt_C' in k) or '')),
            'odds'    : fv(txt(get(lambda k: 'Odds' in k and 'Txt_R' in k) or '')),
            'last3f'  : fv(times[2]) if len(times) > 2 else None,
            'passing' : txt(get(lambda k: 'PassageRate' in k) or '') or None,
            'trainer' : re.sub(r'\s+', ' ', txt(get(lambda k: 'Trainer' in k) or '')) or None,
            'weight'  : txt(get(lambda k: 'Weight' in k) or '') or None,
        }
        horses.append(h)
    o['horses'] = horses
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

def read(p):
    if p.endswith('.gz'):
        return gzip.open(p, 'rt', encoding='utf-8', errors='strict').read()
    return open(p, encoding='utf-8', errors='strict').read()

if __name__ == '__main__':
    src, dst = sys.argv[1], sys.argv[2]
    res = []
    for f in sorted(os.listdir(src)):
        if not (f.endswith('.html') or f.endswith('.html.gz')): continue
        rid = f.split('.')[0]
        res.append(parse(read(os.path.join(src, f)), rid))
    json.dump(res, open(dst, 'w'), ensure_ascii=False)
    print(len(res), '->', dst)
