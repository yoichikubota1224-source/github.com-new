#!/usr/bin/env python3
"""場×頭数33層の『最大出現率』に family-wise 検定をかける（同一出走頭数内の置換）。"""
import sys, os, random, collections
sys.path.insert(0,'/tmp/claude-0/-home-user-github-com-new/47c1892c-ddc4-50e4-8b6f-3403a9782673/scratchpad/k5')
os.chdir('/tmp/claude-0/-home-user-github-com-new/47c1892c-ddc4-50e4-8b6f-3403a9782673/scratchpad/k5')
from final4 import load, points
R,_=load()
BA={'01':'札幌','02':'函館','03':'福島','04':'新潟','05':'東京','06':'中山','07':'中京','08':'京都','09':'阪神','10':'小倉'}
def hb(ns):
    return '3〜9頭' if ns<=9 else '10〜12頭' if ns<=12 else '13〜14頭' if ns<=14 else '15〜16頭' if ns<=16 else '17〜18頭'
A='本命＋穴＋穴'; B='中穴＋中穴＋穴'
for r in R:
    r['lay']=(BA[str(r['rid'])[4:6]], hb(r['ns']))
    r['hit2']=1 if r['comp'] in (A,B) else 0
n=collections.Counter(r['lay'] for r in R)
LAY=[k for k,v in n.items() if v>=200]
print('母数200以上の層数:', len(LAY))
def maxocc(gethit):
    c=collections.Counter()
    for i,r in enumerate(R):
        if gethit(i): c[r['lay']]+=1
    best=None; arg=None
    for k in LAY:
        v=c[k]/n[k]*100
        if best is None or v>best: best=v; arg=k
    return best,arg
obs,arg=maxocc(lambda i:R[i]['hit2'])
print(f'観測の最大出現率 {obs:.4f}%  層={arg}  (全体 {sum(r["hit2"] for r in R)/len(R)*100:.4f}%)')
byns=collections.defaultdict(list)
for i,r in enumerate(R): byns[r['ns']].append(i)
random.seed(20260901)
IT=5000
vals=[]
for _ in range(IT):
    perm=list(range(len(R)))
    for ns,idxs in byns.items():
        src=idxs[:]; random.shuffle(src)
        for a,b in zip(idxs,src): perm[a]=b
    v,_a=maxocc(lambda i:R[perm[i]]['hit2'])
    vals.append(v)
vals.sort()
p=sum(1 for v in vals if v>=obs)/IT
print(f'帰無({IT}回・同一ns内置換): 最大出現率の中央値 {vals[IT//2]:.4f}%  95%点 {vals[int(IT*0.95)]:.4f}%  最大 {vals[-1]:.4f}%')
print(f'family-wise p = {p:.4f}')
# 素の片側p（新潟17-18頭のみ）
k=arg; cnt=0
for _ in range(IT):
    perm=list(range(len(R)))
    for ns,idxs in byns.items():
        src=idxs[:]; random.shuffle(src)
        for a,b in zip(idxs,src): perm[a]=b
    c=sum(1 for i,r in enumerate(R) if r['lay']==k and R[perm[i]]['hit2'])
    if c/n[k]*100 >= obs: cnt+=1
print(f'新潟17〜18頭 単独の片側p = {cnt/IT:.4f}')
# 前後半の安定性
half=len(R)//2
for lab,rows in (('前半',R[:half]),('後半',R[half:])):
    nn=sum(1 for r in rows if r['lay']==k); hh=sum(r['hit2'] for r in rows if r['lay']==k)
    tot=sum(r['hit2'] for r in rows)/len(rows)*100
    print(f'  {lab}: 新潟17-18頭 {hh}/{nn}={hh/nn*100 if nn else 0:.2f}%  全体{tot:.2f}%  比{(hh/nn*100)/tot if nn else 0:.2f}倍')
