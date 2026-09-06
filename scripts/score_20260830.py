#!/usr/bin/env python3
"""8/30 確定結果による採点。荒れの定義は8/23第7報を踏襲。"""
import json, os, math, collections
SP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P  = os.path.join(SP, 'predictions', '20260830')
R  = json.load(open(os.path.join(P, 'results_20260830.json')))
F  = json.load(open(os.path.join(P, '最終統合_20260830.json')))
V  = {'01':'札幌','04':'新潟','07':'中京'}

res = {}
for r in R:
    res[f"{r['venue']}{r['r']}R"] = {h['umaban']: h for h in r['horses']}
sup, meta = {}, {}
for rc in F:
    race = f"{V[rc['racekey'][:2]]}{rc['r']}R"
    meta[race] = rc
    for h in rc['horses']:
        sup[(race, h['uma'])] = h

def wilson(k, n, z=1.96):
    if n == 0: return (0.0, 0.0)
    p = k/n; d = 1+z*z/n; c = p+z*z/(2*n)
    m = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))
    return ((c-m)/d*100, (c+m)/d*100)

def rate(sel, lab):
    s = [x for x in sel if x[0]]
    if not s:
        print(f'  {lab:<30s} n=0'); return
    w  = sum(1 for x in s if x[0] == 1)
    f3 = sum(1 for x in s if x[0] <= 3)
    tan = sum(x[1]*100 for x in s if x[0] == 1 and x[1])
    lo, hi = wilson(f3, len(s))
    print(f'  {lab:<30s} n={len(s):3d}  勝率{w/len(s)*100:5.1f}%  複勝率{f3/len(s)*100:5.1f}% '
          f'CI[{lo:4.1f},{hi:4.1f}]  仮定単回{tan/(len(s)*100)*100:6.1f}%')

# ---- 荒れ判定 ----
A = {}
for r in R:
    race = f"{r['venue']}{r['r']}R"
    fin = sorted([h for h in r['horses'] if h['chakujun']], key=lambda h: h['chakujun'])
    w = fin[0]; t3 = [h['pop'] for h in fin[:3] if h['pop']]
    s3 = sum(t3) if len(t3) == 3 else None
    A[race] = {'ar': (w['pop'] and w['pop'] >= 5) or (s3 and s3 >= 18),
               'wp': w['pop'], 's3': s3, 'wn': w['name'], 'wo': w['odds'], 'wu': w['umaban']}
na = sum(1 for v in A.values() if v['ar'])
print(f'■ 荒れ判定: {na}/35R = {na/35*100:.1f}%  CI{[round(x,1) for x in wilson(na,35)]}')

# ---- 全馬プール ----
rows = []
for race, d in res.items():
    for u, rh in d.items():
        h = sup.get((race, u), {})
        rows.append({'race': race, 'uma': u, 'kn': h.get('kijun_ninki'), 'nsup': h.get('nsup'),
                     'unsei': h.get('unsei'), 'MB': h.get('MB'), 'UL': h.get('UL'),
                     'tr': h.get('total_rank'), 'chaku': rh['chakujun'], 'odds': rh['odds'],
                     'pop': rh['pop'], 'name': rh['name']})
run = [x for x in rows if x['chaku']]
base3 = sum(1 for x in run if x['chaku'] <= 3)/len(run)
print(f'■ 突合 {len(rows)}頭 / 出走 {len(run)}頭 / 全体複勝率 {base3*100:.1f}%\n')

print('■ 対照群 — 基準人気帯')
for lo, hi, lab in ((1,3,'基準1〜3人気'),(4,6,'基準4〜6人気'),(7,12,'基準7〜12人気'),(13,99,'基準13人気以下')):
    rate([(x['chaku'], x['odds']) for x in rows if x['kn'] and lo <= x['kn'] <= hi], lab)
pool = [x for x in run if x['kn'] and 6 <= x['kn'] <= 14]
p3 = sum(1 for x in pool if x['chaku'] <= 3)/len(pool)
print(f'\n  → 本報の穴帯(基準6〜14人気)の母集団複勝率 = {p3*100:.1f}% (n={len(pool)})\n')

# ---- ChatGPT提案ルールの3日目検証 ----
ok = [(race, m.get('compi') or {}) for race, m in meta.items()]
def hit_race(race):
    return any(res[race][u]['chakujun'] and res[race][u]['chakujun'] <= 3
               for (rc, u), h in sup.items() if rc == race and h.get('kijun_ninki')
               and 7 <= h['kijun_ninki'] <= 12 for u in [u])
H = {}
for race in meta:
    H[race] = any((h.get('kijun_ninki') and 7 <= h['kijun_ninki'] <= 12
                   and res[race].get(u, {}).get('chakujun') and res[race][u]['chakujun'] <= 3)
                  for (rc, u), h in sup.items() if rc == race)
print('■ ChatGPT提案ルール — 3日目の検証(判定=基準7〜12人気が3着内)')
def agg(sel, lab, d1, d2):
    k = sum(H[r] for r in sel); n = len(sel)
    if n == 0: print(f'  {lab:<26s} n=0'); return (0,0)
    lo, hi = wilson(k, n)
    print(f'  {lab:<26s} {k:2d}/{n:2d} = {k/n*100:5.1f}%  CI[{lo:4.1f},{hi:4.1f}]   8/22-23:{d1}  8/29:{d2}')
    return (k, n)
cp = {race: (m.get('compi') or {}) for race, m in meta.items()}
P13 = [r for r in cp if cp[r].get('pattern') in ('P1','P2','P3')]
P46 = [r for r in cp if cp[r].get('pattern') in ('P4','P5','P6')]
BOTH= [r for r in P13 if cp[r].get('c1') and cp[r]['c1'] <= 76]
a=agg(P13,'P1-P3(優先)','70.4%','40.0%')
b=agg(P46,'P4-P6(非優先)','41.9%','64.0%')
c=agg(BOTH,'c1≤76 ∧ P1-P3(両立)','78.6%','0/4')
d=agg([r for r in P46 if cp[r].get('c1') and cp[r]['c1']<=76],'c1≤76 ∧ P4-P6','66.7%','100%')
e=agg(list(cp),'全体基準率','52.9%','57.1%')
print(f'\n  3日合算(140R): P1-P3 {19+4+a[0]}/{27+10+a[1]} = {(19+4+a[0])/(27+10+a[1])*100:.1f}% '
      f'/ 両立 {11+0+c[0]}/{14+4+c[1]} = {(11+0+c[0])/(14+4+c[1])*100:.1f}% '
      f'/ 基準 {37+20+e[0]}/{70+35+e[1]} = {(37+20+e[0])/(70+35+e[1])*100:.1f}%')
json.dump({'arare': A, 'compi': cp, 'hit7_12': H}, open(os.path.join(P,'採点_20260830.json'),'w'), ensure_ascii=False, indent=1)

# ================= 個別推奨の採点 =================
print('\n' + '='*70)
def show(title, rows, note_w=26):
    print(f'\n■ {title}')
    hit=0; tan=0; n=0
    for race,uma,name,note in rows:
        rh = res[race].get(uma)
        if not rh: print(f'  {race} {uma} 見つかりません'); continue
        n+=1
        c = rh['chakujun']
        if c and c<=3: hit+=1
        if c==1 and rh['odds']: tan+=rh['odds']*100
        m='◎' if (c and c<=3) else ' '
        print(f"  {race:8s} {uma:2d} {name:<13s} {note:<{note_w}s} → "
              f"{(str(c)+'着') if c else rh['status']:>4s} 確定{rh['pop'] if rh['pop'] else '-':>2}人気 {rh['odds']:>6}倍 {m}")
    lo,hi = wilson(hit,n)
    print(f"  → 3着内 {hit}/{n} = {hit/n*100:.1f}%  CI[{lo:.1f},{hi:.1f}]  仮定単回 {tan/(n*100)*100:.1f}%")
    return hit,n

show('第2報 4-1 二条件クロス 4頭', [
 ('札幌3R',12,'クリコイーコ','9人気 帯調整-2.1 乖離+3.5 支持1'),
 ('中京11R',2,'トウカイジーク','8人気 帯調整-3.4 乖離+2.0 ⚠出遅40%'),
 ('中京12R',13,'タイセイブロウ','6人気 帯調整-3.1 乖離+2.0 ⚠調教z-2.90'),
 ('札幌4R',14,'インテンスゲイズ','6人気 帯調整-4.7 乖離+1.0 ⚠価格同値'),
])
show('第2報 4-2 帯調整後に市場が最も弱気な7頭', [
 ('新潟10R',7,'カノープス','12人気 帯調整-4.2 z-2.44 出遅0%'),
 ('新潟3R',8,'ルークスイテルム','8人気 帯調整-7.1 z-2.35 ⚠出遅100%'),
 ('新潟10R',11,'ヴァルク','13人気 帯調整-3.1 z-2.20 ⚠出遅75%'),
 ('新潟12R',13,'コンパクトファイト','14人気 帯調整-2.7 z-2.11 出遅21%'),
 ('新潟12R',12,'ナインオブレター','11人気 帯調整-2.6 z-1.81 出遅13%'),
 ('札幌4R',14,'インテンスゲイズ','6人気 帯調整-4.7 z-1.65 ★両立'),
 ('中京9R',14,'レウコテア','6人気 帯調整-4.4 z-1.53 ★両立'),
])
show('ChatGPT SHADOW の主候補(羊一様経由で受領)', [
 ('札幌10R',2,'ショウナンカリス','SHADOW1位 札幌10R'),
 ('札幌10R',10,'ララバニュルス','SHADOW1位 札幌10R'),
 ('札幌10R',4,'ルージュベルベット','SHADOW1位 札幌10R'),
 ('札幌4R',14,'インテンスゲイズ','SHADOW2位 札幌4R'),
 ('札幌4R',2,'ジリアート','SHADOW2位 札幌4R'),
 ('中京11R',7,'ハピネスサンライズ','SHADOW3位 中京11R'),
 ('中京11R',2,'トウカイジーク','SHADOW3位 中京11R'),
 ('中京9R',4,'オーブフレッシュ','SHADOW4位 中京9R'),
 ('中京9R',14,'レウコテア','SHADOW4位 中京9R'),
 ('札幌3R',8,'サンエンジェルス','SHADOW5位 札幌3R'),
 ('札幌3R',7,'チャーチルデュース','SHADOW5位 札幌3R'),
 ('中京12R',10,'グラスゴー','SHADOW7位 中京12R 最上位'),
])
print('\n■ ⑤ウルトラ / マストバイ')
for tag,fld in (('ウルトラ','UL'),('マストバイ','MB')):
    xs=[(k,v) for k,v in sup.items() if v.get(fld)]
    hit=0; tan=0
    for (race,uma),h in sorted(xs):
        rh=res[race].get(uma); c=rh['chakujun'] if rh else None
        if c and c<=3: hit+=1
        if c==1 and rh['odds']: tan+=rh['odds']*100
    lo,hi=wilson(hit,len(xs))
    print(f'  {tag:<6s} n={len(xs):2d}  3着内 {hit:2d} = {hit/len(xs)*100:5.1f}% CI[{lo:4.1f},{hi:4.1f}]  '
          f'仮定単回 {tan/(len(xs)*100)*100:6.1f}%  (対照 {base3*100:.1f}%)')
    for (race,uma),h in sorted(xs):
        rh=res[race].get(uma); c=rh['chakujun'] if rh else None
        if c and c<=3:
            print(f"     ◎ {race:8s} {uma:2d} {h['name']:<13s} 基準{int(h['kijun_ninki']) if h['kijun_ninki'] else '-'}人気 → {c}着 {rh['odds']}倍")

# ================= 8/29の中核発見が再現するか =================
print('\n' + '='*70)
print('■ 支持係数 — 8/29の「人気帯を外すと効く」が再現するか')
print('\n (a) 穴帯(基準6〜14人気)に限定')
for lo,hi in ((0,2),(3,3),(4,4),(5,99)):
    lab=f'支持{lo}〜{hi}本' if lo!=hi else f'支持{lo}本'
    if hi==99: lab='支持5本以上'
    rate([(x['chaku'],x['odds']) for x in pool if (x['nsup'] or 0)>=lo and (x['nsup'] or 0)<=hi], lab)
print(f"  (母集団 {p3*100:.1f}%)")

print('\n (b) 人気帯を問わない支持係数上位')
xs=sorted([x for x in run if x['nsup'] is not None], key=lambda x:-x['nsup'])
for n in (14,20,30):
    top=xs[:n]
    rate([(x['chaku'],x['odds']) for x in top], f'支持上位{n}頭(人気帯不問)')
print(f"  (全出走の対照 {base3*100:.1f}%)")
print('\n  支持上位14頭の内訳:')
for x in xs[:14]:
    m='◎' if x['chaku']<=3 else ' '
    print(f"   支持{x['nsup']:>2}本 {x['race']:8s} {x['uma']:2d} {x['name']:<13s} 基準{int(x['kn']) if x['kn'] else '-':>2}人気 → {x['chaku']:2d}着 {x['odds']}倍 {m}")

# 支持係数 vs 基準人気の相関
def spearman(a,b):
    def rk(v):
        s=sorted(range(len(v)),key=lambda i:v[i]); r=[0]*len(v); i=0
        while i<len(s):
            j=i
            while j+1<len(s) and v[s[j+1]]==v[s[i]]: j+=1
            for k in range(i,j+1): r[s[k]]=(i+j)/2+1
            i=j+1
        return r
    ra,rb=rk(a),rk(b); n=len(a); ma=sum(ra)/n; mb=sum(rb)/n
    num=sum((x-ma)*(y-mb) for x,y in zip(ra,rb))
    den=(sum((x-ma)**2 for x in ra)*sum((y-mb)**2 for y in rb))**.5
    return num/den if den else 0
ns=[x['nsup'] for x in rows if x['kn'] and x['nsup'] is not None]
kn=[-x['kn'] for x in rows if x['kn'] and x['nsup'] is not None]
print(f"\n  支持係数 vs 基準人気(上位度) ρ = {spearman(ns,kn):+.3f} (n={len(ns)})   8/29は +0.761")

print('\n■ 運勢(日付バグ修正後の m30 列)別 — 穴帯')
for u in ('◎◎','◎','○','△','×'):
    rate([(x['chaku'],x['odds']) for x in pool if x['unsei']==u], f'運勢{u}')
rate([(x['chaku'],x['odds']) for x in pool if not x['unsei']], '運勢[不足]')

print('\n■ ⑦STRIDE total_rank別(全馬)')
for lo,hi in ((1,3),(4,6),(7,10),(11,99)):
    rate([(x['chaku'],x['odds']) for x in rows if x['tr'] and lo<=x['tr']<=hi], f'total_rank {lo}-{hi}位')

print('\n■ 荒れ12Rの1着馬 — 基準人気と成果物カバー')
cross={('札幌3R',12),('中京11R',2),('中京12R',13),('札幌4R',14)}
band={('新潟10R',7),('新潟3R',8),('新潟10R',11),('新潟12R',13),('新潟12R',12),('札幌4R',14),('中京9R',14)}
cov=0; bandcnt=collections.Counter()
for race,v in A.items():
    if not v['ar']: continue
    k=(race,v['wu']); h=sup.get(k,{})
    kn_=h.get('kijun_ninki'); tags=[]
    if k in cross: tags.append('二条件クロス')
    if k in band: tags.append('帯調整7頭')
    if h.get('UL'): tags.append('ウルトラ')
    if h.get('MB'): tags.append('マストバイ')
    cov+= bool(tags)
    b='基準1〜3' if kn_ and kn_<=3 else '基準4〜6' if kn_ and kn_<=6 else '基準7〜12' if kn_ and kn_<=12 else '基準13〜'
    bandcnt[b]+=1
    print(f"  {race:8s} {v['wu']:2d} {v['wn']:<13s} 確定{v['wp']:2d}人気 {v['wo']:>6}倍 基準{int(kn_) if kn_ else '-':>2}人気 → {'/'.join(tags) if tags else '—'}")
print(f"\n  → 合算カバー {cov}/{na} = {cov/na*100:.0f}%   (8/29は 2/11 = 18%)")
print('  荒れ12Rの1着馬の基準人気分布: ' + ' / '.join(f'{k}:{v}頭' for k,v in bandcnt.items()))
