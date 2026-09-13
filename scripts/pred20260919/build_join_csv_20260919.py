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

# 下流が「0名」を確定値と誤解しないよう状態標識を付ける（[不足]を0へ変換しない）
HOLD = {
    '今村聖奈': '[要確認]_マスタ競合3値(7/4マスタ=木星－／8/22ブック=水星－／9/12ブック=土星＋)。自動統一していない',
    '森田誠也': '[要確認]_8/22ブック=木星－から移動。7/4マスタ(天王星－)と一致する向き。自動統一していない',
    '吉村誠之助': '[要確認]_8/22ブック=天王星＋から移動。前週は括弧欠落の誤記',
    'ミシェル': '[要確認]_8/22ブックに記載なし(8/15と9/12のみ)。DE正本のフルネーム形式では現行lookupが結べない公算',
    '小幡初': '[要確認]_表記ゆれ候補(DE正本=木幡初也)。自動結合しない',
    '小幡育': '[要確認]_表記ゆれ候補(DE正本=木幡育也)。自動結合しない',
    '田山旺祐': '[要確認]_表記ゆれ候補(DE正本=田山旺佑)。自動結合しない',
    'Mデムーロ': '[要確認]_姓のみ「デムーロ」は金星－/火星＋の2群に該当。姓だけで結合しない',
    'Cデムーロ': '[要確認]_姓のみ「デムーロ」は金星－/火星＋の2群に該当。姓だけで結合しない',
    '大江原': '[要確認]_原本は「大江原（女）」。括弧内の識別子を注記除去で落としている',
}

hdr = ['星人グループ']
for d in DAYS: hdr += [f'{d.month}/{d.day}記号', f'{d.month}/{d.day}運気']
hdr += ['騎手名(注記除去)', '人数', '状態', '要確認']

rows, total = [], 0
for i, g in enumerate(GROUPS):
    names = [n for n in (clean(t) for t in split_d(ws.cell(3+i, 4).value)) if n]
    total += len(names)
    r = [g]
    for d in DAYS:
        cyc, mk = unsei(d, g); r += [mk, cyc]
    state = '[不足]_該当騎手0名(0や該当なしへ変換していない)' if not names else '名簿あり'
    flags = '／'.join(f'{n}: {HOLD[n]}' for n in names if n in HOLD)
    r += ['、'.join(names), len(names), state, flags]
    rows.append(r)

with open(OUT, 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f); w.writerow(hdr); w.writerows(rows)
print(f'[実] {OUT}')
print(f'[実] 24群 / 騎手 {total}名 / 3日分の記号・運気')
print('[実] 注記(回収率とみられる数値・条件別評価)は出力していない')
# 残留チェック
bad = [r for r in rows if any(ch.isdigit() for ch in r[7]) or set('✖✕○◎△×（()）') & set(r[7])]
print('[実] 出力名簿に数値・✖・括弧が残った群:', len(bad), [b[0] for b in bad] or 'なし')
