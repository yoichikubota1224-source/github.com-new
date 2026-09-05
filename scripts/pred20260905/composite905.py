#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""複合（係またぎ）v2: ⑤MB/UL × ⑭次走(v1.4) × 穴帯(基準人気7〜12) × ⑥調教 × ⑨運勢 を1頭ごとに並べる。
⚠ 複合は「同じ馬に複数の係の印が付いた」記録であり、序列でも軸でも推奨でもない。
⚠ 運勢は◎◎/◎を「押し上げあり」としてだけ数え、×は数えない（消し根拠にしない）。
⚠ 調教は best_c2 が A3/A2、または last_d2 の z1f ≤ -1.0 を「調教印」とする。[不足]は印なしであって減点ではない。"""
import json, os, collections
D = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'predictions', '20260905')
T = json.load(open(os.path.join(D, 'toukei_20260905.json')))
C = json.load(open(os.path.join(D, 'chokyo_20260905.json')))['horses']
U = json.load(open(os.path.join(D, 'unsei_20260905.json')))['horses']
J = {(h['ba'], h['r'], h['uma']): h for h in json.load(open(os.path.join(D, 'jisou905.json')))['hits']}
rows = []
for rc in T:
    for h in rc['horses']:
        if h['scratched']:
            continue
        key = f"{rc['ba']}|{rc['r']}|{h['uma']}"
        c = C.get(key, {}); u = U.get(key, {}); j = J.get((rc['ba'], rc['r'], h['uma']))
        flags = []
        if h['MB']: flags.append('MB')
        if h['UL']: flags.append('UL')
        if j: flags.append('次走')
        if h.get('kijun_ninki') and 7 <= h['kijun_ninki'] <= 12: flags.append('穴帯')
        cho = None
        if c.get('status') == '[実]':
            z = (c.get('last_d2') or {}).get('z1f')
            if c.get('best_c2') in ('A3', 'A2') or (z is not None and z <= -1.0):
                flags.append('調教'); cho = f"{c.get('best_c2') or '-'}/z{z:+.2f}" if z is not None else f"{c.get('best_c2')}"
        if u.get('jockey_mark') in ('◎◎', '◎'): flags.append('運勢')
        rows.append(dict(ba=rc['ba'], r=rc['r'], title=rc['title'], one=rc['v21']['ONE_HOLE'] if rc['v21'] else None,
                         v21_domain=rc['v21_domain'], n=rc['n_live'], uma=h['uma'], waku=h['waku'], name=h['name'],
                         sire=h['sire'], jockey=h['jockey'], kn=h.get('kijun_ninki'), kt=h['kijun_tan'],
                         compi=h['compi_rank'], idm=h['IDM'], uma_idx=h['uma_idx'], total_rank=h['total_rank'],
                         sinrai=h['sinrai'], myoumi=h['myoumi'],
                         jisou=(f"{j['tier']}/sc{j['score']}" if j else None),
                         # 第5報: 新聞の調教欄（別媒体。TARGETのC-2やz1fへ換算しない。印にもしない）
                         shinbun_oikiri=h.get('saishu_oikiri'), shinbun_chokyo_idx=h.get('chokyo_idx'),
                         st_idx=h.get('st_idx'),   # ⚠ ST指数=IDM+3（446/446）。IDMと独立な能力票として二重に数えない
                         MB=h['MB'], UL=h['UL'], chokyo=cho, chokyo_status=c.get('status'),
                         unsei_j=u.get('jockey_mark'), unsei_t=u.get('trainer_mark'),
                         flags=flags, nflag=len(flags)))
json.dump(rows, open(os.path.join(D, 'composite.json'), 'w'), ensure_ascii=False, indent=1)
cnt = collections.Counter(r['nflag'] for r in rows)
print('[実] 出走', len(rows), '頭 / 係またぎ数の分布', dict(sorted(cnt.items())))
print('[実] 印の延べ数', dict(collections.Counter(f for r in rows for f in r['flags'])))
print('[実] 組み合わせ(2係以上)', dict(collections.Counter('+'.join(r['flags']) for r in rows if r['nflag'] >= 2).most_common(20)))
print('\n== 3係以上 ==')
for r in sorted([r for r in rows if r['nflag'] >= 3], key=lambda r: (-r['nflag'], -(r['one'] or 0))):
    print(f"  {r['ba']}{r['r']:>2}R ONE{r['one']} {r['uma']:>2} {r['name']:<12} 基準人気{r['kn']} {'+'.join(r['flags'])}  次走={r['jisou']} 調教={r['chokyo']} 運勢={r['unsei_j']}")
