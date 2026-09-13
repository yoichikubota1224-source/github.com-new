#!/usr/bin/env python3
"""§4(データリーク実測)の再検算: 競走除外による『土俵ズレ』の補正"""
import json, collections
BASE='/home/user/github.com-new/predictions'
def band(p):
    return '本命' if p<=3 else '中穴' if p<=6 else '穴' if p<=12 else '大穴'
rows=[]; exc=collections.Counter()
for d in ('20260829','20260830'):
    pre=json.load(open(f'{BASE}/{d}/最終統合_{d}.json'))
    res=json.load(open(f'{BASE}/{d}/results_{d}.json'))
    # 構造確認
    def races(o):
        if isinstance(o,dict):
            for k in ('races','data','レース'):
                if k in o: return o[k]
            return list(o.values())
        return o
    RP={}; RR={}
    for r in races(pre):
        rk = r.get('racekey') or r.get('race_key') or r.get('rid')
        RP[rk]=r
    for r in races(res):
        rk = r.get('racekey') or r.get('race_key') or r.get('rid')
        RR[rk]=r
    for rk in RP:
        if rk not in RR: continue
        pr=RP[rk]; rr=RR[rk]
        ph={h['umaban'] if 'umaban' in h else h.get('uma'): h for h in (pr.get('horses') or [])}
        rh={h['umaban'] if 'umaban' in h else h.get('uma'): h for h in (rr.get('horses') or [])}
        starters=[u for u,h in rh.items() if h.get('pop') is not None]
        # 出走馬内での kijun_ninki 再ランク
        kn={u: ph[u].get('kijun_ninki') for u in starters if u in ph}
        order=sorted([u for u in kn if kn[u] is not None], key=lambda u: kn[u])
        rerank={u:i+1 for i,u in enumerate(order)}
        for u in starters:
            if u not in ph or kn.get(u) is None: continue
            rows.append(dict(rk=rk, uma=u, kn=kn[u], kn2=rerank[u], pop=rh[u]['pop']))
        if len(starters) != len(ph): exc[rk]=len(ph)-len(starters)
print('突合行数', len(rows), '／ 除外等のあるレース', dict(exc))
def rep(kkey,label):
    m=sum(1 for r in rows if band(r[kkey])==band(r['pop']))
    ana=[r for r in rows if band(r['pop'])=='穴']
    a2=sum(1 for r in ana if band(r[kkey])=='穴')
    c67=sum(1 for r in rows if (r[kkey]<=6)!=(r['pop']<=6))
    c1213=sum(1 for r in rows if (r[kkey]<=12)!=(r['pop']<=12))
    c34=sum(1 for r in rows if (r[kkey]<=3)!=(r['pop']<=3))
    print(f'{label}: 帯一致 {m}/{len(rows)}={m/len(rows)*100:.4f}%  確定穴のうち事前穴 {a2}/{len(ana)}={a2/len(ana)*100:.4f}%'
          f'  3/4跨ぎ {c34/len(rows)*100:.4f}%  6/7跨ぎ {c67/len(rows)*100:.4f}%  12/13跨ぎ {c1213/len(rows)*100:.4f}%')
rep('kn','A 現状(除外前の順位のまま)')
rep('kn2','B 出走馬内で再ランク')

# 偶然水準（レース内で事前順位を無作為に並べ替えた場合の帯一致率）
import random
byr=collections.defaultdict(list)
for r in rows: byr[r['rk']].append(r)
def chance(kkey):
    # 理論値: Σ_b (帯サイズ_b)^2 / m^2 （出走馬内で再ランクした場合）
    tot=0; n=0
    for rk,rs in byr.items():
        m=len(rs); sz=collections.Counter(band(r['pop']) for r in rs)
        tot += sum(v*v for v in sz.values())/m ; n+=m
    return tot/n*100
print(f'偶然水準(理論, 帯サイズ由来) 全体 {chance("kn2"):.2f}%')
# 確定穴に限定した偶然水準
tot=0;n=0
for rk,rs in byr.items():
    m=len(rs); na=sum(1 for r in rs if band(r['pop'])=='穴')
    tot += na*na/m; n+=na
print(f'偶然水準(理論) 確定穴限定 {tot/n*100:.2f}%')
# レース内順列帰無（B=20000）
random.seed(7)
obs=sum(1 for r in rows if band(r['kn2'])==band(r['pop']))
vals=[]
for _ in range(20000):
    c=0
    for rk,rs in byr.items():
        pops=[r['pop'] for r in rs]; sh=pops[:]; random.shuffle(sh)
        c+=sum(1 for a,b in zip(pops,sh) if band(a)==band(b))
    vals.append(c)
mu=sum(vals)/len(vals); sd=(sum((v-mu)**2 for v in vals)/len(vals))**.5
print(f'順列帰無: 平均一致 {mu/len(rows)*100:.2f}%  SD {sd/len(rows)*100:.2f}pp  観測 {obs/len(rows)*100:.2f}%  z={(obs-mu)/sd:.1f}  観測以上 {sum(1 for v in vals if v>=obs)}/20000')
