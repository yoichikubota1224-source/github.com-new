#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑥調教係(20260830): 直近2週(8/15〜8/28)の追切をDE出走馬に結合し、
場所×コース×日の自前基準(z1f)で終い1Fを評価。未来情報混入禁止(追切日<8/29のみ)。
⚠ chokyo_raw(坂路正規化後)は血統登録番号を持たないため馬名で結合する=[推:馬名結合]。
   第6報の正本解析には使用しない(馬名結合禁止規約)。本結合は当日参考材料に限る。"""
import csv, json, sys
from collections import defaultdict

WORK, DE, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
raw = json.load(open(WORK))       # chokyo_baseline の chokyo_raw.json
de = {}
dup = set()
for r in csv.reader(open(DE, encoding='cp932')):
    nm = r[7].strip()
    if nm in de: dup.add(nm)
    de[nm] = (r[1], int(r[2]), int(r[3]), nm)
for nm in dup: de.pop(nm, None)     # 同名馬は結合しない=[不足]

by_horse = defaultdict(list)
for w in raw:
    if not (20260815 <= int(w['date']) <= 20260828):
        continue
    k = str(w.get('name', '')).strip()
    if k in de:
        by_horse[k].append(w)

out = {}
for k, ws in by_horse.items():
    ba, rno, uma, name = de[k]
    ws.sort(key=lambda x: x['date'])
    zs = [w['z1f'] for w in ws if w.get('z1f') is not None]
    last = ws[-1]
    out[f'{ba}|{rno}|{uma}'] = {
        'name': name, 'n_works': len(ws),
        'best_z': round(min(zs), 2) if zs else None,   # zは小さい=速い
        'last_date': last['date'], 'last_z': round(last['z1f'], 2) if last.get('z1f') is not None else None,
        'last_course': f"{last.get('place','')}{last.get('course','')}",
        'last_f1': last.get('f1'),
    }
json.dump(out, open(OUT, 'w'), ensure_ascii=False, indent=1)
print(f'DE出走馬のうち直近2週の追切あり {len(out)}頭 / 馬名結合[推:馬名結合]')
import statistics
bz = [v['best_z'] for v in out.values() if v['best_z'] is not None]
print(f'best_z: n={len(bz)} 中央値{statistics.median(bz):.2f} 範囲[{min(bz):.2f},{max(bz):.2f}]')
