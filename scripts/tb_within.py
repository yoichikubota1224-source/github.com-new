# -*- coding: utf-8 -*-
# 入力の所在(このリポジトリ外):
#   TB日次バイアス_遡及1年_20250801-20260726.csv  = Google Drive より自己取得 (2026-09-10)
#       SHA-256 0bb3783aed94fbd5da7cb9eb188f60fbe8ee4b3e811e40a009318460b5393f1f / 249,763 bytes / 3,308行
#   荒れ傾向分析_全レース全頭_20250907-20260906.csv / レース単位_結果払戻_20250907-20260906.csv
#       = 受領済み「荒れ傾向分析CSV_過去1年」より
#   いずれも読み取りのみ。原本を変更していない。
"""芝ダ内で四分位を取り直した本検査.
D_PRE_RACE は当日・同場・同芝ダ内の累積平均として定義されているため、
四分位も芝ダ別に取るのが整合的。前回の混合四分位は芝率67.5%→25.1%の交絡を含んでいた。
"""
import csv, collections, math, statistics as st
SP="/tmp/claude-0/-home-user-github-com-new/84a20921-3b38-53dd-8669-b122c897a190/scratchpad"
Z=1.96
def wilson(k,n):
    if n==0: return (float('nan'),0,0)
    ph=k/n; d=1+Z*Z/n; c=(ph+Z*Z/(2*n))/d
    m=Z*math.sqrt(ph*(1-ph)/n+Z*Z/(4*n*n))/d
    return ph*100,(c-m)*100,(c+m)*100
def nb(k1,n1,k2,n2):
    def wl(k,n):
        ph=k/n; d=1+Z*Z/n; c=(ph+Z*Z/(2*n))/d
        m=Z*math.sqrt(ph*(1-ph)/n+Z*Z/(4*n*n))/d
        return (c-m,c+m)
    l1,u1=wl(k1,n1); l2,u2=wl(k2,n2); d=k1/n1-k2/n2
    return d*100,(d-math.sqrt((k1/n1-l1)**2+(u2-k2/n2)**2))*100,(d+math.sqrt((u1-k1/n1)**2+(k2/n2-l2)**2))*100
def fl(v):
    v=(v or '').strip()
    if v=='': return None
    try: return float(v)
    except: return None
MAP={'1':'札幌','2':'函館','3':'福島','4':'新潟','5':'東京','6':'中山','7':'中京','8':'京都','9':'阪神','10':'小倉'}
tb=list(csv.DictReader(open(f"{SP}/tb/TB日次バイアス_遡及1年_20250801-20260726.csv"  # Drive自己取得,encoding='utf-8-sig')))
uma=collections.defaultdict(list)
for r in csv.DictReader(open(f"{SP}/zx/c/荒れ傾向分析_全レース全頭_20250907-20260906.csv",encoding='utf-8-sig')):
    uma[(r['日付'].replace('-',''),r['開催場'],r['R'])].append(r)
use=[]
for r in tb:
    pre=fl(r['D_PRE_RACE'])
    if pre is None: continue
    hs=uma.get((r['date'],MAP[r['venue']],r['race']))
    if not hs: continue
    if str(hs[0]['障害フラグ']).strip() not in ('0','','False','false'): continue
    if str(hs[0]['新馬フラグ']).strip() not in ('0','','False','false'): continue
    use.append((r,pre,hs))

# 芝ダ別の四分位
QS={}
for sd in ['芝','ダ']:
    v=sorted(x[1] for x in use if x[0]['sd']==sd)
    QS[sd]=[v[int(len(v)*f)] for f in (0.25,0.50,0.75)]
    print(f"  {sd}: n={len(v)}  Q1={QS[sd][0]:.4f} Q2={QS[sd][1]:.4f} Q3={QS[sd][2]:.4f}  (min={v[0]:.4f} max={v[-1]:.4f})")
def band(r,p):
    q=QS[r['sd']]
    return 0 if p<q[0] else 1 if p<q[1] else 2 if p<q[2] else 3
BN=['Q1(前不利側)','Q2','Q3','Q4(前有利側)']
def posgroup(hs):
    pos=[]
    for h in hs:
        last=None
        for c in ['通過順1','通過順2','通過順3','通過順4']:
            v=fl(h[c])
            if v is not None: last=v
        pos.append((last,h))
    kn=[(p,h) for p,h in pos if p is not None]
    if len(kn)<6: return {}
    kn.sort(key=lambda t:t[0]); n=len(kn); c1=max(1,n//3); c2=max(c1+1,2*n//3)
    return {id(h):('前' if i<c1 else '中' if i<c2 else '後') for i,(p,h) in enumerate(kn)}
def cross(sub,lo,hi,g):
    out=[]
    for b in range(4):
        k=n=0
        for (r,pre,hs) in sub:
            if band(r,pre)!=b: continue
            pg=posgroup(hs)
            if not pg: continue
            for h in hs:
                if pg.get(id(h))!=g: continue
                p=fl(h['人気'])
                if p is None or not(lo<=p<=hi): continue
                try: c=int(h['着順'])
                except: continue
                n+=1
                if c<=3: k+=1
        out.append((k,n))
    return out

print("\n=== 芝ダ内四分位: 交絡分布の確認 ===")
print(f"{'層':<14}{'R数':>6}{'平均頭数':>10}{'良率':>8}{'芝率':>8}{'平均距離':>10}")
for b in range(4):
    rs=[x for x in use if band(x[0],x[1])==b]
    hd=[fl(x[2][0]['出走頭数']) for x in rs]; hd=[v for v in hd if v]
    good=sum(1 for x in rs if x[2][0]['馬場状態'].strip()=='良')
    sh=sum(1 for x in rs if x[0]['sd']=='芝')
    di=[fl(x[2][0]['距離_m']) for x in rs]; di=[v for v in di if v]
    print(f"{BN[b]:<14}{len(rs):>6}{st.mean(hd):>10.2f}{good/len(rs)*100:>7.1f}%{sh/len(rs)*100:>7.1f}%{st.mean(di):>10.0f}")

def report(title,sub,minr=150):
    if len(sub)<minr:
        print(f"  {title:<24} R={len(sub):>5}  → 母数不足"); return
    res={}
    for lbl,lo,hi in [('本命1-3',1,3),('中穴4-6',4,6),('穴7-12',7,12)]:
        f=cross(sub,lo,hi,'前'); r=cross(sub,lo,hi,'後')
        res[lbl]=(f,r)
    print(f"  ── {title}  (R={len(sub)}) ──")
    for lbl,(f,r) in res.items():
        fs=" ".join(f"{wilson(*f[i])[0]:5.2f}%(n={f[i][1]:>4})" for i in range(4))
        gaps=[(f[i][0]/f[i][1]*100 - r[i][0]/r[i][1]*100) if f[i][1] and r[i][1] else float('nan') for i in range(4)]
        mono=all(f[i][1] and f[i+1][1] and f[i][0]/f[i][1]<=f[i+1][0]/f[i+1][1]+1e-12 for i in range(3))
        gm=all(gaps[i]<=gaps[i+1]+1e-12 for i in range(3))
        d,l,h=nb(*f[3],*f[0]) if f[3][1] and f[0][1] else (float('nan'),)*3
        print(f"     {lbl:<8} 前1/3: {fs}  単調={'YES' if mono else 'no '}  Q4-Q1={d:+.2f}pt CI[{l:+.2f},{h:+.2f}] {'0を含まない' if (l>0 or h<0) else '0を含む'}")
        print(f"     {'':<8} 差(前-後)= " + " ".join(f"{g:+6.2f}pt" for g in gaps) + f"   差単調={'YES' if gm else 'no'}")

print("\n=== 検査G: 芝ダ内四分位での本検査 ===")
for sd in ['芝','ダ']:
    report(f"{sd} 全体",[x for x in use if x[0]['sd']==sd])
print()
for sd in ['芝','ダ']:
    report(f"{sd} 良馬場",[x for x in use if x[0]['sd']==sd and x[2][0]['馬場状態'].strip()=='良'])
print()
for sd in ['芝','ダ']:
    report(f"{sd} 15-18頭",[x for x in use if x[0]['sd']==sd and 15<=(fl(x[2][0]['出走頭数']) or 0)<=18])
print("\n=== 前後半split (芝ダ内四分位・穴7-12×前1/3) ===")
us=sorted(use,key=lambda x:x[0]['date']); h=len(us)//2
for sd in ['芝','ダ']:
    for lab,sub in (('前半',us[:h]),('後半',us[h:])):
        f=cross([x for x in sub if x[0]['sd']==sd],7,12,'前')
        print(f"  {sd} {lab}: " + " ".join(f"{BN[i][:2]}={wilson(*f[i])[0]:5.2f}%(n={f[i][1]:>4})" for i in range(4)))
