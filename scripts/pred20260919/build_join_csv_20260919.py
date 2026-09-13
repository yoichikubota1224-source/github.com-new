#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""9/19-21の結合用CSVを作る。
⚠ 公開リポジトリ向けのため、D列の注記（回収率とみられる数値・条件別の○✖＝卍妙味度由来）は
   一切出力しない。出力するのは騎手氏名だけ。原本(xlsx)は加工も削除もしない。"""
import openpyxl, csv, json, os, sys, datetime
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from gen_unsei import unsei, GROUPS
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from roster_diff import split_d, clean

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC  = '/root/.claude/uploads/47c1892c-ddc4-50e4-8b6f-3403a9782673/b76c30af-____2026.09.12.xlsx'
OUT  = os.path.join(REPO, 'predictions', '20260919', '運勢_20260919-21_結合用.csv')
DAYS = [datetime.date(2026, 9, 19), datetime.date(2026, 9, 20), datetime.date(2026, 9, 21)]

ws = openpyxl.load_workbook(SRC, data_only=True)['2026.09.12']
assert [ws.cell(3+i,1).value for i in range(24)] == GROUPS

hdr = ['星人グループ']
for d in DAYS: hdr += [f'{d.month}/{d.day}記号', f'{d.month}/{d.day}運気']
hdr += ['騎手名(注記除去)', '人数']

rows, total = [], 0
for i, g in enumerate(GROUPS):
    names = [n for n in (clean(t) for t in split_d(ws.cell(3+i, 4).value)) if n]
    total += len(names)
    r = [g]
    for d in DAYS:
        cyc, mk = unsei(d, g); r += [mk, cyc]
    r += ['、'.join(names), len(names)]
    rows.append(r)

with open(OUT, 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f); w.writerow(hdr); w.writerows(rows)
print(f'[実] {OUT}')
print(f'[実] 24群 / 騎手 {total}名 / 3日分の記号・運気')
print('[実] 注記(回収率とみられる数値・条件別評価)は出力していない')
# 残留チェック
bad = [r for r in rows if any(ch.isdigit() for ch in r[7]) or '✖' in r[7] or '（' in r[7]]
print('[実] 出力名簿に数値・✖・括弧が残った群:', len(bad), [b[0] for b in bad] or 'なし')
