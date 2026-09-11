# -*- coding: utf-8 -*-
# 入力の所在(このリポジトリ外):
#   DE260912.CSV = 2026-09-11 に添付受領した 9/12 出走表 (CP932・316行33列・ヘッダなし)
#   マイトバス.xlsx / ウルトラ回収率2026.02.22.xlsx = Google Drive より自己取得 (2026-09-11)
#   競馬場コース事典2_コース構造_101.csv = 2026-09-10 添付受領分 (jra_official_course_verified=NO / [実:提供値])
#   いずれも読み取りのみ。原本を変更していない。
#
# 出力の位置づけ: 救済レイヤーの材料整理。買い目・最終印・資金配分・最終採用馬は出さない。
#   未取得を0や推定値で埋めない。前走情報は出走表に列が無いため該当条件は[条件未確定]とする。
"""ウルトラ条件(阪神11件)の構造化と9/12出走表との照合.
ウルトラ一覧の条件は自然文のため当方が構造化した。**構造化の妥当性は検証対象**。
中山はウルトラ条件が1件も収録されていない(シートなし)ため対象外。
"""
import csv, json, collections
BASE="/tmp/claude-0/-home-user-github-com-new/84a20921-3b38-53dd-8669-b122c897a190/scratchpad"
ENTRY="/root/.claude/uploads/84a20921-3b38-53dd-8669-b122c897a190/2c3472cb-DE260912.CSV"
COL=dict(venue=1,r=2,umaban=3,cond=4,sd=5,dist=6,name=7,sex=8,age=9,jockey=10,
         trainer=12,base=13,sire=16,bms=20,waku=22,field=26)
horses=[]
for row in csv.reader(open(ENTRY,encoding='cp932')):
    h={k:row[i].strip() for k,i in COL.items()}
    for k in ('r','umaban','age','dist','waku','field'): h[k]=int(h[k])
    h['jumps']='障害' in h['cond']; h['new']=h['cond'].startswith('新馬')
    horses.append(h)
CD={}
for r in csv.DictReader(open(f"{BASE}/course3/x/競馬場コース事典2_コース構造_101.csv",encoding='utf-8-sig')):
    sd='芝' if r['surface'].strip()=='turf' else 'ダ'
    CD.setdefault((r['track'].strip(),sd,int(float(r['distance_m']))),
                  {'内回り':'内','外回り':'外','標準':''}[r['course_section'].strip()])
def io_of(h): return CD.get((h['venue'],h['sd'],h['dist']))

# 当方が構造化したウルトラ条件(阪神のみ収録)。prev=前走要求、sire_line=父系判定要
ULTRA=[
 dict(no='045', sd='芝', dists=[(1200,'内')], target=('父系','ストームキャット系'),
      cur=[('umaban_range',(1,None))], prev=[], note='条件②「枠番が1〜6枠」', cur2=[('waku_range',(1,6))]),
 dict(no='046', sd='芝', dists=[(1400,None),(1600,None)], target=('父','ハービンジャー'),
      cur=[('age_max',4)], prev=[], note='条件②「馬齢が4歳以下」'),
 dict(no='047', sd='芝', dists=[(1600,None),(1800,None)], target=('騎手','岩田望来'),
      cur=[], prev=['前走馬体重480kg以上'], note='条件②が前走馬体重'),
 dict(no='048', sd='芝', dists=[(1800,'外')], target=('父系','ロベルト系'),
      cur=[], prev=['前走10着以内'], note='条件②が前走着順'),
 dict(no='052', sd='ダ', dists=[(1400,None),(1600,None),(1800,None)], target=('父','シニスターミニスター'),
      cur=[('umaban_range',(3,16)),('base','栗')], prev=[], note='条件②「馬番3〜16＋関西馬(栗東)」'),
 dict(no='053', sd='ダ', dists=[(1400,None),(1600,None),(1800,None)], target=('父','ドレフォン'),
      cur=[], prev=['前走上がり3F順位4位以内'], note='条件②が前走上がり順位'),
 dict(no='054', sd='ダ', dists=[(1800,None)], target=('父','キズナ'),
      cur=[('age_max',3)], prev=['前走馬体重480kg以上'], note='条件②「3歳以下＋前走馬体重480kg以上」'),
 dict(no='055', sd='ダ', dists=[(1800,None),(2000,None)], target=('騎手','武豊'),
      cur=[('age_max',3),('sex_in',('牡','セ'))], prev=[], note='条件②「3歳以下＋性が牡・セ」'),
 dict(no='056', sd='ダ', dists=[(1800,None),(2000,None)], target=('騎手','M.デムーロ'),
      cur=[('age_max',3)], prev=[], note='条件②「3歳以下」'),
 dict(no='057', sd='ダ', dists=[(1800,None),(2000,None)], target=('騎手','横山典弘'),
      cur=[('umaban_range',(1,10)),('field_min',9)], prev=[], note='条件②「馬番1〜10＋9頭立て以上」'),
 dict(no='058', sd='ダ', dists=[(2000,None)], target=('騎手','松山弘平'),
      cur=[], prev=['前走馬体重520kg未満'], note='条件②が前走馬体重'),
]
U46={u['no']:u for u in json.load(open(f"{BASE}/umb/ultra46.json"))}
SIRE_LINES={'ストームキャット系','ロベルト系'}

def scope(u,h):
    if u['sd']!=h['sd']: return False
    for d,io in u['dists']:
        if d!=h['dist']: continue
        if io is None: return True
        cur=io_of(h)
        if cur is None or cur==io: return True
    return False

out=[]
for h in horses:
    if h['jumps'] or h['venue']!='阪神': continue
    for u in ULTRA:
        if not scope(u,h): continue
        tk,tv=u['target']; reasons=[]; unknowns=[]
        if tk=='騎手':
            if h['jockey']!=tv: continue
            reasons.append(f"騎手一致={tv}")
        elif tk=='父':
            if h['sire']!=tv: continue
            reasons.append(f"父一致={tv}")
        elif tk=='父系':
            reasons.append(f"父={h['sire']} → {tv}該当かは父系判定待ち")
            unknowns.append(f"SIRE_LINE:{tv}")
        ng=False
        for c in u.get('cur',[])+u.get('cur2',[]):
            k,v=c
            if k=='age_max' and h['age']>v: ng=True; break
            if k=='umaban_range':
                lo,hi=v
                if lo and h['umaban']<lo: ng=True; break
                if hi and h['umaban']>hi: ng=True; break
            if k=='waku_range':
                lo,hi=v
                if h['waku']<lo or h['waku']>hi: ng=True; break
            if k=='base' and h['base']!=v: ng=True; break
            if k=='sex_in' and h['sex'] not in v: ng=True; break
            if k=='field_min' and h['field']<v: ng=True; break
            reasons.append(f"{k}満たす")
        if ng: continue
        if u['prev']: unknowns.append("前走列未取得:"+",".join(u['prev']))
        v = 'PENDING_SIRE' if any(x.startswith('SIRE_LINE:') for x in unknowns) else ('PARTIAL_UNKNOWN' if unknowns else 'HIT')
        m=U46[u['no']]
        out.append(dict(system='ウルトラ', rule_id='U'+u['no'], venue=h['venue'], r=h['r'], umaban=h['umaban'],
                        waku=h['waku'], name=h['name'], sex=h['sex'], age=h['age'], jockey=h['jockey'],
                        sire=h['sire'], base=h['base'], field=h['field'], sd=h['sd'], dist=h['dist'],
                        io=io_of(h), cond=h['cond'], new=h['new'],
                        target=f"{tk}:{tv}", cond_text=f"{m['c1']} / {m['c2']}",
                        t3=m['t3'], tan=m['tan'], fuku=m['fuku'], ken=m['ken'], kahi=m['kahi'],
                        verdict=v, reasons=reasons, unknowns=unknowns, struct_note=u['note']))
json.dump(out, open(f"{BASE}/umb/match_ultra.json",'w'), ensure_ascii=False, indent=1, default=str)
print(f"ウルトラ 照合候補 {len(out)}件  内訳={dict(collections.Counter(x['verdict'] for x in out))}")
print("レース別:", dict(collections.Counter(f"{x['venue']}{x['r']}R" for x in out)))
for x in out:
    print(f"  {x['rule_id']} {x['venue']}{x['r']}R {x['umaban']:>2}番 {x['name']:<12} {x['verdict']:<16} 父={x['sire']:<14} 騎={x['jockey']}")
