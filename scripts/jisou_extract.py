#!/usr/bin/env python3
"""⑭次走期待好走馬 抽出 v1.2
v1.1からの変更(2026-08-30 ChatGPT裁定P0を受けて):
  - 候補帯を「確定人気7〜12」から「確定人気4〜12」へ拡張し、層別に出力
    B層=確定4〜6人気(中位妙味) / C層=確定7〜12人気(穴妙味) / D層=13人気以下(例外)
  - 定義バージョンと生成時刻をJSONへ刻印
根拠: 8/29・8/30の実測で、荒れたレースの1着馬の70%(16/23)が基準6人気以内。
      7〜12帯のみを見る設計では原理的に届かない(第5報§5・第11報§6)。
"""
import json, os, sys, re, collections

VERSION = 'jisou_v1.2'
SP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def rank_last3f(horses):
    """レース内の上がり3F順位(小さいほど速い)。同値は同順位。"""
    vals = sorted({h['last3f'] for h in horses if h['last3f']})
    return {v: i + 1 for i, v in enumerate(vals)}

def passing_first(p):
    if not p: return None
    m = re.match(r'(\d+)', p)
    return int(m.group(1)) if m else None

def diff_sec(d):
    """netkeibaの着差表記を概算秒へ。研究用の粗い換算=[推:着差換算]"""
    if d is None: return None
    d = d.strip()
    table = {'': 0.0, 'ハナ': 0.02, 'アタマ': 0.05, 'クビ': 0.1,
             '1/2': 0.1, '3/4': 0.15, '1/4': 0.05, '1.1/4': 0.2, '1.1/2': 0.25,
             '1.3/4': 0.3, '同着': 0.0}
    if d in table: return table[d]
    m = re.match(r'^(\d+)(?:\.(\d+/\d+))?$', d)
    if m:
        return int(m.group(1)) * 0.15 + (table.get(m.group(2), 0) if m.group(2) else 0)
    return None

def score(chaku, l3, back_run, close_diff, pop):
    """注目度スコア。⚠ 重み付けは未検証=[推:研究序列]。印でも軸でもなく「読む順序」。
    以前の報告(第9報初版)は場当たりの計算で算出しており再現できなかったため、
    ここに実装を固定して再現可能にした。"""
    s = 0
    if chaku == 1:      s += 3
    elif chaku in (2, 3): s += 2
    if   l3 == 1: s += 3
    elif l3 == 2: s += 2
    elif l3 == 3: s += 1
    if back_run:   s += 2   # 1角で後方1/3から5着以内
    if close_diff: s += 2   # 勝ち馬から0.3秒以内で4着以下
    if pop and pop >= 7: s += 1
    return s

def band(pop):
    if pop is None: return None
    if pop <= 3:  return 'A'
    if pop <= 6:  return 'B'
    if pop <= 12: return 'C'
    return 'D'

def find_results(day):
    """確定結果ファイルを探す。命名が2系統ある(results確定_YYYYMMDD.json / results_YYYYMMDD.json)
    うえ、8/22のように別日フォルダへ置かれた分もあるため全predictions配下を走査する。
    ⚠ 同名で中身の違うファイルが実在する。predictions/20260816/results_20260816.json と
      predictions/20260822/results_20260822.json は「予想側の評価データ」であって確定結果ではない。
      よって名前ではなく中身('horses'キーの有無)で確定結果を判定する。
      さらに 確定名(results確定_)を優先し、曖昧名(results_)は後順位とする。"""
    hits = []
    base = os.path.join(SP, 'predictions')
    for d in sorted(os.listdir(base)):
        for pref, name in ((0, f'results確定_{day}.json'), (1, f'results_{day}.json')):
            p = os.path.join(base, d, name)
            if not os.path.exists(p): continue
            try:
                j = json.load(open(p))
            except Exception:
                continue
            if isinstance(j, list) and j and isinstance(j[0], dict) and 'horses' in j[0]:
                hits.append((pref, p))
    if not hits:
        raise FileNotFoundError(f'{day} の確定結果ファイル(horsesキーを持つ形式)が見つかりません')
    hits.sort()
    if len(hits) > 1:
        print(f'   ⚠ 確定結果候補が{len(hits)}件。確定名優先で採用: {hits[0][1]}')
    return hits[0][1]

def extract(day):
    R = json.load(open(find_results(day)))
    # ⚠ 障害競走は除外する。14係の平地パイプラインと母集団を揃えるため
    #   (8/22・8/23・8/29・8/30 の既存ファイルは障害を除いた35Rで作られている)
    def lab(r):
        # ⚠ 日によってレース見出しのスキーマが違う(label/meta 版と race_name/distance/course 版)
        if r.get('label'): return r['label']
        return ' '.join(str(r.get(k) or '') for k in ('race_name', 'course', 'distance', 'going'))
    jump = [r for r in R if '障' in lab(r) or '障' in (r.get('meta') or '')]
    R = [r for r in R if r not in jump]
    if jump:
        print(f'   ⚠ 障害{len(jump)}鞍を除外: ' + ' / '.join(f"{x['venue']}{x['r']}R" for x in jump))
    out, checks = [], {'dup': 0, 'pop_gap': 0, 'key_dup': 0, 'scratch': 0}
    keys = set()
    exp = 0
    for r in R:
        if r['racekey'] in keys: checks['key_dup'] += 1
        keys.add(r['racekey'])
        hs = r['horses']
        if len({h['umaban'] for h in hs}) != len(hs): checks['dup'] += 1
        fin = [h for h in hs if h['chakujun']]
        # ⚠ 人気の連番検査は「発走馬」で行う。競走中止馬は馬券発売済みで人気を持つため
        #   完走馬だけで検査すると中止馬の番号が欠番に見える(v1.1の§E定義に合わせる)。
        started = [h for h in hs if h['chakujun'] or h.get('status') == '中止']
        pops = sorted(h['pop'] for h in started if h['pop'])
        if pops and pops != list(range(1, len(pops) + 1)): checks['pop_gap'] += 1
        checks['scratch'] += len(hs) - len(fin)
        checks['chuushi'] = checks.get('chuushi', 0) + sum(1 for h in hs if h.get('status') == '中止')
        checks['jogai'] = checks.get('jogai', 0) + sum(
            1 for h in hs if h.get('status') and h['status'] != '中止')
        # EXPECTED_COUNT: 確定人気4〜12の発走馬
        exp += sum(1 for h in fin if h['pop'] and 4 <= h['pop'] <= 12)
        rk = rank_last3f(fin)
        win = min(fin, key=lambda h: h['chakujun'])
        for h in fin:
            b = band(h['pop'])
            if b in (None, 'A'): continue
            l3 = rk.get(h['last3f'])
            p1 = passing_first(h['passing'])
            n = len(fin)
            ds = diff_sec(h['diff'])
            sig = []
            if h['chakujun'] <= 3: sig.append(f"{h['chakujun']}着")
            if l3 == 1: sig.append('上がり最速')
            elif l3 and l3 <= 3: sig.append(f'上がり{l3}位')
            back_run = bool(p1 and n >= 8 and p1 >= n * 2 / 3 and h['chakujun'] <= 5)
            if back_run:
                sig.append(f'1角{p1}番手から{h["chakujun"]}着')
            close_diff = bool(ds is not None and 0 < ds <= 0.3 and h['chakujun'] >= 4)
            if close_diff:
                sig.append(f'勝ち馬から約{ds:.1f}秒')
            if not sig: continue
            sc = score(h['chakujun'], l3, back_run, close_diff, h['pop'])
            # 層(tier)判定
            if h['chakujun'] <= 3:
                tier = '確定枠'
            elif (l3 == 1) or (ds is not None and ds <= 0.3 and l3 and l3 <= 3):
                tier = '優先高'
            elif (l3 and l3 <= 3) or (p1 and n >= 8 and p1 >= n * 2 / 3 and h['chakujun'] <= 5):
                tier = '優先中'
            else:
                continue
            out.append({
                'day': day, 'race': f"{r['venue']}{r['r']}R", 'racekey': r['racekey'],
                'label': lab(r), 'uma': h['umaban'], 'name': h['name'],
                'horse_id': h['horse_id'], 'jockey': h['jockey'], 'trainer': h['trainer'],
                'sex_age': h['sex_age'], 'pop': h['pop'], 'odds': h['odds'],
                'chaku': h['chakujun'], 'last3f': h['last3f'], 'l3_rank': l3,
                'passing': h['passing'], 'passing_from': h.get('passing_from'),
                'diff': h['diff'], 'diff_sec': ds, 'n': n,
                'band': b, 'tier': tier, 'score': sc, 'signals': sig,
            })
    return out, checks, exp, len(R)

DAYS = sys.argv[1:] or ['20260829', '20260830']
allout = []
for day in DAYS:
    o, c, exp, nr = extract(day)
    allout += o
    print(f'■ {day}: {nr}R  EXPECTED_COUNT(確定4〜12人気の発走馬)={exp}  抽出={len(o)}')
    print(f'   §E検査 馬番重複{c["dup"]} / 人気欠番{c["pop_gap"]} / racekey重複{c["key_dup"]} '
          f'/ 中止{c.get("chuushi",0)}・除外{c.get("jogai",0)}'
          f'  → {"PASS" if c["dup"]==c["pop_gap"]==c["key_dup"]==0 else "FAIL"}')

print()
t = collections.Counter((x['tier'], x['band']) for x in allout)
print('■ 層 × 帯')
print(f"  {'':<8s} {'B層(4〜6人気)':>14s} {'C層(7〜12人気)':>14s} {'D層(13〜)':>12s}")
for tier in ('確定枠', '優先高', '優先中'):
    print(f"  {tier:<8s} {t[(tier,'B')]:>14d} {t[(tier,'C')]:>14d} {t[(tier,'D')]:>12d}")
print(f"  {'合計':<8s} {sum(t[(x,'B')] for x in ('確定枠','優先高','優先中')):>14d}"
      f" {sum(t[(x,'C')] for x in ('確定枠','優先高','優先中')):>14d}"
      f" {sum(t[(x,'D')] for x in ('確定枠','優先高','優先中')):>12d}")
print(f'\n  総計 {len(allout)}頭')

sc = collections.Counter(x['score'] for x in allout)
print('\n■ 注目度スコア分布(重みは未検証=[推:研究序列])')
for k in sorted(sc, reverse=True):
    print(f'  {k}点: {sc[k]:4d}')

import datetime
OUT = os.environ.get('JISOU_OUT', os.path.join(SP,'predictions','20260830','次走期待_20260829-30.json'))
json.dump({'version': VERSION, 'generated_for': '次走監視',
           'source_days': [f'{d[:4]}-{d[4:6]}-{d[6:]}' for d in DAYS],
           'candidate_band': '確定人気4〜12(v1.1の7〜12から拡張)',
           'horses': allout},
          open(OUT, 'w'), ensure_ascii=False, indent=1)
print(f'\n  → {OUT}')
