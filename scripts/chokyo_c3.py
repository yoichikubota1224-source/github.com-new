#!/usr/bin/env python3
# 第3報: 終いハロンの閾値を「絶対秒数」から「コース内の相対位置(パーセンタイル)」に置き換えて検証する。
import csv, io, json, math, os, datetime, collections, bisect
SP22='/tmp/claude-0/-home-user-github-com-new/47c1892c-ddc4-50e4-8b6f-3403a9782673/scratchpad/race_day_20260822'
SP23='/tmp/claude-0/-home-user-github-com-new/47c1892c-ddc4-50e4-8b6f-3403a9782673/scratchpad/race_day_20260823'
GH='/home/user/github.com-new/predictions'

def rd(p,hdr):
    if not os.path.exists(p): return []
    rows=list(csv.reader(io.StringIO(open(p,'rb').read().decode('cp932',errors='replace'))))
    return rows[1:] if hdr else rows

def works(banro_paths, wood_paths):
    """馬名 -> [調教記録]。坂路とウッドを統一形式にする"""
    out=collections.defaultdict(list)
    for p in banro_paths:
        for r in rd(p,False):
            if len(r)<18 or not r[4]: continue
            try: l3,l4,f4=float(r[16]),float(r[17]),float(r[10])
            except ValueError: continue
            out[r[4]].append({'course':'坂路','date':r[1],'l3':l3,'l4':l4,'total':f4,'furlongs':4})
    for p in wood_paths:
        for r in rd(p,True):
            if len(r)<31 or not r[6]: continue
            try: l3,l4=float(r[29]),float(r[30])
            except ValueError: continue
            tot=None
            for i in (16,17,18):            # 6F/5F/4F の累計でいちばん長く取れているもの
                try: tot=float(r[i]); break
                except (ValueError,IndexError): continue
            if tot is None: continue
            out[r[6]].append({'course':'ウッド','date':r[3],'l3':l3,'l4':l4,'total':tot,'furlongs':6})
    return out

# コース別の 終い1F 分布(全母集団)を基準にパーセンタイルを取る
def build_ref(w):
    ref=collections.defaultdict(list)
    for lst in w.values():
        for t in lst: ref[t['course']].append(t['l4'])
    for k in ref: ref[k].sort()
    return ref

DAYS=[('8/22','20260822',[f'{SP22}/坂路8.15－8.21.csv'],[f'{SP22}/ウッド8.15－8.21..csv'],f'{GH}/20260823/results_20260822.json'),
      ('8/23','20260823',[f'{SP23}/坂路8.15－8.21.csv',f'{SP23}/坂路8.22.csv'],
                          [f'{SP23}/ウッド8.15－8.21..csv',f'{SP23}/ウッド8.22..csv'],f'{GH}/20260823/results_20260823.json')]
rows=[]
for lbl,rday,bp,wp,rp in DAYS:
    w=works(bp,wp); ref=build_ref(w)
    cut=(datetime.date(int(rday[:4]),int(rday[4:6]),int(rday[6:]))-datetime.timedelta(days=2)).strftime('%Y%m%d')
    res=json.load(open(rp)); races=res if isinstance(res,list) else list(res.values())
    for x in races:
        for h in x['horses']:
            if h.get('chakujun') is None or not h.get('pop'): continue
            cand=[t for t in w.get(h['name'],[]) if t['date']<=cut]
            if not cand: continue
            last=max(cand,key=lambda t:t['date'])
            arr=ref[last['course']]
            pct=bisect.bisect_left(arr,last['l4'])/len(arr)   # 小さい(速い)ほど0に近い
            rows.append({'day':lbl,'pop':h['pop'],'odds':h.get('odds') or 0.0,'chaku':h['chakujun'],
                         'course':last['course'],'l4':last['l4'],'l3':last['l3'],
                         'accel':last['l4']-last['l3'],'pct':pct})
json.dump(rows,open('c3.json','w'),ensure_ascii=False)
print(f'結合 {len(rows)}頭  コース内訳:', collections.Counter(x['course'] for x in rows).most_common())
