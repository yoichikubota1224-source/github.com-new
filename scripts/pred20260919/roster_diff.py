#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""9/12正本ブックのD列名簿を抽出し、前週(8/22・repo版)と突合する。
⚠ D列には卍由来の妙味度・回収率注記が混在する。本スクリプトは氏名だけを取り出し、
   注記は一切出力しない（公開リポジトリへ先方コンテンツの原数値を書かない）。"""
import openpyxl, re, json, sys, os, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from gen_unsei import GROUPS

SP = '/tmp/claude-0/-home-user-github-com-new/47c1892c-ddc4-50e4-8b6f-3403a9782673/scratchpad'
NEW = '/root/.claude/uploads/47c1892c-ddc4-50e4-8b6f-3403a9782673/b76c30af-____2026.09.12.xlsx'
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def split_d(text):
    """騎手ごとに分ける。括弧内の「、」では切らない（unsei906.py と同一実装）。"""
    out, buf, depth = [], '', 0
    for ch in text or '':
        if ch in '（(': depth += 1
        elif ch in '）)': depth = max(0, depth - 1)
        if depth == 0 and ch in '、,　 \n':
            if buf.strip(): out.append(buf.strip())
            buf = ''
        else:
            buf += ch
    if buf.strip(): out.append(buf.strip())
    return out

def clean(tok):
    """注記を落として氏名だけにする。先頭の回収率数値・括弧内の条件別注記は保持しない。"""
    nm = re.sub(r'^\d+', '', tok)                 # 先頭の数値注記（回収率とみられる）を落とす
    nm = re.sub(r'[（(].*$', '', nm)               # 括弧以降の注記を落とす
    nm = re.sub(r'[✖✕×○◎△\s　]+$', '', nm)       # 末尾に残る評価記号を落とす
    return nm.strip()

def roster(path, sheet):
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb[sheet]
    assert [ws.cell(3+i,1).value for i in range(24)] == GROUPS, 'A列の星人グループ順が正本と違う'
    out = {}
    for i, g in enumerate(GROUPS):
        names = [clean(t) for t in split_d(ws.cell(3+i, 4).value)]
        out[g] = [n for n in names if n]
    return out

new = roster(NEW, '2026.09.12')
old = roster(NEW, '2026.08.22')                                   # 同一ブック内の前々週
repo = roster(os.path.join(REPO, 'predictions', '20260905', '騎手運勢2026.09.05.xlsx'), '2026.09.05')

def inv(r):
    m = {}
    for g, ns in r.items():
        for n in ns: m.setdefault(n, []).append(g)
    return m

res = {}
for lbl, base in (('vs_2026.08.22_同一ブック', old), ('vs_2026.09.05_当方生成', repo)):
    a, b = inv(base), inv(new)
    added   = sorted(set(b) - set(a))
    removed = sorted(set(a) - set(b))
    moved   = sorted(n for n in set(a) & set(b) if a[n] != b[n])
    res[lbl] = dict(
        base_names=len(a), new_names=len(b),
        added=added, removed=removed,
        moved=[{'name': n, 'from': a[n], 'to': b[n]} for n in moved],
        dup_in_new=sorted(n for n, gs in b.items() if len(gs) > 1),
    )

counts = {g: len(v) for g, v in new.items()}
res['group_counts_0912'] = counts
res['empty_groups'] = [g for g, c in counts.items() if c == 0]
res['single_groups'] = [g for g, c in counts.items() if c == 1]
res['total_names_0912'] = sum(counts.values())
json.dump({'roster_0912': new, 'diff': res}, open(os.path.join(SP, 'roster0919.json'), 'w'), ensure_ascii=False, indent=1)

print(f"[実] 9/12ブック 名簿 {res['total_names_0912']}名 / 24群")
print(f"[実] 0名の群: {res['empty_groups'] or 'なし'}")
print(f"[実] 1名の群: {res['single_groups'] or 'なし'}")
for lbl in ('vs_2026.08.22_同一ブック', 'vs_2026.09.05_当方生成'):
    d = res[lbl]
    print(f"\n--- {lbl} (基準{d['base_names']}名 → 今週{d['new_names']}名) ---")
    print(f"  追加 {len(d['added'])}名: {'、'.join(d['added']) if d['added'] else 'なし'}")
    print(f"  消失 {len(d['removed'])}名: {'、'.join(d['removed']) if d['removed'] else 'なし'}")
    print(f"  群移動 {len(d['moved'])}名:")
    for m in d['moved']: print(f"    ⚠ {m['name']}: {m['from']} → {m['to']}")
    if d['dup_in_new']: print(f"  ⚠ 今週ブックで複数群に重複: {d['dup_in_new']}")
