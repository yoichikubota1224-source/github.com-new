#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""騎手運勢ブックに 2026.09.19 シート(9/19土・9/20日・9/21月=敬老の日)を先頭追加する。
・原本は読み取りのみ。書き出しは別ファイル（SOURCE_DATA_MUTATION=NO）。
・3日開催のため日付列を1本増やす。ブック内の3日シート(2025.11.21 ほか)と同じ作り＝
  日付列を右へ1列増やし、騎手名列をその右へ寄せる。
・記号セルの塗り/フォントは値から再構築せず、原本セルの書式オブジェクトを複製する。
・D列(騎手名)は値・書式とも原本のまま移すだけ。注記の加工も削除もしない（原本尊重）。
"""
import copy, datetime, os, sys
import openpyxl
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from gen_unsei import unsei, GROUPS, serial

SP  = '/tmp/claude-0/-home-user-github-com-new/47c1892c-ddc4-50e4-8b6f-3403a9782673/scratchpad'
SRC = '/root/.claude/uploads/47c1892c-ddc4-50e4-8b6f-3403a9782673/b76c30af-____2026.09.12.xlsx'
DST = os.path.join(SP, '騎手運勢2026.09.19.xlsx')
BASE_SHEET, NEW_SHEET = '2026.09.12', '2026.09.19'
DAYS = [datetime.date(2026, 9, 19), datetime.date(2026, 9, 20), datetime.date(2026, 9, 21)]

wb = openpyxl.load_workbook(SRC)
base = wb[BASE_SHEET]
before_names = list(wb.sheetnames)
before_cells = {s: {(r, c): wb[s].cell(r, c).value
                    for r in range(1, wb[s].max_row + 1) for c in range(1, wb[s].max_column + 1)}
                for s in before_names}

# 記号ごとの書式プロトタイプを原本B/C列から採る
proto = {}
for r in range(3, 27):
    for c in (2, 3):
        proto.setdefault(base.cell(r, c).value, base.cell(r, c))
assert set(proto) == {'◎◎', '◎', '○', '△', '×'}, proto.keys()

new = wb.copy_worksheet(base)
new.title = NEW_SHEET
wb.move_sheet(NEW_SHEET, offset=-(wb.sheetnames.index(NEW_SHEET)))

def move(src_col, dst_col):
    """列を丸ごと右へ寄せる（値＋書式）。"""
    for r in range(1, 27):
        s, d = new.cell(r, src_col), new.cell(r, dst_col)
        d.value = s.value
        d.font, d.fill, d.border = copy.copy(s.font), copy.copy(s.fill), copy.copy(s.border)
        d.alignment, d.number_format = copy.copy(s.alignment), s.number_format

move(4, 5)                                   # 騎手名列 D → E
for r in range(1, 27):                       # D列を日付/記号列として作り直す
    d = new.cell(r, 4)
    d.value = None
    src = new.cell(r, 3)                     # C列(=2日目)の書式を土台にする
    d.font, d.fill, d.border = copy.copy(src.font), copy.copy(src.fill), copy.copy(src.border)
    d.alignment, d.number_format = copy.copy(src.alignment), src.number_format

new['B2'], new['C2'], new['D2'] = (serial(d) for d in DAYS)
new['E2'] = '騎手名'

for i, g in enumerate(GROUPS):
    row = 3 + i
    assert new.cell(row, 1).value == g, (row, new.cell(row, 1).value, g)
    for col, d in zip((2, 3, 4), DAYS):
        cyc, mark = unsei(d, g)
        cell = new.cell(row, col)
        cell.value = mark
        p = proto[mark]
        cell.fill, cell.font = copy.copy(p.fill), copy.copy(p.font)
        cell.alignment, cell.border = copy.copy(p.alignment), copy.copy(p.border)

w = new.column_dimensions
w['E'].width = base.column_dimensions['D'].width      # 騎手名の幅を引き継ぐ
w['D'].width = base.column_dimensions['B'].width      # 3日目は記号列の幅に
w['F'].width = base.column_dimensions['E'].width
wb.save(DST)

# ---- 自己検査 ----
chk = openpyxl.load_workbook(DST)
ok = []
def t(name, cond): ok.append((name, bool(cond)))
t('新シートが先頭', chk.sheetnames[0] == NEW_SHEET)
t(f'既存{len(before_names)}シートが順序ごと不変', chk.sheetnames[1:] == before_names)
t('B2/C2/D2 = 46284/46285/46286', [chk[NEW_SHEET][x].value for x in ('B2','C2','D2')] == [serial(d) for d in DAYS])
t('星人グループ 24/24', [chk[NEW_SHEET].cell(3+i,1).value for i in range(24)] == GROUPS)
t('E2=騎手名', chk[NEW_SHEET]['E2'].value == '騎手名')
t('騎手名24行が原本D列と一致', [chk[NEW_SHEET].cell(3+i,5).value for i in range(24)] == [base.cell(3+i,4).value for i in range(24)])
t('E1見出しが原本D1と一致', chk[NEW_SHEET]['E1'].value == base['D1'].value)
t('記号 72/72 が算出値と一致',
  all(chk[NEW_SHEET].cell(3+i, c).value == unsei(d, g)[1]
      for i, g in enumerate(GROUPS) for c, d in zip((2,3,4), DAYS)))
def fmt(c): 
    f=c.fill
    return (f.fill_type, f.fgColor.type, f.fgColor.rgb if f.fgColor.type=='rgb' else (f.fgColor.theme, f.fgColor.tint), c.font.name, c.font.sz, c.font.b, c.font.color.rgb if c.font.color and c.font.color.type=='rgb' else None)
t('記号書式 72/72 が記号別の原本書式と一致',
  all(fmt(chk[NEW_SHEET].cell(3+i,c)) == fmt(proto[unsei(d,g)[1]])
      for i,g in enumerate(GROUPS) for c,d in zip((2,3,4),DAYS)))
t('騎手名列の書式24行が原本と一致',
  all(fmt(chk[NEW_SHEET].cell(3+i,5)) == fmt(base.cell(3+i,4)) for i in range(24)))
same = all(chk[s].cell(r,c).value == v for s in before_names for (r,c), v in before_cells[s].items())
t(f'既存{len(before_names)}シートの全セル値が不変', same)
import collections
dist = [collections.Counter(chk[NEW_SHEET].cell(3+i,c).value for i in range(24)) for c in (2,3,4)]
t('記号分布 ◎◎2・◎3・○11・△2・×6 が3日とも同じ',
  all(dict(x) == {'×':6,'△':2,'○':11,'◎':3,'◎◎':2} for x in dist))
t('D列に日付以外が残っていない', all(chk[NEW_SHEET].cell(r,4).value in (None,'◎◎','◎','○','△','×') for r in (1,) ) and chk[NEW_SHEET]['D1'].value is None)

for n, v in ok: print(('PASS ' if v else 'FAIL ') + n)
print(f"\n{'すべてPASS' if all(v for _,v in ok) else '⚠ FAILあり'}  {sum(v for _,v in ok)}/{len(ok)}")
print('saved', DST, os.path.getsize(DST), 'bytes /', len(chk.sheetnames), 'sheets')
