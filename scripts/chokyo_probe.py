#!/usr/bin/env python3
# 追加検査2件:
#  (A) STRIDEの「調教指数」は本当に調教を測っているのか、それとも人気の言い換えか
#  (B) 坂路/ウッドCSVに載らない329頭は誰か(選択バイアスの点検)
import json, os, math, collections
import os
# 中間成果物の置き場。作業領域が変わる場合は CHOKYO_WORK で上書きする。
WORK = os.environ.get("CHOKYO_WORK", "/tmp/claude-0/-home-user-github-com-new/47c1892c-ddc4-50e4-8b6f-3403a9782673/scratchpad/rev")
os.makedirs(WORK, exist_ok=True)
SC = WORK
STRIDE = os.environ.get('CHOKYO_STRIDE', '/tmp/claude-0/-home-user-github-com-new/47c1892c-ddc4-50e4-8b6f-3403a9782673/scratchpad/chokyo/joined.json')
old = json.load(open(STRIDE))
new = json.load(open(f'{SC}/joined_z.json'))
zk = {(x['day'], x['venue'], x['r'], x['name']) for x in new}

print('=== (A) STRIDE調教指数の3分割ごとの人気分布 ===')
rank = [x for x in old if x.get('ck_frac')]
for lab, f in [('上位1/3', lambda x: x['ck_frac'] <= 1/3),
               ('中位1/3', lambda x: 1/3 < x['ck_frac'] <= 2/3),
               ('下位1/3', lambda x: x['ck_frac'] > 2/3)]:
    sub = [x for x in rank if f(x) and x.get('pop')]
    n = len(sub)
    mp = sum(x['pop'] for x in sub) / n
    b = collections.Counter('1-3' if x['pop'] <= 3 else '4-6' if x['pop'] <= 6 else '7-12' if x['pop'] <= 12 else '13-' for x in sub)
    dist = ' '.join(f'{k}:{100*b[k]/n:4.1f}%' for k in ('1-3', '4-6', '7-12', '13-'))
    print(f'  {lab}  n={n:>4}  平均人気 {mp:4.1f}   {dist}')

print('\n  → 同じ人気帯の中だけで調教指数を切ると、識別は残るか')
for band, f in [('1〜3人気', lambda p: p <= 3), ('4〜6人気', lambda p: 4 <= p <= 6), ('7〜12人気', lambda p: 7 <= p <= 12)]:
    sub = [x for x in rank if x.get('pop') and f(x['pop'])]
    up = [x for x in sub if x['ck_frac'] <= 1/3]; lo = [x for x in sub if x['ck_frac'] > 2/3]
    def k3(v): return sum(1 for x in v if x['chaku'] <= 3)
    print(f'    {band}: 上位1/3 {k3(up)}/{len(up)}={100*k3(up)/max(1,len(up)):.1f}%  '
          f'下位1/3 {k3(lo)}/{len(lo)}={100*k3(lo)/max(1,len(lo)):.1f}%')

print('\n=== (B) 坂路/ウッドCSVに追切が無かった馬は誰か ===')
miss = [x for x in old if (x['day'], x['venue'], x['r'], x['name']) not in zk]
have = [x for x in old if (x['day'], x['venue'], x['r'], x['name']) in zk]
print(f'  無し {len(miss)}頭 / 有り {len(have)}頭  (STRIDE側 {len(old)}頭)')
for lab, v in [('追切データ有り', have), ('追切データ無し', miss)]:
    n = len(v); p = [x for x in v if x.get('pop')]
    k3 = sum(1 for x in v if x['chaku'] <= 3)
    roi = sum(x['odds'] for x in v if x['chaku'] == 1) / n * 100
    print(f'  {lab}: n={n:>4}  平均人気 {sum(x["pop"] for x in p)/len(p):4.1f}  '
          f'3着内 {100*k3/n:4.1f}%  単回収 {roi:5.1f}%')
c = collections.Counter(x.get('pattern') or '[不足]' for x in miss)
print('  無し側の調教パターン上位:', c.most_common(6))
