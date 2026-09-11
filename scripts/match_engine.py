# -*- coding: utf-8 -*-
# 入力の所在(このリポジトリ外):
#   DE260912.CSV = 2026-09-11 に添付受領した 9/12 出走表 (CP932・316行33列・ヘッダなし)
#   マイトバス.xlsx / ウルトラ回収率2026.02.22.xlsx = Google Drive より自己取得 (2026-09-11)
#   競馬場コース事典2_コース構造_101.csv = 2026-09-10 添付受領分 (jra_official_course_verified=NO / [実:提供値])
#   いずれも読み取りのみ。原本を変更していない。
#
# 出力の位置づけ: 救済レイヤーの材料整理。買い目・最終印・資金配分・最終採用馬は出さない。
#   未取得を0や推定値で埋めない。前走情報は出走表に列が無いため該当条件は[条件未確定]とする。
"""9/12出走表 × ウルトラ/マストバイ条件 の機械照合.
出所: 出走表 DE260912.CSV(添付受領) / マイトバス.xlsx・ウルトラ回収率2026.02.22.xlsx(Drive自己取得)
      内外回りは 競馬場コース事典2_コース構造_101.csv (jra_official_course_verified=NO / [実:提供値])
原則: 未取得を0や推定で埋めない。前走情報は出走表に存在しないため該当条件は[条件未確定]とする。
      父系(〜系)の判定は本スクリプトでは行わず、別途エージェント検証に回す(SIRE_LINE_PENDING)。
本スクリプトは照合であり、買い目・最終印・資金配分・最終採用馬を出さない。
"""
import csv, json, collections

BASE="/tmp/claude-0/-home-user-github-com-new/84a20921-3b38-53dd-8669-b122c897a190/scratchpad"
ENTRY="/root/.claude/uploads/84a20921-3b38-53dd-8669-b122c897a190/2c3472cb-DE260912.CSV"

# ---- 出走表 ----
COL=dict(date=0,venue=1,r=2,umaban=3,cond=4,sd=5,dist=6,name=7,sex=8,age=9,jockey=10,
         kin=11,trainer=12,base=13,owner=14,producer=15,sire=16,dam=17,ketto=18,unk19=19,
         bms=20,color=21,waku=22,p23=23,p24=24,p25=25,field=26,p27=27,money=28)
horses=[]
for r in csv.reader(open(ENTRY,encoding='cp932')):
    h={k:r[i].strip() for k,i in COL.items()}
    h['r']=int(h['r']); h['umaban']=int(h['umaban']); h['age']=int(h['age'])
    h['dist']=int(h['dist']); h['waku']=int(h['waku']); h['field']=int(h['field'])
    h['jumps']='障害' in h['cond']
    h['maiden_new']=h['cond'].startswith('新馬')
    horses.append(h)

# ---- 内外(コース事典[実:提供値]) ----
CD={}
for r in csv.DictReader(open(f"{BASE}/course3/x/競馬場コース事典2_コース構造_101.csv",encoding='utf-8-sig')):
    sd='芝' if r['surface'].strip()=='turf' else 'ダ'
    sec=r['course_section'].strip()
    io={'内回り':'内','外回り':'外','標準':''}.get(sec,'')
    CD.setdefault((r['track'].strip(),sd,int(float(r['distance_m']))), io)
def io_of(h): return CD.get((h['venue'],h['sd'],h['dist']),None)

# ---- ルール ----
mb=json.load(open(f"{BASE}/umb/mb_rules.json"))
ultra=json.load(open(f"{BASE}/umb/ultra46.json"))

PREVCOLS=['PrevFinishMin','PrevFinishMax','Prev4CMax','Prev3FMax','PrevDistanceMin',
          'PrevDistGECurrent','PrevTrackDiff','PrevFieldGECurrent','PrevBodyWeightMin',
          'WeeksSincePrevMin','WeeksSincePrevMax','前走距離≦今回距離']
def has(x): return x is not None and str(x).strip() not in ('','None','nan','False')
def num(x):
    try: return float(str(x))
    except: return None

SIRE_LINES = {'ディープインパクト系','グラスワンダー系','エーピーインディ系','ストームキャット系','ロベルト系'}

def mb_scope(rule, h):
    """距離・芝ダ・内外の適用範囲に入るか"""
    if str(rule['芝ダ']).strip()!=h['sd']: return False
    for i in (1,2,3,4):
        d=num(rule.get(f'距離_{i}'))
        if d is None: continue
        if int(d)!=h['dist']: continue
        io=rule.get(f'内外_{i}')
        io=str(io).strip() if has(io) else ''
        cur=io_of(h)
        if io=='' : return True
        if cur is None: return True   # 内外不明 → 範囲内として扱い、下流で要確認
        if io==cur: return True
    return False

def mb_eval(rule, h):
    """判定可能条件を評価。戻り: (verdict, reasons, unknowns)
       verdict: 'HIT' / 'NO' / 'PENDING_SIRE' / 'PARTIAL_UNKNOWN'"""
    reasons=[]; unknowns=[]
    tgt=str(rule['ターゲット']).strip(); tk=str(rule['ターゲット種別']).strip()
    # ターゲット照合
    if tk=='鞍上':
        if h['jockey']!=tgt: return 'NO',[f"騎手不一致({h['jockey']}≠{tgt})"],[]
        reasons.append(f"騎手一致={tgt}")
    elif tk=='父':
        if h['sire']!=tgt: return 'NO',[f"父不一致({h['sire']}≠{tgt})"],[]
        reasons.append(f"父一致={tgt}")
    elif tk=='父系':
        if tgt not in SIRE_LINES: unknowns.append(f"父系名未知({tgt})")
        reasons.append(f"父={h['sire']} → {tgt}該当かは父系判定待ち")
        unknowns.append(f"SIRE_LINE:{tgt}")
    else:
        unknowns.append(f"ターゲット種別未対応({tk})")
    # 判定可能な現況条件
    def chk(key, ok, label):
        if not has(rule[key]): return True
        if ok: reasons.append(label+"=満たす"); return True
        reasons.append(label+"=満たさない"); return False
    if has(rule['HorseNoMin']) and h['umaban'] < num(rule['HorseNoMin']): return 'NO',[f"馬番{h['umaban']}<{rule['HorseNoMin']}"],unknowns
    if has(rule['HorseNoMax']) and h['umaban'] > num(rule['HorseNoMax']): return 'NO',[f"馬番{h['umaban']}>{rule['HorseNoMax']}"],unknowns
    if has(rule['FrameMin'])  and h['waku']  < num(rule['FrameMin']):   return 'NO',[f"枠{h['waku']}<{rule['FrameMin']}"],unknowns
    if has(rule['FrameMax'])  and h['waku']  > num(rule['FrameMax']):   return 'NO',[f"枠{h['waku']}>{rule['FrameMax']}"],unknowns
    if has(rule['AgeMin'])    and h['age']   < num(rule['AgeMin']):     return 'NO',[f"齢{h['age']}<{rule['AgeMin']}"],unknowns
    if has(rule['AgeMax'])    and h['age']   > num(rule['AgeMax']):     return 'NO',[f"齢{h['age']}>{rule['AgeMax']}"],unknowns
    if has(rule['SexAllow']):
        allow=str(rule['SexAllow'])
        okset = {'牡','セ','セン'} if '牡' in allow else ({'牝'} if '牝' in allow else set())
        sx = h['sex']
        s_ok = (sx in okset) or (sx=='セ' and ('セ' in allow or 'セン' in allow))
        if not s_ok: return 'NO',[f"性{sx}が{allow}に不適"],unknowns
        reasons.append(f"性{sx}∈{allow}")
    if has(rule['TrainerBase']):
        want=str(rule['TrainerBase']).strip()
        cur={'美':'美浦','栗':'栗東'}.get(h['base'],h['base'])
        if cur!=want: return 'NO',[f"所属{cur}≠{want}"],unknowns
        reasons.append(f"所属={cur}")
    if has(rule['CurrentFieldEq']) and h['field']!=num(rule['CurrentFieldEq']): return 'NO',[f"頭数{h['field']}≠{rule['CurrentFieldEq']}"],unknowns
    if has(rule['CurrentFieldMax']) and h['field']>num(rule['CurrentFieldMax']): return 'NO',[f"頭数{h['field']}>{rule['CurrentFieldMax']}"],unknowns
    if has(rule['CurrentFieldMin']) and h['field']<num(rule['CurrentFieldMin']): return 'NO',[f"頭数{h['field']}<{rule['CurrentFieldMin']}"],unknowns
    if has(rule['WeightAllowanceEq']):
        unknowns.append("減量記号が出走表に無い(WeightAllowanceEq)")
    # 前走条件
    prev=[k for k in PREVCOLS if has(rule[k])]
    if prev:
        unknowns.append("前走列未取得:"+",".join(prev))
    if any(u.startswith('SIRE_LINE:') for u in unknowns):
        return 'PENDING_SIRE', reasons, unknowns
    if unknowns:
        return 'PARTIAL_UNKNOWN', reasons, unknowns
    return 'HIT', reasons, unknowns

out=[]
for h in horses:
    if h['jumps']: continue
    for rule in mb:
        if str(rule['競馬場']).strip()!=h['venue']: continue
        if not mb_scope(rule,h): continue
        v,rs,un = mb_eval(rule,h)
        if v=='NO': continue
        out.append(dict(system='マストバイ', rule_id=rule['Rule_ID'], venue=h['venue'], r=h['r'],
                        umaban=h['umaban'], waku=h['waku'], name=h['name'], sex=h['sex'], age=h['age'],
                        jockey=h['jockey'], sire=h['sire'], base=h['base'], field=h['field'],
                        sd=h['sd'], dist=h['dist'], io=io_of(h), cond=h['cond'], new=h['maiden_new'],
                        target=f"{rule['ターゲット種別']}:{rule['ターゲット']}", cond_text=str(rule['条件']),
                        t3=rule['3着内率'], fuku=rule['複勝回収率'], page=rule['ページ'],
                        verdict=v, reasons=rs, unknowns=un))
json.dump(out, open(f"{BASE}/umb/match_mb.json",'w'), ensure_ascii=False, indent=1, default=str)
c=collections.Counter(x['verdict'] for x in out)
print(f"マストバイ 照合候補 {len(out)}件  内訳={dict(c)}")
print("レース別:", dict(collections.Counter(f"{x['venue']}{x['r']}R" for x in out)))
