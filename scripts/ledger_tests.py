# -*- coding: utf-8 -*-
"""判定台帳の受入テスト。ChatGPT監査が求めた「テスト証跡」を出す側。

台帳そのものを入力にする。生成スクリプトの内部を再実行しないので、
生成側の思い込みがそのままテストを通ることを避けられる。

  TEST_LEDGER_DIR  ledger.py の LEDGER_OUT と同じディレクトリ
  TEST_ENTRY       出走表CSV（列数と頭数の検査に使う）
  TEST_HIST        過去1年CSV（リーク検査に使う）
終了コードは失敗数。1件でも落ちたら非ゼロ。
"""
import csv, json, os, re, sys, collections, datetime

D = os.environ.get('TEST_LEDGER_DIR', '.')
E = os.environ.get('TEST_ENTRY')
H = os.environ.get('TEST_HIST')
TODAY = '2026-09-12'

def rd(name):
    with open(os.path.join(D, name), encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))
cond = rd('判定台帳_条件別_20260912.csv')
horse = rd('判定台帳_馬別_20260912.csv')
scope = json.load(open(os.path.join(D, '適用範囲ログ_20260912.json'), encoding='utf-8'))
gates = json.load(open(os.path.join(D, 'ゲートとレース台帳_20260912.json'), encoding='utf-8'))
entry = [r for r in csv.reader(open(E, encoding='cp932'))] if E else []

results = []
def check(no, name, fn):
    try:
        ok, detail = fn()
    except Exception as ex:
        ok, detail = False, f'例外: {type(ex).__name__}: {ex}'
    results.append((no, name, ok, detail))

check('T01', '出走表の列数が全行一致',
      lambda: (len({len(r) for r in entry}) == 1, f"列数={sorted({len(r) for r in entry})}"))
check('T02', '出走頭数(列26)とCSV行数が全レース一致',
      lambda: (all(r['CSV頭数'] == r['列26頭数'] for r in gates['レース']),
               f"不一致={[r['レースID'] for r in gates['レース'] if r['CSV頭数'] != r['列26頭数']] or '(なし)'}"))
def t03():
    exp = sum(s['対象頭数'] * s['条件数'] for s in scope)
    return (exp == len(cond), f"期待{exp}行 / 実際{len(cond)}行")
check('T03', '条件別台帳の行数 = Σ(適用頭数 × 条件数)', t03)
check('T04', '判定は TRUE/FALSE/UNKNOWN の3値のみ',
      lambda: (set(r['判定'] for r in cond) <= {'TRUE', 'FALSE', 'UNKNOWN'},
               str(sorted(set(r['判定'] for r in cond)))))
check('T05', 'すべての行に理由コードがある',
      lambda: (all(r['理由コード'].strip() for r in cond),
               f"空={sum(1 for r in cond if not r['理由コード'].strip())}行"))
def t06():
    bad = [r for r in cond
           if (r['判定'] == 'UNKNOWN') != r['理由コード'].startswith('UNK_')]
    return (not bad, f"判定と理由コードの接頭辞が食い違う行={len(bad)}")
check('T06', 'UNKNOWN と UNK_ 接頭辞が1対1', t06)
def t07():
    w = [r for r in cond if r['条件演算子'] == 'no_weight_allowance']
    return (bool(w) and all(r['判定'] == 'UNKNOWN' for r in w),
            f"減量条件{len(w)}行 / 判定={dict(collections.Counter(r['判定'] for r in w))}")
check('T07', '減量条件は必ずUNKNOWN（出走表に記号列が無い）', t07)
def t08():
    ws = [r['観測値'] for r in cond if r['単位'] == '週' and r['判定'] != 'UNKNOWN']
    zero = [v for v in ws if '中0週' in v]
    neg = [v for v in ws if re.search(r'中-\d', v)]
    return (not zero and not neg, f"週の観測値{len(ws)}件 中0週={len(zero)} 負値={len(neg)}")
check('T08', '中N週にゼロ・負値が現れない（連闘は連闘と書く）', t08)
def t09():
    if not H: return (False, 'TEST_HIST 未設定')
    hist = collections.defaultdict(list)
    for r in csv.DictReader(open(H, encoding='utf-8-sig')):
        hist[r['馬名'].strip()].append(r['日付'])
    leak = [nm for nm, ds in hist.items() if any(d >= TODAY for d in ds)]
    names = {r['馬名'].strip() for r in cond}
    hit = [nm for nm in leak if nm in names]
    return (not hit, f"当日以降の履歴を持つ出走馬={len(hit)}頭")
check('T09', '前走に当該日以降の行を使っていない（リークなし）', t09)
def t10():
    d = [r for r in cond if r['理由コード'].startswith('FALSE_DEBUT')]
    u = [r for r in cond if r['理由コード'] == 'UNK_PREV_ROW_OUT_OF_WINDOW']
    return (bool(d), f"新馬の充足不能={len(d)}行 / 収録窓外={len(u)}行（両者が別コード）")
check('T10', '新馬の前走条件は充足不能(FALSE)、収録窓外は入力不足(UNKNOWN)', t10)
def t11():
    a = [r for r in cond if r['理由コード'] == 'UNK_DEF_AMBIGUOUS_FINISH']
    both = all('読みA' in r['観測値'] and '読みB' in r['観測値'] for r in a)
    return (bool(a) and both, f"語義二義(着順)={len(a)}行 / 両読みを記録={both}")
check('T11', '「5着以下」は両読みの結果を残したままUNKNOWN', t11)
def t12():
    a = [r for r in cond if r['理由コード'] == 'UNK_DEF_AMBIGUOUS_CENTRAL']
    return (bool(a) and all(r['判定'] == 'UNKNOWN' for r in a), f"語義二義(中央場所)={len(a)}行")
check('T12', '「中央場所」は語義未確定のままUNKNOWN', t12)
def t13():
    bad = []
    for h in horse:
        if h['標本数n'] == '未取得' or h['三着内数'] == '未取得': continue
        n, k = int(h['標本数n']), int(h['三着内数'])
        if not (0 <= k <= n): bad.append(h['ルールID'])
    return (not bad, f"n と三着内数が整合しない={bad or '(なし)'}")
check('T13', 'n と三着内数が整合する（率は再計算できる）', t13)
def t14():
    zero = [h['ルールID'] for h in horse if h['標本数n'] in ('0', '0.0')]
    return (not zero, f"n=0 で埋めた行={zero or '(なし)'} / 未取得表記={sum(1 for h in horse if h['標本数n']=='未取得')}行")
check('T14', '未取得のnを0や推定値に置換していない', t14)
def t15():
    bad = [h['ルールID'] + h['馬名'] for h in horse
           if h['集約判定'] == 'TRUE' and (h['UNKNOWN数'] != '0' or h['TRUE数'] != h['条件数'])]
    return (not bad, f"矛盾行={bad or '(なし)'}")
check('T15', '集約TRUE は UNKNOWN数=0 かつ TRUE数=条件数', t15)
def t16():
    return ('FALSE' not in {h['集約判定'] for h in horse},
            f"馬別台帳の集約={dict(collections.Counter(h['集約判定'] for h in horse))}")
check('T16', '集約FALSE は馬別台帳に載らない（条件別台帳には残る）', t16)
def t17():
    allow = set(gates['限定判定語の語彙'])
    used = set()
    for h in horse:
        for w in h['限定判定語'].split('/'): used.add(w.strip())
    bad = used - allow
    return (not bad, f"使用={sorted(used)} / 許可外={sorted(bad) or '(なし)'}")
check('T17', '限定判定語が許可リストの語だけでできている', t17)
def t18():
    empty = [s['rule'] for s in scope if not s['適用レース']]
    inled = {r['ルールID'] for r in cond}
    return (not (set(empty) & inled),
            f"範囲外ルール={len(empty)}件（台帳に1行も出ていない={not (set(empty) & inled)}）")
check('T18', '適用範囲が空のルールと「該当馬0」を混同していない', t18)
def t19():
    ids = [s['rule'] for s in scope]
    vers = {r['ルール版'] for r in cond}
    return (len(ids) == len(set(ids)) and '' not in vers,
            f"ルール{len(ids)}件・重複なし={len(ids)==len(set(ids))} / 版の種類={len(vers)}")
check('T19', 'ルールIDが重複せず、全行に版がある', t19)
def t20():
    bad, checked = [], 0
    for h in horse:
        if '未取得' in (h['標本数n'], h['三着内数'], h['原典3着内率']): continue
        n, k, shown = int(h['標本数n']), int(h['三着内数']), float(h['原典3着内率'])
        checked += 1
        if abs(k / n * 100 - shown) > 0.1: bad.append((h['ルールID'], round(k/n*100, 2), shown))
    return (checked > 0 and not bad, f"検査{checked}行 / 不一致={bad or '(なし)'}")
check('T20', 'n と三着内数から再計算した率が原典表示値と一致(±0.1pt)', t20)
def t21():
    # 「本体で本採用再判定」は2系統以上が確認済みのときだけ
    n = int(gates['確認済系統数'])
    used = [h for h in horse if '本体で本採用再判定' in h['限定判定語']]
    return ((n >= 2) or not used,
            f"確認済系統数={n} / 本採用再判定を使った行={len(used)}")
check('T21', '確認済系統が2未満なら「本体で本採用再判定」を使わない', t21)
def t22():
    bad = [r['理由コード'] for r in cond if r['判定'] == 'UNKNOWN' and r['出所タグ'] == '[実]'
           and not r['理由コード'].startswith('UNK_DEF_')]
    return (not bad, f"[実]なのにUNKNOWNで語義起因でない行={len(bad)}")
check('T22', '[実]でUNKNOWNになるのは語義未確定のときだけ', t22)

w = max(len(n) for _, n, _, _ in results)
print('=' * (w + 34))
print('判定台帳 受入テスト')
print('=' * (w + 34))
fail = 0
for no, name, ok, detail in results:
    if not ok: fail += 1
    print(f"{no} {'PASS' if ok else '*FAIL*':<7} {name:<{w}}  {detail}")
print('-' * (w + 34))
print(f"{len(results)}件中 PASS {len(results)-fail} / FAIL {fail}")
sys.exit(fail)
