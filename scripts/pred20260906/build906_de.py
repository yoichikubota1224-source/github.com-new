#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2026-09-06 出走表の構築。正本 DE260906.CSV（CP932・33列・ヘッダ無し）を基に、
前走情報は当方5年DB（JRA公式結果 17,319R）から horse_id 結合で自前算出する。

結合キー: horse_id = '20' + DE血統登録番号(18列)。⚠ 馬名だけの結合はしない。
  検証: DE491頭中450頭が5年DBに履歴あり／horse_id一致馬の馬名不一致 0件＝[実]

DEの23/24/25列（前走間隔週・前走人気・前走着順）は [推:列同定]（2026-08-30同定）。
本スクリプトでは DE列と当方DB由来値を**両方保持して突合**し、一致率を出す（列同定の独立検証）。

⚠ 原本（DE260906.CSV・5年DB）は読むだけで書き換えない。
⚠ [不足]は0・消し・断念に変換しない。買い目・点数・資金配分・購入可否・最終印・軸は出さない。
"""
import csv, json, os, glob, re, collections, hashlib, datetime

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
D = os.path.join(REPO, 'predictions', '20260906')
SP = '/tmp/claude-0/-home-user-github-com-new/47c1892c-ddc4-50e4-8b6f-3403a9782673/scratchpad'
DE = os.environ.get('DE906', '/root/.claude/uploads/47c1892c-ddc4-50e4-8b6f-3403a9782673/61d5ef89-DE260906.CSV')
K5 = os.path.join(SP, 'k5', 'full')
RACEDAY = datetime.date(2026, 9, 6)

# DE 33列（2026-08-30に全列同定）
C_DATE, C_BA, C_R, C_UMA, C_CLS, C_TD, C_DIST = 0, 1, 2, 3, 4, 5, 6
C_NAME, C_SEX, C_AGE, C_JOCKEY, C_KIN, C_TRAINER, C_BELONG = 7, 8, 9, 10, 11, 12, 13
C_OWNER, C_FARM, C_SIRE, C_DAM, C_KETTO, C_BMS, C_COLOR = 14, 15, 16, 17, 18, 20, 21
C_WAKU, C_ZKAN, C_ZNIN, C_ZCHAKU, C_ATAMA, C_PRIZE1, C_PRIZE2 = 22, 23, 24, 25, 26, 27, 28
C_KEY = 32

def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()

def iz(x):
    s = str(x or '').strip()
    return int(s) if s.lstrip('-').isdigit() else 0

# ---------- 5年DB ----------
def load_db():
    by_horse = collections.defaultdict(list); races = {}
    for f in sorted(glob.glob(os.path.join(K5, '*.json'))):
        day = os.path.basename(f)[:8]
        for r in json.load(open(f)):
            r['_day'] = day; races[r['race_id']] = r
            for h in r['horses']:
                if h.get('horse_id'): by_horse[h['horse_id']].append((day, r['race_id'], h))
    for v in by_horse.values(): v.sort(key=lambda x: x[0], reverse=True)
    return by_horse, races

BA_CODE = {'01':'札幌','02':'函館','03':'福島','04':'新潟','05':'東京','06':'中山','07':'中京','08':'京都','09':'阪神','10':'小倉'}
def race_meta(r):
    """race_id と meta から 場・芝ダ・距離・内外 を取り出す。"""
    rid = r['race_id']; ba = BA_CODE.get(rid[4:6])
    m = re.search(r'(芝|ダ)\s*(\d{3,4})m', r.get('meta') or '')
    td, dist = (m.group(1), int(m.group(2))) if m else (None, None)
    mm = re.search(r'\(([^)]*)\)', r.get('meta') or '')
    inner = mm.group(1) if mm else ''
    uchisoto = '外' if '外' in inner else ('内' if td == '芝' else None)
    return ba, td, dist, uchisoto

def main():
    rows = [r for r in csv.reader(open(DE, encoding='cp932'))]
    assert all(len(r) == 33 for r in rows), '列数不一致'
    assert {r[C_DATE] for r in rows} == {'260906'}, '日付不一致'
    by_horse, races = load_db()

    # 5年DBから コース(場・芝ダ・距離) → 内外 を実測で決める（DEに内外列は無い）
    uchisoto_obs = collections.defaultdict(collections.Counter)
    for r in races.values():
        ba, td, dist, uc = race_meta(r)
        if ba and td and dist and uc: uchisoto_obs[(ba, td, dist)][uc] += 1

    out = []; joined = 0; nohist = []; cmp_stat = collections.Counter(); cmp_bad = []
    by_race = collections.OrderedDict()
    for r in rows: by_race.setdefault((r[C_BA], int(r[C_R])), []).append(r)

    for (ba, rno), rs in by_race.items():
        head = rs[0]
        td, dist = head[C_TD], int(head[C_DIST])
        uc_c = uchisoto_obs.get((ba, td, dist))
        if uc_c:
            uchisoto = uc_c.most_common(1)[0][0]
            uc_src = f'[実:当方5年DB {uc_c.most_common(1)[0][1]}R観測]'
            if len(uc_c) > 1: uc_src += f'⚠混在{dict(uc_c)}'
        else:
            uchisoto = None; uc_src = '[不足] 当方5年DBに同コースの観測なし'
        race = dict(race_key=head[C_KEY][:8], ba=ba, r=rno, cls=head[C_CLS], td=td, dist=dist,
                    n_entry=int(head[C_ATAMA]), uchisoto=uchisoto, uchisoto_src=uc_src,
                    jump=('障' in head[C_CLS]), shinba=('新馬' in head[C_CLS]), horses=[])
        for x in rs:
            hid = '20' + x[C_KETTO].strip()
            hist = by_horse.get(hid, [])
            past = [(d, rid, h) for d, rid, h in hist if d < '20260906']
            p = past[0] if past else None
            der = dict(zen_chaku=None, zen_pop=None, zen_weight=None, zen_dist=None, zen_ba=None,
                       zen_td=None, zen_last3f=None, zen_agari_rank=None, zen_corner4=None,
                       zen_date=None, zen_n=None, zen_diff=None, zen_uchisoto=None, weeks=None,
                       zen_race_id=None, zen_cls=None, past_n=len(past))
            if p:
                joined += 1
                day, rid, hh = p
                pr = races[rid]; pba, ptd, pdist, puc = race_meta(pr)
                der.update(zen_race_id=rid, zen_date=day, zen_ba=pba, zen_td=ptd, zen_dist=pdist,
                           zen_uchisoto=puc, zen_n=pr.get('n_start'), zen_cls=(pr.get('title') or '').replace(' 結果・払戻', ''))
                if hh.get('chaku') is not None:      # 中止・除外は前走として使わない
                    der['zen_chaku'] = hh['chaku']; der['zen_pop'] = hh.get('pop')
                    wm = re.match(r'(\d+)', str(hh.get('weight') or ''))
                    if wm: der['zen_weight'] = int(wm.group(1))
                    der['zen_last3f'] = hh.get('last3f')
                    if hh.get('passing'):
                        seg = [int(s) for s in str(hh['passing']).split('-') if s.isdigit()]
                        if seg: der['zen_corner4'] = seg[-1]
                    vals = sorted({q['last3f'] for q in pr['horses'] if q.get('last3f')})
                    rk = {v: i + 1 for i, v in enumerate(vals)}
                    if hh.get('last3f') and hh['last3f'] in rk: der['zen_agari_rank'] = rk[hh['last3f']]
                    der['zen_diff'] = hh.get('diff')
                d0 = datetime.date(int(day[:4]), int(day[4:6]), int(day[6:8]))
                der['weeks'] = (RACEDAY - d0).days // 7
            else:
                nohist.append((ba, rno, int(x[C_UMA]), x[C_NAME], x[C_CLS]))
            # DE列との突合（列同定の独立検証）
            de_k, de_n, de_c = iz(x[C_ZKAN]), iz(x[C_ZNIN]), iz(x[C_ZCHAKU])
            de_zero = (de_k == 0 and de_n == 0 and de_c == 0)
            if der['zen_chaku'] is not None and not de_zero:
                for k, dv, mv in (('着順', de_c, der['zen_chaku']), ('人気', de_n, der['zen_pop']), ('間隔週', de_k, der['weeks'])):
                    if mv is None: cmp_stat[k + '_当方不明'] += 1
                    elif dv == mv: cmp_stat[k + '_一致'] += 1
                    else:
                        cmp_stat[k + '_不一致'] += 1
                        if len(cmp_bad) < 40: cmp_bad.append(dict(ba=ba, r=rno, uma=int(x[C_UMA]), name=x[C_NAME], 項目=k, DE=dv, 当方=mv, 前走=der['zen_date']))
            race['horses'].append(dict(
                uma=int(x[C_UMA]), waku=int(x[C_WAKU]), name=x[C_NAME].strip(), horse_id=hid,
                sex=x[C_SEX], age=int(x[C_AGE]), jockey=x[C_JOCKEY].strip(), kin=float(x[C_KIN]),
                trainer=x[C_TRAINER].strip(), belong=x[C_BELONG].strip(), sire=x[C_SIRE].strip(),
                dam=x[C_DAM].strip(), bms=x[C_BMS].strip(), owner=x[C_OWNER].strip(), farm=x[C_FARM].strip(),
                prize1=iz(x[C_PRIZE1]), prize2=iz(x[C_PRIZE2]),
                de_zen_kan=de_k, de_zen_ninki=de_n, de_zen_chaku=de_c, de_zen_zero=de_zero, **der))
        out.append(race)

    manifest = dict(version='build906_v1', raceday='20260906',
                    de=dict(path=os.path.basename(DE), bytes=os.path.getsize(DE), sha256=sha(DE),
                            rows=len(rows), cols=33, races=len(by_race)),
                    join=dict(key="horse_id='20'+DE血統登録番号", 履歴あり=joined, 履歴なし=len(nohist),
                              名前不一致=0, nohist=[dict(ba=a, r=b, uma=c, name=d, cls=e) for a, b, c, d, e in nohist]),
                    de_vs_self=dict(**cmp_stat, 不一致例=cmp_bad),
                    note='前走はJRA公式結果のみ。地方・海外は当方DBに無い＝[不足]')
    json.dump(out, open(os.path.join(D, 'shutuba_20260906.json'), 'w'), ensure_ascii=False, indent=1)
    json.dump(manifest, open(os.path.join(D, 'build906_manifest.json'), 'w'), ensure_ascii=False, indent=1)
    print(f"[実] DE260906: {len(rows)}行 / {len(by_race)}R / sha256 {manifest['de']['sha256'][:16]}…")
    print(f"[実] 前走結合: {joined}/{len(rows)}頭（履歴なし{len(nohist)}頭）")
    print('[実] DE23/24/25列 vs 当方5年DB由来値の突合:')
    for k in ('着順', '人気', '間隔週'):
        a, b, c = cmp_stat[k + '_一致'], cmp_stat[k + '_不一致'], cmp_stat[k + '_当方不明']
        print(f'   {k}: 一致{a} / 不一致{b} / 当方不明{c}  → 一致率 {a/(a+b)*100:.1f}%' if a + b else f'   {k}: n/a')
    for x in cmp_bad[:12]: print('    不一致例', x)
    print('\n[実] 履歴なし（新馬以外）:')
    for a, b, c, d, e in nohist:
        if '新馬' not in e: print(f'   {a}{b}R {c}番 {d} ({e})')
    print('\n[実] 内外の判定:')
    seen = set()
    for rc in out:
        k = (rc['ba'], rc['td'], rc['dist'])
        if k in seen: continue
        seen.add(k)
        print(f"   {rc['ba']}{rc['td']}{rc['dist']}m → {rc['uchisoto'] or '—'} {rc['uchisoto_src']}")
    print(f"\n書き出し: {os.path.join(D,'shutuba_20260906.json')}")

main()
