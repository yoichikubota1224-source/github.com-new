# -*- coding: utf-8 -*-
# 入力の所在(このリポジトリ外):
#   DE260912.CSV = 2026-09-11 に添付受領した 9/12 出走表 (CP932・316行33列・ヘッダなし・騎手名は4文字切り詰め)
#   マイトバス.xlsx / ウルトラ回収率2026.02.22.xlsx = Google Drive より自己取得 (2026-09-11)
#   読み取りのみ。原本を変更していない。
# 父系判定は独立3エージェントの全会一致のみ採用。出所タグ[推:父系]。
# 買い目・最終印・資金配分・最終採用馬・本採用/断念の確定は出さない。
"""父系判定(独立3エージェントの全会一致)を照合結果に適用し最終集計を出す.
YES合意: ロベルト系={エピファネイア,モーリス,ルヴァンスレーヴ} / グラスワンダー系={モーリス}
         ディープインパクト系={シルバーステート} / エーピーインディ系={} (該当0)
いずれも「その種牡馬自身の父」の記載が血統事実として検算を通ったもののみ採用。
ルール表作成者の系統定義は未提供のため、判定は一般的な父系分類に基づく推定 → 出所タグ[推:父系]。
"""
import json, collections
YES={'ロベルト系':{'エピファネイア','モーリス','ルヴァンスレーヴ'},
     'グラスワンダー系':{'モーリス'},
     'ディープインパクト系':{'シルバーステート'},
     'エーピーインディ系':set()}
mb=json.load(open('match_mb.json')); ul=json.load(open('match_ultra.json'))
final=[]
for x in mb+ul:
    sl=[u.split(':',1)[1] for u in x['unknowns'] if u.startswith('SIRE_LINE:')]
    if not sl:
        final.append(x); continue
    line=sl[0]
    if x['sire'] in YES[line]:
        rest=[u for u in x['unknowns'] if not u.startswith('SIRE_LINE:')]
        y=dict(x); y['unknowns']=rest+[f"父系判定[推:父系]={line}に該当(3/3全会一致)"]
        y['verdict']='HIT' if not rest else 'PARTIAL_UNKNOWN'
        y['reasons']=x['reasons']+[f"父系{line}に該当(独立3判定の全会一致)"]
        final.append(y)
    # YESでなければ除外(NO)
json.dump(final, open('match_final.json','w'), ensure_ascii=False, indent=1, default=str)
c=collections.Counter(x['verdict'] for x in final)
print(f"父系判定適用後の候補 = {len(final)}件  内訳={dict(c)}")
print(f"  (父系判定で除外 = {len(mb+ul)-len(final)}件)")
print()
print("="*118)
print("【最終】確定該当 (判定可能な全条件を満たす)")
print("="*118)
hits=[x for x in final if x['verdict']=='HIT']
print(f"{'系':<7}{'ID':<6}{'レース':<9}{'馬番':>4}{'枠':>3} {'馬名':<15}{'性齢':<6}{'騎手':<10}{'父':<18}{'3着内':>7}")
for x in sorted(hits,key=lambda y:(y['venue'],y['r'],y['umaban'])):
    t3=float(x['t3']); t3s=f"{t3*100:.1f}%" if t3<1 else f"{t3:.1f}%"
    print(f"{x['system']:<7}{x['rule_id']:<6}{x['venue']+str(x['r'])+'R':<9}{x['umaban']:>4}{x['waku']:>3} {x['name']:<15}{x['sex']+str(x['age']):<6}{x['jockey']:<10}{x['sire']:<18}{t3s:>7}")
    extra=[u for u in x['unknowns'] if u.startswith('父系判定')]
    if extra: print(f"        └ {extra[0]}")
print()
print("="*118)
print("【最終】前走列未取得のみが残る候補 (父系・現況条件は確定済)")
print("="*118)
pu=[x for x in final if x['verdict']=='PARTIAL_UNKNOWN']
for x in sorted(pu,key=lambda y:(y['venue'],y['r'],y['umaban'])):
    sire_ok = any(u.startswith('父系判定') for u in x['unknowns'])
    print(f"  {x['system']:<6}{x['rule_id']:<6}{x['venue']+str(x['r'])+'R':<9}{x['umaban']:>3}番 {x['name']:<14}{x['sex']+str(x['age']):<5}{x['jockey']:<9}父={x['sire']:<16}{'[新馬]' if x['new'] else ''}{'  ★父系確定' if sire_ok else ''}")
    print(f"        条件={x['cond_text']}")
    print(f"        未確定={' / '.join(u for u in x['unknowns'] if not u.startswith('父系判定'))}")
