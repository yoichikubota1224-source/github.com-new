#!/usr/bin/env python3
"""8/29 確定結果による採点。
荒れの定義は8/23の07報を踏襲: 1着が5番人気以下 または 上位3頭の確定人気合計>=18"""
import json, re, os, sys, collections

SP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(SP, 'predictions', '20260829')
R = json.load(open(os.path.join(P, 'results_20260829.json')))

# --- レース索引 ---
by_key = {r['racekey']: r for r in R}
by_name = {}
for r in R:
    by_name[f"{r['venue']}{r['r']}R"] = r

def arare(r):
    fin = sorted([h for h in r['horses'] if h['chakujun']], key=lambda h: h['chakujun'])
    if not fin: return None, None, None
    w = fin[0]
    top3 = [h['pop'] for h in fin[:3] if h['pop']]
    s3 = sum(top3) if len(top3) == 3 else None
    hit = (w['pop'] is not None and w['pop'] >= 5) or (s3 is not None and s3 >= 18)
    return hit, w['pop'], s3

# --- 1. 全35Rの荒れ判定 ---
A = {}
for r in R:
    hit, wp, s3 = arare(r)
    A[f"{r['venue']}{r['r']}R"] = {'arare': hit, 'win_pop': wp, 'top3sum': s3,
                                   'key': r['racekey'], 'n': r['head_count']}

# --- 2. 予想の荒れランキングを02から抽出 ---
md = open(os.path.join(P, '02_Claude独立再評価_20260829.md'), encoding='utf-8').read()
sec = md.split('### 全35Rランキング')[1].split('\n## ')[0]
rank = []
for line in sec.splitlines():
    m = re.match(r'\|\s*\*{0,2}(\d+)\*{0,2}\s*\|\s*\*{0,2}([^\|\*]+?R)\*{0,2}\s*\|', line)
    if m: rank.append((int(m.group(1)), m.group(2)))
assert len(rank) == 35, f'ランキング抽出={len(rank)}'

# --- 3. 穴馬27頭を抽出 ---
sec2 = md.split('### 支持4本以上 — 27頭')[1].split('### 荒れ上位10R')[0]
ana = []
for line in sec2.splitlines():
    c = [x.strip() for x in line.strip().strip('|').split('|')]
    if len(c) < 11 or not c[0].replace('*','').isdigit(): continue
    st = lambda s: s.replace('**','').strip()
    ana.append({'arank': int(st(c[0])), 'race': st(c[1]), 'uma': int(st(c[2])),
                'name': st(c[3]), 'jockey': st(c[4]), 'kninki': int(st(c[5])),
                'ktan': float(st(c[6])), 'kfuku': float(st(c[7])),
                'unsei': st(c[8]), 'shiji': int(st(c[9]))})
assert len(ana) == 27, f'穴馬抽出={len(ana)}'

def find(race, uma):
    r = by_name.get(race)
    if not r: return None, None
    for h in r['horses']:
        if h['umaban'] == uma: return r, h
    return r, None

out = {'races': A, 'rank': rank, 'ana': [], 'ultra': [], 'mb': []}

for a in ana:
    r, h = find(a['race'], a['uma'])
    a['chaku'] = h['chakujun'] if h else None
    a['status'] = h['status'] if h else None
    a['pop'] = h['pop'] if h else None
    a['odds'] = h['odds'] if h else None
    a['res_name'] = h['name'] if h else None
    a['arare'] = A[a['race']]['arare']
    out['ana'].append(a)

# --- 4. ウルトラ / マストバイ ---
for tag, fn in (('ultra', 'ウルトラ該当_20260829.json'), ('mb', 'マストバイ該当_20260829.json')):
    p = os.path.join(P, fn)
    if not os.path.exists(p): continue
    d = json.load(open(p))
    rows = d if isinstance(d, list) else d.get('hits', d.get('rows', []))
    for x in rows:
        ba = x.get('ba') or x.get('場') or x.get('venue')
        rr = x.get('r') or x.get('R')
        um = x.get('uma') or x.get('umaban') or x.get('馬番')
        if not (ba and rr and um): continue
        race = f"{ba}{rr}R"
        r, h = find(race, int(um))
        out[tag].append({'race': race, 'uma': int(um),
                         'name': x.get('name') or x.get('馬名') or (h['name'] if h else None),
                         'rule': x.get('rule') or x.get('cond') or x.get('no'),
                         'chaku': h['chakujun'] if h else None,
                         'pop': h['pop'] if h else None, 'odds': h['odds'] if h else None,
                         'status': h['status'] if h else None})

json.dump(out, open(os.path.join(P, '採点_20260829.json'), 'w'), ensure_ascii=False, indent=1)

# ================= 出力 =================
na = sum(1 for v in A.values() if v['arare'])
print(f'■ 荒れ判定: {na}/35R ({na/35*100:.1f}%)')
top10 = [n for _, n in rank[:10]]
hit10 = sum(1 for n in top10 if A[n]['arare'])
print(f'■ 選定上位10R: 的中 {hit10}/10 = 適合率{hit10/10*100:.0f}%  / 再現率 {hit10}/{na} = {hit10/na*100:.0f}%')
print(f'  基準率(何も選ばない場合) {na/35*100:.1f}% → リフト {(hit10/10)/(na/35):.2f}倍')
for band, sl in (('上位10R', rank[:10]), ('11-20R', rank[10:20]), ('21-35R', rank[20:])):
    h = sum(1 for _, n in sl if A[n]['arare'])
    print(f'  {band}: {h}/{len(sl)} = {h/len(sl)*100:.0f}%')
print()
print('■ 荒れ上位10Rの内訳')
for i, n in rank[:10]:
    v = A[n]
    print(f'  {i:2d}位 {n:8s} 1着{v["win_pop"]}人気 上位3頭人気計{v["top3sum"]:>3} → {"荒れ" if v["arare"] else "堅い"}')
print()
fin = [a for a in out['ana'] if a['chaku']]
win = [a for a in fin if a['chaku'] == 1]
fuku = [a for a in fin if a['chaku'] <= 3]
print(f'■ 穴馬27頭(基準人気7〜12): 出走{len(fin)} 1着{len(win)} 3着内{len(fuku)}')
print(f'  勝率{len(win)/len(fin)*100:.1f}% 複勝率{len(fuku)/len(fin)*100:.1f}%')
tan = sum(a['odds']*100 for a in win if a['odds'])
print(f'  仮定単勝回収率 {tan/(len(fin)*100)*100:.1f}%  (0円Shadow・実購入なし)')
print()
print('  3着内に来た馬:')
for a in sorted(fuku, key=lambda x: x['chaku']):
    print(f"   {a['race']:8s} {a['uma']:2d} {a['name']:<12s} 支持{a['shiji']} 運勢{a['unsei']:<3s}"
          f" 基準{a['kninki']}人気 → {a['chaku']}着 確定{a['pop']}人気 {a['odds']}倍")

# ================= 深掘り: 対照群と各指標の予測力 =================
print('\n' + '='*64)
F = json.load(open(os.path.join(P, '最終統合_20260829.json')))
res_h = {}
for r in R:
    for h in r['horses']:
        res_h[(r['racekey'], h['umaban'])] = h

rows = []
for rc in F:
    for h in rc['horses']:
        rh = res_h.get((rc['racekey'], h['uma']))
        if not rh: continue
        rows.append({'key': rc['racekey'], 'ba': None, 'r': rc['r'], 'uma': h['uma'],
                     'name': h['name'], 'kn': h['kijun_ninki'], 'ktan': h['kijun_tan'],
                     'nsup': h.get('nsup'), 'unsei': h.get('unsei'), 'MB': h.get('MB'),
                     'UL': h.get('UL'), 'total_rank': h.get('total_rank'),
                     'chaku': rh['chakujun'], 'pop': rh['pop'], 'odds': rh['odds'],
                     'status': rh['status']})
run = [x for x in rows if x['chaku']]
print(f'■ 結合: 統合{sum(len(rc["horses"]) for rc in F)}頭 / 結果482頭 / 突合成立 {len(rows)}頭 (出走{len(run)})')

def rate(sel, lab):
    s = [x for x in sel if x['chaku']]
    if not s: print(f'  {lab:<28s} n=0'); return
    w = sum(1 for x in s if x['chaku'] == 1); f3 = sum(1 for x in s if x['chaku'] <= 3)
    tan = sum(x['odds']*100 for x in s if x['chaku'] == 1 and x['odds'])
    print(f'  {lab:<28s} n={len(s):3d}  勝率{w/len(s)*100:5.1f}%  複勝率{f3/len(s)*100:5.1f}%  仮定単回{tan/(len(s)*100)*100:6.1f}%')

print('\n■ 対照群 — 基準人気帯ごとの実測(全35R)')
for lo, hi, lab in ((1,3,'基準1〜3人気'), (4,6,'基準4〜6人気'), (7,12,'基準7〜12人気(穴帯)'), (13,99,'基準13人気以下')):
    rate([x for x in rows if x['kn'] and lo <= x['kn'] <= hi], lab)

pool = [x for x in rows if x['kn'] and 7 <= x['kn'] <= 12 and x['chaku']]
p3 = sum(1 for x in pool if x['chaku'] <= 3) / len(pool)
print(f'\n  → 穴帯の母集団基準複勝率 = {p3*100:.1f}% (n={len(pool)})')
print(f'  → 推奨27頭の複勝率 11.1% は基準比 {11.1/(p3*100):.2f}倍')

print('\n■ 支持係数(nsup)別 — 穴帯のみ')
for lo, hi in ((0,2),(3,3),(4,4),(5,9)):
    lab = f'支持{lo}〜{hi}本' if lo != hi else f'支持{lo}本'
    rate([x for x in pool if x['nsup'] is not None and lo <= x['nsup'] <= hi], lab)

print('\n■ 運勢別 — 穴帯のみ (8/29はm29列=正しい参照)')
for u in ('◎◎', '◎', '○', '△', '×'):
    rate([x for x in pool if x['unsei'] == u], f'運勢{u}')
rate([x for x in pool if not x['unsei']], '運勢[不足]')

print('\n■ ⑤ウルトラ / マストバイ該当馬(全人気帯)')
rate([x for x in rows if x.get('UL')], 'ウルトラ該当')
rate([x for x in rows if x.get('MB')], 'マストバイ該当')

print('\n■ ⑦STRIDE総合順位別(全馬)')
for lo, hi in ((1,3),(4,6),(7,10),(11,99)):
    rate([x for x in rows if x['total_rank'] and lo <= x['total_rank'] <= hi], f'total_rank {lo}-{hi}位')
