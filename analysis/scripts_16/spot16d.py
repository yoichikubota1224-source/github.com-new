#!/usr/bin/env python3
"""事前人気帯で定義し直したら出現率はどう動くか（遷移行列の正しい伝播）"""
import sys, os, json, collections, itertools
sys.path.insert(0,'/tmp/claude-0/-home-user-github-com-new/47c1892c-ddc4-50e4-8b6f-3403a9782673/scratchpad/k5')
os.chdir('/tmp/claude-0/-home-user-github-com-new/47c1892c-ddc4-50e4-8b6f-3403a9782673/scratchpad/k5')
from final4 import load, band, key, BANDS
BASE='/home/user/github.com-new/predictions'
# 遷移行列 P(事前帯 | 確定帯) を 943頭（出走馬内再ランク）から
trans=collections.defaultdict(collections.Counter)
for d in ('20260829','20260830'):
    pre=json.load(open(f'{BASE}/{d}/最終統合_{d}.json'))
    res=json.load(open(f'{BASE}/{d}/results_{d}.json'))
    def races(o):
        if isinstance(o,dict):
            for k in ('races','data','レース'):
                if k in o: return o[k]
            return list(o.values())
        return o
    RP={ (r.get('racekey') or r.get('rid')):r for r in races(pre)}
    RR={ (r.get('racekey') or r.get('rid')):r for r in races(res)}
    for rk in RP:
        if rk not in RR: continue
        ph={h.get('umaban') or h.get('uma'):h for h in (RP[rk].get('horses') or [])}
        rh={h.get('umaban') or h.get('uma'):h for h in (RR[rk].get('horses') or [])}
        st=[u for u,h in rh.items() if h.get('pop') is not None and u in ph and ph[u].get('kijun_ninki') is not None]
        order=sorted(st, key=lambda u: ph[u]['kijun_ninki'])
        for i,u in enumerate(order):
            trans[band(rh[u]['pop'])][band(i+1)] += 1
P={b:{a:c/sum(v.values()) for a,c in v.items()} for b,v in trans.items()}
print('P(事前帯|確定帯):')
for b in BANDS:
    if b in P: print(' ',b,{a:round(x,4) for a,x in sorted(P[b].items(), key=lambda kv:BANDS.index(kv[0]))})
R,_=load()
agg=collections.Counter(); tot=0.0
for r in R:
    dists=[P[band(p)] for p in r['pops']]
    for combo in itertools.product(*[list(d.items()) for d in dists]):
        pr=1.0
        for _,w in combo: pr*=w
        agg[key([b for b,_ in combo])]+=pr
    tot+=1
S=sum(agg.values())
print(f'Σ(伝播後の出現率) = {S/len(R)*100:.4f}%  （100%でなければモデル破綻）')
for c in ('本命＋穴＋穴','中穴＋中穴＋穴'):
    obs=sum(1 for r in R if r['comp']==c)/len(R)*100
    print(f'{c}: 確定帯 {obs:.4f}% → 事前帯（推計）{agg[c]/len(R)*100:.4f}%  ×{agg[c]/len(R)*100/obs:.3f}')
