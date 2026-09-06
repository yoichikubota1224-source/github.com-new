#!/usr/bin/env python3
"""元資料(predictions/20260823/11_ChatGPT見解の検証..._20260823.md §2)の106R表を再現する。
独立に作った本パイプラインが、既存成果物と同じ数字を出すかの検査。"""
import json, os, collections, sys
src=open('final.py').read().split("if __name__")[0]; ns={}; exec(src, ns)
R,_=ns['load']()
DAYS=['20260816','20260822','20260823']
sub=[r for r in R if r['day'] in DAYS]
print(f'再現対象 {len(sub)}R (元資料は106R)')
if not sub: sys.exit('該当日が未取得')
c=collections.Counter(r['comp'] for r in sub)
per=collections.defaultdict(collections.Counter)
for r in sub: per[r['day']][r['comp']]+=1
EXPECT={'本命＋本命＋中穴':(10,13,9,32),'本命＋中穴＋穴':(10,7,9,26),'本命＋本命＋穴':(7,6,7,20),
        '本命＋中穴＋中穴':(3,4,3,10),'本命＋穴＋穴':(2,2,2,6),'中穴＋穴＋穴':(2,1,1,4),
        '中穴＋中穴＋穴':(1,2,0,3),'本命＋本命＋本命':(0,0,3,3),'中穴＋中穴＋中穴':(1,0,0,1),
        '穴＋穴＋穴':(0,0,1,1)}
ng=0
print(f'{"構成":<18s}{"8/16":>6s}{"8/22":>6s}{"8/23":>6s}{"計":>5s}   {"元資料":>14s}  判定')
for comp,e in EXPECT.items():
    got=tuple(per[d][comp] for d in DAYS)+(c[comp],)
    ok = got==e
    ng += not ok
    print(f'{comp:<18s}{got[0]:>6d}{got[1]:>6d}{got[2]:>6d}{got[3]:>5d}   {str(e):>14s}  {"一致" if ok else "⚠不一致"}')
print(f'\n不一致 {ng}/10 構成   合計 {sum(c.values())}R vs 元資料106R')
