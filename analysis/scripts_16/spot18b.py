#!/usr/bin/env python3
"""6軸層別(年/頭数/場/クラス/芝ダ/場×クラス)の帰無を、同一出走頭数内の置換に正して測り直す。"""
import sys, os, random, collections, re
sys.path.insert(0,'/tmp/claude-0/-home-user-github-com-new/47c1892c-ddc4-50e4-8b6f-3403a9782673/scratchpad/k5')
os.chdir('/tmp/claude-0/-home-user-github-com-new/47c1892c-ddc4-50e4-8b6f-3403a9782673/scratchpad/k5')
from final4 import load, points, BANDS
R,_=load()
BA={'01':'札幌','02':'函館','03':'福島','04':'新潟','05':'東京','06':'中山','07':'中京','08':'京都','09':'阪神','10':'小倉'}
def klass(t):
    if 'ステークス' in t or '賞' in t or re.search(r'[GＧ][ⅠⅡⅢ123]', t): pass
    for k,lab in [('新馬','新馬'),('未勝利','未勝利'),('１勝','1勝'),('1勝','1勝'),
                  ('２勝','2勝'),('2勝','2勝'),('３勝','3勝'),('3勝','3勝'),
                  ('オープン','OP')]:
        if k in t: return lab
    return '重賞/その他'
def surf(m):
    return '芝' if '芝' in (m or '') else 'ダ' if 'ダ' in (m or '') else '?'
import json
META={}
for fn in sorted(os.listdir('days2')):
    if not fn.endswith('.json'): continue
    for x in json.load(open(os.path.join('days2',fn))):
        META[x['race_id']]=(x.get('title',''), x.get('meta',''))
for r in R:
    r['jyo']=BA[str(r['rid'])[4:6]]; r['yr']=r['day'][:4]
    t,m=META.get(r['rid'],('',''))
    r['kl']=klass(t); r['sf']=surf(m)
AX=[('年',lambda r:r['yr']),('頭数',lambda r:str(r['ns'])),('場',lambda r:r['jyo']),
    ('クラス',lambda r:r['kl']),('芝ダ',lambda r:r['sf']),('場×クラス',lambda r:r['jyo']+'×'+r['kl'])]
print('クラス分布:', collections.Counter(r['kl'] for r in R))
print('芝ダ分布:', collections.Counter(r['sf'] for r in R))

COMPS=sorted({r['comp'] for r in R})
def scan(comps, getcomp, getsan, minn=100):
    inv=collections.Counter(); pay=collections.Counter(); n=collections.Counter()
    for i,r in enumerate(R):
        c=getcomp(i); s=getsan(i)
        for nm,f in AX:
            key=f(r); n[(nm,key)]+=1
        for comp in comps:
            p=points(comp,r['ns'])*100
            if not p: continue
            for nm,f in AX:
                k=(comp,nm,f(r)); inv[k]+=p
                if c==comp and s: pay[k]+=s
    res={}
    for comp in comps:
        cnt=0; mx=0
        for (cc,nm,key),iv in inv.items():
            if cc!=comp or n[(nm,key)]<minn or iv<=0: continue
            v=pay[(cc,nm,key)]/iv*100
            if v>100: cnt+=1
            mx=max(mx,v)
        res[comp]=(cnt,mx)
    return res

A='本命＋穴＋穴'; B='中穴＋中穴＋穴'
obs=scan([A,B], lambda i:R[i]['comp'], lambda i:R[i]['san'])
print('観測:', {k:(v[0],round(v[1],1)) for k,v in obs.items()})
byns=collections.defaultdict(list)
for i,r in enumerate(R): byns[r['ns']].append(i)
random.seed(101)
ex={A:[],B:[]}
IT=1000
for _ in range(IT):
    perm=list(range(len(R)))
    for ns,idxs in byns.items():
        src=idxs[:]; random.shuffle(src)
        for a,b in zip(idxs,src): perm[a]=b
    r2=scan([A,B], lambda i:R[perm[i]]['comp'], lambda i:R[perm[i]]['san'])
    for c in (A,B): ex[c].append(r2[c][0])
for c in (A,B):
    m=sum(ex[c])/IT; p=sum(1 for x in ex[c] if x>=obs[c][0])/IT
    print(f'[{c}] 100%超 観測{obs[c][0]}層  帰無期待{m:.2f}層  p(観測以上)={p:.3f}  (ITER={IT}, 同一ns内置換)')
