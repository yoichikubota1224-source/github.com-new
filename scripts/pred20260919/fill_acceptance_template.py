#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ChatGPT(羊一データラボ 独立再評価レイヤー)の 02_受入テンプレート_9_19から21.csv を埋め戻す。
⚠ 値は「原本シートから読んだ」ものではなく「正本ツール①日運自動の数式で算出」したもの。
   出所欄にその区別を明記する。空欄を推測で埋めたのではない点を状態欄で示す。"""
import csv, os, sys, datetime
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from gen_unsei import unsei, GROUPS, serial

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT  = os.path.join(REPO, 'predictions', '20260919', '02_受入テンプレート_9_19から21_記入済.csv')
DAYS = [datetime.date(2026,9,19), datetime.date(2026,9,20), datetime.date(2026,9,21)]
COL  = {0:'B', 1:'C', 2:'D'}

rows = []
for i, g in enumerate(GROUPS):
    row = 3 + i
    marks = [unsei(d, g)[1] for d in DAYS]
    src = '生成シート 2026.09.19!' + '/'.join(f'{COL[k]}{row}' for k in range(3))
    rows.append([i+1, g, *marks, src, '算出済（原本の記号列から読取ではなく①日運自動の数式で算出）'])

with open(OUT, 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f)
    w.writerow(['行','星人グループ','2026-09-19','2026-09-20','2026-09-21','原本の出所（シート名・セル）','状態'])
    w.writerows(rows)
    w.writerow([])
    w.writerow(['# 注記','算出式 = MOD(シリアル-DATE(1950,1,1)+32,60)+1 → MOD(MOD(星数,12)+MOD(2*星人帯+(−:-2/＋:-1),12),12) → サイクル→記号'])
    w.writerow(['# シリアル', f'9/19={serial(DAYS[0])} / 9/20={serial(DAYS[1])} / 9/21={serial(DAYS[2])}'])
    w.writerow(['# 照合', '原本ブックの 2026.09.12 / 2026.08.22 / 2026.08.15 の計144セルに同式を当てて 144/144 一致（不一致0）'])
    w.writerow(['# 限界', '2026.06.06以前のシートとは記号対応が異なるため一致しない。現行対応のみで検証している'])
    w.writerow(['# 未確定', '3日開催の列位置は当方の提案（B/C/D=日付・E=騎手名）。羊一様の確認が必要'])
print('[実]', OUT)
for r in rows: print('  ', r[1], r[2], r[3], r[4])
