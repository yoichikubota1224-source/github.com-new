#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2026-09-05 統合ビルド。6CSV＋当方の出馬表＋当方5年データ＋⑤該当馬 を結合し、
荒れ選定(are_score_v21)と穴馬候補(基準人気7〜12)を出す。
⚠ 確定オッズ・確定人気は使用しない。買い目・点数・資金配分は出力しない。
⚠ 取消馬(札幌8R②リテラシー)は出走頭数から除き、候補からも外す。ただし[不足]でなく[実:取消]と記録する。
"""
import json, math, os, collections
D = os.path.dirname(os.path.abspath(__file__))
P = json.load(open(os.path.join(D,'pack.json')))
S = json.load(open(os.path.join(D,'shutuba_20260905.json')))
H = json.load(open(os.path.join(D,'hits_20260905.json')))
J = json.load(open(os.path.join(D,'jisou905.json')))

def num(x, d=None):
    s=str(x or '').strip().replace('%','')
    if s in ('','-','--','未','null','取消','除外'): return d
    try: return float(s)
    except ValueError: return d

by = {k: {(r['race_id'], int(r['馬番'])): r for r in v} for k, v in P.items()}
sh = {}
for r in S:
    if r['jump']: continue
    sh[r['race_id']] = r

# ---- are_score_v21 (2026-08-02凍結・当方で再実装。8/29・8/30と同一) ----
O1_T=[(0.0,1.9,15.2,11.7,50.9,8.0),(1.9,2.6,27.3,13.6,55.0,12.3),
      (2.6,3.5,41.2,19.4,61.9,17.1),(3.5,99.0,54.9,31.6,73.8,29.8)]
N_T =[(8,12,24.8,10.4,46.3,6.2),(12,15,34.7,18.3,62.7,15.1),(15,19,38.0,21.2,63.4,20.3)]
BASE=(34.5,18.3,59.8,16.2)
def _cell(t,v):
    for row in t:
        if row[0] <= v < row[1]: return row
    return t[-1]
def _logit(p): p=min(max(p,1e-4),1-1e-4); return math.log(p/(1-p))
def _sig(z): return 1/(1+math.exp(-z))
def are_v21(o1,n):
    if o1 is None or n is None: return None
    a=_cell(O1_T,o1); b=_cell(N_T,n); out={}
    for i,key in enumerate(('FAV_OUT','HEAD_HOLE','ONE_HOLE','MULTI_HOLE')):
        ai=a[2+i] if i<2 else (a[4] if i==2 else a[5])
        bi=b[2+i] if i<2 else (b[4] if i==2 else b[5])
        z=(_logit(ai/100)+_logit(bi/100))/2
        z=_logit(BASE[i]/100)+1.5*(z-_logit(BASE[i]/100))
        out[key]=round(_sig(z)*100,1)
    return out

mbh=collections.defaultdict(list); ulh=collections.defaultdict(list)
for x in H['mustbuy']: mbh[(x['ba'],x['r'],x['uma'])].append(f"{x['対象']}／{x['条件']}")
for x in H['ultra']:   ulh[(x['ba'],x['r'],x['uma'])].append(f"No.{x['no']} {x['条件1']}／{x['条件2']}")
jis={(x['ba'],x['r'],x['uma']): x for x in J['hits']}

TORIKESHI = set()   # 取消馬 (race_id, 馬番)
races=[]
for rid, r in sh.items():
    horses=[]
    for h in r['horses']:
        k=(rid,h['uma'])
        tm=by['タイム指数'].get(k,{}); idm=by['IDM'].get(k,{}); um=by['ウマトク'].get(k,{})
        st=by['スライド競馬新聞'].get(k,{}); jd=by['JRDB_基準単複オッズ'].get(k,{}); cp=by['コンピ指数'].get(k,{})
        scratched = (str(tm.get('印','')).strip()=='取消') or (str(tm.get('単勝オッズ','')).strip()=='取消')
        if scratched: TORIKESHI.add(k)
        horses.append(dict(
            uma=h['uma'], waku=h['waku'], name=h['name'], sire=h['sire'], bms=h['bms'],
            jockey=h['jockey'], trainer=h.get('trainer'), belong=h.get('belong'),
            sex=h['sex'], age=h['age'], kin=h['kin'], kyakushitsu=h.get('kyakushitsu'),
            rotation=h.get('rotation'), blinker=h.get('blinker'), horse_id=h['horse_id'],
            scratched=scratched,
            kijun_tan=num(jd.get('基準単勝')), kijun_fuku=num(jd.get('基準複勝')),
            compi_rank=num(cp.get('コンピ順位')), compi=num(cp.get('コンピ指数')),
            IDM=num(idm.get('IDM')), idm_mark=str(idm.get('IDM印','')).strip() or None,
            idm_kyaku=str(idm.get('脚質','')).strip() or None,
            time_max=num(tm.get('最高指数')), time_5avg=num(tm.get('5走平均')),
            time_dist=num(tm.get('距離指数')), time_course=num(tm.get('コース指数')),
            time_note=str(tm.get('欠損注記','')).strip() or None,
            uma_idx=num(um.get('馬トク指数')), geki=num(um.get('激走指数')),
            SAV=num(st.get('SAV')), total=num(st.get('合計値')), total_rank=num(st.get('合計値順位')),
            tenkai=num(st.get('展開順位')), sinrai=str(st.get('信頼度','')).strip() or None,
            myoumi=str(st.get('妙味度','')).strip() or None,
            MB=mbh.get((r['ba'],r['r'],h['uma']),[]), UL=ulh.get((r['ba'],r['r'],h['uma']),[]),
            JISOU=jis.get((r['ba'],r['r'],h['uma'])),
        ))
    live=[h for h in horses if not h['scratched']]
    n=len(live)
    # 基準単勝から事前人気順位を付ける（確定人気は使わない）
    ranked=sorted([h for h in live if h['kijun_tan'] is not None], key=lambda h:h['kijun_tan'])
    for i,h in enumerate(ranked,1): h['kijun_ninki']=i
    for h in live:
        h.setdefault('kijun_ninki', None)
    o1=min([h['kijun_tan'] for h in live if h['kijun_tan'] is not None], default=None)
    races.append(dict(race_id=rid, ba=r['ba'], r=r['r'], title=r['title'], meta=r['meta'],
                      td=r['td'], dist=r['dist'], uchisoto=('外' if '外' in r['meta'] else '内'),
                      n_entry=len(horses), n_live=n, o1=o1, v21=are_v21(o1,n), horses=horses))
races.sort(key=lambda x:(x['ba'],x['r']))
json.dump(races, open(os.path.join(D,'toukei_20260905.json'),'w'), ensure_ascii=False, indent=1)

print(f'[実] {len(races)}R / 延べ{sum(r["n_entry"] for r in races)}頭 / 取消 {len(TORIKESHI)}頭')
for k in TORIKESHI:
    r=sh[k[0]]; h=next(x for x in r["horses"] if x["uma"]==k[1])
    print(f'   取消: {r["ba"]}{r["r"]}R {k[1]}番 {h["name"]} → 出走頭数 {r["n_entry"]}→{r["n_entry"]-1}頭')
print('\n=== 荒れ度 are_score_v21（ONE_HOLE降順・上位12R） ===')
print(f'{"場R":<8}{"頭数":>4}{"1番人気基準単勝":>14}{"FAV_OUT":>9}{"HEAD":>7}{"ONE_HOLE":>10}{"MULTI":>8}  {"レース"}')
for r in sorted([x for x in races if x['v21']], key=lambda x:-x['v21']['ONE_HOLE'])[:12]:
    v=r['v21']
    print(f"{r['ba']}{r['r']:>2}R{'':<2}{r['n_live']:>4}{r['o1']:>14.1f}"
          f"{v['FAV_OUT']:>8.1f}%{v['HEAD_HOLE']:>6.1f}%{v['ONE_HOLE']:>9.1f}%{v['MULTI_HOLE']:>7.1f}%  {r['title'][:26]}")
