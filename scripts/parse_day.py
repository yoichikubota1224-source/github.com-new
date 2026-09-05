#!/usr/bin/env python3
"""任意日のnetkeiba結果ページ群を results_YYYYMMDD.json / 払戻_YYYYMMDD.json へ。
scripts/parse_netkeiba_results.py と同じ規約(文字化けを黙認しない・通過順は
コーナー通過順位表から復元・列数の最頻値で結果表の行を同定)を踏襲する。"""
import json, os, re, html, sys, collections
SP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = sys.argv[1]; DAY = sys.argv[2]; OUTDIR = sys.argv[3]
V = {'01':'札幌','02':'函館','03':'福島','04':'新潟','05':'東京',
     '06':'中山','07':'中京','08':'京都','09':'阪神','10':'小倉'}
NEED = {'単勝':1,'複勝':1,'枠連':2,'馬連':2,'ワイド':2,'馬単':2,'3連複':3,'3連単':3}

def txt(s): return html.unescape(re.sub(r'<[^>]+>', '', s)).replace('\xa0', ' ').strip()
def cells(tr): return [txt(x) for x in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', tr, re.S)]

def derive_passing(corners):
    per = {}
    for ci, raw in enumerate(corners):
        s = raw.split('  ')[0]; pos = 0
        for tok in re.finditer(r'\(([^)]*)\)|([\d]+)', s):
            pos += 1
            grp = tok.group(1)
            for m in (re.findall(r'\d+', grp) if grp is not None else [tok.group(2)]):
                per.setdefault(int(m), {})[ci] = pos
    return {u: '-'.join(str(v[i]) for i in sorted(v)) for u, v in per.items()}

races, pays = [], {}
ids = sorted(f[:-5] for f in os.listdir(RAW) if f.endswith('.html') and f[:8] == DAY[:4]+DAY[4:6]+'' or True)
ids = sorted({f[:-5] for f in os.listdir(RAW) if f.endswith('.html')})
target = [i for i in ids if i in set(json.load(open('/tmp/racelists.json'))[DAY])]
for rid in target:
    raw = open(os.path.join(RAW, rid + '.html'), 'rb').read()
    m = re.search(rb'charset=["\']?([\w-]+)', raw[:3000])
    doc = raw.decode(m.group(1).decode() if m else 'utf-8', errors='strict')
    trs = re.findall(r'<tr[^>]*class="[^"]*HorseList[^"]*"[^>]*>(.*?)</tr>', doc, re.S)
    cand = [t for t in trs if '/horse/' in t]
    if not cand: print('NO ROWS', rid); continue
    modal = collections.Counter(len(cells(t)) for t in cand).most_common(1)[0][0]
    trs = [t for t in cand if len(cells(t)) == modal]
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
        pos = int(c[0]) if c[0].isdigit() else None
        gi = lambda i: c[i] if i < len(c) else ''
        num = lambda x: (float(x) if re.match(r'^\d+(\.\d+)?$', x or '') else None)
        hm = re.search(r'/horse/(\d+)', tr); jm = re.search(r'/jockey/result/recent/(\w+)', tr)
        tm = re.search(r'/trainer/result/recent/(\w+)', tr)
        horses.append({'chakujun': pos, 'status': None if pos else (c[0] or '除外'),
                       'waku': gi(1), 'umaban': int(gi(2)), 'name': gi(3),
                       'horse_id': hm.group(1) if hm else None, 'sex_age': gi(4),
                       'kinryo': gi(5), 'jockey': gi(6), 'jockey_id': jm.group(1) if jm else None,
                       'time': gi(7), 'diff': gi(8),
                       'pop': int(gi(9)) if gi(9).isdigit() else None, 'odds': num(gi(10)),
                       'last3f': num(gi(11)), 'passing': gi(12) or None,
                       'trainer': gi(14) if len(c) > 14 else '',
                       'trainer_id': tm.group(1) if tm else '', 'weight': gi(15) if len(c) > 15 else ''})
    if horses and not any(h.get('passing') for h in horses) and corners:
        dv = derive_passing(corners)
        for h in horses: h['passing'] = dv.get(h['umaban']); h['passing_from'] = 'derived'
    else:
        for h in horses: h.setdefault('passing_from', 'netkeiba')
    dm = re.search(r'<div[^>]*class="RaceData01"[^>]*>(.*?)</div>', doc, re.S)
    tt = re.search(r'<title>(.*?)</title>', doc, re.S)
    ttl = txt(tt.group(1)) if tt else ''
    ba = V[rid[4:6]]; rr = int(rid[10:12])
    # 14係の主キー racekey = 場(2)+年下2桁(2)+開催回(1)+開催日目(1)+R(2)
    # 既存の確定結果ファイル(8/16・8/23・8/29・8/30)がこの8桁形式で、race_id(12桁)とは別物。
    # ここを12桁のまま入れると同一馬が別キーになり、日をまたいだ結合が壊れる。
    kai, nichi = int(rid[6:8]), int(rid[8:10])
    if kai > 9 or nichi > 9:
        raise ValueError(f'racekeyの回/日が1桁に収まりません: {rid} (回{kai} 日{nichi}) [要確認]')
    rkey = f'{rid[4:6]}{rid[2:4]}{kai}{nichi}{rid[10:12]}'
    races.append({'racekey': rkey, 'race_id': rid, 'date': f'{DAY[:4]}-{DAY[4:6]}-{DAY[6:]}',
                  'venue': ba, 'r': rr, 'label': f"{rr}R {ttl.split(' 結果')[0].strip()}",
                  'meta': txt(dm.group(1)) if dm else '', 'head_count': len(horses),
                  'corners': corners, 'horses': horses})
    p = {}
    for mm in re.finditer(r'<tr[^>]*>\s*<th[^>]*>([^<]+)</th>(.*?)</tr>', doc, re.S):
        nm = txt(mm.group(1)); body = mm.group(2)
        res = re.search(r'<td class="Result">(.*?)</td>', body, re.S)
        pyo = re.search(r'<td class="Payout">(.*?)</td>', body, re.S)
        if not (res and pyo) or nm not in NEED: continue
        nz = [t for t in (txt(x) for x in re.findall(r'<span>(.*?)</span>', res.group(1), re.S)) if t]
        k = NEED[nm]; combos = [nz[i:i+k] for i in range(0, len(nz), k)]
        yens = [txt(x) for x in re.split(r'<br\s*/?>', pyo.group(1)) if txt(x)]
        p[nm] = [('-'.join(c), y) for c, y in zip(combos, yens)]
    pays[rid] = p

races.sort(key=lambda r: (r['venue'], r['r']))
os.makedirs(OUTDIR, exist_ok=True)
# ⚠ 出力名は results確定_ とする。results_YYYYMMDD.json は日によって「予想側の評価データ」を
#   指すため(8/16・8/22が実例)、同名で中身が違うファイルを増やさない。
json.dump(races, open(os.path.join(OUTDIR, f'results確定_{DAY}.json'), 'w'), ensure_ascii=False)
json.dump(pays, open(os.path.join(OUTDIR, f'払戻_{DAY}.json'), 'w'), ensure_ascii=False, indent=1)

bad = []
for r in races:
    fin = [h for h in r['horses'] if h['chakujun']]
    from collections import Counter
    cc = Counter(sorted(h['chakujun'] for h in fin)); exp = 1; ok = True
    for k in sorted(cc):
        if k != exp: ok = False; break
        exp = k + cc[k]
    if not ok: bad.append((r['racekey'], 'chaku'))
    ps = [h['pop'] for h in r['horses'] if h['pop']]
    if len(set(ps)) != len(ps): bad.append((r['racekey'], 'pop dup'))
print(f'{DAY}: {len(races)}R {sum(len(r["horses"]) for r in races)}頭  整合エラー: {bad if bad else "なし"}')
