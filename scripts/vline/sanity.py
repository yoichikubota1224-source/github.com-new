"""full/ の健全性検査。days2(正本)との突合を含む。"""
import json, glob, os, collections
F = sorted(glob.glob('full/*.json')); D = sorted(glob.glob('days2/*.json'))
print(f'[実] full {len(F)}日 / days2 {len(D)}日')
nr=nh=njump=ndh=0; miss=collections.Counter(); pas=0; l3=0
for f in F:
    for r in json.load(open(f)):
        nr+=1; njump+=bool(r.get('jump')); ndh+=bool(r.get('dead_heat'))
        for h in r['horses']:
            nh+=1
            for k in ('pop','odds','passing','last3f','horse_id','chaku','weight'):
                if h.get(k) in (None,''): miss[k]+=1
            pas += bool(h.get('passing')); l3 += h.get('last3f') is not None
print(f'[実] 全レース {nr} / 障害 {njump} / 同着 {ndh} / 延べ出走 {nh}')
print(f'[実] 通過順位 充足 {pas}/{nh} = {pas/nh*100:.2f}%   上がり3F {l3/nh*100:.2f}%')
print('[実] 欠測(None/空):', dict(miss))
# days2 との突合
dm = {}
for f in D:
    for r in json.load(open(f)): dm[r['race_id']] = r
bad=0; chk=0
for f in F:
    for r in json.load(open(f)):
        o = dm.get(r['race_id'])
        if not o: continue
        chk+=1
        for k in ('jump','n_start','dead_heat','top3','pay','n_rows_all','meta','title'):
            if r.get(k) != o.get(k):
                bad+=1; print('  MISMATCH', r['race_id'], k); break
print(f'[実] days2との突合 {chk}R 照合 / 不一致 {bad}件')
