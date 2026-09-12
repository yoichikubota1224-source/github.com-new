# -*- coding: utf-8 -*-
"""前走実測による保留17件の確定/除外。
語義両義: 「前走の着順が5着以下」(R014/R045のみ)は他ルールの「N着以内」と向きが逆。
          両方の読みを併記し、当方では確定しない → 人間確認必須。
"""
import csv, json, collections
SP="/tmp/claude-0/-home-user-github-com-new/84a20921-3b38-53dd-8669-b122c897a190/scratchpad/umb"
E="/root/.claude/uploads/84a20921-3b38-53dd-8669-b122c897a190/2c3472cb-DE260912.CSV"
prev=json.load(open(f'{SP}/prev.json'))
fin=json.load(open(f'{SP}/match_confirmed2.json'))
er={r[32]:r for r in csv.reader(open(E,encoding='cp932'))}
def pkey(v,R,u):
    for k,r in er.items():
        if r[1]==v and int(r[2])==R and int(r[3])==u: return k
    return None
JUDGE={
 ('R042','前走10着以内'): lambda p,h: (p['chaku'] is not None and p['chaku']<=10, f"前走{p['chaku']}着≦10着"),
 ('R043','前走12着以内+別場'): lambda p,h: (p['chaku'] is not None and p['chaku']<=12 and p['venue']!=h['venue'], f"前走{p['chaku']}着≦12着 かつ 前走{p['venue']}≠今回{h['venue']}"),
 ('R044','前走13着以内'): lambda p,h: (p['chaku'] is not None and p['chaku']<=13, f"前走{p['chaku']}着≦13着"),
 ('R033','前走馬体重460kg+'): lambda p,h: (p['bodyweight'] is not None and p['bodyweight']>=460, f"前走馬体重{p['bodyweight']:.0f}kg vs 460kg"),
 ('R041','前走480kg+4角12以内'): lambda p,h: (p['bodyweight'] is not None and p['bodyweight']>=480 and p['corner4'] is not None and p['corner4']<=12, f"前走馬体重{p['bodyweight']:.0f}kg vs 480kg / 4角{p['corner4']}"),
 ('R003','前走9着以内'): lambda p,h: (p['chaku'] is not None and p['chaku']<=9, f"前走{p['chaku']}着≦9着"),
 ('U048','前走10着以内'): lambda p,h: (p['chaku'] is not None and p['chaku']<=10, f"前走{p['chaku']}着≦10着"),
 ('U047','前走480kg+'): lambda p,h: (p['bodyweight'] is not None and p['bodyweight']>=480, f"前走馬体重{p['bodyweight']:.0f}kg vs 480kg"),
 ('U053','前走上り4位以内'): lambda p,h: (p['rank3f'] is not None and p['rank3f']<=4, f"前走上がり3F{p['rank3f']}位≦4位"),
}
AMBIG={'R045':'前走5着以下+4角12以内','R014':'前走5着以下+馬番3-16'}
hits=[]; excl=[]; amb=[]
base=[x for x in fin if x['verdict']=='HIT']
for x in fin:
    if x['verdict']!='PARTIAL_UNKNOWN': continue
    k=pkey(x['venue'],x['r'],x['umaban']); p=prev.get(k)
    rid=x['rule_id']
    if rid in AMBIG:
        # 両読みを評価
        c=p['chaku']
        ok_min = c is not None and c>=5     # 「5着以下」=5着かそれより下位
        ok_max = c is not None and c<=5     # 「5着以内」
        extra=True; ex=""
        if rid=='R045':
            extra = p['corner4'] is not None and p['corner4']<=12; ex=f"4角{p['corner4']}≦12"
        else:
            extra = 3<=x['umaban']<=16; ex=f"馬番{x['umaban']}∈3-16"
        amb.append((x,p,ok_min and extra, ok_max and extra, f"前走{c}着 / {ex}"))
        continue
    fn=None
    for (r_,lbl),f in JUDGE.items():
        if r_==rid: fn=(f,lbl); break
    if fn is None: continue
    ok,why = fn[0](p,x)
    (hits if ok else excl).append((x,p,why))
print("="*114); print(f"【前走実測による確定 追加 {len(hits)}件】"); print("="*114)
for x,p,why in sorted(hits,key=lambda t:(t[0]['venue'],t[0]['r'],t[0]['umaban'])):
    print(f"  {x['system']:<6}{x['rule_id']:<6}{x['venue']}{x['r']}R {x['umaban']:>2}番 {x['name']:<14}{x['sex']}{x['age']} {x['jockey']:<9} → **確定**  {why}")
print()
print("="*114); print(f"【前走実測による除外 {len(excl)}件】"); print("="*114)
for x,p,why in sorted(excl,key=lambda t:(t[0]['venue'],t[0]['r'],t[0]['umaban'])):
    print(f"  {x['system']:<6}{x['rule_id']:<6}{x['venue']}{x['r']}R {x['umaban']:>2}番 {x['name']:<14} → 除外  {why}")
print()
print("="*114); print(f"【条件文の語義両義により当方では確定しない {len(amb)}件 → 人間確認必須】"); print("="*114)
for x,p,m,M,why in sorted(amb,key=lambda t:(t[0]['venue'],t[0]['r'],t[0]['umaban'])):
    print(f"  {x['system']:<6}{x['rule_id']:<6}{x['venue']}{x['r']}R {x['umaban']:>2}番 {x['name']:<14} {why}")
    print(f"        「5着以下」= 5着かそれより下位 と読む → {'該当' if m else '除外'}")
    print(f"        「5着以内」= 5着まで        と読む → {'該当' if M else '除外'}")
allh=base+[x for x,_,_ in hits]
print()
print("="*114); print(f"【最終確定 {len(allh)}件】"); print("="*114)
for x in sorted(allh,key=lambda y:(y['venue'],y['r'],y['umaban'])):
    t3=float(x['t3']); t3s=f"{t3*100:.1f}%" if t3<1 else f"{t3:.1f}%"
    print(f"  {x['system']:<6}{x['rule_id']:<6}{x['venue']+str(x['r'])+'R':<9}{x['umaban']:>3}番 枠{x['waku']} {x['name']:<15}{x['sex']+str(x['age']):<5}{x['jockey']:<10}{x['sire']:<17}{t3s:>7}")
print()
print("レース別:", dict(collections.Counter(f"{x['venue']}{x['r']}R" for x in allh)))
per=collections.defaultdict(list)
for x in allh: per[(x['venue'],x['r'],x['umaban'],x['name'])].append(f"{x['system']}/{x['rule_id']}")
dbl={k:v for k,v in per.items() if len(v)>1}
print("★二重検出:", {f"{k[0]}{k[1]}R {k[2]}番 {k[3]}":v for k,v in dbl.items()} or "なし")
print("同一レースに該当2頭以上:", {k:v for k,v in collections.Counter(f"{x['venue']}{x['r']}R" for x in allh).items() if v>=2})
json.dump([x for x in allh], open(f'{SP}/final_hits.json','w'), ensure_ascii=False, indent=1, default=str)
