#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, glob, os, re, collections, math
S='/tmp/claude-0/-home-user-github-com-new/47c1892c-ddc4-50e4-8b6f-3403a9782673/scratchpad'
D='predictions/20260906'
MET=re.compile(r'(芝|ダ)(\d+)m'); BAB=re.compile(r'馬場:(良|稍重|重|不良)')
def c4(p):
    if not p: return None
    v=[x for x in re.split(r'[-‐−ー]',str(p)) if x.strip().isdigit()]
    return int(v[-1]) if v else None
def wilson(k,n,z=1.96):
    if not n: return (None,None)
    ph=k/n; d=1+z*z/n; c=(ph+z*z/(2*n))/d; hw=z*math.sqrt(ph*(1-ph)/n+z*z/(4*n*n))/d
    return (round(100*(c-hw),1), round(100*(c+hw),1))

T={(r['ba'],r['r']):r for r in json.load(open(os.path.join(D,'toukei_20260906.json')))['races']}
_s=json.load(open(os.path.join(D,'shutuba_20260906.json')));SH={(r['ba'],r['r']):r for r in (_s['races'] if isinstance(_s,dict) else _s)}
rc=T[('中山',9)]; sh=SH[('中山',9)]
hid={h['uma']:h.get('horse_id') for h in sh['horses']}
names={h['uma']:h['name'] for h in rc['horses']}

# 5年DBを馬ごとに索引
runs=collections.defaultdict(list)
for f in sorted(glob.glob(S+'/k5/full/*.json')):
    date=os.path.basename(f)[:8]
    for r in json.load(open(f)):
        if r.get('jump'): continue
        m=MET.search(r.get('meta') or ''); b=BAB.search(r.get('meta') or '')
        if not m or not b: continue
        rid=str(r['race_id'])
        for h in r['horses']:
            if not h.get('horse_id'): continue
            runs[h['horse_id']].append(dict(date=date, ba=rid[4:6], td=m.group(1), dist=int(m.group(2)), baba=b.group(1),
                chaku=h.get('chaku'), pop=h.get('pop'), c4=c4(h.get('passing')), last3f=h.get('last3f'), waku=h.get('waku'), uma=h.get('uma'), n=r.get('n_start')))
print('索引した馬', len(runs))

OUT=[]
for h in sorted(rc['horses'], key=lambda x:x['kijun_ninki']):
    u=h['uma']; hi=hid.get(u); rs=sorted(runs.get(hi,[]), key=lambda x:x['date'], reverse=True)
    heavy=[x for x in rs if x['baba'] in ('重','不良')]
    soft=[x for x in rs if x['baba']=='稍重']
    hv3=sum(1 for x in heavy if isinstance(x['chaku'],int) and x['chaku']<=3)
    hvw=sum(1 for x in heavy if x['chaku']==1)
    dirt_heavy=[x for x in heavy if x['td']=='ダ']
    dh3=sum(1 for x in dirt_heavy if isinstance(x['chaku'],int) and x['chaku']<=3)
    c4s=[x['c4'] for x in rs[:5] if x['c4']]
    OUT.append(dict(uma=u, name=names[u], ninki=h['kijun_ninki'], waku=h['waku'], kyaku=h['kyakushitsu'],
        deokure=h['deokure'], IDM=h['IDM'], time_max=h['time_max'], time_5avg=h['time_5avg'],
        n_run=len(rs), n_heavy=len(heavy), heavy_top3=hv3, heavy_win=hvw,
        n_dirt_heavy=len(dirt_heavy), dirt_heavy_top3=dh3, n_soft=len(soft),
        heavy_detail=[f"{x['date'][:4]}/{x['date'][4:6]}/{x['date'][6:]} {x['td']}{x['dist']}{x['baba']} {x['chaku']}着({x['pop']}人)4角{x['c4']}" for x in heavy[:6]],
        c4_recent5=c4s, c4_avg=(round(sum(c4s)/len(c4s),1) if c4s else None)))
print(f"{'番':>2} {'馬名':<10} {'人':>2} {'枠':>2} {'脚質':<3} {'出遅':>4} {'重走':>3} {'重3着内':>5} {'重勝':>3} {'ダ重':>4} {'4角平均':>5}  重の内訳")
for o in OUT:
    print(f"{o['uma']:>2} {o['name'][:10]:<10} {o['ninki']:>2} {o['waku']:>2} {str(o['kyaku']):<3} {str(o['deokure']):>4} {o['n_heavy']:>3} {o['heavy_top3']:>5} {o['heavy_win']:>3} {o['n_dirt_heavy']:>4} {str(o['c4_avg']):>5}  {'; '.join(o['heavy_detail'][:3])}")
json.dump(OUT, open(S+'/baba_nakayama9r_horses.json','w'), ensure_ascii=False, indent=1)
