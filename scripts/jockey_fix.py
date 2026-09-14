# -*- coding: utf-8 -*-
# 入力の所在(このリポジトリ外):
#   DE260912.CSV = 2026-09-11 に添付受領した 9/12 出走表 (CP932・316行33列・ヘッダなし・騎手名は4文字切り詰め)
#   マイトバス.xlsx / ウルトラ回収率2026.02.22.xlsx = Google Drive より自己取得 (2026-09-11)
#   読み取りのみ。原本を変更していない。
# 父系判定は独立3エージェントの全会一致のみ採用。出所タグ[推:父系]。
# 買い目・最終印・資金配分・最終採用馬・本採用/断念の確定は出さない。
"""騎手照合の修正 + 新馬の前走条件の扱い(検証エージェントの指摘2・9への対応).
指摘9: 出走表の騎手名は4文字で切り詰められており(文字数分布=2/3/4のみ)、
        5文字以上の騎手名(M.デムーロ・C.ルメール)は完全一致で外れる。
        → NFKC正規化した上で prefix 一致に変更。
指摘2: 新馬(前走なし)に前走条件を当てると偽陽性になる。
        → 「前走なし=条件不成立」として除外し、その旨を明記する。
"""
import csv, collections, unicodedata, json
p="/root/.claude/uploads/84a20921-3b38-53dd-8669-b122c897a190/2c3472cb-DE260912.CSV"
rows=[r for r in csv.reader(open(p,encoding='cp932'))]
def nz(s): return unicodedata.normalize('NFKC', s.strip())
RULE_JK={'M.デムーロ':['マストバイR032(中山芝1600外)','ウルトラU056(阪神ダ1800-2000)'],
         'C.ルメール':['ウルトラU016(東京ダ2100)※当日東京不開催'],
         '高杉史麒':['ウルトラU041(京都ダ1400-1800)※当日京都不開催'],
         '藤岡佑介':['マストバイR012(阪神ダ1800)'],
         '北村宏司':['ウルトラU009(東京芝2000)※当日東京不開催']}
print("=== prefix一致での再照合(完全一致で外していた騎手) ===")
for name, rules in RULE_JK.items():
    n=nz(name)
    hits=[r for r in rows if n.startswith(nz(r[10])) and len(nz(r[10]))>=2]
    exact=[r for r in rows if nz(r[10])==n]
    print(f"\n■ 「{name}」 (該当ルール: {', '.join(rules)})")
    print(f"   完全一致 {len(exact)}騎乗 / prefix一致 **{len(hits)}騎乗**")
    for r in hits:
        print(f"      表記「{r[10]}」 {r[1]}{r[2]:>2}R {r[3]:>3}番 {r[7]:<14} {r[8]}{r[9]} {r[5]}{r[6]:>5} {r[4]:<12} 頭数{r[26]}")
    if not hits: print("      → 出走表に該当なし(取りこぼしではない)")

print("\n" + "="*100)
print("=== 新馬に前走条件が当たっていた候補(除外対象) ===")
print("="*100)
fin=json.load(open('match_confirmed.json'))
removed=[]; kept=[]
for x in fin:
    prev=[u for u in x['unknowns'] if u.startswith('前走列未取得')]
    if x['new'] and prev:
        removed.append(x)
    else:
        kept.append(x)
for x in removed:
    print(f"  {x['system']:<6}{x['rule_id']:<6}{x['venue']}{x['r']}R {x['umaban']:>2}番 {x['name']:<14}{x['sex']}{x['age']}  {x['cond']}")
    print(f"        条件={x['cond_text']}")
    print(f"        → **新馬のため前走が存在しない = 条件不成立として除外**")
json.dump(kept, open('match_confirmed2.json','w'), ensure_ascii=False, indent=1, default=str)
c=collections.Counter(x['verdict'] for x in kept)
print(f"\n除外 {len(removed)}件 → 残る候補 {len(kept)}件  内訳={dict(c)}")
