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

def band(pop):
    if pop is None: return None
    if pop <= 3:  return 'A'
    if pop <= 6:  return 'B'
    if pop <= 12: return 'C'
    return 'D'

def extract(day):
    P = os.path.join(SP, 'predictions', day)
    R = json.load(open(os.path.join(P, f'results_{day}.json')))
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
            if p1 and n >= 8 and p1 >= n * 2 / 3 and h['chakujun'] <= 5:
                sig.append(f'1角{p1}番手から{h["chakujun"]}着')
            if ds is not None and 0 < ds <= 0.3 and h['chakujun'] >= 4:
                sig.append(f'勝ち馬から約{ds:.1f}秒')
            if not sig: continue
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
                'label': r['label'], 'uma': h['umaban'], 'name': h['name'],
                'horse_id': h['horse_id'], 'jockey': h['jockey'], 'trainer': h['trainer'],
                'sex_age': h['sex_age'], 'pop': h['pop'], 'odds': h['odds'],
                'chaku': h['chakujun'], 'last3f': h['last3f'], 'l3_rank': l3,
                'passing': h['passing'], 'passing_from': h.get('passing_from'),
                'diff': h['diff'], 'diff_sec': ds, 'n': n,
                'band': b, 'tier': tier, 'signals': sig,
            })
    return out, checks, exp, len(R)

allout = []
for day in ('20260829', '20260830'):
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

import datetime
json.dump({'version': VERSION, 'generated_for': '2026-09-06以降の次走監視',
           'source_days': ['2026-08-29', '2026-08-30'],
           'candidate_band': '確定人気4〜12(v1.1の7〜12から拡張)',
           'horses': allout},
          open(os.path.join(SP, 'predictions', '20260830', '次走期待_20260829-30.json'), 'w'),
          ensure_ascii=False, indent=1)
