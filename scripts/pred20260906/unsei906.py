#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑨本シートゲート(9/6): 9/6の騎手運勢・調教師運勢を出走484頭へ結合する。9/5 unsei905 v4 と同じ手順（9/6記号列を読む）。v2: DE正本フルネーム向けの逆方向規則(1字姓・略記逆一致・区切り無視)を追加。田山旺佑は候補HOLD。

出所:
  * 運勢_20260905-06_結合用.csv … 星人グループ×9/5記号/運気。D列に騎手名の一覧(＋ROI注記)
  * 調教師名→星人グループ の対応 … Obsidian正本 調教師運勢_lookup_20260704_星人変換済み.csv 由来。
    ⚠ 元CSVは209名の生年月日を含むため公開リポジトリへは格納しない。
      本スクリプトが使うのは「調教師名→星人グループ」の2列のみ(scratchpad)。

⚠ 運勢×は「押し上げが無い」だけであり、消し根拠・減点材料に転用しない。

v4(第7報):
  * D列のROI注記（回収率とみられる数値・条件別の○✖）は出力へ一切保持しない（公開リポジトリへ原数値・帯を書かない）。
  * 結合キー(現週ブックの氏名)と新聞CSVの騎手フルネームを突き合わせ、字が違う場合(例: ブック「田山旺祐」／新聞「田山旺佑」)は
    「別ソース参照候補」に落としてHOLD（自動PASSしない。原記号は jockey_mark に残し、jockey_mark_usable は None）。
  * jockey_kubun = 素材一致／別ソース参照候補／マスタ競合／未結合 を1騎乗ごとに付け、unsei_4kubun_20260905.csv を本スクリプトから書く。
"""
import csv, json, os, re, collections, sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SP = '/tmp/claude-0/-home-user-github-com-new/47c1892c-ddc4-50e4-8b6f-3403a9782673/scratchpad'
UNSEI = os.path.join(REPO, 'predictions', '20260905', '運勢_20260905-06_結合用.csv')   # 9/5・9/6の両日を持つ結合用CSV。9/6列を使う
TMAP = os.path.join(SP, 'trainer_seijin.tsv')
PACK = os.environ.get('PACK906', os.path.join(SP, 'd0906', 'pack.json'))   # 新聞CSVの騎手フルネーム（氏名整合検査にだけ使う）

grp = {}          # 星人グループ -> (9/5記号, 9/5運気)
jockey_grp = {}   # 騎手名(表記ゆれ含む) -> 星人グループ
grp_row = {}      # 星人グループ -> 結合用CSVの行番号（見出し=行1）
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

for i, r in enumerate(csv.DictReader(open(UNSEI, encoding='utf-8-sig')), start=2):
    g = r['星人グループ'].strip()
    grp[g] = (r['9/6記号'].strip(), r['9/6運気'].strip())
    grp_row[g] = i
    for tok in split_d(r.get('D列原文(騎手名・ROI注記)', '')):
        nm = re.sub(r'^\d+', '', tok)              # 先頭の数値注記を落とす（保持しない）
        nm = re.sub(r'[（(].*$', '', nm).strip()    # 括弧内の注記を落とす（保持しない）
        if nm:
            jockey_grp[norm(nm)] = g
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
    # --- 9/6 v2: 出走表がDE正本のフルネームになったための逆方向規則（9/5はnetkeiba略記で不要だった） ---
    # (a) 表側が1字の姓（幸・原・黛）: フルネームがその字で始まり、他に候補が無いときだけ結ぶ
    cand = [k for k in table if len(k) == 1 and q.startswith(k)]
    if len(cand) == 1 and not [k for k in table if len(k) >= 2 and q.startswith(k)]:
        return table[cand[0]], f'逆前方一致1字({cand[0]})', cand[0]
    # (b) 表側が略記「姓2字＋名末尾1字」（鮫島駿）でフルネームが4字以上（鮫島克駿）: 一意なときだけ結ぶ
    if len(q) >= 4:
        cand = [k for k in table if len(k) == 3 and q.startswith(k[:2]) and q.endswith(k[2])]
        if len(cand) == 1:
            return table[cand[0]], f'略記逆一致({cand[0]})', cand[0]
        if len(cand) > 1:
            return None, '[要確認]_略記逆一致が' + str(len(cand)) + '件', None
    # (c) 区切り記号の差（Ｍ．デム ↔ Mデムーロ）: 「．.」を落として前方一致。一意なときだけ
    q2 = q.replace('.', '').replace('．', '')
    if q2 != q:
        cand = [k for k in table if k.startswith(q2)]
        if len(cand) == 1:
            return table[cand[0]], f'前方一致・区切り無視({cand[0]})', cand[0]
    return None, '[不足]_対応表に無い', None

def nname(s):
    """氏名整合検査用の正規化: 全角英字→半角、区切り(．. 空白 ・)・減量記号(☆★▲△◇)・[替] を落とす"""
    s = norm(s or '')
    return re.sub(r'\[替\]|[☆★▲△◇◎○．.\s・　]', '', s)

def name_check(book_key, full):
    """現週ブックの氏名(結合キー)と新聞CSVの騎手フルネームの整合。字が違えば「表記差」＝候補HOLD"""
    if not full:
        return '新聞欠'
    b, f = nname(book_key), nname(full)
    if b == f or f.startswith(b) or f.endswith(b) or b.startswith(f):
        return '一致'
    if len(b) == 3 and f.startswith(b[:2]) and f.endswith(b[2]):
        return '一致(略記)'
    return f'表記差(ブック={book_key}／新聞={full})'

shinbun = {}
if os.path.exists(PACK):
    _p = json.load(open(PACK))
    shinbun = {(r['race_id'], int(r['馬番'])): r.get('騎手', '') for r in _p.get('スライド競馬新聞', [])}
    print(f'[実] 新聞CSVの騎手フルネーム {len(shinbun)}行（氏名整合検査にだけ使用）')
else:
    print('[不足] pack.json が無い。氏名整合検査は「新聞欠」になる')

races = json.load(open(os.path.join(REPO, 'predictions', '20260906', 'toukei_20260906.json')))['races']
out = {}
rows4 = []
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
        # 9/6 v2: 田山旺佑(DE正本) ↔ 田山旺祐(現週ブック)。9/5第7報と同じく別ソース参照候補としてHOLD。自動結合しない
        if jm is None and h.get('jockey') == '田山旺佑':
            cg, chow, ckey = lookup('田山旺祐', jockey_grp)
            if cg and grp.get(cg):
                cand = dict(group=cg, mark=grp[cg][0], unki=grp[cg][1], reason=f'[要確認]_表記差(ブック={ckey}／DE={h["jockey"]})。承認済み別名対応なし。自動結合していない')
        # 第5報: 現週表と7/4マスタで星人グループが競合する騎手（ChatGPT SHADOW監査の指摘）
        CONFLICT = {'今村聖奈': '7/4マスタ=木星－（現週表=水星－）', '森田誠也': '7/4マスタ=天王星－（現週表=木星－）'}
        conflict = CONFLICT.get(jkey) if jkey else None
        full = shinbun.get((rc['race_id'], h['uma']), '')
        chk = name_check(jkey, full) if jkey else None
        # 第7報: 4区分。表記差(字が違う)は自動PASSせず候補としてHOLD
        if jm is None:
            kubun = '別ソース参照候補' if cand else '未結合'
        elif conflict:
            kubun = 'マスタ競合'
        elif chk and not chk.startswith('一致'):
            kubun = '別ソース参照候補'
            cand = dict(group=jg, mark=jm[0], unki=jm[1], reason=f'[要確認]_{chk}。人物ID(ブック側に無い)で同定できず、承認済み別名対応も無い。自動結合していない')
        else:
            kubun = '素材一致'
        usable = (kubun == '素材一致')
        st['騎手_結合' if jm else '騎手_' + jhow.split('_')[0]] += 1
        st['騎手_区分_' + kubun] += 1
        st['調教師_結合' if tm else '調教師_' + thow.split('_')[0]] += 1
        out[key] = dict(
            name=h['name'], jockey=h.get('jockey'), trainer=h.get('trainer'), scratched=h.get('scratched', False),
            jockey_group=jg, jockey_join=jhow, jockey_book_key=jkey,
            jockey_shinbun_name=full or None, jockey_name_check=chk,
            jockey_kubun=kubun,
            jockey_mark=jm[0] if jm else None, jockey_unki=jm[1] if jm else None,          # 原記録（HOLD分も保持。消さない）
            jockey_mark_usable=(jm[0] if (jm and usable) else None),                       # 利用可能（素材一致のみ）
            jockey_candidate=cand, jockey_master_conflict=('[要確認]_' + conflict) if conflict else None,
            trainer_group=tg, trainer_join=thow,
            trainer_mark=tm[0] if tm else None, trainer_unki=tm[1] if tm else None,
        )
        rows4.append(dict(
            target_date='2026-09-06', ba=rc['ba'], r=rc['r'], race_id=rc['race_id'], uma=h['uma'], name=h['name'],
            scratched=int(bool(h.get('scratched'))), jockey=h.get('jockey'), shinbun_jockey=full or '',
            kubun=kubun, join=jhow, book_key=jkey or '', name_check=chk or '',
            seijin_group=jg or '', mark_raw=(jm[0] if jm else ''), unki=(jm[1] if jm else ''), mark_usable=(jm[0] if (jm and usable) else ''),
            source_row=(f'運勢_20260905-06_結合用.csv 行{grp_row[jg]}（9/6記号列）' if jg in grp_row else ''),
            source_xlsx_row=(f'騎手運勢2026.09.05.xlsx!2026.09.06 行{grp_row[jg] + 1}（B列=9/6記号・D列=名簿）[推:CSV行+1]' if jg in grp_row else ''),
            candidate=(f"{cand['group']}/{cand['mark']} {cand['reason']}" if cand else ''),
            master_conflict=('[要確認]_' + conflict) if conflict else '',
        ))

print('\n=== 結合の内訳（484頭）===')
for k, v in sorted(st.items()):
    print(f'  {k:26s} {v:4d}')
jm = collections.Counter(v['jockey_mark'] for v in out.values())
tm = collections.Counter(v['trainer_mark'] for v in out.values())
print('\n[実] 騎手運勢記号の分布  :', dict(jm))
print('[実] 調教師運勢記号の分布:', dict(tm))
print('⚠ ×は「押し上げが無い」の意味であり、消し根拠・減点材料ではない')

dest = os.path.join(REPO, 'predictions', '20260906', 'unsei_20260906.json')
json.dump(dict(version='unsei906_v2', raceday='20260906',
               note='運勢×は消し根拠にしない。騎手=運勢_20260905-06_結合用.csv(星人グループ×9/6記号)。調教師=Obsidian正本 調教師運勢_lookup_20260704_星人変換済み.csv の星人グループのみ(生年月日は保持していない)。v4: D列の数値注記は保持しない。jockey_kubun(4区分)と jockey_mark_usable(素材一致のみ)を追加。',
               horses=out), open(dest, 'w'), ensure_ascii=False, indent=1)
print(f'\n書き出し: {dest}')
dest4 = os.path.join(REPO, 'predictions', '20260906', 'unsei_4kubun_20260906.csv')
with open(dest4, 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows4[0].keys()), lineterminator='\n')
    w.writeheader(); w.writerows(rows4)
k4 = collections.Counter(r['kubun'] for r in rows4 if not r['scratched'])
print(f'書き出し: {dest4} ({len(rows4)}行。取消除く4区分: {dict(k4)})')
print('[実] 氏名整合検査:', dict(collections.Counter(r['name_check'] for r in rows4 if r['name_check'])))
