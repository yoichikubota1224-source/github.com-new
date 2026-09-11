# -*- coding: utf-8 -*-
"""前走8項目の結合。完全性検査の最重要指摘への対応。
供給源: 荒れ傾向分析_全レース全頭_20250907-20260906.csv (48,274行・既に受領済)
        → 送付依頼は不要だった。当方の見落としを訂正する。
前走 = 2026-09-12 より前の最新出走。前走上がり3F順位は同一レース内の秒のランク。
前走行が引けない馬(新馬・収録窓外)は「判定不能」ではなく区別して記録する。
"""
import csv, collections, json
E="/root/.claude/uploads/84a20921-3b38-53dd-8669-b122c897a190/2c3472cb-DE260912.CSV"
H="/tmp/claude-0/-home-user-github-com-new/84a20921-3b38-53dd-8669-b122c897a190/scratchpad/zx/c/荒れ傾向分析_全レース全頭_20250907-20260906.csv"
def fl(v):
    v=(v or '').strip()
    if v=='': return None
    try: return float(v)
    except: return None
# レース単位で上がり3F順位を作る
byrace=collections.defaultdict(list)
rows=[]
for r in csv.DictReader(open(H,encoding='utf-8-sig')):
    rows.append(r); byrace[r['racekey']].append(r)
rank3f={}
for rk,hs in byrace.items():
    vs=[(fl(h['上がり3F_秒']), h) for h in hs]
    kn=sorted([(v,h) for v,h in vs if v is not None], key=lambda t:t[0])
    for i,(v,h) in enumerate(kn,1):
        rank3f[(rk,h['馬番'])]=i
def lastcorner(h):
    last=None
    for c in ['通過順1','通過順2','通過順3','通過順4']:
        v=fl(h[c])
        if v is not None: last=v
    return last
hist=collections.defaultdict(list)
for r in rows: hist[r['馬名'].strip()].append(r)
for k in hist: hist[k].sort(key=lambda r:r['日付'])
TODAY='2026-09-12'
def dnum(d): return int(d[:4])*10000+int(d[5:7])*100+int(d[8:10])
def daydiff(a,b):
    import datetime
    da=datetime.date(int(a[:4]),int(a[5:7]),int(a[8:10]))
    db=datetime.date(int(b[:4]),int(b[5:7]),int(b[8:10]))
    return (db-da).days
prev={}
er=[r for r in csv.reader(open(E,encoding='cp932'))]
stat=collections.Counter()
for r in er:
    nm=r[7].strip(); key=r[32]
    hs=[h for h in hist.get(nm,[]) if h['日付']<TODAY]
    if not hs:
        prev[key]=dict(found=False, reason='新馬' if r[4].strip().startswith('新馬') else '収録窓外または地方/海外帰り')
        stat['前走なし' if r[4].strip().startswith('新馬') else '前走引けず']+=1
        continue
    h=hs[-1]
    rk=h['racekey']
    try: chaku=int(h['着順'])
    except: chaku=None
    prev[key]=dict(found=True, date=h['日付'], venue=h['開催場'], dist=int(float(h['距離_m'])),
                   sd=h['芝ダ障'], chaku=chaku, corner4=lastcorner(h), field=int(float(h['出走頭数'])),
                   bodyweight=fl(h['馬体重_kg']), rank3f=rank3f.get((rk,h['馬番'])),
                   weeks=daydiff(h['日付'],TODAY)/7.0, ninki=fl(h['人気']))
    stat['前走あり']+=1
json.dump(prev, open('prev.json','w'), ensure_ascii=False, indent=1, default=str)
print(f"前走結合: {dict(stat)}")
# 保留17件の前走を表示
fin=json.load(open('match_confirmed2.json'))
pu=[x for x in fin if x['verdict']=='PARTIAL_UNKNOWN']
print(f"\n=== 保留候補 {len(pu)}件の前走実測 ===")
ek={r[32]:r for r in er}
for x in sorted(pu,key=lambda y:(y['venue'],y['r'],y['umaban'])):
    k=[kk for kk,r in ek.items() if r[1]==x['venue'] and int(r[2])==x['r'] and int(r[3])==x['umaban']]
    p=prev.get(k[0]) if k else None
    if not p or not p['found']:
        print(f"  {x['system']:<6}{x['rule_id']:<6}{x['venue']}{x['r']}R {x['umaban']:>2}番 {x['name']:<14} → 前走引けず({p['reason'] if p else '不明'})")
        continue
    bw = f"{p['bodyweight']:.0f}kg" if p['bodyweight'] else "計不"
    print(f"  {x['system']:<6}{x['rule_id']:<6}{x['venue']}{x['r']}R {x['umaban']:>2}番 {x['name']:<14} 前走={p['date']} {p['venue']}{p['sd']}{p['dist']} {p['chaku']}着 4角{p['corner4']} 上り{p['rank3f']}位 {p['field']}頭 {bw} 中{p['weeks']:.0f}週")
