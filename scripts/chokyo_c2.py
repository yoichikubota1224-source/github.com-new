#!/usr/bin/env python3
# 第2報: 坂路CSVの4本ハロンラップから C-2判定(A3/A2/A1/B)を再計算し、
# タイム・終いハロン・加速幅の入着率を人気統制つきで測る。
import csv, io, json, math, os, re, collections
SP22='/tmp/claude-0/-home-user-github-com-new/47c1892c-ddc4-50e4-8b6f-3403a9782673/scratchpad/race_day_20260822'
SP23='/tmp/claude-0/-home-user-github-com-new/47c1892c-ddc4-50e4-8b6f-3403a9782673/scratchpad/race_day_20260823'
GH='/home/user/github.com-new/predictions'

def rd_banro(paths):
    """坂路CSV(ヘッダ無し18列) -> 馬名ごとの調教リスト"""
    out=collections.defaultdict(list)
    for p in paths:
        if not os.path.exists(p): continue
        for r in csv.reader(io.StringIO(open(p,'rb').read().decode('cp932',errors='replace'))):
            if len(r)<18 or not r[4]: continue
            try: laps=[float(r[i]) for i in (14,15,16,17)]
            except ValueError: continue
            try: f4=float(r[10])
            except ValueError: continue
            out[r[4]].append({'place':r[0],'date':r[1],'f4':f4,'laps':laps,'trainer':r[9]})
    return out

def c2_grade(laps):
    """C-2: A3=終い1F 11秒台+加速 / A2=終い2Fとも12秒台+加速 / A1=終い1Fのみ12秒台+加速 / B=減速"""
    l3,l4=laps[2],laps[3]
    accel = l4 < l3
    if not accel: return 'B'
    if 11.0 <= l4 < 12.0: return 'A3'
    if 12.0 <= l4 < 13.0 and 12.0 <= l3 < 13.0: return 'A2'
    if 12.0 <= l4 < 13.0: return 'A1'
    return 'B'   # 13秒台以上の加速は現行C-2の定義外 → Bに寄せる

DAYS=[('8/22','20260822',[f'{SP22}/坂路8.15－8.21.csv'], f'{GH}/20260823/results_20260822.json'),
      ('8/23','20260823',[f'{SP23}/坂路8.15－8.21.csv',f'{SP23}/坂路8.22.csv'], f'{GH}/20260823/results_20260823.json')]
rows=[]; datedist=collections.Counter(); dup=0
for lbl,rday,paths,rp in DAYS:
    ban=rd_banro(paths)
    res=json.load(open(rp)); races=res if isinstance(res,list) else list(res.values())
    for x in races:
        for h in x['horses']:
            if h.get('chakujun') is None or not h.get('pop'): continue
            w=ban.get(h['name'])
            if not w: continue
            w=[t for t in w if t['date']<rday]
            if not w: continue
            if len(w)>1: dup+=1
            last=max(w,key=lambda t:t['date'])          # 最終追切 = レース日より前で最新
            datedist[(lbl,last['date'])]+=1
            rows.append({'day':lbl,'venue':x['venue'],'r':x['r'],'name':h['name'],'pop':h['pop'],
                         'odds':h.get('odds') or 0.0,'chaku':h['chakujun'],
                         'f4':last['f4'],'l3':last['laps'][2],'l4':last['laps'][3],
                         'accel':last['laps'][3]-last['laps'][2],'grade':c2_grade(last['laps']),
                         'place':last['place'],'wdate':last['date'],'nwork':len(w)})
print(f'坂路で結合できた出走馬: {len(rows)}頭 (複数本あり {dup}頭は最新を採用)')
print('最終追切日の分布:', dict(sorted(datedist.items())))
json.dump(rows,open('c2_joined.json','w'),ensure_ascii=False)
