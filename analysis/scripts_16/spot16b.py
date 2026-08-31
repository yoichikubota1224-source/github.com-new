#!/usr/bin/env python3
"""第16報§3・§5の『新潟17〜18頭 97.6%』に多重比較の帰無検定を当てる。
帰無: 場は結果と無関係。同一 ns 内で (構成, 3連複配当) を並べ替える（点数構造は不変）。"""
import sys, os, random, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))
from final4 import load, points
R,_ = load()
N=len(R)
A='本命＋穴＋穴'; B='中穴＋中穴＋穴'
BA={'01':'札幌','02':'函館','03':'福島','04':'新潟','05':'東京','06':'中山','07':'中京','08':'京都','09':'阪神','10':'小倉'}
def hb(ns):
    if ns<=9: return '3〜9頭'
    if ns<=12: return '10〜12頭'
    if ns<=14: return '13〜14頭'
    if ns<=16: return '15〜16頭'
    return '17〜18頭'
for r in R:
    r['jyo']=BA.get(str(r['rid'])[4:6],'?'); r['hb']=hb(r['ns'])
    r['lay']=(r['jyo'], r['hb'])
    r['pts']=points(A,r['ns'])+points(B,r['ns'])

def layer_stats(get_comp, get_san):
    inv=collections.Counter(); pay=collections.Counter(); n=collections.Counter()
    for i,r in enumerate(R):
        n[r['lay']]+=1; inv[r['lay']]+=r['pts']*100
        c=get_comp(i); s=get_san(i)
        if c in (A,B) and s: pay[r['lay']]+=s
    return {L:(n[L], pay[L]/inv[L]*100) for L in n if inv[L]>0 and n[L]>=200}

obs = layer_stats(lambda i: R[i]['comp'], lambda i: R[i]['san'])
srt = sorted(obs.items(), key=lambda kv:-kv[1][1])
print(f'母数200以上の層: {len(obs)}')
for L,(n,v) in srt[:6]: print(f'  {L[0]} {L[1]}: n={n} 回収{v:.2f}%')
obs_max = srt[0][1][1]; obs_over = sum(1 for _,(n,v) in obs.items() if v>100)
print(f'観測: 最大 {obs_max:.2f}%  100%超の層 {obs_over}')

by_ns=collections.defaultdict(list)
for i,r in enumerate(R): by_ns[r['ns']].append(i)
random.seed(20260831)
B_ITER=3000
maxes=[]; overs=[]
for it in range(B_ITER):
    perm=[0]*N
    for ns,idxs in by_ns.items():
        src=idxs[:]; random.shuffle(src)
        for a,b in zip(idxs,src): perm[a]=b
    st = layer_stats(lambda i: R[perm[i]]['comp'], lambda i: R[perm[i]]['san'])
    vals=[v for _,v in st.values()]
    maxes.append(max(vals)); overs.append(sum(1 for v in vals if v>100))
maxes.sort()
p_max = sum(1 for m in maxes if m>=obs_max)/B_ITER
p_over= sum(1 for o in overs if o>=obs_over)/B_ITER
print(f'帰無({B_ITER}回): 最大回収率の中央値 {maxes[B_ITER//2]:.2f}%  95%点 {maxes[int(B_ITER*0.95)]:.2f}%')
print(f'  観測最大 {obs_max:.2f}% の family-wise p = {p_max:.3f}')
print(f'  100%超の層数 期待 {sum(overs)/B_ITER:.2f}  観測 {obs_over}  p = {p_over:.3f}')
