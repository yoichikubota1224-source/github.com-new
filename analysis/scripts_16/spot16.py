#!/usr/bin/env python3
"""第16報 改訂のための自前スポット検算（検証エージェントの主要数値を独立確認）"""
import sys, os, json, math, random, collections, itertools
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))
from final4 import load, band, sizes, points, BANDS, key
from fractions import Fraction
from math import comb

R, skip = load()
N = len(R)
print('N =', N, 'skip =', dict(skip))

A = '本命＋穴＋穴'; B = '中穴＋中穴＋穴'
def stats(comp):
    inv = hit = pay = 0; pts = []
    for r in R:
        p = points(comp, r['ns']); pts.append(p)
        inv += p*100
        if r['comp'] == comp and r['san']:
            hit += 1; pay += r['san']
    return dict(inv=inv, hit=hit, pay=pay, roi=pay/inv*100, mean_pts=sum(pts)/N,
                mean_pay=pay/hit if hit else 0, occ=sum(1 for r in R if r['comp']==comp)/N*100)
sa, sb = stats(A), stats(B)
for nm,s in (('A '+A,sa),('B '+B,sb)):
    print(f"{nm}: 出現{s['occ']:.4f}% 的中{s['hit']} 平均点{s['mean_pts']:.4f} 回収{s['roi']:.4f}% "
          f"分岐点数{s['mean_pts']*s['roi']/100:.4f} 必要倍率{100/s['roi']:.4f}")

# (1) 恒等式: 分岐点数/平均点 == 回収率, 必要倍率 == 1/回収率 （全構成で厳密）
comps = sorted({r['comp'] for r in R})
ok1=ok2=0; tot=0
for c in comps:
    inv = sum(points(c, r['ns']) for r in R)*100
    pay = sum(r['san'] for r in R if r['comp']==c and r['san'])
    if inv==0 or pay==0: continue
    tot+=1
    roi = Fraction(pay, inv)
    mp  = Fraction(sum(points(c, r['ns']) for r in R), N)
    bp  = Fraction(pay, 100*N)           # 分岐点数
    hit = sum(1 for r in R if r['comp']==c and r['san'])
    mpay= Fraction(pay, hit)
    need= Fraction(100)*mp/mpay          # 必要出現率
    cur = Fraction(hit, N)
    if bp/mp == roi: ok1+=1
    if need/cur == 1/roi: ok2+=1
print(f'(1) 恒等式: 分岐点数/平均点==回収率 {ok1}/{tot}, 必要出現率倍率==1/回収率 {ok2}/{tot}')

# (2) log(平均配当) ~ log(1点あたり的中率) の回帰
xs=[]; ys=[]
for c in comps:
    hit = sum(1 for r in R if r['comp']==c and r['san'])
    pay = sum(r['san'] for r in R if r['comp']==c and r['san'])
    pts = sum(points(c, r['ns']) for r in R)
    if hit==0 or pts==0: continue
    xs.append(math.log(hit/pts)); ys.append(math.log(pay/hit))
def reg(xs,ys):
    n=len(xs); mx=sum(xs)/n; my=sum(ys)/n
    sxy=sum((a-mx)*(b-my) for a,b in zip(xs,ys)); sxx=sum((a-mx)**2 for a in xs)
    syy=sum((b-my)**2 for b in ys)
    return sxy/sxx, sxy/math.sqrt(sxx*syy)
sl,r = reg(xs,ys); print(f'(2) 19構成 log-log 傾き {sl:.4f} r {r:.4f} (n={len(xs)})')
# 逆側: log(回収率)~log(1点あたり的中率)
ys2=[math.log(math.exp(y)*math.exp(x)) for x,y in zip(xs,ys)]
sl2,r2 = reg(xs,ys2); print(f'    log(回収率)~log(的中率) 傾き {sl2:.4f} r {r2:.4f}')

# (3) 点(確定人気の三つ組)レベル: A構成の45点
random.seed(20260831)
def point_level(comp):
    bset = comp.split('＋')
    # 各レースで comp に対応する点の集合を人気三つ組で列挙するのは重いので、
    # 「実際に的中した三つ組」と「買われた回数」を集計
    buy = collections.Counter(); hit = collections.Counter(); pay = collections.Counter()
    for r in R:
        p = points(comp, r['ns'])
        if p==0: continue
        sz = sizes(r['ns'])
        pools = {'本命': list(range(1,min(3,r['ns'])+1)),
                 '中穴': list(range(4,4+sz['中穴'])),
                 '穴'  : list(range(7,7+sz['穴'])),
                 '大穴': list(range(13,13+sz['大穴']))}
        cnt = collections.Counter(bset)
        combos=[]
        per=[list(itertools.combinations(pools[b], k)) for b,k in cnt.items()]
        for tup in itertools.product(*per):
            t = tuple(sorted(sum(tup, ())))
            combos.append(t)
        for t in combos: buy[t]+=1
        if r['comp']==comp and r['san']:
            t=tuple(r['pops']); hit[t]+=1; pay[t]+=r['san']
    return buy, hit, pay
buy,hit,pay = point_level(A)
print(f'(3) A構成の点数(異なる三つ組) {len(buy)}')
rate = {t: hit[t]/buy[t] for t in buy}
top = sorted(buy, key=lambda t:-rate[t])
k = round(len(buy)*0.25)
inv_t = sum(buy[t] for t in top[:k])*100; pay_t = sum(pay[t] for t in top[:k])
print(f'    的中率上位{k}点のみ購入 → 回収率 {pay_t/inv_t*100:.1f}%')
# 後知恵ベスト22点
roi_t = {t: (pay[t]/(buy[t]*100)) for t in buy}
best = sorted(buy, key=lambda t:-roi_t[t])
for kk in (5,10,22,45):
    kk=min(kk,len(buy))
    i=sum(buy[t] for t in best[:kk])*100; p=sum(pay[t] for t in best[:kk])
    print(f'    後知恵ベスト{kk}点 → 回収率 {p/i*100:.1f}%')
# ランダム22点
res=[]
allp=list(buy)
for _ in range(2000):
    s=random.sample(allp, min(22,len(allp)))
    i=sum(buy[t] for t in s)*100; p=sum(pay[t] for t in s)
    res.append(p/i*100)
res.sort()
print(f'    ランダム22点 中央値 {res[len(res)//2]:.2f}% 5-95% [{res[100]:.2f}, {res[1900]:.2f}] 100%超 {sum(1 for x in res if x>100)}/2000')

# (4) A-B 差のペアード・ブートストラップ
random.seed(1224)
idx=list(range(N))
def roi_of(sample, comp):
    inv=pay=0
    for i in sample:
        r=R[i]; inv+=points(comp,r['ns'])*100
        if r['comp']==comp and r['san']: pay+=r['san']
    return pay/inv*100 if inv else 0
# 高速化: 事前に配列化
PA=[points(A,r['ns'])*100 for r in R]; YA=[r['san'] if (r['comp']==A and r['san']) else 0 for r in R]
PB=[points(B,r['ns'])*100 for r in R]; YB=[r['san'] if (r['comp']==B and r['san']) else 0 for r in R]
diffs=[]; rois_a=[]; rois_b=[]
for _ in range(4000):
    ia=random.choices(idx,k=N)
    ia_pa=sum(PA[i] for i in ia); ia_ya=sum(YA[i] for i in ia)
    ia_pb=sum(PB[i] for i in ia); ia_yb=sum(YB[i] for i in ia)
    ra=ia_ya/ia_pa*100; rb=ia_yb/ia_pb*100
    rois_a.append(ra); rois_b.append(rb); diffs.append(ra-rb)
diffs.sort(); rois_a.sort(); rois_b.sort()
print(f'(4) A-B = {sa["roi"]-sb["roi"]:+.2f}pt  95%CI [{diffs[100]:+.2f}, {diffs[3900]:+.2f}]  P(A>B)={sum(1 for d in diffs if d>0)/len(diffs):.3f}')
print(f'    A 95%CI [{rois_a[100]:.2f}, {rois_a[3900]:.2f}]  必要倍率 [{100/rois_a[3900]:.3f}, {100/rois_a[100]:.3f}]')
print(f'    B 95%CI [{rois_b[100]:.2f}, {rois_b[3900]:.2f}]  必要倍率 [{100/rois_b[3900]:.3f}, {100/rois_b[100]:.3f}]')
print(f'    100%超 A {sum(1 for x in rois_a if x>100)}/4000  B {sum(1 for x in rois_b if x>100)}/4000')
