#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑭次走期待好走馬（2026-09-05 出走馬版）。

⚠ 定義の精密化: 「次走期待」は次走で期待する馬なので、判定対象の走りは
   その馬の **前走（直近走）** でなければならない。開催日を横断して拾うと
   「7月に好走したがその後8月に凡走した馬」まで入り、古い信号が残る。
   本実装は 9/5 出走馬それぞれの past[0]（＝前走）だけを評価する。

⚠ jisou_v1.2 からの訂正: netkeiba の着差列は「前の馬との着差」であり
   「勝ち馬からの差」ではない。1着からの累積で計算し直した（v1.3）。
"""
import json, re, os, sys, collections

D = os.path.dirname(os.path.abspath(__file__))
K = '/tmp/claude-0/-home-user-github-com-new/47c1892c-ddc4-50e4-8b6f-3403a9782673/scratchpad/k5/full'
sys.path.insert(0, D)
from jisou import diff_sec, band, score, first_pass

def load_index():
    import glob
    idx = {}
    for f in glob.glob(os.path.join(K, '*.json')):
        for r in json.load(open(f)): idx[r['race_id']] = r
    return idx

def eval_past(p, race):
    """前走 p（出馬表側）と、その前走レースの全結果 race から判定材料を作る。"""
    if race is None: return None
    fin = [h for h in race['horses'] if h.get('chaku')]
    if not fin: return None
    vals = sorted({h['last3f'] for h in fin if h.get('last3f') is not None})
    rk = {v: i + 1 for i, v in enumerate(vals)}
    fin = sorted(fin, key=lambda h: h['chaku'])
    cum = {}; acc = 0.0; ok = True
    for h in fin:
        if h['chaku'] == 1: cum[h['uma']] = 0.0; continue
        d = diff_sec(h.get('diff'))
        if d is None: ok = False; break
        acc += d; cum[h['uma']] = acc
    me = next((h for h in fin if h['uma'] == p.get('uma')), None)
    if me is None:
        # 完走馬に居ない = その前走で競走中止/除外だった（出馬表側も chaku=null で一致）
        allh = next((h for h in race['horses'] if h['uma'] == p.get('uma')), None)
        return {'__abort__': True, 'found': allh is not None}
    n = len(fin)
    l3 = rk.get(me.get('last3f'))
    p1 = first_pass(me.get('passing'))
    dwin = cum.get(me['uma']) if ok else None
    return dict(n=n, chaku=me['chaku'], pop=me.get('pop'), last3f=me.get('last3f'),
                l3_rank=l3, passing=me.get('passing'), p1=p1, diff_from_win=dwin,
                jump=race.get('jump'), title=race.get('title'), meta=race.get('meta', '')[:32])

def main():
    S = json.load(open(os.path.join(D, 'shutuba_20260905.json')))
    idx = load_index()
    out, nomatch, nopast = [], [], 0
    for r in S:
        if r['jump']: continue
        for h in r['horses']:
            if not h['past']: nopast += 1; continue
            p = h['past'][0]
            race = idx.get(p.get('race_id'))
            if race is None:
                nomatch.append(dict(ba=r['ba'], r=r['r'], uma=h['uma'], name=h['name'],
                                    zen=p.get('race_id'), zen_ba=p.get('ba'), reason='前走が当方5年データ外(地方/海外)'))
                continue
            e = eval_past(p, race)
            if e is None:
                nomatch.append(dict(ba=r['ba'], r=r['r'], uma=h['uma'], name=h['name'],
                                    zen=p.get('race_id'), reason='前走レースを解析できず'))
                continue
            if e.get('__abort__'):
                nomatch.append(dict(ba=r['ba'], r=r['r'], uma=h['uma'], name=h['name'],
                                    zen=p.get('race_id'), zen_ba=p.get('ba'),
                                    reason='前走が競走中止・除外で着順なし(出馬表と5年データの双方で一致)'))
                continue
            if e['jump']: continue
            b = band(e['pop'])
            if b in (None, 'A'): continue          # 前走1〜3人気は対象外(定義)
            sig = []
            if e['chaku'] <= 3: sig.append(f"{e['chaku']}着")
            if e['l3_rank'] == 1: sig.append('上がり最速')
            elif e['l3_rank'] and e['l3_rank'] <= 3: sig.append(f"上がり{e['l3_rank']}位")
            back_run = bool(e['p1'] and e['n'] >= 8 and e['p1'] >= e['n']*2/3 and e['chaku'] <= 5)
            if back_run: sig.append(f"1角{e['p1']}番手から{e['chaku']}着")
            close_win = bool(e['diff_from_win'] is not None and 0 < e['diff_from_win'] <= 0.3 and e['chaku'] >= 4)
            if close_win: sig.append(f"勝ち馬から{e['diff_from_win']:.2f}秒")
            if not sig: continue
            sc = score(e['chaku'], e['l3_rank'], back_run, close_win, e['pop'])
            if e['chaku'] <= 3: tier = '確定枠'
            elif (e['l3_rank'] == 1) or (e['diff_from_win'] is not None and e['diff_from_win'] <= 0.3
                                         and e['l3_rank'] and e['l3_rank'] <= 3): tier = '優先高'
            elif (e['l3_rank'] and e['l3_rank'] <= 3) or back_run: tier = '優先中'
            else: continue
            out.append(dict(ba=r['ba'], r=r['r'], race=r['title'], course=f"{r['td']}{r['dist']}",
                n_entry=r['n_entry'], waku=h['waku'], uma=h['uma'], name=h['name'],
                horse_id=h['horse_id'], jockey=h['jockey'], sire=h['sire'], sex=h['sex'], age=h['age'],
                rotation=h.get('rotation'), kyakushitsu=h.get('kyakushitsu'),
                zen_date=p.get('date'), zen_ba=p.get('ba'), zen_course=f"{p.get('td')}{p.get('dist')}",
                zen_n=e['n'], zen_pop=e['pop'], zen_chaku=e['chaku'], zen_l3=e['last3f'],
                zen_l3rank=e['l3_rank'], zen_passing=e['passing'], zen_diff_win=e['diff_from_win'],
                band=b, tier=tier, score=sc, signals=sig))
    out.sort(key=lambda x: (-x['score'], x['ba'], x['r'], x['uma']))
    ORD = {'確定枠':0,'優先高':1,'優先中':2}
    print(f'[実] 9/5 平地35R・447頭のうち、前走が評価できた馬から抽出')
    print(f'[実] 抽出 {len(out)}頭 / 前走なし(新馬・未出走) {nopast}頭 / 前走を照合できず {len(nomatch)}頭＝[不足]')
    t = collections.Counter((x['tier'], x['band']) for x in out)
    print(f"\n■ 層 × 帯（帯は前走の確定人気）")
    print(f"  {'':<8}{'B層(4〜6人気)':>16}{'C層(7〜12人気)':>16}{'D層(13〜)':>14}{'計':>8}")
    for tier in ('確定枠','優先高','優先中'):
        row=[t[(tier,b)] for b in 'BCD']
        print(f"  {tier:<8}{row[0]:>16}{row[1]:>16}{row[2]:>14}{sum(row):>8}")
    print(f"\n■ 全{len(out)}頭（score降順）")
    print(f"{'sc':>3} {'層':<5}{'帯':<3}{'9/5':<20}{'馬名':<15}{'前走':<22}{'根拠'}")
    for x in out:
        print(f"{x['score']:>3} {x['tier']:<5}{x['band']:<3}"
              f"{x['ba']}{x['r']:>2}R{x['uma']:>3}番 {x['course']:<8}"
              f"{x['name']:<15}"
              f"{x['zen_date'][5:]}{x['zen_ba']}{x['zen_pop']:>3}人{x['zen_chaku']:>2}着 "
              f"{'・'.join(x['signals'])}")
    if nomatch:
        print(f"\n■ [不足] 前走を照合できなかった {len(nomatch)}頭")
        for m in nomatch: print('   ', m)
    json.dump({'version':'jisou_v1.3_20260905','hits':out,'unmatched':nomatch,'no_past':nopast},
              open(os.path.join(D,'jisou905.json'),'w'), ensure_ascii=False, indent=1)

main()
