#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""騎手運勢ブックに 2026.09.19 シート(9/19・9/20・9/21)を先頭追加する（v2: XML直接編集）。

v1(openpyxl再保存)で失われていたものを保つための作り直し:
  * 日付セルの表示書式(numFmtId=56)  … v1では D2 が「46286」と生数字表示になっていた
  * printerSettings / pageSetup の参照
  * phoneticPr(ふりがな設定)
  * sharedStrings / docProps / fileVersion
原本ZIPの全パートをそのまま複製し、(a)新シートXMLの追加 (b)workbook.xml と rels と
[Content_Types].xml への3行追加 だけを行う。既存34シートのXMLは1バイトも触らない。
"""
import re, os, sys, shutil, zipfile, datetime
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from gen_unsei import unsei, GROUPS, serial

SP   = '/tmp/claude-0/-home-user-github-com-new/47c1892c-ddc4-50e4-8b6f-3403a9782673/scratchpad'
SRC  = '/root/.claude/uploads/47c1892c-ddc4-50e4-8b6f-3403a9782673/b76c30af-____2026.09.12.xlsx'
DST  = os.path.join(SP, '騎手運勢2026.09.19.xlsx')
BASE_SHEET, NEW_SHEET = '2026.09.12', '2026.09.19'
DAYS = [datetime.date(2026, 9, 19), datetime.date(2026, 9, 20), datetime.date(2026, 9, 21)]

zin  = zipfile.ZipFile(SRC)
names = zin.namelist()
rd    = lambda n: zin.read(n).decode('utf-8')

# --- 原本の基準シートを特定（シート名→r:id→Target） ---
wbx   = rd('xl/workbook.xml')
rid   = re.search(r'<sheet name="%s"[^>]*r:id="(rId\d+)"' % re.escape(BASE_SHEET), wbx).group(1)
relsx = rd('xl/_rels/workbook.xml.rels')
target= re.search(r'Id="%s"[^>]*Target="([^"]+)"' % rid, relsx).group(1).lstrip('/')
base_part = 'xl/' + target if not target.startswith('xl/') else target
sx = rd(base_part)

# --- 記号→(sharedString index, style id) を原本から採る（値から作らない） ---
ss    = rd('xl/sharedStrings.xml')
items = re.findall(r'<si>(?:<t[^>]*>(.*?)</t>)?</si>', ss, re.S)
sidx  = {t: i for i, t in enumerate(items)}
style = {}
for r in range(3, 27):
    row = re.search(r'<row r="%d"[^>]*>(.*?)</row>' % r, sx, re.S).group(1)
    for c in re.finditer(r'<c r="([BC])%d" s="(\d+)" t="s"><v>(\d+)</v></c>' % r, row):
        style.setdefault(items[int(c.group(3))], c.group(2))
assert set(style) == {'◎◎', '◎', '○', '△', '×'}, style
S_B2 = re.search(r'<c r="B2" s="(\d+)"', sx).group(1)      # 日付セルの書式(numFmtId=56を含む)
S_D1 = re.search(r'<c r="D1" s="(\d+)"', sx).group(1)      # 見出し(青字)
S_D2 = re.search(r'<c r="D2" s="(\d+)"', sx).group(1)      # 「騎手名」
S_C1 = re.search(r'<c r="C1" s="(\d+)"', sx).group(1)      # 空セル

def cell(ref, s, v, shared=False):
    if v is None: return f'<c r="{ref}" s="{s}"/>'
    return f'<c r="{ref}" s="{s}" t="s"><v>{v}</v></c>' if shared else f'<c r="{ref}" s="{s}"><v>{v}</v></c>'

def old(ref):
    """原本セルをそのまま（style も共有文字列インデックスも触らない）"""
    m = re.search(r'<c r="%s"[^>]*?(?:/>|>.*?</c>)' % ref, sx, re.S)
    return m.group(0)

def shift(ctag, frm, to):
    return ctag.replace(f'r="{frm}"', f'r="{to}"', 1)

rows_out = []
for r in range(1, 27):
    rowm = re.search(r'<row r="%d"([^>]*)>(.*?)</row>' % r, sx, re.S)
    attrs = rowm.group(1).replace('spans="1:4"', 'spans="1:5"')
    if r == 1:
        cells = old('A1') + old('B1') + old('C1') + cell('D1', S_C1, None) + shift(old('D1'), 'D1', 'E1')
    elif r == 2:
        cells = (old('A2')
                 + cell('B2', S_B2, serial(DAYS[0])) + cell('C2', S_B2, serial(DAYS[1]))
                 + cell('D2', S_B2, serial(DAYS[2]))
                 + shift(old('D2'), 'D2', 'E2'))
    else:
        g = GROUPS[r - 3]
        marks = [unsei(d, g)[1] for d in DAYS]
        cells = old(f'A{r}')
        for col, mk in zip('BCD', marks):
            cells += cell(f'{col}{r}', style[mk], sidx[mk], shared=True)
        cells += shift(old(f'D{r}'), f'D{r}', f'E{r}')
    rows_out.append(f'<row r="{r}"{attrs}>{cells}</row>')

new_sx = sx
new_sx = new_sx.replace(re.search(r'<sheetData>.*?</sheetData>', sx, re.S).group(0),
                        '<sheetData>' + ''.join(rows_out) + '</sheetData>')
new_sx = new_sx.replace('<dimension ref="A1:E26"/>', '<dimension ref="A1:F26"/>')
new_sx = new_sx.replace(re.search(r'<cols>.*?</cols>', sx, re.S).group(0),
    '<cols>'
    '<col min="1" max="1" width="7.875" style="3" customWidth="1"/>'
    '<col min="2" max="4" width="9.25" style="3" customWidth="1"/>'
    '<col min="5" max="5" width="102.875" style="84" customWidth="1"/>'
    '<col min="6" max="6" width="5.75" style="84" customWidth="1"/>'
    '</cols>')

# --- 追加するパート名 / rId を既存と衝突しないよう決める ---
n = 1
while f'xl/worksheets/sheet{n}.xml' in names: n += 1
new_part = f'xl/worksheets/sheet{n}.xml'
used = set(re.findall(r'Id="(rId\d+)"', relsx))
k = 1
while f'rId{k}' in used: k += 1
new_rid = f'rId{k}'
sheet_ids = [int(x) for x in re.findall(r'sheetId="(\d+)"', wbx)]
new_sid = max(sheet_ids) + 1

wbx2   = wbx.replace('<sheets>', f'<sheets><sheet name="{NEW_SHEET}" sheetId="{new_sid}" r:id="{new_rid}"/>', 1)
relsx2 = relsx.replace('</Relationships>',
    f'<Relationship Id="{new_rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{n}.xml"/></Relationships>')
ctx    = rd('[Content_Types].xml')
ctx2   = ctx.replace('</Types>',
    f'<Override PartName="/{new_part}" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')

base_rels_part = base_part.replace('worksheets/', 'worksheets/_rels/') + '.rels'
new_rels_part  = f'xl/worksheets/_rels/sheet{n}.xml.rels'
base_rels_data = zin.read(base_rels_part) if base_rels_part in names else None
payload = {it.filename: zin.read(it.filename) for it in zin.infolist()}
infos = list(zin.infolist())
zin.close()

repl = {'xl/workbook.xml': wbx2, 'xl/_rels/workbook.xml.rels': relsx2, '[Content_Types].xml': ctx2}
with zipfile.ZipFile(DST, 'w', zipfile.ZIP_DEFLATED) as zo:
    for it in infos:
        data = repl[it.filename].encode('utf-8') if it.filename in repl else payload[it.filename]
        zo.writestr(it, data)
    zo.writestr(new_part, new_sx.encode('utf-8'))
    if base_rels_data is not None:
        zo.writestr(new_rels_part, base_rels_data)
print('saved', DST, os.path.getsize(DST), 'bytes')

# ---------------- 自己検査（原本と生成物を開き直して実測する） ----------------
import collections, openpyxl
za, zb = zipfile.ZipFile(SRC), zipfile.ZipFile(DST)
na, nb = set(za.namelist()), set(zb.namelist())
ok = []
def t(name, cond): ok.append((name, bool(cond)))

added = sorted(nb - na)
changed = sorted(x for x in na if za.read(x) != zb.read(x))
t('原本の全パートが生成物に存在', na <= nb)
t(f'追加は新シートとそのrelsのみ', len(added) == 2 and new_part in added)
t('変更は workbook.xml / rels / [Content_Types].xml の3つだけ',
  changed == sorted(['[Content_Types].xml', 'xl/_rels/workbook.xml.rels', 'xl/workbook.xml']))
for part in ('xl/sharedStrings.xml', 'xl/styles.xml', 'docProps/app.xml', 'docProps/core.xml'):
    if part in na: t(f'{part} が1バイトも変わっていない', za.read(part) == zb.read(part))
t('printerSettings パートが保持されている', any('printerSettings' in x for x in nb))
nsx_chk = zb.read(new_part).decode('utf-8')
t('新シートに phoneticPr(ふりがな設定)がある', '<phoneticPr' in nsx_chk)
t('新シートに pageSetup の r:id 参照がある', re.search(r'<pageSetup[^>]*r:id=', nsx_chk) is not None)
t('新シートのrelsが printerSettings を指す',
  any(x.endswith('.rels') and 'printerSettings' in zb.read(x).decode('utf-8') for x in added))
for ref in ('B2', 'C2', 'D2'):
    m = re.search(r'<c r="%s" s="(\d+)"' % ref, nsx_chk)
    t(f'{ref} が原本の日付書式 s={S_B2} を持つ（生数字表示にならない）', m and m.group(1) == S_B2)
za.close(); zb.close()

wo = openpyxl.load_workbook(SRC, data_only=True)
wn = openpyxl.load_workbook(DST, data_only=True)
ns, bs = wn[NEW_SHEET], wo[BASE_SHEET]
t('新シートが先頭', wn.sheetnames[0] == NEW_SHEET)
t(f'既存{len(wo.sheetnames)}シートが順序ごと不変', wn.sheetnames[1:] == wo.sheetnames)
t(f'既存{len(wo.sheetnames)}シートの全セル値が不変',
  all(wn[s].cell(r, c).value == wo[s].cell(r, c).value
      for s in wo.sheetnames for r in range(1, wo[s].max_row + 1) for c in range(1, wo[s].max_column + 1)))
t('星人グループ 24/24', [ns.cell(3 + i, 1).value for i in range(24)] == GROUPS)
t('B2/C2/D2 = 46284/46285/46286', [ns[x].value for x in ('B2', 'C2', 'D2')] == [serial(d) for d in DAYS])
t('記号 72/72 が算出値と一致',
  all(ns.cell(3 + i, c).value == unsei(d, g)[1] for i, g in enumerate(GROUPS) for c, d in zip((2, 3, 4), DAYS)))
t('E列の騎手名24行が原本D列と一致（1文字も変えていない）',
  [ns.cell(3 + i, 5).value for i in range(24)] == [bs.cell(3 + i, 4).value for i in range(24)])
t('E1見出しが原本D1と一致', ns['E1'].value == bs['D1'].value)
t('E2 = 騎手名', ns['E2'].value == '騎手名')
t('D1が空（見出しはE1へ移動済み）', ns['D1'].value is None)
t('記号分布 ◎◎2・◎3・○11・△2・×6 が3日とも同じ',
  all(dict(collections.Counter(ns.cell(3 + i, c).value for i in range(24)))
      == {'×': 6, '△': 2, '○': 11, '◎': 3, '◎◎': 2} for c in (2, 3, 4)))
def fmt(c):
    f = c.fill
    return (f.fill_type, f.fgColor.type,
            f.fgColor.rgb if f.fgColor.type == 'rgb' else (f.fgColor.theme, f.fgColor.tint),
            c.font.name, c.font.sz, c.font.b,
            c.font.color.rgb if c.font.color and c.font.color.type == 'rgb' else None)
proto = {}
for r in range(3, 27):
    for c in (2, 3): proto.setdefault(bs.cell(r, c).value, bs.cell(r, c))
t('記号の書式 72/72 が記号別の原本書式と一致',
  all(fmt(ns.cell(3 + i, c)) == fmt(proto[unsei(d, g)[1]])
      for i, g in enumerate(GROUPS) for c, d in zip((2, 3, 4), DAYS)))
t('騎手名列の書式24行が原本と一致', all(fmt(ns.cell(3 + i, 5)) == fmt(bs.cell(3 + i, 4)) for i in range(24)))
cd = {k: (v.min, v.max, v.width) for k, v in ns.column_dimensions.items()}
t('列幅 A=7.875 / B〜D=9.25 / E=102.875 / F=5.75',
  cd.get('A') == (1, 1, 7.875) and cd.get('B') == (2, 4, 9.25)
  and cd.get('E') == (5, 5, 102.875) and cd.get('F') == (6, 6, 5.75))
t('連続性 9/13→9/19 が6日進行で成立',
  all(unsei(datetime.date(2026, 9, 13), g)[0] ==
      ['種子','緑生','立花','健弱','達成','乱気','再会','財成','安定','陰影','停止','減退'][
        (['種子','緑生','立花','健弱','達成','乱気','再会','財成','安定','陰影','停止','減退'].index(unsei(DAYS[0], g)[0]) - 6) % 12]
      for g in GROUPS))

for name, v in ok: print(('PASS ' if v else '★FAIL ') + name)
print(f"\n{'すべてPASS' if all(v for _, v in ok) else '⚠ FAILあり'}  {sum(v for _, v in ok)}/{len(ok)}")
