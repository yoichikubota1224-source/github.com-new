#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2026-09-05 統合ビルド。6CSV＋当方の出馬表＋当方5年データ＋⑤該当馬 を結合し、
荒れ選定(are_score_v21)と穴馬候補(基準人気7〜12)を出す。
⚠ 確定オッズ・確定人気は使用しない。買い目・点数・資金配分は出力しない。
⚠ 取消馬(札幌8R②リテラシー)は出走頭数から除き、候補からも外す。ただし[不足]でなく[実:取消]と記録する。
"""
import json, math, os, collections
D = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'predictions', '20260905')
# pack.json = 6CSVをそのまま辞書化したもの。原本(6CSV)はリポジトリに置かないため作業領域から読む。
PACK = os.environ.get('PACK905', '/tmp/claude-0/-home-user-github-com-new/47c1892c-ddc4-50e4-8b6f-3403a9782673/scratchpad/d0905/pack.json')
P = json.load(open(PACK))
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
    # 凍結版 are_score_v21.py (sha256 c63c3f41…, 2026-08-02凍結) の lk() は域外で BASE を返す。
    # v3.1: 末尾セルを流用していた当方の再実装を凍結版に合わせた（第6報で訂正）。域外は v21_domain で別に印を付ける。
    for row in t:
        if row[0] <= v < row[1]: return row
    return (None, None) + BASE
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
            # --- v2 追加: 第4報の14係再確認で「正本にあるのに統合JSONへ取り込んでいない」と指摘された列 ---
            st_idx=num(st.get('ST指数')), shiage=num(st.get('仕上指数')),
            lap_tekisei=str(st.get('ラップ適性','')).strip() or None, lap_chara=str(st.get('ラップキャラ','')).strip() or None,
            deokure=num(st.get('出遅率')), senko=num(st.get('先行力')), tsuiso=num(st.get('追走力')),
            jikyu=num(st.get('持久力')), jizoku=num(st.get('持続力')), shunpatsu=num(st.get('瞬発力')),
            zen3f_rank=num(st.get('前3F順位')), zen3f_diff=num(st.get('前3F差')), zen3f_pos=str(st.get('前3F内外','')).strip() or None,
            shobu_rank=num(st.get('勝負所順位')), shobu_diff=num(st.get('勝負所差')), shobu_pos=str(st.get('勝負所内外','')).strip() or None,
            gmae_rank=num(st.get('G前順位')), gmae_diff=num(st.get('G前差')), gmae_pos=str(st.get('G前内外','')).strip() or None,
            jk_type=str(st.get('騎手タイプ','')).strip() or None, jk_idx=num(st.get('騎手指数')),
            # --- v3 追加: 第5報(ChatGPT SHADOW監査)で指摘。新聞CSVの調教欄・騎手/厩舎/外厩/血統の成績欄・特記 ---
            saishu_oikiri=str(st.get('最終追切','')).strip() or None,      # 例 '55(札ダ)'。新聞掲載の指数であり時計・生ラップではない
            isshu_oikiri=str(st.get('1週前追切','')).strip() or None,
            chokyo_idx=num(st.get('調教指数')), chokyo_pattern=str(st.get('調教パターン','')).strip() or None,
            jk_comment=str(st.get('騎手コメント','')).strip() or None,
            jk_course_n=num(st.get('当該コース騎手総数')), jk_course_win=num(st.get('当該コース騎手勝率')),
            jk_course_ren=num(st.get('当該コース騎手連対率')), jk_course_fuku=num(st.get('当該コース騎手複勝率')),
            trainer_full=str(st.get('厩舎','')).strip() or None, houboku=str(st.get('最近放牧先','')).strip() or None,
            nanso=num(st.get('何走目')),
            gaikyu_n=num(st.get('厩舎外厩総数')), gaikyu_win=num(st.get('厩舎外厩勝率')), gaikyu_ren=num(st.get('厩舎外厩連対率')), gaikyu_fuku=num(st.get('厩舎外厩複勝率')),
            uma_gaikyu_n=num(st.get('馬外厩総数')), uma_gaikyu_fuku=num(st.get('馬外厩複勝率')),
            hizume=str(st.get('蹄','')).strip() or None, omo_tekisei=str(st.get('重適性','')).strip() or None,
            tokki=[x for x in (str(st.get(f'特記{i}','')).strip() for i in (1,2,3)) if x],
            sire_n=num(st.get('血統総数')), sire_win=num(st.get('血統勝率')), sire_ren=num(st.get('血統連対率')), sire_fuku=num(st.get('血統複勝率')),
            time_3=num(tm.get('3走')), time_2=num(tm.get('2走')), time_1=num(tm.get('前走')),
            geki_mark=str(um.get('激印','')).strip() or None,
            geki_f=[x for x in (str(um.get(f'激走要因{i}','')).strip() for i in (1,2,3)) if x],
            haran=num(um.get('波乱度')), fav_sinrai=num(um.get('1番人気信頼度')), fav_myoumi=num(um.get('1番人気妙味度')),
            weight=num(um.get('馬体重')), weight_diff=str(um.get('増減','')).strip() or None,
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
                      n_entry=len(horses), n_live=n, o1=o1, v21=are_v21(o1,n),
                      # v21の学習域は頭数8〜18。域外(N<8)は _cell が末尾セル(N15〜18)を流用するため値を序列に使わない＝[要確認]
                      v21_domain=('域内' if 8 <= n <= 18 else f'域外(N={n}: 凍結版と同じくBASEへ退避)'),
                      # ⚠ 凍結版の主変数 o1 は「T-15 1番人気オッズ」。当方は JRDB基準単勝(前日値)を代入している＝仕様外の代替。
                      #   凍結版は NO_VALID_SNAPSHOT=HOLD を定めるため、意思決定への利用は HOLD（第6報）。
                      v21_o1_source='JRDB基準単勝（T-15スナップショットではない＝HOLD）',
                      horses=horses))
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
