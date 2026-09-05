#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2026-09-06 統合ビルド v1（9/5 build905 v3.2 と同じ方針）。
6CSV（コンピ/ウマトク/IDM/タイム/スライド/JRDB基準単複）＋当方出走表（DE260906正本由来 shutuba_20260906.json）
＋⑤該当馬（hits_20260906.json）＋⑭次走期待（jisou906.json）を結合し toukei_20260906.json を書く。
- 主キー: race_id(netkeiba 12桁)＋馬番。6CSVの racekey(JRDB 8桁) と出走表の race_key を 1:1 で対応させる。馬名では結合しない。
- are_score_v21 は監査値(v21_audit)としてのみ算術再現。意思決定用4列(v21_decision)は空欄＝HOLD（4出力すべて）。
- 確定オッズ・確定人気は使用しない。買い目・点数・資金配分は出力しない。
- [不足]は0・消しへ変換しない。タイム指数の未掲載は time_note と4指数の None で保持する。
- def_version: 本日の定義刻印（9/5第9報 課題#2 への対応。規則の変更ではなく記録）。
"""
import json, math, os, collections
D = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'predictions', '20260906')
SP = '/tmp/claude-0/-home-user-github-com-new/47c1892c-ddc4-50e4-8b6f-3403a9782673/scratchpad/d0906'
PACK = os.environ.get('PACK906', os.path.join(SP, 'pack.json'))
P = json.load(open(PACK))
S = json.load(open(os.path.join(D, 'shutuba_20260906.json')))
H = json.load(open(os.path.join(D, 'hits_20260906.json')))
J = json.load(open(os.path.join(D, 'jisou906.json')))

DEF_VERSION = {
    'kijun_ninki': 'JRDB基準単勝の昇順で当方が付けた事前人気順位（確定人気ではない）。v1 2026-08-29〜',
    '穴帯': '基準人気 7〜12（kijun_ninki）。v1 2026-08-29〜（8/30の6〜14は使わない）',
    'テクニカル6': 'コンピ上位3頭の指数合計。P1≤205/P2≤208/P3≤211/P4≤215/P5≤219/P6≥220。v1 2026-08-22〜',
    'c1': 'コンピ最高値。両立 = c1≤76 ∧ P1-P3。v1 2026-08-22〜',
    'are_score_v21': '2026-08-02凍結 sha256 c63c3f41…。入力 o1=JRDB基準単勝の最小値(T-15ではない)・n=出走頭数。監査値のみ・意思決定HOLD',
}

def num(x, d=None):
    s = str(x or '').strip().replace('%', '')
    if s in ('', '-', '--', '未', 'null', '取消', '除外'): return d
    try: return float(s)
    except ValueError: return d

# 6CSV: (race_id, 馬番) -> row
by = {k: {(r['race_id'], int(r['馬番'])): r for r in v} for k, v in P.items()}
# racekey -> race_id（コンピCSVから。1:1でなければ止める）
rk2rid = collections.defaultdict(set)
for r in P['コンピ指数']:
    rk2rid[r['racekey']].add(r['race_id'])
assert all(len(v) == 1 for v in rk2rid.values()), '[要確認] racekey→race_id が1:1でない'
rk2rid = {k: list(v)[0] for k, v in rk2rid.items()}
# レース見出し（番組表示・発走）はCSVから
rmeta = {}
for r in P['コンピ指数']:
    rmeta.setdefault(r['race_id'], dict(banggumi=r['番組表示'], hasso=r['発走'], ba=r['開催場'], R=int(r['R'])))

# ---- are_score_v21 (2026-08-02凍結・当方で再実装。8/29〜9/5と同一) ----
O1_T=[(0.0,1.9,15.2,11.7,50.9,8.0),(1.9,2.6,27.3,13.6,55.0,12.3),
      (2.6,3.5,41.2,19.4,61.9,17.1),(3.5,99.0,54.9,31.6,73.8,29.8)]
N_T =[(8,12,24.8,10.4,46.3,6.2),(12,15,34.7,18.3,62.7,15.1),(15,19,38.0,21.2,63.4,20.3)]
BASE=(34.5,18.3,59.8,16.2)
def _cell(t,v):
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

mbh=collections.defaultdict(list); ulh=collections.defaultdict(list); ulref=collections.defaultdict(list)
for x in H['mustbuy']: mbh[(x['ba'],x['r'],x['uma'])].append(f"{x['対象']}／{x['条件']}")
for x in H['ultra']:   ulh[(x['ba'],x['r'],x['uma'])].append(f"No.{x['no']} {x['対象']}／{x['条件']}")
for x in H.get('ultra_ref_sapporo', []):   # 正本外（退避テンプレ由来）。UL には数えない＝[要確認]
    ulref[(x['ba'],x['r'],x['uma'])].append(f"[要確認]正本外 {x.get('対象')}／{x.get('条件')}")
jis={(x['ba'],x['r'],x['uma']): x for x in J['hits']}

TORIKESHI = set()
races=[]
for rc in S:
    if rc['jump']: continue
    rid = rk2rid.get(rc['race_key'])
    if rid is None:
        raise SystemExit(f"[要確認] 出走表 race_key {rc['race_key']} が6CSVに無い")
    horses=[]
    for h in rc['horses']:
        k=(rid,h['uma'])
        tm=by['タイム指数'].get(k,{}); idm=by['IDM'].get(k,{}); um=by['ウマトク'].get(k,{})
        st=by['スライド競馬新聞'].get(k,{}); jd=by['JRDB_基準単複オッズ'].get(k,{}); cp=by['コンピ指数'].get(k,{})
        if not (tm and idm and um and st and jd and cp):
            raise SystemExit(f"[要確認] {rc['ba']}{rc['r']}R {h['uma']} が6CSVのどれかに無い")
        scratched = (str(tm.get('印','')).strip()=='取消') or (str(tm.get('単勝オッズ','')).strip()=='取消') \
                    or any('取消' in str(x.get('出走状態','')) or '除外' in str(x.get('出走状態','')) for x in (jd,cp))
        if scratched: TORIKESHI.add((rc['ba'],rc['r'],h['uma']))
        # 馬名の照合（結合キーではない。9文字切り詰め等の表記差を記録するだけ）
        name_csv = cp.get('馬名','')
        name_note = None if name_csv == h['name'] else f"[要確認]表記差 CSV={name_csv} / DE={h['name']}"
        horses.append(dict(
            uma=h['uma'], waku=h['waku'], name=h['name'], name_note=name_note, sire=h['sire'], bms=h.get('bms'),
            jockey=h['jockey'], trainer=h.get('trainer'), belong=h.get('belong'),
            sex=h['sex'], age=h['age'], kin=h['kin'],
            kyakushitsu=str(idm.get('脚質','')).strip() or None,     # 9/5はnetkeiba脚質。9/6はIDM CSVの脚質＝[実:IDM列]
            rotation=(f"中{h['weeks']}週" if h.get('weeks') is not None else None),   # DE前走間隔週から
            blinker=None, horse_id=h['horse_id'],
            scratched=scratched,
            kijun_tan=num(jd.get('基準単勝')), kijun_fuku=num(jd.get('基準複勝')),
            compi_rank=num(cp.get('コンピ順位')), compi=num(cp.get('コンピ指数')),
            IDM=num(idm.get('IDM')), idm_mark=str(idm.get('IDM印','')).strip() or None,
            idm_kyaku=str(idm.get('脚質','')).strip() or None,
            time_max=num(tm.get('最高指数')), time_5avg=num(tm.get('5走平均')),
            time_dist=num(tm.get('距離指数')), time_course=num(tm.get('コース指数')),
            time_note=str(tm.get('欠損注記','')).strip() or None,
            time_status=str(tm.get('source_status','')).strip() or None,
            uma_idx=num(um.get('馬トク指数')), geki=num(um.get('激走指数')),
            SAV=num(st.get('SAV')), total=num(st.get('合計値')), total_rank=num(st.get('合計値順位')),
            tenkai=num(st.get('展開順位')), sinrai=str(st.get('信頼度','')).strip() or None,
            myoumi=str(st.get('妙味度','')).strip() or None,
            st_status=str(st.get('source_status','')).strip() or None,
            st_idx=num(st.get('ST指数')), shiage=num(st.get('仕上指数')),
            lap_tekisei=str(st.get('ラップ適性','')).strip() or None, lap_chara=str(st.get('ラップキャラ','')).strip() or None,
            deokure=num(st.get('出遅率')), senko=num(st.get('先行力')), tsuiso=num(st.get('追走力')),
            jikyu=num(st.get('持久力')), jizoku=num(st.get('持続力')), shunpatsu=num(st.get('瞬発力')),
            zen3f_rank=num(st.get('前3F順位')), zen3f_diff=num(st.get('前3F差')), zen3f_pos=str(st.get('前3F内外','')).strip() or None,
            shobu_rank=num(st.get('勝負所順位')), shobu_diff=num(st.get('勝負所差')), shobu_pos=str(st.get('勝負所内外','')).strip() or None,
            gmae_rank=num(st.get('G前順位')), gmae_diff=num(st.get('G前差')), gmae_pos=str(st.get('G前内外','')).strip() or None,
            jk_type=str(st.get('騎手タイプ','')).strip() or None, jk_idx=num(st.get('騎手指数')),
            saishu_oikiri=str(st.get('最終追切','')).strip() or None,
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
            # --- v1.1: 9/6から新聞CSVに追加された末尾8列（Codex 06記録）。14係の再確認後に追加取込。穴帯照合には未使用 ---
            crs_kyusha_n=num(st.get('コース厩舎総数')), crs_kyusha_win=num(st.get('コース厩舎勝率')),
            crs_kyusha_ren=num(st.get('コース厩舎連対率')), crs_kyusha_fuku=num(st.get('コース厩舎複勝率')),
            chokyoP_kyusha_n=num(st.get('調教P厩舎総数')), chokyoP_kyusha_win=num(st.get('調教P厩舎勝率')),
            chokyoP_kyusha_ren=num(st.get('調教P厩舎連対率')), chokyoP_kyusha_fuku=num(st.get('調教P厩舎複勝率')),
            time_3=num(tm.get('3走')), time_2=num(tm.get('2走')), time_1=num(tm.get('前走')),
            geki_mark=str(um.get('激印','')).strip() or None,
            geki_f=[x for x in (str(um.get(f'激走要因{i}','')).strip() for i in (1,2,3)) if x],
            haran=num(um.get('波乱度')), fav_sinrai=num(um.get('1番人気信頼度')), fav_myoumi=num(um.get('1番人気妙味度')),
            weight=num(um.get('馬体重')), weight_diff=str(um.get('増減','')).strip() or None,
            # DE正本由来の前走（当方5年DBで補完）。⑭・⑤の入力と同じ
            zen_chaku=h.get('zen_chaku'), zen_pop=h.get('zen_pop'), zen_dist=h.get('zen_dist'), zen_ba=h.get('zen_ba'),
            zen_td=h.get('zen_td'), zen_last3f=h.get('zen_last3f'), zen_agari_rank=h.get('zen_agari_rank'),
            zen_date=h.get('zen_date'), past_n=h.get('past_n'),
            MB=mbh.get((rc['ba'],rc['r'],h['uma']),[]), UL=ulh.get((rc['ba'],rc['r'],h['uma']),[]),
            UL_REF=ulref.get((rc['ba'],rc['r'],h['uma']),[]),
            JISOU=jis.get((rc['ba'],rc['r'],h['uma'])),
        ))
    live=[h for h in horses if not h['scratched']]
    n=len(live)
    ranked=sorted([h for h in live if h['kijun_tan'] is not None], key=lambda h:h['kijun_tan'])
    for i,h in enumerate(ranked,1): h['kijun_ninki']=i
    for h in horses: h.setdefault('kijun_ninki', None)
    o1=min([h['kijun_tan'] for h in live if h['kijun_tan'] is not None], default=None)
    # テクニカル6 / c1 / P区分（②荒れ選定の入口。コンピ指数から）
    cs=sorted([h['compi'] for h in live if h['compi'] is not None], reverse=True)
    c1=cs[0] if cs else None; t6=sum(cs[:3]) if len(cs)>=3 else None
    pat=None
    if t6 is not None:
        for lim,nm in ((205,'P1'),(208,'P2'),(211,'P3'),(215,'P4'),(219,'P5')):
            if t6<=lim: pat=nm; break
        else: pat='P6'
    m=rmeta[rid]
    races.append(dict(race_id=rid, race_key=rc['race_key'], ba=rc['ba'], r=rc['r'], title=rc['cls'],
                      meta=m['banggumi'], hasso=m['hasso'],
                      td=rc['td'], dist=rc['dist'], uchisoto=rc.get('uchisoto'), uchisoto_src=rc.get('uchisoto_src'),
                      shinba=rc.get('shinba'),
                      n_entry=len(horses), n_live=n, o1=o1,
                      c1=c1, t6=t6, pattern=pat, ryoritsu=(c1 is not None and c1<=76 and pat in ('P1','P2','P3')),
                      v21_audit=are_v21(o1,n),
                      v21_decision={'FAV_OUT': None, 'HEAD_HOLE': None, 'ONE_HOLE': None, 'MULTI_HOLE': None},
                      v21_decision_status='HOLD',
                      v21_hold_reasons=(['T15_SNAPSHOT_MISSING: o1にJRDB基準単勝(前日値)を代入。凍結版はT-15固定・NO_VALID_SNAPSHOT=HOLD',
                                         'LABEL_DEF_UNCONFIRMED: 4出力の人気帯定義(6〜12/7〜12)が正本で未確認']
                                        + ([] if 8 <= n <= 18 else [f'OUT_OF_DOMAIN: N={n}は学習域(8〜18)外。凍結版lk()と同じくBASEへ退避した監査値'])),
                      v21_domain=('域内' if 8 <= n <= 18 else f'域外(N={n}: 凍結版と同じくBASEへ退避)'),
                      v21_o1_source='JRDB基準単勝（T-15スナップショットではない＝HOLD）',
                      v21_flags_applied=False,
                      v21_flag_inputs='[不足] flag_55heiritsu / flag_fuku11_kochaku の入力列が当方パイプラインに無い（未適用）',
                      horses=horses))
races.sort(key=lambda x:(x['ba'],x['r']))
out = dict(version='toukei906_v1.1', raceday='20260906', def_version=DEF_VERSION,
           source='6CSV(SHA256SUMS_20260906と6/6一致)＋shutuba_20260906.json(DE260906正本由来)＋hits_20260906.json＋jisou906.json',
           races=races)
json.dump(out, open(os.path.join(D,'toukei_20260906.json'),'w'), ensure_ascii=False, indent=1)

print(f'[実] {len(races)}R / 延べ{sum(r["n_entry"] for r in races)}頭 / 取消・除外 {len(TORIKESHI)}頭 {sorted(TORIKESHI)}')
nn=[(r['ba'],r['r'],h['uma'],h['name_note']) for r in races for h in r['horses'] if h['name_note']]
print(f'[要確認] 馬名の表記差 {len(nn)}件', nn)
tn=sum(1 for r in races for h in r['horses'] if h['time_max'] is None and h['time_5avg'] is None and h['time_dist'] is None and h['time_course'] is None)
print(f'[不足] タイム指数 中核4指数すべて空欄 {tn}頭 / source_status HOLD {sum(1 for r in races for h in r["horses"] if (h["time_status"] or "").startswith("HOLD"))}頭')
print(f'[不足] 新聞 HOLD {sum(1 for r in races for h in r["horses"] if (h["st_status"] or "").startswith("HOLD"))}頭')
print(f'[実] ⑤MB {sum(1 for r in races for h in r["horses"] if h["MB"])}頭 / UL {sum(1 for r in races for h in r["horses"] if h["UL"])}頭 / UL_REF(正本外) {sum(1 for r in races for h in r["horses"] if h["UL_REF"])}頭 / ⑭ {sum(1 for r in races for h in r["horses"] if h["JISOU"])}頭')
print('\n=== 荒れ選定の入口（P区分・c1・両立・v21監査値）===')
print(f'{"場R":<7}{"頭":>3}{"o1":>5}{"c1":>4}{"T6":>5} {"P":<3}{"両立":<3}{"ONE":>6}  {"クラス"}')
for r in races:
    v=r['v21_audit'] or {}
    print(f"{r['ba']}{r['r']:>2}R {r['n_live']:>3}{r['o1']:>5.1f}{r['c1']:>4.0f}{r['t6']:>5.0f} {r['pattern']:<3}{'★' if r['ryoritsu'] else '　':<3}{v.get('ONE_HOLE',0):>6.1f}  {r['title']} {r['td']}{r['dist']}")
