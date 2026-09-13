#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""中山9R 各馬の道悪実績 v2（馬場表記 良/稍/重/不 を正しく取る）"""
import json, glob, os, re, collections
S='/tmp/claude-0/-home-user-github-com-new/47c1892c-ddc4-50e4-8b6f-3403a9782673/scratchpad'
D='predictions/20260906'
MET=re.compile(r'(芝|ダ)(\d+)m'); BAB=re.compile(r'馬場:([^\s/]*)')
NORM={'良':'良','稍':'稍重','重':'重','不':'不良'}
def klass(t):
    t=t or ''
    for a,b in [('新馬','新馬'),('未勝利','未勝利'),('１勝','1勝'),('1勝','1勝'),('２勝','2勝'),('2勝','2勝'),('３勝','3勝'),('3勝','3勝')]:
        if a in t: return b
    return 'OP以上'
def c4(p):
    if not p: return None
    v=[x for x in re.split(r'[-‐−ー]',str(p)) if x.strip().isdigit()]
    return int(v[-1]) if v else None
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
            runs[h['horse_id']].append(dict(date=date,ba=rid[4:6],td=m.group(1),dist=int(m.group(2)),
                baba=NORM.get(b.group(1),b.group(1)),cls=klass(r.get('title')),chaku=h.get('chaku'),pop=h.get('pop'),c4=c4(h.get('passing'))))
T={(r['ba'],r['r']):r for r in json.load(open(os.path.join(D,'toukei_20260906.json')))['races']}
_s=json.load(open(os.path.join(D,'shutuba_20260906.json'))); SH={(r['ba'],r['r']):r for r in (_s['races'] if isinstance(_s,dict) else _s)}
rc=T[('中山',9)]; hid={h['uma']:h.get('horse_id') for h in SH[('中山',9)]['horses']}
OUT=[]
print(f"{'番':>2} {'馬名':<10} {'人':>2} | 稍重 重 不良 (走数/3着内) | 中山ダ1200の道悪実績（クラス付き）")
for h in sorted(rc['horses'], key=lambda x:x['kijun_ninki']):
    u=h['uma']; rs=sorted(runs.get(hid.get(u),[]), key=lambda x:x['date'], reverse=True)
    cnt={}
    for bb in ('稍重','重','不良'):
        v=[x for x in rs if x['baba']==bb]
        cnt[bb]=(len(v), sum(1 for x in v if isinstance(x['chaku'],int) and x['chaku']<=3))
    same=[x for x in rs if x['ba']=='06' and x['td']=='ダ' and x['dist']==1200 and x['baba'] in ('稍重','重','不良')]
    s=' / '.join(f"{x['date'][:4]}/{x['date'][4:6]}/{x['date'][6:]} {x['baba']}・{x['cls']} {x['chaku']}着({x['pop']}人)4角{x['c4']}" for x in same)
    OUT.append(dict(uma=u,name=h['name'],ninki=h['kijun_ninki'],waku=h['waku'],counts=cnt,same=same,
        same_str=s, n_dobo=sum(c[0] for c in cnt.values()), n_dobo3=sum(c[1] for c in cnt.values())))
    print(f"{u:>2} {h['name'][:10]:<10} {h['kijun_ninki']:>2} | 稍{cnt['稍重'][0]}/{cnt['稍重'][1]} 重{cnt['重'][0]}/{cnt['重'][1]} 不{cnt['不良'][0]}/{cnt['不良'][1]} | {s}")
json.dump(OUT, open(S+'/baba_nakayama9r_horses_v2.json','w'), ensure_ascii=False, indent=1)
