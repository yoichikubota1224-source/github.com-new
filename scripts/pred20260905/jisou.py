#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑭次走期待好走馬 抽出（jisou_v1.2 の定義を当方5年データ上に再実装）＋ 9/5出走との突合。

⚠ v1.2 からの訂正1件:
   v1.2 は netkeiba の着差列 diff を「勝ち馬からの差」として扱い
   「勝ち馬から約X秒」と表示していたが、diff は **前の馬との着差** である＝誤り。
   本実装では diff_prev(v1.2互換) と diff_from_win(1着からの累積) の両方を出し、
   判定は **diff_from_win**（条件文の本来の意味）を正とする。v1.2互換値も併記する。
"""
import json, re, os, sys, glob, collections

K = '/tmp/claude-0/-home-user-github-com-new/47c1892c-ddc4-50e4-8b6f-3403a9782673/scratchpad/k5/full'
D = os.path.dirname(os.path.abspath(__file__))
VERSION = 'jisou_v1.3(diff訂正)'

DIFF = {'': 0.0, 'ハナ': 0.02, 'アタマ': 0.05, 'クビ': 0.1, 'same': 0.0, '同着': 0.0,
        '1/2': 0.1, '3/4': 0.15, '1/4': 0.05, '1.1/4': 0.2, '1.1/2': 0.25, '1.3/4': 0.3}
def diff_sec(d):
    if d is None: return 0.0
    d = str(d).strip()
    if d in DIFF: return DIFF[d]
    m = re.match(r'^(\d+)(?:\.(\d+/\d+))?$', d)
    if m: return int(m.group(1)) * 0.15 + (DIFF.get(m.group(2), 0.0) if m.group(2) else 0.0)
    m = re.match(r'^大差$', d)
    return 1.5 if m else None

def band(pop):
    if pop is None: return None
    if pop <= 3: return 'A'
    if pop <= 6: return 'B'
    if pop <= 12: return 'C'
    return 'D'

def score(chaku, l3, back_run, close_diff, pop):
    s = 0
    if chaku == 1: s += 3
    elif chaku in (2, 3): s += 2
    if l3 == 1: s += 3
    elif l3 == 2: s += 2
    elif l3 == 3: s += 1
    if back_run: s += 2
    if close_diff: s += 2
    if pop and pop >= 7: s += 1
    return s

def first_pass(p):
    if not p: return None
    m = re.match(r'(\d+)', str(p))
    return int(m.group(1)) if m else None

def extract(day):
    f = os.path.join(K, f'{day}.json')
    R = json.load(open(f))
    out = []; nj = 0; checks = collections.Counter()
    for r in R:
        if r.get('jump'): nj += 1; continue
        hs = r['horses']
        fin = [h for h in hs if h.get('chaku')]
        if not fin: continue
        if len({h['uma'] for h in hs}) != len(hs): checks['馬番重複'] += 1
        pops = sorted(h['pop'] for h in hs if h.get('pop'))
        if pops and pops != list(range(1, len(pops)+1)): checks['人気欠番'] += 1
        # 上がり3F順位
        vals = sorted({h['last3f'] for h in fin if h.get('last3f') is not None})
        rk = {v: i+1 for i, v in enumerate(vals)}
        # 1着からの累積着差
        fin.sort(key=lambda h: h['chaku'])
        cum = {}; acc = 0.0; ok = True
        for h in fin:
            if h['chaku'] == 1: cum[h['uma']] = 0.0; continue
            d = diff_sec(h.get('diff'))
            if d is None: ok = False; break
            acc += d; cum[h['uma']] = acc
        if not ok: cum = {}
        n = len(fin)
        for h in fin:
            b = band(h.get('pop'))
            if b in (None, 'A'): continue
            l3 = rk.get(h.get('last3f'))
            p1 = first_pass(h.get('passing'))
            dprev = diff_sec(h.get('diff'))
            dwin = cum.get(h['uma'])
            sig = []
            if h['chaku'] <= 3: sig.append(f"{h['chaku']}着")
            if l3 == 1: sig.append('上がり最速')
            elif l3 and l3 <= 3: sig.append(f'上がり{l3}位')
            back_run = bool(p1 and n >= 8 and p1 >= n*2/3 and h['chaku'] <= 5)
            if back_run: sig.append(f'1角{p1}番手から{h["chaku"]}着')
            close_win  = bool(dwin is not None and 0 < dwin <= 0.3 and h['chaku'] >= 4)
            close_prev = bool(dprev is not None and 0 < dprev <= 0.3 and h['chaku'] >= 4)
            if close_win: sig.append(f'勝ち馬から約{dwin:.2f}秒')
            if not sig: continue
            sc = score(h['chaku'], l3, back_run, close_win, h.get('pop'))
            if h['chaku'] <= 3: tier = '確定枠'
            elif (l3 == 1) or (dwin is not None and dwin <= 0.3 and l3 and l3 <= 3): tier = '優先高'
            elif (l3 and l3 <= 3) or back_run: tier = '優先中'
            else: continue
            out.append(dict(day=day, race=f"{r['race_id']}", label=r['title'], meta=r['meta'][:40],
                uma=h['uma'], name=h['name'], horse_id=h.get('horse_id'), jockey=h.get('jockey'),
                pop=h.get('pop'), chaku=h['chaku'], last3f=h.get('last3f'), l3_rank=l3,
                passing=h.get('passing'), diff_prev=dprev, diff_from_win=dwin, n=n,
                band=b, tier=tier, score=sc, signals=sig,
                close_win=close_win, close_prev=close_prev))
    return out, nj, checks

def main():
    days = sys.argv[1:] or ['20260829', '20260830']
    allout = []
    for d in days:
        o, nj, c = extract(d)
        allout += o
        print(f'■ {d}: 障害{nj}鞍除外 / 抽出 {len(o)}頭  §E検査 {dict(c) or "PASS(0件)"}')
    # v1.2 との差（close_diff の定義違い）
    only_prev = [x for x in allout if x['close_prev'] and not x['close_win']]
    print(f'\n⚠ v1.2の誤り検出: 「前の馬から0.3秒以内」だが「勝ち馬からは0.3秒超」= {len(only_prev)}頭')
    print('   （v1.2はこれらを「勝ち馬から約X秒」として加点していた）')
    t = collections.Counter((x['tier'], x['band']) for x in allout)
    print('\n■ 層 × 帯')
    print(f"  {'':<8s}{'B層(4〜6人気)':>16s}{'C層(7〜12人気)':>16s}{'D層(13〜)':>14s}")
    for tier in ('確定枠', '優先高', '優先中'):
        print(f"  {tier:<8s}{t[(tier,'B')]:>16d}{t[(tier,'C')]:>16d}{t[(tier,'D')]:>14d}")

    # ---- 9/5 出走との突合（horse_id で結合。馬名だけでは結合しない）----
    S = json.load(open(os.path.join(D, 'shutuba_20260905.json')))
    ent = {}
    for r in S:
        for h in r['horses']:
            if h.get('horse_id'): ent[h['horse_id']] = (r, h)
    hit = []
    for x in allout:
        e = ent.get(x['horse_id'])
        if not e: continue
        r, h = e
        hit.append(dict(x, next_ba=r['ba'], next_r=r['r'], next_race=r['title'],
                        next_course=f"{r['td']}{r['dist']}", next_uma=h['uma'],
                        next_jockey=h['jockey'], next_waku=h['waku'], next_n=r['n_entry'],
                        next_rot=h.get('rotation')))
    hit.sort(key=lambda x: (-x['score'], x['next_ba'], x['next_r']))
    print(f'\n■ 8/29-30の次走期待好走馬 {len(allout)}頭 のうち 9/5 に出走 = {len(hit)}頭')
    print(f'{"score":>5} {"層":<6}{"帯":<3}{"前走":<26}{"→ 9/5":<22}{"馬名":<14}{"根拠"}')
    for x in hit:
        print(f"{x['score']:>5} {x['tier']:<6}{x['band']:<3}"
              f"{x['day'][4:6]}/{x['day'][6:]} {x['pop']:>2}人{x['chaku']:>2}着{'':<12}"
              f"{x['next_ba']}{x['next_r']:>2}R {x['next_uma']:>2}番 {x['next_course']:<8}"
              f"{x['name']:<14}{'・'.join(x['signals'])}")
    json.dump({'version': VERSION, 'source_days': days, 'all': allout, 'entered_20260905': hit},
              open(os.path.join(D, 'jisou_20260905.json'), 'w'), ensure_ascii=False, indent=1)

if __name__ == "__main__":
    main()
