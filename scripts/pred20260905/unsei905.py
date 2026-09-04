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
for r in csv.DictReader(open(UNSEI, encoding='utf-8-sig')):
    g = r['星人グループ'].strip()
    grp[g] = (r['9/5記号'].strip(), r['9/5運気'].strip())
    for tok in re.split(r'[、,]', r.get('D列原文(騎手名・ROI注記)', '')):
        tok = tok.strip().strip('　')
        if not tok:
            continue
        nm = re.sub(r'^\d+', '', tok)              # 先頭のROI数値を落とす
        nm = re.sub(r'[（(].*$', '', nm).strip()    # 括弧内の注記を落とす
        if nm:
            jockey_grp[nm] = g
            jockey_note[nm] = tok
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
    候補が2件以上あれば[要確認]として結ばない(静かに潰さない)。"""
    if not name:
        return None, '[不足]_名前が無い'
    if name in table:
        return table[name], '完全一致'
    cand = [k for k in table if k.startswith(name)]
    if len(cand) == 1:
        return table[cand[0]], f'前方一致({cand[0]})'
    if len(cand) > 1:
        return None, '[要確認]_前方一致が' + str(len(cand)) + '件'
    return None, '[不足]_対応表に無い'

races = json.load(open(os.path.join(REPO, 'predictions', '20260905', 'toukei_20260905.json')))
out = {}
st = collections.Counter()
for rc in races:
    for h in rc['horses']:
        key = f"{rc['ba']}|{rc['r']}|{h['uma']}"
        jg, jhow = lookup(h.get('jockey'), jockey_grp)
        tg, thow = lookup(h.get('trainer'), tmap)
        jm = grp.get(jg) if jg else None
        tm = grp.get(tg) if tg else None
        st['騎手_結合' if jm else '騎手_' + jhow.split('_')[0]] += 1
        st['調教師_結合' if tm else '調教師_' + thow.split('_')[0]] += 1
        out[key] = dict(
            name=h['name'], jockey=h.get('jockey'), trainer=h.get('trainer'),
            jockey_group=jg, jockey_join=jhow,
            jockey_mark=jm[0] if jm else None, jockey_unki=jm[1] if jm else None,
            jockey_note=jockey_note.get(h.get('jockey')) if jg else None,
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
json.dump(dict(version='unsei905_v1', raceday='20260905',
               note='運勢×は消し根拠にしない。調教師の生年月日は保持していない。',
               horses=out), open(dest, 'w'), ensure_ascii=False, indent=1)
print(f'\n書き出し: {dest}')
