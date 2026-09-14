# -*- coding: utf-8 -*-
# 入力の所在(このリポジトリ外):
#   DE260912.CSV = 2026-09-11 に添付受領した 9/12 出走表 (CP932・316行33列・ヘッダなし)
#   マイトバス.xlsx / ウルトラ回収率2026.02.22.xlsx = Google Drive より自己取得 (2026-09-11)
#   競馬場コース事典2_コース構造_101.csv = 2026-09-10 添付受領分 (jra_official_course_verified=NO / [実:提供値])
#   いずれも読み取りのみ。原本を変更していない。
#
# 出力の位置づけ: 救済レイヤーの材料整理。買い目・最終印・資金配分・最終採用馬は出さない。
#   未取得を0や推定値で埋めない。前走情報は出走表に列が無いため該当条件は[条件未確定]とする。
"""減量(負担重量の軽減)の導出.
出走表に減量記号(☆★▲△)の列が無いため、同一レース内の斤量分布から基準斤量を読み取り、
基準との差で減量を導出する。出所タグ = [推:斤量差]。記号そのものは未取得のまま。
定量戦(同性の斤量が単一値に集中する条件)でのみ導出し、ハンデ戦・別定戦では導出しない。
"""
import csv, collections, json
p="/root/.claude/uploads/84a20921-3b38-53dd-8669-b122c897a190/2c3472cb-DE260912.CSV"
rows=[r for r in csv.reader(open(p,encoding='cp932'))]
races=collections.defaultdict(list)
for r in rows:
    if '障害' in r[4]: continue
    races[(r[1],int(r[2]))].append(r)

def derive(hs):
    """性別ごとの基準斤量(最多値)と、各馬の減量kgを返す。
       定量判定: ある性で最多値の占有率が50%以上かつ2頭以上"""
    bysex=collections.defaultdict(list)
    for r in hs: bysex[r[8]].append(float(r[11]))
    base={}
    for sx,ws in bysex.items():
        c=collections.Counter(ws)
        top,cnt=c.most_common(1)[0]
        base[sx]=(top, cnt, len(ws), cnt/len(ws))
    return base

out={}
for k,hs in sorted(races.items()):
    base=derive(hs)
    cond=hs[0][4]
    handi = 'Ｈ' in cond or 'H' in cond
    for r in hs:
        sx=r[8]; w=float(r[11])
        b,cnt,n,ratio = base[sx]
        if handi or ratio<0.5 or cnt<2:
            ded=None; tag='導出不可(ハンデ/別定または分布が単一でない)'
        else:
            ded=round(b-w,1); tag=f'基準{b}kg(同性{cnt}/{n}頭)'
        out[r[32]]=dict(venue=k[0], r=k[1], umaban=int(r[3]), name=r[7], sex=sx, age=r[9],
                        kin=w, base=b, deduction=ded, tag=tag, cond=cond, jockey=r[10])
json.dump(out, open('weight_allow.json','w'), ensure_ascii=False, indent=1)
tgt=[('中山',3,6),('中山',4,7)]
print("=== 減量導出: WeightAllowanceEq 条件の該当2頭 ===")
for v,R,u in tgt:
    for kk,x in out.items():
        if (x['venue'],x['r'],x['umaban'])==(v,R,u):
            verdict = '減量なし(条件を満たす)' if x['deduction']==0 else (f"減量{x['deduction']}kgあり(条件を満たさない)" if x['deduction'] is not None else '導出不可')
            print(f"  {v}{R}R {u}番 {x['name']}  {x['sex']}{x['age']}  斤量{x['kin']} / {x['tag']}  → **{verdict}**  騎手={x['jockey']}")
print()
c=collections.Counter('導出可' if x['deduction'] is not None else '導出不可' for x in out.values())
print(f"全308頭の導出可否: {dict(c)}")
d=collections.Counter(x['deduction'] for x in out.values() if x['deduction'] is not None)
print(f"減量kgの分布: {dict(sorted(d.items(), key=lambda t:t[0]))}")
