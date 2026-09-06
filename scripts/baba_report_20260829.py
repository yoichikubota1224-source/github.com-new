# -*- coding: utf-8 -*-
import json
B = json.load(open('predictions/20260829/baba_niigata_20260829.json'))
D = json.load(open('predictions/20260829/最終統合_20260829.json'))
NI = {R['r']: R for R in D if R['ba'] == '新潟'}
DRIFT = {int(k): v for k, v in json.load(open('predictions/20260829/人気別3着内率_ドリフト補正後.json')).items()}

L = []
def w(s=''): L.append(s)

def avg_rank(hs):
    vals = sorted([(h['uma'], h['total']) for h in hs], key=lambda z: -z[1])
    rk, i = {}, 0
    while i < len(vals):
        j = i
        while j + 1 < len(vals) and vals[j+1][1] == vals[i][1]:
            j += 1
        a = (i + j) / 2 + 1
        for k in range(i, j+1):
            rk[vals[k][0]] = a
        i = j + 1
    return rk

def mkt_p3(R):
    hs = R['horses']
    s = sum(1/h['kijun_fuku'] for h in hs if h.get('kijun_fuku'))
    return {h['uma']: (1/h['kijun_fuku'])*3/s for h in hs if h.get('kijun_fuku')}

def hosei(R, u, ninki):
    m = mkt_p3(R).get(u)
    if m is None or not ninki: return None
    c = DRIFT.get(min(int(ninki), 16))
    if c is None: return None
    return 100*(m - c)

# ---- 識別力 ----
disc = {}
for o in B:
    rows = o['rows']; n = len(rows)
    c = {k: sum(1 for r in rows if r['omo'] == k) for k in ('◎','○','△','')}
    known = n - c['']
    rate = (c['◎']+c['○'])/known*100 if known else None
    if not known: lv, why = '[不足]', 'STRIDE重適性が全頭空欄(新馬)'
    elif rate >= 80: lv, why = '低', 'ほぼ全頭が重巧者=相対差がつかない'
    elif rate <= 10: lv, why = '低', 'ほぼ全頭が重不得手=相対差がつかない'
    elif rate <= 30: lv, why = '高', '重巧者が少数=該当馬に相対優位'
    else: lv, why = '中', ''
    disc[o['r']] = (c, known, rate, lv, why)

MARK = {'◎': '◎ 重巧者', '○': '○ こなす', '△': '△ 割引', '': '[不足]'}
JUDGE_UP = '押し上げ'
def judge(r, lv):
    o = r['omo']
    if o == '': return '[不足]'
    if lv == '低': return '中立(識別力低)'
    if o == '◎': return '押し上げ'
    if o == '○': return '維持'
    return '割引'

w('# 第9報 新潟 馬場適性アップデート(小雨・芝稍重／ダート稍重)')
w()
w('日付: 2026-08-29 ／ 対象: 新潟 全11R・169頭 ／ 契機: 羊一様ご指示「小雨のため芝、ダート稍重」')
w()
w('```')
w('RACE_GATE_STATUS = BLOCKED')
w('PURCHASE_ALLOWED = NO')
w('LIVE_PREDICTION  = NOT_AUTHORIZED')
w('RULE_PROMOTION   = NONE')
w('SHADOW_ONLY      = TRUE')
w('```')
w()
w('本報は**馬場状態の重み付けのみ**を更新するものです。')
w('買い目・点数・資金配分・購入可否・最終印・軸は一切出しません。')
w()
w('---')
w()
w('## 0. 先に申し上げる制約 — この更新で検証できないこと [不足]')
w()
w('| 論点 | 状態 |')
w('|---|---|')
w('| 馬場状態の入力そのもの | **[要確認]** 羊一様のご申告(小雨→芝稍重・ダ稍重)。JRA公式発表を当方は取得できておりません |')
w('| 稍重の効果量の検証 | **[不足]** 当方の較正標本70R・2,568頭は**全て良馬場**。稍重で3着内率がどう動くかを自前データで測れません |')
w('| 前走馬場と着順の対応 | **[不足]** DE出走表に前走馬場状態の列がなく、馬ごとの道悪実績を当方で再計算できません |')
w('| 血統(父・母父)の道悪傾向 | **[不足]** 父系別の道悪成績DBを保有しておらず、[推]でしか語れないため本報では採用しません |')
w('| 当日の含水率・クッション値・TB | **[不足]** 未取得 |')
w()
w('したがって本報は、**[実]で持っている2本の道悪指標だけ**で構成します。')
w()
w('| 指標 | 出所 | 網羅 |')
w('|---|---|---|')
w('| STRIDE `重適性`(◎/○/△) | STRIDE指数CSV 正本 [実] | **151/169頭**(空欄18頭=新潟4R新馬・全頭) |')
w('| 騎手の道悪ROI(数値) | 騎手運勢シート 2026.08.29 備考欄 [実] | **14/169頭**([不足]155頭) |')
w()
w('⚠ **[不足]155頭を「道悪が下手」に変換していません。**未取得は未取得のままです。')
w()
w('---')
w()
w('## 1. レース別 識別力 — 稍重が着差をつける余地があるか')
w()
w('同じ稍重でも、**出走馬の大半が重巧者なら道悪は差を生みません**。')
w('レースごとに「重適性の分布がどれだけ割れているか」を先に測りました。')
w()
w('| R | 条件 | 頭数 | ◎ | ○ | △ | 空 | ◎○率 | 識別力 | 読み |')
w('|---|---|---:|---:|---:|---:|---:|---:|---|---|')
for o in B:
    c, known, rate, lv, why = disc[o['r']]
    rs = f'{rate:.1f}%' if rate is not None else '—'
    w(f"| **{o['r']}** | {o['cls']} {o['td']}{o['dist']} | {len(o['rows'])} | {c['◎']} | {c['○']} | {c['△']} | {c['']} | {rs} | **{lv}** | {why} |")
w()
w('### 読み方')
w()
w('- **識別力 高(5R・10R・11R)** … 重巧者が少数。`◎`/`○`を持つ馬に**相対的な優位**が立ちます。')
w('- **識別力 低(8R ＢＳＮ賞L)** … 11頭中10頭が`◎`または`○`。')
w('  ダート重賞級のメンバーはそもそも道悪をこなす馬が集まるため、')
w('  **稍重を材料に順位を動かす根拠になりません**。8Rは馬場更新を「中立」で扱います。')
w('- **[不足](4R 新馬)** … 全頭空欄。新馬に重適性データは存在しないため、')
w('  4Rは**馬場更新の対象外**とします([不足]を推測で埋めません)。')
w()
w('---')
w()
w('## 2. レース別オーバーレイ(支持3本以上の馬)')
w()
w('列の定義:')
w()
w('- `補正差` = 市場p3(基準複勝の逆数を3に正規化) − ドリフト補正後較正p3。**＋=市場が強気／−=市場が弱気**')
w('- `乖離` = コンピ順位 − 総合順位。**＋=指数が市場より高評価**(8/29第8報で訂正済みの正しい向き)')
w('- `重適性` = STRIDE正本 [実]／`騎手重ROI` = 運勢シート備考の数値 [実]')
w('- `判定` は**馬場のみ**の方向づけです。能力・回収率・展開を上書きしません(ファクター優先順位 能力>運勢>回収率>展開馬場>調教>補強>オッズ)')
w()
for o in B:
    R = NI[o['r']]
    c, known, rate, lv, why = disc[o['r']]
    cr = {h['uma']: h['compi_rank'] for h in R['horses']}
    tr = avg_rank(R['horses'])
    sel = sorted([r for r in o['rows'] if r['nsup'] >= 3], key=lambda z: -z['nsup'])
    if not sel: continue
    w(f"### 新潟{o['r']}R {o['cls']} {o['td']}{o['dist']}m {len(o['rows'])}頭 — 識別力**{lv}**")
    w()
    w(f"c1={o['c1']} / {o['pattern']} / ONE_HOLE={o['one']} / 荒れ{o['haran']}")
    w()
    w('| 馬番 | 馬名 | 騎手 | 基準人気 | 補正差 | 乖離 | 支持 | 重適性 | 脚質 | 出遅 | 騎手重ROI | 判定 |')
    w('|---:|---|---|---:|---:|---:|---:|:-:|:-:|---:|---:|---|')
    for r in sel:
        u = r['uma']
        hs = hosei(R, u, r['ninki'])
        kai = (cr[u] - tr[u]) if cr.get(u) is not None and tr.get(u) is not None else None
        ok = f"{r['okure']:.0f}%" if r['okure'] is not None else '—'
        okm = f"⚠{ok}" if (r['okure'] is not None and r['okure'] >= 40) else ok
        jr = str(r['jockey_wet_roi']) if r['jockey_wet_roi'] else '—'
        hsx = f'{hs:+.1f}pt' if hs is not None else '—'
        kax = (f'{kai:+.1f}' if abs(kai - round(kai)) > 1e-9 else f'{kai:+.0f}') if kai is not None else '—'
        w(f"| {u} | {r['name']} | {r['jockey']} | {r['ninki']} | {hsx} | {kax} | {r['nsup']} | "
          f"{r['omo'] or '[不足]'} | {r['kyakusitu'] or '—'} | {okm} | {jr} | {judge(r, lv)} |")
    w()
open('/tmp/claude-0/-home-user-github-com-new/47c1892c-ddc4-50e4-8b6f-3403a9782673/scratchpad/09_body.md','w').write('\n'.join(L))
print('\n'.join(L[:60]))
print('...lines:', len(L))
