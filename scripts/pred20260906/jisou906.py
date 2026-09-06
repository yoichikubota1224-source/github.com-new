#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑭次走期待好走馬 v1.4（2026-09-06 出走馬版）。

定義: 「次走で期待する馬」なので、判定対象の走りはその馬の**前走（直近走）**に限る。
      9/6 出走馬それぞれの直近走だけを評価する（開催日を横断して古い好走を拾わない）。
判定材料（v1.4）:
  ・前走の確定人気が4人気以下（1〜3人気＝A層は定義上の対象外）
  ・着順1〜3着 / 上がり3F順位（JRA式競走順位＝同値同順位・次を飛ばす）/
    後方一気（1角が下位1/3以降かつ5着以内）/ 勝ち馬から0.3秒以内かつ4着以下
  ・score = 1着+3・2〜3着+2 / 上がり1位+3・2位+2・3位+1 / 後方一気+2 / 僅差+2 / 前走7人気以下+1
  ・層: 確定枠(1〜3着) / 優先高(上がり最速 or 僅差かつ上がり3位以内) / 優先中(上がり3位以内 or 後方一気)
⚠ 「確定枠」は本抽出の分類名であり、好走の確定でも本採用の確定でもない。
⚠ 買い目・点数・資金配分・購入可否・最終印・軸は出さない。障害戦は対象外。
入力: 正本 DE260906.CSV 由来の shutuba_20260906.json ＋ 当方5年DB（前走レースの全着順）
"""
import json, os, sys, glob, collections

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
D = os.path.join(REPO, 'predictions', '20260906')
K = '/tmp/claude-0/-home-user-github-com-new/47c1892c-ddc4-50e4-8b6f-3403a9782673/scratchpad/k5/full'
sys.path.insert(0, os.path.join(REPO, 'scripts', 'pred20260905'))
from jisou import diff_sec, band, score, first_pass

def main():
    S = json.load(open(os.path.join(D, 'shutuba_20260906.json')))
    idx = {}
    for f in glob.glob(os.path.join(K, '*.json')):
        for r in json.load(open(f)): idx[r['race_id']] = r
    out, nomatch, nopast, ajun = [], [], 0, 0
    for rc in S:
        if rc['jump']: continue
        for h in rc['horses']:
            if not h['zen_race_id']:
                nopast += 1
                if h['past_n'] == 0 and not rc['shinba'] and h['de_zen_chaku']:
                    nomatch.append(dict(ba=rc['ba'], r=rc['r'], uma=h['uma'], name=h['name'],
                                        reason='当方5年DBに履歴なし（地方・海外の可能性）。DE前走列では'
                                               f"{h['de_zen_kan']}週前{h['de_zen_ninki']}人気{h['de_zen_chaku']}着＝[推:列同定]"))
                continue
            race = idx.get(h['zen_race_id'])
            if race is None:
                nomatch.append(dict(ba=rc['ba'], r=rc['r'], uma=h['uma'], name=h['name'],
                                    zen=h['zen_race_id'], reason='前走レースを当方DBで解析できず')); continue
            if race.get('jump'): continue
            fin = [x for x in race['horses'] if x.get('chaku')]
            me = next((x for x in race['horses'] if x.get('horse_id') == h['horse_id']), None)
            if me is None or me.get('chaku') is None:
                nomatch.append(dict(ba=rc['ba'], r=rc['r'], uma=h['uma'], name=h['name'],
                                    zen=h['zen_race_id'], reason='前走が競走中止・除外で着順なし')); continue
            allv = [x['last3f'] for x in fin if x.get('last3f') is not None]
            rk = {v: 1 + sum(1 for y in allv if y < v) for v in set(allv)}   # JRA式競走順位
            fs = sorted(fin, key=lambda x: x['chaku'])
            cum = {}; acc = 0.0; ok = True
            for x in fs:
                if x['chaku'] == 1: cum[x['uma']] = 0.0; continue
                dv = diff_sec(x.get('diff'))
                if dv is None: ok = False; break
                acc += dv; cum[x['uma']] = acc
            n = len(fin); l3 = rk.get(me.get('last3f')); p1 = first_pass(me.get('passing'))
            dwin = cum.get(me['uma']) if ok else None
            b = band(me.get('pop'))
            if b in (None, 'A'):
                ajun += 1; continue                      # 前走1〜3人気は定義上の対象外
            sig = []
            if me['chaku'] <= 3: sig.append(f"{me['chaku']}着")
            if l3 == 1: sig.append('上がり最速')
            elif l3 and l3 <= 3: sig.append(f'上がり{l3}位')
            back_run = bool(p1 and n >= 8 and p1 >= n * 2 / 3 and me['chaku'] <= 5)
            if back_run: sig.append(f"1角{p1}番手から{me['chaku']}着")
            close_win = bool(dwin is not None and 0 < dwin <= 0.3 and me['chaku'] >= 4)
            if close_win: sig.append(f'勝ち馬から{dwin:.2f}秒')
            if not sig: continue
            sc = score(me['chaku'], l3, back_run, close_win, me.get('pop'))
            if me['chaku'] <= 3: tier = '確定枠'
            elif (l3 == 1) or (dwin is not None and dwin <= 0.3 and l3 and l3 <= 3): tier = '優先高'
            elif (l3 and l3 <= 3) or back_run: tier = '優先中'
            else: continue
            out.append(dict(ba=rc['ba'], r=rc['r'], race=rc['cls'], course=f"{rc['td']}{rc['dist']}",
                n_entry=rc['n_entry'], waku=h['waku'], uma=h['uma'], name=h['name'], horse_id=h['horse_id'],
                jockey=h['jockey'], sire=h['sire'], sex=h['sex'], age=h['age'], belong=h['belong'],
                naka=(h['weeks'] - 1 if h['weeks'] else None),
                zen_date=h['zen_date'], zen_ba=h['zen_ba'], zen_course=f"{h['zen_td']}{h['zen_dist']}",
                zen_cls=h['zen_cls'], zen_n=n, zen_pop=me.get('pop'), zen_chaku=me['chaku'],
                zen_l3=me.get('last3f'), zen_l3rank=l3, zen_passing=me.get('passing'),
                zen_diff_win=dwin, band=b, tier=tier, score=sc, signals=sig))
    out.sort(key=lambda x: (-x['score'], x['ba'], x['r'], x['uma']))
    print(f'[実] 9/6 平地35R・484頭（中山1R障害7頭は対象外）')
    print(f'[実] 抽出 {len(out)}頭 / 前走なし(新馬・履歴なし) {nopast}頭 / 前走1〜3人気で対象外 {ajun}頭 / 前走を照合できず {len(nomatch)}頭＝[不足]')
    t = collections.Counter((x['tier'], x['band']) for x in out)
    print('\n■ 層 × 帯（帯は前走の確定人気）')
    print(f"  {'':<8}{'B層(4〜6人気)':>15}{'C層(7〜12人気)':>15}{'D層(13〜)':>13}{'計':>7}")
    for tier in ('確定枠', '優先高', '優先中'):
        row = [t[(tier, b)] for b in 'BCD']
        print(f'  {tier:<8}{row[0]:>15}{row[1]:>15}{row[2]:>13}{sum(row):>7}')
    print(f'\n■ 全{len(out)}頭（score降順）')
    for x in out:
        print(f"{x['score']:>3} {x['tier']:<4}{x['band']:<2}{x['ba']}{x['r']:>2}R{x['uma']:>3}番 {x['course']:<7}"
              f"{x['name']:<13}{x['zen_date'][4:6]}/{x['zen_date'][6:]}{x['zen_ba']}{x['zen_course']:<7}"
              f"{x['zen_pop']:>2}人{x['zen_chaku']:>2}着 中{x['naka'] if x['naka'] is not None else '—'}週 {'・'.join(x['signals'])}")
    if nomatch:
        print(f'\n■ [不足] 前走を照合できなかった {len(nomatch)}頭')
        for m in nomatch: print('   ', m['ba'], f"{m['r']}R", f"{m['uma']}番", m['name'], '—', m['reason'])
    json.dump({'version': 'jisou_v1.4_20260906', 'raceday': '20260906', 'hits': out,
               'unmatched': nomatch, 'no_past': nopast, 'excluded_A': ajun},
              open(os.path.join(D, 'jisou906.json'), 'w'), ensure_ascii=False, indent=1)

main()
