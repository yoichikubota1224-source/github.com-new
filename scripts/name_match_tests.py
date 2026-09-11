# -*- coding: utf-8 -*-
"""氏名照合の回帰検査。ChatGPT r4-B3「3/4文字の略名が別名へ同時一致する」への回帰。

生成スクリプト(ledger.py)から nfkc と evaluate だけをASTで隔離して実行する。
外部検査(08b_追加確認_読取専用.py)と同じ隔離条件にそろえ、補助関数への依存が
入り込んでいないことも同時に確かめる。

  NM_LEDGER_CODE  検査する ledger.py（既定 scripts/ledger.py）
  NM_COND_CSV     同じ版の条件別台帳（あれば実データ側も検査する）
終了コードは失敗数。
"""
import ast, collections, csv, os, sys, unicodedata

CODE = os.environ.get('NM_LEDGER_CODE',
                      os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ledger.py'))
COND = os.environ.get('NM_COND_CSV')

env = {'unicodedata': unicodedata,
       'COL': {'umaban': 3, 'age': 9, 'sex': 8, 'waku': 22, 'jockey': 10, 'trainer': 12, 'name': 7},
       'T': 'TRUE', 'F': 'FALSE', 'U': 'UNKNOWN'}
tree = ast.parse(open(CODE, encoding='utf-8-sig').read())
for node in tree.body:
    if isinstance(node, ast.FunctionDef) and node.name in {'nfkc', 'evaluate'}:
        exec(compile(ast.Module(body=[node], type_ignores=[]), 'isolated', 'exec'), env)
if 'evaluate' not in env:
    raise SystemExit('evaluate を隔離できない（補助関数へ依存している可能性）')

def probe(op, want, got, official=None, horse='検査馬名', entry_horse='検査馬名', clash=False):
    """合成入力。実在の馬・騎手ではない。"""
    idx = 10 if op == 'jockey_eq' else 12
    r = [''] * 33
    for i, v in {3: '1', 7: entry_horse, 8: '牡', 9: '3', 22: '1', idx: got}.items():
        r[i] = v
    meta = {'n_csv': 16}
    if official is not None:
        meta['正式名'] = {1: {'馬名': horse, '騎手': official, '調教師': official,
                           '衝突': clash}}
    return env['evaluate'](op, want, r, None, None, meta)

CASES = [
    # (ラベル, 条件名, 出走表名, 正式名, 期待)
    ('空欄entry',        '検査名甲',   '',           None,         'UNKNOWN'),
    ('空欄rule',         '',           '検査名甲',   None,         'UNKNOWN'),
    ('2文字prefix',      '検査名甲',   '検査',       None,         'UNKNOWN'),
    ('完全一致',         '検査名甲',   '検査名甲',   None,         'TRUE'),
    ('完全不一致',       '検査名甲',   '別検査名',   None,         'FALSE'),
    ('3文字衝突_甲',     '検査名甲',   '検査名',     None,         'UNKNOWN'),
    ('3文字衝突_乙',     '検査名乙',   '検査名',     None,         'UNKNOWN'),
    ('4文字衝突_甲',     '検査氏名甲', '検査氏名',   None,         'UNKNOWN'),
    ('4文字衝突_乙',     '検査氏名乙', '検査氏名',   None,         'UNKNOWN'),
    # 正式名が引ければ一意に解ける
    ('正式名で一致',     '検査氏名甲', '検査氏名',   '検査氏名甲', 'TRUE'),
    ('正式名で不一致',   '検査氏名乙', '検査氏名',   '検査氏名甲', 'FALSE'),
    ('正式名が別表記',   '検査氏名甲', 'ミシェル',   'Ｍ．ミシェル', 'FALSE'),
    ('正式名と無関係',   '検査氏名甲', '別表記',     '検査氏名甲', 'UNKNOWN'),
    # 切られた表記が条件名と一致しても、正式名が別人なら一致にしない
    ('切詰め同一_別人',  '検査氏名',   '検査氏名',   '検査氏名甲', 'FALSE'),
]
# 結合キー(馬名)が合わないときは、原略名の完全一致へ戻さずその場で止める
JOIN_CASES = [
    ('結合_馬名一致',     '検査氏名', '検査氏名', '検査氏名甲', '照合対象馬', '照合対象馬', False, 'FALSE'),
    ('結合_馬名不一致',   '検査氏名', '検査氏名', '検査氏名甲', '別の馬',     '照合対象馬', False, 'UNKNOWN'),
    ('結合_正式名側が空', '検査氏名', '検査氏名', '',           '別の馬',     '照合対象馬', False, 'TRUE'),
    ('結合_キーが一意でない', '検査氏名', '検査氏名', '検査氏名甲', '照合対象馬', '照合対象馬', True, 'UNKNOWN'),
]

results = []
def check(no, name, ok, detail):
    results.append((no, name, ok, detail))

n = 0
for op in ('jockey_eq', 'trainer_eq'):
    for label, want, got, official, expected in CASES:
        n += 1
        v = probe(op, want, got, official)
        check(f'N{n:02d}', f'{op} {label}', v[0] == expected,
              f'条件={want or "(空)"} 出走表={got or "(空)"} 正式名={official or "(未取得)"} '
              f'→ {v[0]}（期待{expected}） 理由={v[5]}')

for op in ('jockey_eq', 'trainer_eq'):
    for label, want, got, official, ohorse, ehorse, clash, expected in JOIN_CASES:
        n += 1
        v = probe(op, want, got, official, horse=ohorse, entry_horse=ehorse, clash=clash)
        check(f'N{n:02d}', f'{op} {label}', v[0] == expected,
              f'条件={want} 出走表={got} 正式名={official or "(空)"} '
              f'正式名側の馬名={ohorse} 出走表の馬名={ehorse} 結合衝突={clash} '
              f'→ {v[0]}（期待{expected}） 理由={v[5]}')

# 実データ側: 前方一致だけでTRUE/FALSEにした行が残っていないこと
if COND and os.path.exists(COND):
    rows = [r for r in csv.DictReader(open(COND, encoding='utf-8-sig'))
            if r['条件演算子'] in ('jockey_eq', 'trainer_eq')]
    bad = [r for r in rows if '前方一致' in r['観測値'] and r['判定'] != 'UNKNOWN']
    tags = collections.Counter(r['出所タグ'] for r in rows)
    check(f'N{n+1:02d}', '実データに前方一致で確定した氏名条件がない', not bad,
          f'氏名条件{len(rows)}行 / 前方一致で確定={len(bad)} / 出所タグ={dict(tags)}')
else:
    # 入力未受領は「検査していない(INPUT_HOLD)」。欠陥を検出したFAILとは区別する。
    check(f'N{n+1:02d}', '実データに前方一致で確定した氏名条件がない', 'HOLD',
          'NM_COND_CSV 未設定。条件別台帳が無いため実データ側は検査していない')

w = max(len(x) for _, x, _, _ in results)
print('=' * (w + 40))
print('氏名照合 回帰検査（合成入力。実在の馬・騎手ではない）')
print('=' * (w + 40))
fail = hold = 0
for no, name, ok, detail in results:
    if ok == 'HOLD':
        hold += 1; mark = 'HOLD'
    elif ok:
        mark = 'PASS'
    else:
        fail += 1; mark = '*FAIL*'
    print(f"{no} {mark:<7} {name:<{w}}  {detail}")
print('-' * (w + 40))
print(f'{len(results)}件中 PASS {len(results)-fail-hold} / FAIL {fail} / INPUT_HOLD {hold}')
if hold:
    print('INPUT_HOLD は入力が未受領で検査していない項目。合格でも不合格でもない。')
sys.exit(fail)
