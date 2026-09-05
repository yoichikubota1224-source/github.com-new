#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑨本シートゲート: 9/5の騎手運勢・調教師運勢を出走447頭へ結合する。

出所:
  * 運勢_20260905-06_結合用.csv … 星人グループ×9/5記号/運気。D列に騎手名の一覧(＋ROI注記)
  * 調教師名→星人グループ の対応 … Obsidian正本 調教師運勢_lookup_20260704_星人変換済み.csv 由来。
    ⚠ 元CSVは209名の生年月日を含むため公開リポジトリへは格納しない。
      本スクリプトが使うのは「調教師名→星人グループ」の2列のみ(scratchpad)。

⚠ 運勢×は「押し上げが無い」だけであり、消し根拠・減点材料に転用しない。
"""
import csv, json, os, re, collections, sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SP = '/tmp/claude-0/-home-user-github-com-new/47c1892c-ddc4-50e4-8b6f-3403a9782673/scratchpad'
UNSEI = os.path.join(REPO, 'predictions', '20260905', '運勢_20260905-06_結合用.csv')
TMAP = os.path.join(SP, 'trainer_seijin.tsv')

grp = {}          # 星人グループ -> (9/5記号, 9/5運気)
jockey_grp = {}   # 騎手名(表記ゆれ含む) -> 星人グループ
jockey_note = {}
def split_d(text):
    """D列を騎手ごとに分ける。区切りは「、」「，」「　」「 」だが、括弧（ ）の内側の「、」では切らない。"""
    out, buf, depth = [], '', 0
    for ch in text:
        if ch in '（(': depth += 1
        elif ch in '）)': depth = max(0, depth - 1)
        if depth == 0 and ch in '、,　 ':
            if buf.strip(): out.append(buf.strip())
            buf = ''
        else:
            buf += ch
    if buf.strip(): out.append(buf.strip())
    return out

def norm(s):
    """全角英字→半角、長音・空白の揺れを吸収（Ｍデム / Mデムーロ など）"""
    return ''.join(chr(ord(c) - 0xFEE0) if 0xFF21 <= ord(c) <= 0xFF5A else c for c in s).replace('ﾃﾞ', 'デ')

for r in csv.DictReader(open(UNSEI, encoding='utf-8-sig')):
    g = r['星人グループ'].strip()
    grp[g] = (r['9/5記号'].strip(), r['9/5運気'].strip())
    for tok in split_d(r.get('D列原文(騎手名・ROI注記)', '')):
        nm = re.sub(r'^\d+', '', tok)              # 先頭のROI数値を落とす
        nm = re.sub(r'[（(].*$', '', nm).strip()    # 括弧内の注記を落とす
        if nm:
            jockey_grp[norm(nm)] = g
            jockey_note[norm(nm)] = tok             # 注記は括弧の内側も含めて丸ごと保持する
print(f'[実] 星人グループ {len(grp)}件 / 運勢CSVから拾えた騎手名 {len(jockey_grp)}件')

tmap = {}
if os.path.exists(TMAP):
    for line in open(TMAP, encoding='utf-8'):
        p = line.rstrip('\n').split('\t')
        if len(p) == 2:
            tmap[p[0]] = p[1]
    print(f'[実] 調教師→星人グループ {len(tmap)}件（生年月日は保持していない）')
else:
    print('[不足] 調教師→星人グループの対応が無い。調教師運勢は判定しない')

def lookup(name, table):
    """netkeibaの略記(2〜3字)と正本の氏名(4字)を、前方一致でだけ結ぶ。
    候補が2件以上あれば[要確認]として結ばない(静かに潰さない)。返り値は(値, 結合方法, 当たったキー)。"""
    if not name:
        return None, '[不足]_名前が無い', None
    q = norm(name)
    if q in table:
        return table[q], '完全一致', q
    cand = [k for k in table if k.startswith(q)]
    if len(cand) == 1:
        return table[cand[0]], f'前方一致({cand[0]})', cand[0]
    if len(cand) > 1:
        return None, '[要確認]_前方一致が' + str(len(cand)) + '件', None
    # 逆方向: 対応表側が短い（例: 表「戸崎」← 出馬表「戸崎圭」）。一意なときだけ結ぶ
    cand = [k for k in table if len(k) >= 2 and q.startswith(k)]
    if len(cand) == 1:
        return table[cand[0]], f'逆前方一致({cand[0]})', cand[0]
    if len(cand) > 1:
        return None, '[要確認]_逆前方一致が' + str(len(cand)) + '件', None
    # netkeiba略記「姓2字＋名の末尾1字」（例: 石神道 ← 石神深道）。一意なときだけ結ぶ
    if len(q) == 3:
        cand = [k for k in table if len(k) >= 4 and k.startswith(q[:2]) and k.endswith(q[2])]
        if len(cand) == 1:
            return table[cand[0]], f'略記一致({cand[0]})', cand[0]
        if len(cand) > 1:
            return None, '[要確認]_略記一致が' + str(len(cand)) + '件', None
    return None, '[不足]_対応表に無い', None

races = json.load(open(os.path.join(REPO, 'predictions', '20260905', 'toukei_20260905.json')))
out = {}
st = collections.Counter()
for rc in races:
    for h in rc['horses']:
        key = f"{rc['ba']}|{rc['r']}|{h['uma']}"
        jg, jhow, jkey = lookup(h.get('jockey'), jockey_grp)
        tg, thow, _ = lookup(h.get('trainer'), tmap)
        jm = grp.get(jg) if jg else None
        tm = grp.get(tg) if tg else None
        # 第5報: 現週表の表記ゆれ（小幡初/小幡育 ＝ 木幡初也/木幡育也の誤記とみられる）は自動結合せず候補として残す＝[要確認]
        cand = None
        if jm is None and h.get('jockey') and h['jockey'].startswith('木幡'):
            alt = '小幡' + h['jockey'][2:]
            cg, chow, ckey = lookup(alt, jockey_grp)
            if cg and grp.get(cg):
                cand = dict(group=cg, mark=grp[cg][0], unki=grp[cg][1], reason=f'[要確認]_表記ゆれ候補({ckey}→{h["jockey"]})。自動結合していない')
        # 第5報: 現週表と7/4マスタで星人グループが競合する騎手（ChatGPT SHADOW監査の指摘）
        CONFLICT = {'今村聖奈': '7/4マスタ=木星－（現週表=水星－）', '森田誠也': '7/4マスタ=天王星－（現週表=木星－）'}
        conflict = CONFLICT.get(jkey) if jkey else None
        st['騎手_結合' if jm else '騎手_' + jhow.split('_')[0]] += 1
        st['調教師_結合' if tm else '調教師_' + thow.split('_')[0]] += 1
        out[key] = dict(
            name=h['name'], jockey=h.get('jockey'), trainer=h.get('trainer'),
            jockey_group=jg, jockey_join=jhow,
            jockey_mark=jm[0] if jm else None, jockey_unki=jm[1] if jm else None,
            jockey_note=jockey_note.get(jkey) if jkey else None,
            jockey_candidate=cand, jockey_master_conflict=('[要確認]_' + conflict) if conflict else None,
            trainer_group=tg, trainer_join=thow,
            trainer_mark=tm[0] if tm else None, trainer_unki=tm[1] if tm else None,
        )

print('\n=== 結合の内訳（447頭）===')
for k, v in sorted(st.items()):
    print(f'  {k:26s} {v:4d}')
jm = collections.Counter(v['jockey_mark'] for v in out.values())
tm = collections.Counter(v['trainer_mark'] for v in out.values())
print('\n[実] 騎手運勢記号の分布  :', dict(jm))
print('[実] 調教師運勢記号の分布:', dict(tm))
print('⚠ ×は「押し上げが無い」の意味であり、消し根拠・減点材料ではない')

dest = os.path.join(REPO, 'predictions', '20260905', 'unsei_20260905.json')
json.dump(dict(version='unsei905_v3', raceday='20260905',
               note='運勢×は消し根拠にしない。騎手=運勢_20260905-06_結合用.csv(星人グループ×9/5記号)。調教師=Obsidian正本 調教師運勢_lookup_20260704_星人変換済み.csv の星人グループのみ(生年月日は保持していない)。',
               horses=out), open(dest, 'w'), ensure_ascii=False, indent=1)
print(f'\n書き出し: {dest}')
