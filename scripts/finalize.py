# -*- coding: utf-8 -*-
# 入力の所在(このリポジトリ外):
#   DE260912.CSV = 2026-09-11 に添付受領した 9/12 出走表 (CP932・316行33列・ヘッダなし・騎手名は4文字切り詰め)
#   マイトバス.xlsx / ウルトラ回収率2026.02.22.xlsx = Google Drive より自己取得 (2026-09-11)
#   読み取りのみ。原本を変更していない。
# 父系判定は独立3エージェントの全会一致のみ採用。出所タグ[推:父系]。
# 買い目・最終印・資金配分・最終採用馬・本採用/断念の確定は出さない。
"""父系判定 + 減量導出 を統合した最終集計."""
import json, collections
final=json.load(open('match_final.json'))
wa=json.load(open('weight_allow.json'))
key={ (x['venue'],x['r'],x['umaban']): x for x in wa.values() }
out=[]
for x in final:
    un=[u for u in x['unknowns'] if '減量記号' not in u]
    if len(un)!=len(x['unknowns']):
        w=key.get((x['venue'],x['r'],x['umaban']))
        if w is None or w['deduction'] is None:
            un.append("減量: 記号列なし・斤量からも導出不可")
        elif w['deduction']==0:
            x=dict(x); x['reasons']=x['reasons']+[f"減量なし[推:斤量差] 斤量{w['kin']}=基準{w['base']}"]
            un.append(f"減量なしと導出[推:斤量差] 斤量{w['kin']}=基準{w['base']}kg")
        else:
            continue   # 減量ありのため条件を満たさない → 除外
        x=dict(x)
    y=dict(x); y['unknowns']=un
    hard=[u for u in un if u.startswith('前走列未取得') or '導出不可' in u]
    y['verdict']='HIT' if not hard else 'PARTIAL_UNKNOWN'
    out.append(y)
json.dump(out, open('match_confirmed.json','w'), ensure_ascii=False, indent=1, default=str)
c=collections.Counter(x['verdict'] for x in out)
print(f"最終候補 {len(out)}件  内訳={dict(c)}")
hits=[x for x in out if x['verdict']=='HIT']
print()
print("="*120)
print(f"【最終確定】ウルトラ・マストバイ該当馬  {len(hits)}件")
print("="*120)
print(f"{'系':<7}{'ID':<6}{'レース':<10}{'馬番':>4}{'枠':>3} {'馬名':<16}{'性齢':<6}{'騎手':<10}{'父':<18}{'3着内':>7}{'複回':>7}")
for x in sorted(hits,key=lambda y:(y['venue'],y['r'],y['umaban'])):
    t3=float(x['t3']); t3s=f"{t3*100:.1f}%" if t3<1 else f"{t3:.1f}%"
    fk=float(x.get('fuku') or 0); fks=f"{fk:.2f}" if fk<10 else f"{fk/100:.2f}"
    print(f"{x['system']:<7}{x['rule_id']:<6}{x['venue']+str(x['r'])+'R':<10}{x['umaban']:>4}{x['waku']:>3} {x['name']:<16}{x['sex']+str(x['age']):<6}{x['jockey']:<10}{x['sire']:<18}{t3s:>7}{fks:>7}")
    print(f"        適用={x['sd']}{x['dist']}{x['io'] or ''} / {x['target']} / {x['cond_text']}")
    for r in x['reasons']: print(f"        ・{r}")
print()
byr=collections.Counter(f"{x['venue']}{x['r']}R" for x in hits)
print("レース別の確定件数:", dict(byr))
# 二重検出
per=collections.defaultdict(list)
for x in hits: per[(x['venue'],x['r'],x['umaban'],x['name'])].append(f"{x['system']}/{x['rule_id']}")
dbl={k:v for k,v in per.items() if len(v)>1}
print("二重検出(同一馬が複数条件に該当):", {f"{k[0]}{k[1]}R {k[2]}番 {k[3]}":v for k,v in dbl.items()} or "なし")
