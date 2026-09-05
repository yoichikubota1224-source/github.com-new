#!/usr/bin/env python3
"""検算エージェントの主要指摘を当方で再確認する。"""
import sys, os, random, itertools, collections, math
sys.path.insert(0,'/tmp/claude-0/-home-user-github-com-new/47c1892c-ddc4-50e4-8b6f-3403a9782673/scratchpad/k5')
os.chdir('/tmp/claude-0/-home-user-github-com-new/47c1892c-ddc4-50e4-8b6f-3403a9782673/scratchpad/k5')
from final4 import load, sizes, points
R,_=load(); R.sort(key=lambda r:(r['day'], r['rid']))
A='本命＋穴＋穴'
def combos(r, comp):
    sz=sizes(r['ns']); bset=comp.split('＋')
    pools={'本命':list(range(1,min(3,r['ns'])+1)),'中穴':list(range(4,4+sz['中穴'])),
           '穴':list(range(7,7+sz['穴'])),'大穴':list(range(13,13+sz['大穴']))}
    cnt=collections.Counter(bset)
    per=[list(itertools.combinations(pools[b],k)) for b,k in cnt.items()]
    return [tuple(sorted(sum(t,()))) for t in itertools.product(*per)]
def tally(rows):
    buy=collections.Counter(); pay=collections.Counter()
    for r in rows:
        if points(A,r['ns'])==0: continue
        for t in combos(r,A): buy[t]+=1
        if r['comp']==A and r['san']: pay[tuple(r['pops'])]+=r['san']
    return buy,pay
def roi(sel,buy,pay):
    i=sum(buy[t] for t in sel)*100; p=sum(pay[t] for t in sel)
    return p/i*100 if i else 0

buy,pay=tally(R)
allp=sorted(buy)
print('総点種', len(allp))

# 60/40 分割
n=len(R); cut=int(n*0.6)
b1,p1=tally(R[:cut]); b2,p2=tally(R[cut:])
print(f'60/40: 前半{cut}R 後半{n-cut}R  後半の全点購入 {roi(allp,b2,p2):.2f}%')
r1={t:(p1[t]/(b1[t]*100) if b1[t] else 0) for t in allp}
top22=sorted(allp,key=lambda t:-r1[t])[:22]
d=roi(top22,b2,p2)-roi(allp,b2,p2)
print(f'  前半上位22点: 学習内 {roi(top22,b1,p1):.2f}% → 検証 {roi(top22,b2,p2):.2f}%  差 {d:+.2f}pt')
# 帰無: ランダム22点の後半回収率分布
rnd=random.Random(20260901); vals=[]
for _ in range(5000):
    s=rnd.sample(allp,22); vals.append(roi(s,b2,p2))
vals.sort()
pv=sum(1 for v in vals if v>=roi(top22,b2,p2))/len(vals)
print(f'  ランダム22点の後半分布 中央{vals[2500]:.2f}%  上側p={pv:.4f}  100%超 {sum(1 for v in vals if v>100)}/5000')

# 50/50 分割
cut2=n//2
b1b,p1b=tally(R[:cut2]); b2b,p2b=tally(R[cut2:])
r1b={t:(p1b[t]/(b1b[t]*100) if b1b[t] else 0) for t in allp}
t22b=sorted(allp,key=lambda t:-r1b[t])[:22]
print(f'50/50: 前半{cut2}R 後半{n-cut2}R  後半の全点購入 {roi(allp,b2b,p2b):.2f}%')
print(f'  前半上位22点: 学習内 {roi(t22b,b1b,p1b):.2f}% → 検証 {roi(t22b,b2b,p2b):.2f}%  差 {roi(t22b,b2b,p2b)-roi(allp,b2b,p2b):+.2f}pt')

# 後知恵の最良k点（総当り k<=5、貪欲/Dinkelbach で k>=6）
rall={t:(pay[t]/(buy[t]*100) if buy[t] else 0) for t in allp}
print('後知恵の最良k点(全期間):')
for k in (1,2,3,4,5):
    best=max(itertools.combinations(allp,k), key=lambda s: roi(s,buy,pay))
    print(f'  k={k}: {roi(best,buy,pay):.2f}%')
for k in (10,22,26,45):
    srt=sorted(allp,key=lambda t:-rall[t])[:k]
    print(f'  k={k}(回収率順): {roi(srt,buy,pay):.2f}%   平均点数/R={sum(buy[t] for t in srt)/len(R):.2f}')
