#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑭次走期待好走馬の機械可読CSV(02)を jisou905.json から書き出す。UTF-8 BOM / LF（Driveと同一形）。"""
import csv, json, os
D = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'predictions', '20260905')
J = json.load(open(os.path.join(D, 'jisou905.json')))
cols = ['score','tier','band','ba','r','race','course','n_entry','waku','uma','name','horse_id','jockey','sire','sex','age',
        'rotation','kyakushitsu','zen_date','zen_ba','zen_course','zen_n','zen_pop','zen_chaku','zen_l3','zen_l3rank',
        'zen_passing','zen_diff_win','signals']
dest = os.path.join(D, '02_次走期待好走馬_20260905.csv')
with open(dest, 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore', lineterminator='\n')
    w.writeheader()
    for h in J['hits']:
        w.writerow({c: ('' if h.get(c) is None else h.get(c)) for c in cols})
print(J['version'], len(J['hits']), '頭 →', dest, os.path.getsize(dest), 'bytes')
