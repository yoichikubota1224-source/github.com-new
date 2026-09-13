#!/usr/bin/env python3
"""第14報の層別頑健性CSVに、ペアード・ブートストラップCIと多重比較の判定を付ける。
高速化: レースを「(点数A,点数B,払戻A,払戻B)が同一」のセルに畳み、
セル単位のポアソン・ブートストラップ(重み~Poisson(1)の和=Poisson(セル件数))で再標本化する。"""
import sys, os, random, math, collections
sys.path.insert(0,'/tmp/claude-0/-home-user-github-com-new/47c1892c-ddc4-50e4-8b6f-3403a9782673/scratchpad/k5')
os.chdir('/tmp/claude-0/-home-user-github-com-new/47c1892c-ddc4-50e4-8b6f-3403a9782673/scratchpad/k5')
from final4 import load, points
R,_ = load()
A='本命＋穴＋穴'; B='中穴＋中穴＋穴'
BA={'01':'札幌','02':'函館','03':'福島','04':'新潟','05':'東京','06':'中山','07':'中京','08':'京都','09':'阪神','10':'小倉'}
def hb(ns):
    return '3-9頭' if ns<=9 else '10-12頭' if ns<=12 else '13-14頭' if ns<=14 else '15-16頭' if ns<=16 else '17-18頭'
for r in R:
    r['jyo']=BA[str(r['rid'])[4:6]]; r['hb']=hb(r['ns']); r['yr']=r['day'][:4]
    r['pa']=points(A,r['ns'])*100; r['pb']=points(B,r['ns'])*100
    r['ya']=r['san'] if (r['comp']==A and r['san']) else 0
    r['yb']=r['san'] if (r['comp']==B and r['san']) else 0

LAYERS=[('全体','全体',lambda r:True)]
for h in ['3-9頭','10-12頭','13-14頭','15-16頭','17-18頭']:
    LAYERS.append(('頭数',h,(lambda hh: (lambda r: r['hb']==hh))(h)))
for y in ['2021','2022','2023','2024','2025','2026']:
    LAYERS.append(('年',y,(lambda yy: (lambda r: r['yr']==yy))(y)))
for j in ['札幌','函館','福島','新潟','東京','中山','中京','京都','阪神','小倉']:
    LAYERS.append(('場',j,(lambda jj: (lambda r: r['jyo']==jj))(j)))

def pois(lam, rnd):
    """Poisson(lam) 乱数。lam が大きいときは正規近似+連続性補正。"""
    if lam < 30:
        L=math.exp(-lam); k=0; p=1.0
        while True:
            p*=rnd.random()
            if p<=L: return k
            k+=1
    v=rnd.gauss(lam, math.sqrt(lam))
    return max(0, int(v+0.5))

BOOT=20000
rows=[]; raw_p=[]
rnd=random.Random(20260901)
for kind,name,f in LAYERS:
    S=[r for r in R if f(r)]
    n=len(S)
    cells=collections.Counter((r['pa'],r['pb'],r['ya'],r['yb']) for r in S)
    C=[(k[0],k[1],k[2],k[3],c) for k,c in cells.items()]
    ia=sum(pa*c for pa,pb,ya,yb,c in C); pay_a=sum(ya*c for pa,pb,ya,yb,c in C)
    ib=sum(pb*c for pa,pb,ya,yb,c in C); pay_b=sum(yb*c for pa,pb,ya,yb,c in C)
    ra=pay_a/ia*100; rb=pay_b/ib*100; d=ra-rb
    ds=[]
    for _ in range(BOOT):
        sa=sb=qa=qb=0
        for pa,pb,ya,yb,c in C:
            w=pois(c,rnd)
            if w:
                sa+=pa*w; sb+=pb*w
                if ya: qa+=ya*w
                if yb: qb+=yb*w
        ds.append(qa/sa*100 - qb/sb*100)
    ds.sort()
    lo=ds[int(BOOT*0.025)]; hi=ds[int(BOOT*0.975)]
    pr=min(1.0, 2*min(sum(1 for x in ds if x<=0), sum(1 for x in ds if x>=0))/BOOT)
    raw_p.append(pr)
    rows.append([kind,name,n,f'{ra:.2f}',f'{rb:.2f}',f'{d:+.2f}',f'{lo:+.2f}',f'{hi:+.2f}',
                 'YES' if lo<=0<=hi else 'NO', f'{pr:.4f}'])
    print(f'{kind}/{name}: n={n} cells={len(C)} A={ra:.2f} B={rb:.2f} d={d:+.2f} CI[{lo:+.2f},{hi:+.2f}] p={pr:.4f}', flush=True)

m=len(rows)-1
order=sorted(range(1,len(rows)), key=lambda i: raw_p[i])
bh={}; prev=1.0
for rank,i in enumerate(reversed(order),start=1):
    k=m-rank+1
    q=min(prev, raw_p[i]*m/k); prev=q; bh[i]=q
for i,row in enumerate(rows):
    if i==0: row += ['-','-','（基準・多重比較の対象外）']
    else:
        bonf=min(1.0, raw_p[i]*m)
        row += [f'{bonf:.4f}', f'{bh[i]:.4f}', '有意' if bh[i]<0.05 else '区別できない']
hdr=['層の種類','層','母数','穴＋穴＋本命%','穴＋中穴＋中穴%','差pt(A-B)',
     'CI下限','CI上限','CIが0を含む','素のp(両側)','Bonferroni p','BH q','判定']
out='/home/user/github.com-new/analysis/17_層別頑健性_CI付き_正本定義.csv'
with open(out,'w',encoding='utf-8') as fp:
    fp.write(','.join(hdr)+'\n')
    for row in rows: fp.write(','.join(str(x) for x in row)+'\n')
print('\n--- 書き出し ---'); print(open(out,encoding='utf-8').read())
print('BOOT=',BOOT,'多重比較の対象層数 m=',m)
