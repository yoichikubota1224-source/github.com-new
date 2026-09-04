#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑥調教係(2026-09-05): 8/29〜9/4の追切を9/5出走447頭へ結合する。

結合キーの方針（統治規約「馬名だけで結合しない」への対応）:
  * ウッド … 血統登録番号(31列目) == netkeiba horse_id で結合する = [実]
  * 坂路   … 血統登録番号を持たない。馬名で結合するほかない = [推:馬名結合]
             出走表側・調教側の双方で馬名が一意な場合に限って結合し、
             重複するものは [要確認] として結合しない（静かに潰さない）。

未来情報混入の防止: 採用する追切日は 20260829〜20260904（すべて 20260905 より前）。
"""
import csv, io, json, os, glob, statistics as st, collections, sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHOKYO = os.path.join(REPO, 'data', 'chokyo')
RACEDAY = '20260905'
SINCE, UNTIL = '20260829', '20260904'

def f(x):
    try:
        v = float(x)
        return v if v > 0 else None
    except (TypeError, ValueError):
        return None

# ---------------------------------------------------------------- 読み込み
rows = []
decode_repl = []
for kind, sub, ncol in (('HANRO', 'hanro', 18), ('WOOD', 'wood', 40)):
    for path in sorted(glob.glob(os.path.join(CHOKYO, sub, '*.csv'))):
        d = os.path.splitext(os.path.basename(path))[0]
        if not (SINCE <= d <= UNTIL):
            continue
        raw = open(path, 'rb').read()
        try:
            text = raw.decode('cp932')
        except UnicodeDecodeError:
            decode_repl.append(path)          # 握り潰さず記録する
            text = raw.decode('cp932', errors='surrogateescape')
        rr = list(csv.reader(io.StringIO(text)))
        if kind == 'WOOD':
            rr = rr[1:]
        for r in rr:
            if len(r) < ncol:
                continue
            if kind == 'HANRO':
                laps = [f(r[i]) for i in (14, 15, 16, 17)]
                rec = dict(kind='坂路', place=r[0], date=r[1], name=r[4].strip(), trainer=r[9].strip(),
                           course='坂路', hid=None, f4=f(r[10]), f3=f(r[11]), f2=f(r[12]), f1=f(r[13]),
                           laps=laps)
            else:
                laps = [f(r[27]), f(r[28]), f(r[29]), f(r[30])]   # Lap4..Lap1
                hid = (r[31] or '').strip()
                rec = dict(kind='ウッド', place=r[0], date=r[3], name=r[6].strip(), trainer=r[11].strip(),
                           course=r[1], hid=hid if hid.isdigit() else None,
                           f4=f(r[18]), f3=f(r[19]), f2=f(r[20]), f1=f(r[21]), laps=laps)
            if rec['name'] and rec['date'] and rec['f1']:
                rows.append(rec)

print(f'[実] 採用期間 {SINCE}〜{UNTIL}（すべて競走日 {RACEDAY} より前）')
print(f'[実] 読み込み {len(rows)}本 '
      f"(坂路{sum(1 for x in rows if x['kind']=='坂路')} / ウッド{sum(1 for x in rows if x['kind']=='ウッド')})")
if decode_repl:
    print(f'⚠ CP932で復号できないバイトを含むファイル: {decode_repl}（surrogateescapeで保持。errors="replace"は使っていない）')

# ---------------------------------------------------------------- 馬場差ベースライン(終い1F)
grp = collections.defaultdict(list)
for x in rows:
    grp[(x['date'], x['place'], x['kind'], x['course'])].append(x['f1'])
base = {k: (st.mean(v), st.pstdev(v), len(v)) for k, v in grp.items() if len(v) >= 20}
print(f'[実] ベースライン成立 {len(base)}群 / 全{len(grp)}群 (n>=20の群のみ)')
nz = 0
for x in rows:
    k = (x['date'], x['place'], x['kind'], x['course'])
    if k in base:
        m, s, n = base[k]
        x['z1f'] = round((x['f1'] - m) / s, 3) if s > 0 else None
    else:
        x['z1f'] = None
    nz += x['z1f'] is not None
print(f'[実] z化できた追切 {nz}/{len(rows)}本（残りは群のn<20＝[不足]）')

# ---------------------------------------------------------------- C-2判定
def c2_grade(laps):
    """A3=終い1F 11秒台+加速 / A2=終い2Fとも12秒台+加速 / A1=終い1Fのみ12秒台+加速 / B=減速。
    ラップが揃わない場合は None（[不足]）を返す。0や'B'に変換しない。"""
    if laps is None or len(laps) < 4 or any(l is None for l in laps):
        return None
    l3, l4 = laps[2], laps[3]
    if not (l4 < l3):
        return 'B'
    if 11.0 <= l4 < 12.0:
        return 'A3'
    if 12.0 <= l4 < 13.0 and 12.0 <= l3 < 13.0:
        return 'A2'
    if 12.0 <= l4 < 13.0:
        return 'A1'
    return 'B'

for x in rows:
    # C-2 は坂路のハロン構成に対して定義された判定。ウッドへ流用しない＝[不足]のまま置く。
    x['c2'] = c2_grade(x['laps']) if x['kind'] == '坂路' else None

# ---------------------------------------------------------------- 出走表
races = json.load(open(os.path.join(REPO, 'predictions', RACEDAY, f'toukei_{RACEDAY}.json')))
entries = []
for rc in races:
    for h in rc['horses']:
        entries.append(dict(ba=rc['ba'], r=rc['r'], race_id=rc['race_id'], uma=h['uma'],
                            name=h['name'], hid=h.get('horse_id'), trainer=h.get('trainer'),
                            belong=h.get('belong'), scratched=h.get('scratched', False)))
print(f'[実] 出走表 {len(entries)}頭 / {len(races)}レース（取消 {sum(1 for e in entries if e["scratched"])}頭を含む）')

# 曖昧性の検査
name_in_card = collections.Counter(e['name'] for e in entries)
name_in_work = collections.defaultdict(set)
for x in rows:
    name_in_work[x['name']].add((x['trainer'],))
dup_card = {n for n, c in name_in_card.items() if c > 1}
dup_work = {n for n, s in name_in_work.items() if len(s) > 1}
print(f'[要確認] 出走表内で同名 {len(dup_card)}件 / 調教データ内で同名かつ調教師違い {len(dup_work)}件')

by_hid = collections.defaultdict(list)
by_name = collections.defaultdict(list)
for x in rows:
    if x['hid']:
        by_hid[x['hid']].append(x)
    by_name[x['name']].append(x)

out = {}
stat = collections.Counter()
for e in entries:
    key = f"{e['ba']}|{e['r']}|{e['uma']}"
    got, how = [], None
    hid_hit = by_hid.get(e['hid'] or '', [])
    if hid_hit:
        got, how = list(hid_hit), '血統登録番号'
    # 坂路は血統登録番号を持たないので、同じ馬の坂路分を馬名で足す
    nm_hit = [x for x in by_name.get(e['name'], []) if x['kind'] == '坂路']
    if nm_hit:
        ambiguous = e['name'] in dup_card or e['name'] in dup_work
        if ambiguous:
            stat['坂路_同名で結合せず[要確認]'] += 1
        else:
            got += nm_hit
            how = (how + '+馬名') if how else '馬名'
    # ウッドで血統登録番号が空だった行を馬名で拾う（あれば）
    nm_wood = [x for x in by_name.get(e['name'], []) if x['kind'] == 'ウッド' and not x['hid']]
    if nm_wood and e['name'] not in dup_card and e['name'] not in dup_work:
        got += nm_wood
        how = (how or '') + '+馬名(ウッドID欠)'

    if not got:
        stat['[不足]_期間内に追切なし'] += 1
        out[key] = dict(name=e['name'], hid=e['hid'], scratched=e['scratched'],
                        status='[不足]', reason='8/29〜9/4に追切の記録が無い',
                        n_works=0, join=None)
        continue
    got.sort(key=lambda x: (x['date'], x['kind']))
    last = got[-1]
    hz = [x['z1f'] for x in got if x['z1f'] is not None]
    c2s = [x['c2'] for x in got if x['c2']]            # 坂路のみ（ウッドはNone）
    han = [x for x in got if x['kind'] == '坂路']
    stat['結合できた'] += 1
    stat['結合方法_' + how] += 1
    out[key] = dict(
        name=e['name'], hid=e['hid'], scratched=e['scratched'], status='[実]', join=how,
        n_works=len(got),
        last=dict(date=last['date'], kind=last['kind'], place=last['place'], course=last['course'],
                  f4=last['f4'], f3=last['f3'], f2=last['f2'], f1=last['f1'],
                  laps=last['laps'], z1f=last['z1f'], c2=last['c2']),
        best_z1f=min(hz) if hz else None,
        best_c2=(sorted(c2s, key=lambda g: ['A3', 'A2', 'A1', 'B'].index(g))[0] if c2s else None),
        c2_source=('坂路' if c2s else '[不足]_坂路の追切なし'),
        n_hanro=len(han), n_wood=len(got) - len(han),
        works=[dict(date=x['date'], kind=x['kind'], place=x['place'], course=x['course'],
                    f4=x['f4'], f1=x['f1'], z1f=x['z1f'], c2=x['c2']) for x in got],
    )

print('\n=== 結合の内訳 ===')
for k, v in sorted(stat.items()):
    print(f'  {k:34s} {v:4d}')
liveN = sum(1 for e in entries if not e['scratched'])
joined = sum(1 for k, v in out.items() if v['status'] == '[実]')
print(f'\n[実] 結合率 {joined}/{len(entries)} = {joined/len(entries)*100:.1f}%（取消1頭を含む母数）')
c2dist = collections.Counter(v.get('best_c2') for v in out.values() if v['status'] == '[実]')
print('[実] C-2判定(best)の分布:', dict(c2dist))
zz = [v['best_z1f'] for v in out.values() if v.get('best_z1f') is not None]
if zz:
    print(f'[実] best_z1f: n={len(zz)} 中央値{st.median(zz):+.2f} 範囲[{min(zz):+.2f},{max(zz):+.2f}]（負=その日その場で速い）')

dest = os.path.join(REPO, 'predictions', RACEDAY, f'chokyo_{RACEDAY}.json')
json.dump(dict(version='chokyo905_v1', raceday=RACEDAY, window=[SINCE, UNTIL],
               n_entries=len(entries), n_joined=joined, horses=out),
          open(dest, 'w'), ensure_ascii=False, indent=1)
print(f'\n書き出し: {dest}')
