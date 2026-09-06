#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""中山9R(ダ1200)の重馬場再検証。当方5年DB(k5/full)から馬場状態別に実測する。
出所: すべて当方5年DB=[実]。馬場状態そのものは羊一様のご申告=[申告]。実オッズ・確定人気は当日ぶんを使わない。"""
import json, glob, os, re, collections, math
S = '/tmp/claude-0/-home-user-github-com-new/47c1892c-ddc4-50e4-8b6f-3403a9782673/scratchpad'
D = 'predictions/20260906'
MET = re.compile(r'(芝|ダ)(\d+)m')
BAB = re.compile(r'馬場:(良|稍重|重|不良)')

def wilson(k, n, z=1.96):
    if not n: return (None, None)
    ph = k/n; d = 1+z*z/n
    c = (ph+z*z/(2*n))/d; hw = z*math.sqrt(ph*(1-ph)/n+z*z/(4*n*n))/d
    return (round(100*(c-hw),1), round(100*(c+hw),1))

def corner4(p):
    """passing 文字列から4角(最終コーナー)の通過順を取る。"""
    if not p: return None
    v = [x for x in re.split(r'[-‐−ー]', str(p)) if x.strip().isdigit()]
    return int(v[-1]) if v else None

races = []
for f in sorted(glob.glob(S+'/k5/full/*.json')):
    for rc in json.load(open(f)):
        if rc.get('jump'): continue
        m = MET.search(rc.get('meta') or ''); b = BAB.search(rc.get('meta') or '')
        if not m or not b: continue
        rid = str(rc['race_id'])
        races.append(dict(rid=rid, ba=rid[4:6], td=m.group(1), dist=int(m.group(2)), baba=b.group(1),
                         horses=rc['horses'], n=rc.get('n_start') or len(rc['horses']), date=os.path.basename(f)[:8]))
print('平地レース総数', len(races), '[実]')

NAKAYAMA = '06'
def sel(pred): return [r for r in races if pred(r)]
d1200_nk = sel(lambda r: r['ba']==NAKAYAMA and r['td']=='ダ' and r['dist']==1200)
d_short  = sel(lambda r: r['td']=='ダ' and 1000<=r['dist']<=1400)
print('中山ダ1200', len(d1200_nk), ' 全場ダ1000-1400', len(d_short))
by = collections.Counter(r['baba'] for r in d1200_nk)
print('中山ダ1200 馬場別レース数', dict(by))

def agg(rs, label):
    """人気別3着内率・脚質(4角)別・枠別・1番人気成績・荒れ度"""
    pop = collections.defaultdict(lambda:[0,0]); c4 = collections.defaultdict(lambda:[0,0,0])
    waku = collections.defaultdict(lambda:[0,0]); fav=[0,0,0]; win_pop=[]; sum3=[]
    l3best=[0,0]
    for r in rs:
        hs=[h for h in r['horses'] if isinstance(h.get('chaku'),int)]
        if not hs: continue
        n=r['n']
        # 上がり最速
        l3=[h for h in hs if h.get('last3f')]
        if l3:
            mn=min(h['last3f'] for h in l3)
            for h in l3:
                if h['last3f']==mn:
                    l3best[1]+=1
                    if h['chaku']<=3: l3best[0]+=1
        for h in hs:
            p=h.get('pop'); ch=h['chaku']
            if p:
                pop[p][1]+=1
                if ch<=3: pop[p][0]+=1
                if p==1:
                    fav[2]+=1
                    if ch==1: fav[0]+=1
                    if ch<=3: fav[1]+=1
            k=corner4(h.get('passing'))
            if k:
                grp = '逃・先(1-3)' if k<=3 else ('中団(4-8)' if k<=8 else '後方(9-)')
                c4[grp][1]+=1
                if ch<=3: c4[grp][0]+=1
                if ch==1: c4[grp][2]+=1
            w=h.get('waku')
            if w:
                grp2='内(1-3枠)' if w<=3 else ('中(4-5枠)' if w<=5 else '外(6-8枠)')
                waku[grp2][1]+=1
                if ch<=3: waku[grp2][0]+=1
        w1=[h for h in hs if h['chaku']==1]
        if w1 and w1[0].get('pop'): win_pop.append(w1[0]['pop'])
        t3=[h.get('pop') for h in hs if h['chaku']<=3 and h.get('pop')]
        if len(t3)==3: sum3.append(sum(t3))
    out=dict(label=label, n_race=len(rs))
    out['fav']=dict(win=fav[0], top3=fav[1], n=fav[2],
                    win_rate=round(100*fav[0]/fav[2],1) if fav[2] else None,
                    top3_rate=round(100*fav[1]/fav[2],1) if fav[2] else None,
                    top3_ci=wilson(fav[1],fav[2]))
    out['pop']={p:dict(hit=v[0],n=v[1],rate=round(100*v[0]/v[1],1),ci=wilson(v[0],v[1])) for p,v in sorted(pop.items()) if v[1]>=10}
    out['corner4']={k:dict(top3=v[0],n=v[1],win=v[2],top3_rate=round(100*v[0]/v[1],1),win_rate=round(100*v[2]/v[1],1),ci=wilson(v[0],v[1])) for k,v in c4.items()}
    out['waku']={k:dict(top3=v[0],n=v[1],rate=round(100*v[0]/v[1],1),ci=wilson(v[0],v[1])) for k,v in waku.items()}
    out['last3f_best']=dict(top3=l3best[0],n=l3best[1],rate=round(100*l3best[0]/l3best[1],1) if l3best[1] else None)
    out['are']=dict(win_pop_ge5=round(100*sum(1 for x in win_pop if x>=5)/len(win_pop),1) if win_pop else None,
                    sum3_ge18=round(100*sum(1 for x in sum3 if x>=18)/len(sum3),1) if sum3 else None, n=len(win_pop))
    return out

RES={}
RES['中山ダ1200_良'] = agg([r for r in d1200_nk if r['baba']=='良'],'中山ダ1200 良')
RES['中山ダ1200_稍重'] = agg([r for r in d1200_nk if r['baba']=='稍重'],'中山ダ1200 稍重')
RES['中山ダ1200_重不良'] = agg([r for r in d1200_nk if r['baba'] in ('重','不良')],'中山ダ1200 重+不良')
RES['全場ダ短_良'] = agg([r for r in d_short if r['baba']=='良'],'全場ダ1000-1400 良')
RES['全場ダ短_重不良'] = agg([r for r in d_short if r['baba'] in ('重','不良')],'全場ダ1000-1400 重+不良')
for k,v in RES.items():
    print(f"\n== {v['label']} R={v['n_race']}")
    print('  1番人気 勝率',v['fav']['win_rate'],'% 3着内',v['fav']['top3_rate'],'%',v['fav']['top3_ci'],'n=',v['fav']['n'])
    print('  4角位置:', {k2:(v2['top3_rate'],v2['win_rate'],v2['n']) for k2,v2 in v['corner4'].items()})
    print('  枠:', {k2:(v2['rate'],v2['n']) for k2,v2 in v['waku'].items()})
    print('  上がり最速の3着内率', v['last3f_best'])
    print('  荒れ: 1着5人気以下', v['are']['win_pop_ge5'],'% / 上位3頭人気合計>=18', v['are']['sum3_ge18'],'% (n=',v['are']['n'],')')
    print('  人気別3着内率', {p:(d['rate'],d['n']) for p,d in list(v['pop'].items())[:12]})
json.dump(RES, open(S+'/baba_nakayama9r.json','w'), ensure_ascii=False, indent=1)
