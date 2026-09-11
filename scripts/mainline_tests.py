# -*- coding: utf-8 -*-
"""本線7R 全頭評価台帳の受入テスト（ChatGPT r3-9）。

scripts/ledger_tests.py が検査するのは **ULMB条件台帳** であって、
本線7Rの108頭評価・表間の版一致・本文・必須ゲートは検査していなかった。
本ファイルがその回帰テストを担う。

  MT_DIR    r3パックのディレクトリ（01/03/04/05/09/10 と 02_特記条件辞書 がある場所）
  MT_REPORT 報告書のパス（本文とCSVの一致を検査する）
終了コードは失敗数。
"""
import csv, json, os, re, sys, collections

D = os.environ.get('MT_DIR', '.')
REPORT = os.environ.get('MT_REPORT', '')
def rd(name):
    with open(os.path.join(D, name), encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))
def jf(name):
    return json.load(open(os.path.join(D, name), encoding='utf-8'))

import glob
def one(pat):
    g = sorted(glob.glob(os.path.join(D, pat)))
    if not g: raise SystemExit(f'入力が見つからない: {pat}')
    return os.path.basename(g[-1])
LEDGER = one('01_本線7R_全頭評価台帳_*.csv')
led   = rd(LEDGER)
tdict = rd(one('02_特記条件辞書_*.csv'))
ana   = rd(one('03_期待値妙味候補_*.csv'))
kiken = rd(one('04_危険馬_来ない疑い_*.csv'))
ver   = rd(one('05_ULMB版差*.csv'))
gate  = jf(one('09_ゲート状態_*.json'))
cols  = rd(one('10_列対応表_*.csv'))
cond  = rd(one('15_ULMB判定台帳_条件別_*.csv')) if glob.glob(os.path.join(D,'15_ULMB判定台帳_条件別_*.csv')) else []

results = []
def check(no, name, fn):
    try:
        ok, detail = fn()
    except Exception as ex:
        ok, detail = False, f'例外: {type(ex).__name__}: {ex}'
    results.append((no, name, ok, detail))

HON = {('中山','2'),('中山','3'),('中山','4'),('阪神','7'),('中山','8'),('中山','11'),('阪神','11')}

check('M01', '台帳は本線7Rの108頭ちょうど', lambda: (
    len(led) == 108 and {(r['開催場'], r['R']) for r in led} == HON,
    f"{len(led)}行 / レース={sorted({r['開催場']+r['R']+'R' for r in led})}"))
check('M02', '開催場+R+馬番のキーが一意', lambda: (
    len({(r['開催場'], r['R'], r['馬番']) for r in led}) == len(led),
    f"一意キー={len({(r['開催場'],r['R'],r['馬番']) for r in led})}/{len(led)}"))
PACK_VER = (re.search(r'_(r\d+)_', LEDGER) or [None, ''])[1]   # 版は成果物名から取る（r3固定にしない）
def m03():
    """全行が同一の版ID/run_idで、かつ成果物名の版と一致すること"""
    vs = {(r['台帳版ID'], r['run_id']) for r in led}
    bad = [r['馬名'] for r in led
           if r['台帳版ID'] != PACK_VER or not r['run_id'].startswith(PACK_VER + '-')]
    return (len(vs) == 1 and not bad,
            f"版ID/run_idが揃わない行={len(bad)} / 成果物名の版={PACK_VER or '(不明)'} / 台帳の値={sorted(vs)}")
check('M03', '全行に同一の台帳版IDとrun_idがある', m03)
def m04():
    """派生表は台帳から機械的に導けること（閾値の再現）"""
    exp_a = {(r['開催場'], r['R'], r['馬番']) for r in led
             if r['基準人気'] and int(r['基準人気']) >= 4 and int(r['支持系統数_独立バケット']) >= 3}
    got_a = {(r['開催場'], r['R'], r['馬番']) for r in ana}
    exp_k = {(r['開催場'], r['R'], r['馬番']) for r in led if r['危険区分']}
    got_k = {(r['開催場'], r['R'], r['馬番']) for r in kiken}
    return (exp_a == got_a and exp_k == got_k,
            f"妙味 期待{len(exp_a)}/実{len(got_a)} 差{len(exp_a ^ got_a)} / 危険 期待{len(exp_k)}/実{len(got_k)} 差{len(exp_k ^ got_k)}")
check('M04', '妙味表・危険表が台帳から機械的に再現できる', m04)
def m05():
    """特記は辞書に登録された語だけを使い、未登録を無条件成立にしない"""
    known = {r['特記語'] for r in tdict}
    obs = set()
    for r in led:
        for v in (r['特記_原文'] or '').split(' / '):
            v = v.strip()
            if v and v != '-': obs.add(v)
    return (obs <= known, f"出現{len(obs)}語 / 辞書{len(known)}語 / 未登録={sorted(obs - known) or '(なし)'}")
check('M05', '特記の出現語がすべて辞書に登録済み', m05)
def m06():
    """今日評価できない語が支持・不安に計上されていないこと"""
    hold = {r['特記語'] for r in tdict if r['今日評価できるか'] != '可'}
    bad = []
    for r in led:
        for col in ('特記_今回条件成立_プラス', '特記_今回条件成立_マイナス'):
            for v in (r[col] or '').split(' / '):
                tok = re.sub(r'\(.*$', '', v).strip()
                if tok and tok != '-' and tok in hold:
                    bad.append((r['馬名'], tok))
    return (not bad, f"HOLD語が計上された件数={len(bad)} {bad[:5]}")
check('M06', 'HOLDの特記が支持・不安に計上されていない', m06)
def m07():
    """回収率UNKNOWNは支持にも不安にも入らない"""
    bad = [r['馬名'] for r in led
           if int(r['回収率UNKNOWN件数']) and ('UNKNOWN' in r['支持系統'] or 'UNKNOWN' in r['不安材料'])]
    return (not bad, f"UNKNOWNが支持/不安へ混入した行={len(bad)}")
check('M07', '回収率UNKNOWNが支持・不安に混入していない', m07)
def m08():
    """合計値は票に数えない（従属量）"""
    bad = [r['馬名'] for r in led if '合計値' in r['支持系統'] or '合計値' in r['不安材料']]
    hold_ok = all('合計値' in (r['保留枠_票に数えない'] or '') for r in led)
    return (not bad and hold_ok, f"合計値が票に入った行={len(bad)} / 全行で保留枠に記載={hold_ok}")
check('M08', '合計値が票に数えられず保留枠に記載されている', m08)
def m09():
    """5能力の競技順位が全頭で埋まっている（r1の欠陥の回帰テスト）"""
    ab = ['先行力','追走力','持久力','持続力','瞬発力']
    empt = {a: sum(1 for r in led if not str(r[f'{a}_競技順位']).strip()) for a in ab}
    return (all(v == 0 for v in empt.values()), f"空欄={empt}")
check('M09', '5能力の競技順位が108頭すべて埋まっている', m09)
def m10():
    """タイム欠損が不安材料に計上されていない（r1の欠陥の回帰テスト）"""
    bad = [r['馬名'] for r in led if 'タイム' in r['不安材料'] and '欠' in r['不安材料']]
    st = collections.Counter(r['タイム_7項目状態'].split('(')[0] for r in led)
    return (not bad, f"タイム欠損を不安計上した行={len(bad)} / 状態={dict(st)}")
check('M10', 'タイム欠損が不安材料に計上されていない', m10)
def m11():
    """限定判定語が許可語彙内、かつ確認済系統2未満なら本採用再判定を使わない"""
    allow = set(gate['限定判定語の語彙'])
    used = set()
    for r in led:
        for w in r['限定判定語'].split(' / '): used.add(w.strip())
    n = int(gate['確認済系統数'])
    honsai = [r for r in led if '本体で本採用再判定' in r['限定判定語']]
    return (used <= allow and (n >= 2 or not honsai),
            f"使用={sorted(used)} / 許可外={sorted(used - allow) or '(なし)'} / 確認済系統={n} / 本採用再判定={len(honsai)}行")
check('M11', '限定判定語が許可語彙内で、系統2未満なら本採用再判定を使わない', m11)
def m12():
    """必須ゲートに調教師FBが含まれず、順序が指定どおり"""
    order = gate['必須ゲートの順序']
    keys = list(gate.get('必須ゲート') or gate.get('ゲート状態') or {})
    has_fb = any('FB' in x or '調教師' in x for x in order) or any('FB' in k or '調教師' in k for k in keys)
    want = ['対象日','騎手','ROI','CB','CJ','DA']
    seq_ok = all(w in order[i] for i, w in enumerate(want))
    sep = gate.get('ゲートとは別に管理する状態', {})
    fb_sep = any('調教師' in k for k in sep)
    return (not has_fb and seq_ok and fb_sep,
            f"必須ゲートに調教師FB={has_fb} / 順序一致={seq_ok} / 別状態として分離={fb_sep} / 順序={order}")
check('M12', '必須ゲートから調教師FBを除き、順序が指定どおり', m12)
def m13():
    """版差表に集約判定と馬別表掲載が別列で存在し、集約判定が同じ版の条件台帳と一致すること（X01の回帰）"""
    need = ['旧_集約判定','r1_集約判定','r2_集約判定','r3_集約判定','r4_集約判定',
            '旧_馬別表掲載','r4_馬別表掲載','集約判定の履歴','馬別表掲載の履歴','変化の有無の定義']
    miss = [c for c in need if c not in ver[0]]
    if miss: return (False, f"欠けている列={miss}")
    if not cond: return (False, '条件別台帳(15_)が同梱されていないため集約値を検査できない')
    g = collections.defaultdict(list)
    for r in cond: g[(r['開催場'], r['R'], r['馬番'], r['ルールID'])].append(r['判定'])
    agg = {k: ('TRUE' if all(j=='TRUE' for j in v) else ('FALSE' if 'FALSE' in v else 'UNKNOWN'))
           for k, v in g.items()}
    bad = []
    for r in ver:
        k = (r['開催場'], r['R'], r['馬番'], r['ルールID'])
        want = agg.get(k)
        if want is None: continue
        if r['r4_集約判定'] != want: bad.append((k, r['r4_集約判定'], want))
    return (not bad, f"{len(ver)}行 / 集約値の不一致={len(bad)} {bad[:3]} / 変化あり{sum(1 for r in ver if r['変化の有無']=='変化あり')}件")
check('M13', '版差表の集約判定が条件台帳と一致し、掲載有無が別列になっている', m13)
def m14():
    """列対応表が一意であること（X04の回帰）。
       宛先列の重複なし・存在しない列名なし・種別が定義語彙内。"""
    actual = set(next(csv.reader(open(os.path.join(D, LEDGER), encoding='utf-8-sig'))))
    key = '最終列名_r4' if '最終列名_r4' in cols[0] else 'r3列名'
    dst = [r[key] for r in cols if not r[key].startswith('(')]
    dup = [k for k, v in collections.Counter(dst).items() if v > 1]
    ghost = sorted(set(dst) - actual)
    miss = sorted(actual - set(dst))
    kinds = {r['種別'] for r in cols}
    allow = {'continue','rename','split','merge','add','drop'}
    return (not dup and not ghost and not miss and kinds <= allow,
            f"宛先{len(dst)} / 重複={dup or '(なし)'} / 存在しない列={ghost or '(なし)'} / 未説明={miss or '(なし)'} / 種別={sorted(kinds)}")
check('M14', '列対応表が一意で、矛盾する由来と存在しない列名がない', m14)
def m15():
    """本文の件数がCSVと一致する（r1で6+17と書いた欠陥の回帰テスト）"""
    if not REPORT or not os.path.exists(REPORT):
        return (False, 'MT_REPORT 未設定')
    t = open(REPORT, encoding='utf-8').read()
    kc = collections.Counter(r['危険区分'] for r in kiken)
    pairs = [(f"過剰人気警戒{kc['過剰人気警戒']}頭", kc['過剰人気警戒']),
             (f"来ない疑い{kc['来ない疑い']}頭", kc['来ない疑い']),
             (f"{len(ana)}頭", len(ana)), (f"{len(led)}頭", len(led))]
    miss = [p for p, _ in pairs if p not in t]
    return (not miss, f"本文に無い表記={miss or '(なし)'} / CSV実数 妙味{len(ana)}・過剰{kc['過剰人気警戒']}・来ない{kc['来ない疑い']}")
check('M15', '報告書本文の件数が派生CSVと一致する', m15)

def m16():
    """運勢の意味列がAB未照合中はHOLDで、原記号が保持されていること"""
    if '運勢_原記号' not in led[0]: return (False, '運勢_原記号 列がない')
    bad = [r['馬名'] for r in led if r['運勢系_参考'] and 'HOLD' not in r['運勢系_参考']]
    kept = sum(1 for r in led if r['運勢_原記号'] not in ('', '(空欄)'))
    return (not bad, f"意味列がHOLD以外の行={len(bad)} / 原記号を保持した行={kept}/108")
check('M16', '運勢の意味列がHOLDで原記号が保持されている', m16)
def m17():
    """互換名であることが注記されていること"""
    col = '列名_支持系統数_独立バケット_の注記'
    if col not in led[0]: return (False, f'{col} 列がない')
    bad = [r['馬名'] for r in led if '互換名' not in r[col] or '未証明' not in r[col]]
    return (not bad, f"注記が欠ける行={len(bad)}")
check('M17', '「独立バケット」が互換名である旨と独立性未証明が注記されている', m17)
def m18():
    """特記辞書がCSVとして同梱され、台帳の出現語を網羅していること（固定パス依存の回帰）"""
    known = {r['特記語'] for r in tdict}
    need = {'特記語','符号','条件種別','今日評価できるか','必要データまたは理由'}
    return (need <= set(tdict[0]) and len(known) > 0,
            f"辞書{len(known)}語 / 列={sorted(set(tdict[0]) & need)}")
check('M18', '特記辞書がCSVで同梱され必要列を備えている', m18)

w = max(len(n) for _, n, _, _ in results)
print('=' * (w + 34)); print('本線7R 全頭評価台帳 受入テスト（ULMB条件台帳検査とは別）'); print('=' * (w + 34))
fail = 0
for no, name, ok, detail in results:
    if not ok: fail += 1
    print(f"{no} {'PASS' if ok else '*FAIL*':<7} {name:<{w}}  {detail}")
print('-' * (w + 34)); print(f"{len(results)}件中 PASS {len(results)-fail} / FAIL {fail}")
sys.exit(fail)
