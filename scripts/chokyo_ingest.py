#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""坂路/ウッドの週次ラップCSVを「1日1ファイル」の正規化レイアウトへ取り込む。

週次ファイルは範囲が重複する(例: 坂路7.18.csv / 坂路7.18－7.24merged.csv /
坂路7.18-7.25merged.csv)ので、週次のまま置くと毎週の追加が冪等にならない。
そこで日付単位に割り直し、行レベルで重複排除する。

    data/chokyo/hanro/YYYYMMDD.csv   坂路 ヘッダ無し18列 CP932
    data/chokyo/wood/YYYYMMDD.csv    ウッド ヘッダ有り40列 CP932
    data/chokyo/SHA256SUMS.txt
    data/chokyo/coverage.json        収録日・本数・欠落の機械可読な一覧

方針:
  * 種別はファイル名ではなく中身で判定する(名前の付け間違いが実在するため)。
  * CP932 のまま保存する(既存スクリプトが cp932 でデコードしている)。
  * 復号できないバイトは surrogateescape で持ち回り、バイト単位で保存する。
  * 既に正規化済みの hanro/ wood/ も入力として読み直すので、毎週の追加は追記になる。
  * 同一キーで内容が違う行は握りつぶさず CONFLICT として報告する。
  * ウッドが無い日を 0 本に化けさせない。coverage.json では "[不足]" と書く。

使い方:
    python3 scripts/chokyo_ingest.py                 # 既定の置き場から取り込む
    python3 scripts/chokyo_ingest.py --src DIR       # 入力を差し替える
    python3 scripts/chokyo_ingest.py --dry-run       # 書かずに報告だけ
    python3 scripts/chokyo_ingest.py --no-carry      # 既存の正規化済みを引き継がず作り直す
"""
import argparse
import collections
import csv
import glob
import hashlib
import io
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SRC = '/tmp/claude-0/-home-user-github-com-new/47c1892c-ddc4-50e4-8b6f-3403a9782673/scratchpad/dl'
DEFAULT_DEST = os.path.join(REPO, 'data', 'chokyo')

HANRO, WOOD = 'HANRO', 'WOOD'
SUBDIR = {HANRO: 'hanro', WOOD: 'wood'}
NCOL = {HANRO: 18, WOOD: 40}
# 重複排除のキー(列番号)。坂路=調教場/日付/時刻/馬名、ウッド=場所/コース/年月日/時刻/馬名。
KEYCOL = {HANRO: (0, 1, 3, 4), WOOD: (0, 1, 3, 5, 6)}
DATECOL = {HANRO: 1, WOOD: 3}
# 並べ替え用: (場, コース, 時刻, 馬名)
SORTCOL = {HANRO: (0, None, 3, 4), WOOD: (0, 1, 5, 6)}
NAMECOL = {HANRO: 4, WOOD: 6}
# 報告用の列名。坂路はヘッダが無いので定義から起こす。
# 8列目は README では「クラス」だが、値が 0/170/400/900/2050 と JRA の収得賞金(万円)そのもので、
# 同一馬・同一日のウッド10列目(収得賞金)とも一致する。実体は収得賞金とみて報告する。
HANRO_COLS = ['調教場', '日付', '曜日', '時刻', '馬名', 'Ｃ', '性別', '年齢', '収得賞金(README上はクラス)',
              '調教師', '4F', '3F', '2F', '1F', 'ラップ1', 'ラップ2', 'ラップ3', 'ラップ4']


# ---------------------------------------------------------------- 入出力の下ごしらえ

def read_csv_bytes(path):
    """CP932 のまま読み、復号できないバイトは surrogateescape で保持する。"""
    raw = open(path, 'rb').read()
    strict = True
    try:
        raw.decode('cp932')
    except UnicodeDecodeError:
        strict = False
    text = raw.decode('cp932', errors='surrogateescape')
    rows = [r for r in csv.reader(io.StringIO(text)) if r and any(c.strip() for c in r)]
    return raw, rows, strict


def encode_rows(rows):
    """元データの方言に合わせて書き出す。空白を含む欄だけを引用符で囲む。

    取り込み元38本のうち36本がこの方言。残る2本は引用符を一切使わない別方言だが、
    csv として読めば同じ値なので、出力はこちらに揃える。
    """
    out = []
    for r in rows:
        cells = []
        for c in r:
            if ' ' in c or '"' in c or ',' in c or '\r' in c or '\n' in c:
                cells.append('"%s"' % c.replace('"', '""'))
            else:
                cells.append(c)
        out.append(','.join(cells))
    return ('\r\n'.join(out) + '\r\n').encode('cp932', errors='surrogateescape')


def detect_kind(rows):
    """中身で坂路/ウッドを判定する。ファイル名は信用しない。"""
    if rows and rows[0] and rows[0][0].strip() == '場所':
        return WOOD
    width = max((len(r) for r in rows), default=0)
    return WOOD if width >= 35 else HANRO


DATE_RE = re.compile(r'^\d{8}$')


def valid_date(d):
    if not DATE_RE.match(d):
        return False
    y, m, dd = int(d[:4]), int(d[4:6]), int(d[6:])
    return 2000 <= y <= 2100 and 1 <= m <= 12 and 1 <= dd <= 31


def time_key(t):
    m = re.match(r'^\s*(\d{1,2})\s*:\s*(\d{1,2})', t or '')
    return (0, int(m.group(1)) * 60 + int(m.group(2))) if m else (1, 0)


def sort_key(kind, row):
    p, c, t, n = SORTCOL[kind]
    return (row[p], row[c] if c is not None else '', time_key(row[t]), row[n], tuple(row))


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def write_if_changed(path, data, dry):
    """中身が同じなら触らない(mtime も動かさない)。冪等性のため。"""
    if os.path.exists(path) and open(path, 'rb').read() == data:
        return False
    if not dry:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as fh:
            fh.write(data)
    return True


# ---------------------------------------------------------------- 本体

def main():
    ap = argparse.ArgumentParser(description='坂路/ウッドCSVを日付単位の正規化レイアウトへ取り込む')
    ap.add_argument('--src', default=DEFAULT_SRC, help='取り込み元ディレクトリ(*.csv を全部読む)')
    ap.add_argument('--dest', default=DEFAULT_DEST, help='正規化レイアウトの置き場')
    ap.add_argument('--dry-run', action='store_true', help='書き込まずに報告だけ')
    ap.add_argument('--no-carry', action='store_true',
                    help='既存の hanro/ wood/ を入力に含めない(作り直し)')
    args = ap.parse_args()
    dry = args.dry_run

    # --- 入力を集める。既存の正規化済みも読み直すので毎週の追加は追記になる。
    inputs = []
    seen_path = set()

    def add(paths, label):
        for p in sorted(paths):
            rp = os.path.realpath(p)
            if rp in seen_path:
                continue
            seen_path.add(rp)
            inputs.append((p, label))

    add(glob.glob(os.path.join(args.src, '*.csv')), 'src')
    add(glob.glob(os.path.join(args.dest, '*.csv')), 'weekly')       # 旧レイアウトの週次CSV
    if not args.no_carry:
        add(glob.glob(os.path.join(args.dest, SUBDIR[HANRO], '*.csv')), 'kept')
        add(glob.glob(os.path.join(args.dest, SUBDIR[WOOD], '*.csv')), 'kept')

    if not inputs:
        sys.exit('入力CSVが1本も見つからない: %s' % args.src)

    # store[kind][key] = {row_tuple: [出所ファイル名...]}
    store = {HANRO: collections.OrderedDict(), WOOD: collections.OrderedDict()}
    raw_rows = collections.Counter()
    nameless = collections.Counter()
    dropped_dup = collections.Counter()
    conflicts = []
    mismatches = []
    identical_pairs = []
    bad_decode = []
    bad_rows = collections.Counter()
    bad_examples = []
    wood_headers = collections.Counter()
    by_hash = {}
    file_report = []

    for path, label in inputs:
        base = os.path.basename(path)
        raw, rows, strict = read_csv_bytes(path)
        if not rows:
            continue
        if not strict:
            bad_decode.append(base)

        digest = hashlib.sha256(raw).hexdigest()
        if digest in by_hash and by_hash[digest] != base:
            identical_pairs.append((by_hash[digest], base))   # 名前違い・中身同一 = 誤アップロードの疑い
        by_hash.setdefault(digest, base)

        kind = detect_kind(rows)

        # 名前と中身の不一致(ユーザの誤アップロード)を明示的に拾う
        if base.startswith('ウッド') and kind == HANRO:
            mismatches.append((base, 'ウッド', HANRO))
        elif base.startswith('坂路') and kind == WOOD:
            mismatches.append((base, '坂路', WOOD))

        body = rows
        if kind == WOOD:
            wood_headers[tuple(rows[0])] += 1
            body = rows[1:]

        need = NCOL[kind]
        for r in body:
            if len(r) < need:
                bad_rows['列不足'] += 1
                if len(bad_examples) < 5:
                    bad_examples.append((base, '列不足', r[:6]))
                continue
            row = tuple(r[:need])
            d = row[DATECOL[kind]].strip()
            if not valid_date(d):
                bad_rows['日付不正'] += 1
                if len(bad_examples) < 5:
                    bad_examples.append((base, '日付不正', list(row[:6])))
                continue
            raw_rows[kind] += 1
            if row[NAMECOL[kind]].strip():
                key = tuple(row[i] for i in KEYCOL[kind])
            else:
                # 馬名が空の行が実在する(坂路517本/ウッド28本)。規定のキーだと
                # 「同じ場・同じ日・同じ時刻の別馬」が1本に潰れて消えるので、
                # 名無しの行だけは行全体をキーにして取りこぼさない。
                key = ('\x00NONAME',) + row
                nameless[kind] += 1
            slot = store[kind].setdefault(key, collections.OrderedDict())
            if row in slot:
                slot[row].append(base)
                dropped_dup[kind] += 1                 # 同一キー・同一内容 → 黙って1本に
            else:
                if slot:
                    dropped_dup[kind] += 1             # 同一キー・別内容 → 1本に寄せるが下で報告
                slot[row] = [base]

    # --- CONFLICT: 同一キーで内容が違う行
    for kind in (HANRO, WOOD):
        for key, slot in store[kind].items():
            if len(slot) > 1:
                variants = sorted(slot.items())
                conflicts.append((kind, key, variants))

    # --- 採用行を決める。入力の並び順やファイル名に依存させない(冪等性のため)。
    #     空欄が少ない行(＝情報が多い行)を優先し、同点なら辞書順で最小の行に固定する。
    #     どちらが新しい取得時点かは中身からは判らないので、これ以上は踏み込まない。
    def completeness(row):
        return (sum(1 for c in row if not c.strip()), row)

    chosen = {HANRO: [], WOOD: []}
    for kind in (HANRO, WOOD):
        for key, slot in store[kind].items():
            chosen[kind].append(min(slot, key=completeness))

    # --- ウッドのヘッダ
    wood_header = None
    if wood_headers:
        top = max(wood_headers.values())
        wood_header = sorted(k for k, v in wood_headers.items() if v == top)[0]

    # --- 日付ごとに束ね、書き出す
    days = {HANRO: collections.defaultdict(list), WOOD: collections.defaultdict(list)}
    for kind in (HANRO, WOOD):
        for row in chosen[kind]:
            days[kind][row[DATECOL[kind]].strip()].append(row)

    written, unchanged, removed = [], [], []
    for kind in (HANRO, WOOD):
        d = os.path.join(args.dest, SUBDIR[kind])
        want = set()
        for date, rows in sorted(days[kind].items()):
            rows.sort(key=lambda r: sort_key(kind, r))
            out = ([list(wood_header)] if kind == WOOD and wood_header else []) + [list(r) for r in rows]
            path = os.path.join(d, date + '.csv')
            want.add(path)
            (written if write_if_changed(path, encode_rows(out), dry) else unchanged).append(path)
        for stale in sorted(glob.glob(os.path.join(d, '*.csv'))):
            if stale not in want:
                removed.append(stale)
                if not dry:
                    os.remove(stale)

    # --- 旧レイアウトの週次CSVは取り込み済みなので消す
    for p in sorted(glob.glob(os.path.join(args.dest, '*.csv'))):
        removed.append(p)
        if not dry:
            os.remove(p)

    # --- coverage.json / SHA256SUMS.txt
    all_days = sorted(set(days[HANRO]) | set(days[WOOD]))
    wood_missing = [d for d in all_days if d not in days[WOOD]]
    hanro_missing = [d for d in all_days if d not in days[HANRO]]

    cov = {
        'layout': 'data/chokyo/{hanro,wood}/YYYYMMDD.csv',
        'encoding': 'cp932',
        'generator': 'scripts/chokyo_ingest.py',
        'note': [
            'ウッドが無い日は 0 本ではなく "[不足]"。データが無いことを 0 に変換してはならない。',
            '月曜は調教が無いので日付の切れ目は正常。',
        ],
        'days': [
            {
                'date': d,
                'hanro': len(days[HANRO][d]) if d in days[HANRO] else '[不足]',
                'wood': len(days[WOOD][d]) if d in days[WOOD] else '[不足]',
            }
            for d in all_days
        ],
        'summary': {
            'first_date': all_days[0] if all_days else None,
            'last_date': all_days[-1] if all_days else None,
            'days_total': len(all_days),
            'hanro': {'days': len(days[HANRO]), 'rows': sum(len(v) for v in days[HANRO].values())},
            'wood': {'days': len(days[WOOD]), 'rows': sum(len(v) for v in days[WOOD].values())},
        },
        'wood_missing_days': wood_missing,
        'hanro_missing_days': hanro_missing,
    }
    cov_bytes = (json.dumps(cov, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode('utf-8')
    cov_path = os.path.join(args.dest, 'coverage.json')
    (written if write_if_changed(cov_path, cov_bytes, dry) else unchanged).append(cov_path)

    if not dry:
        lines = []
        for p in sorted(glob.glob(os.path.join(args.dest, '**', '*'), recursive=True)):
            if not os.path.isfile(p) or os.path.basename(p) == 'SHA256SUMS.txt':
                continue
            lines.append('%s  %s' % (sha256_file(p), os.path.relpath(p, args.dest).replace(os.sep, '/')))
        write_if_changed(os.path.join(args.dest, 'SHA256SUMS.txt'),
                         ('\n'.join(lines) + '\n').encode('utf-8'), dry)

    # ---------------------------------------------------------------- 報告
    W = lambda s='': print(s)
    W('=' * 78)
    W('調教CSV取り込み  src=%s' % args.src)
    W('                 dest=%s%s' % (args.dest, '   [DRY-RUN 書き込みなし]' if dry else ''))
    W('=' * 78)
    W('読み込んだファイル %d本 (取り込み元 %d / 旧週次 %d / 既存の正規化済み %d)'
      % (len(inputs),
         sum(1 for _, l in inputs if l == 'src'),
         sum(1 for _, l in inputs if l == 'weekly'),
         sum(1 for _, l in inputs if l == 'kept')))
    W()
    W('  種別      読み込み行   重複排除で落ちた   採用行   収録日数')
    for kind in (HANRO, WOOD):
        W('  %-8s %10d %16d %9d %9d'
          % (kind, raw_rows[kind], dropped_dup[kind], len(chosen[kind]), len(days[kind])))
    W('  %-8s %10d %16d %9d %9d'
      % ('合計', sum(raw_rows.values()), sum(dropped_dup.values()),
         len(chosen[HANRO]) + len(chosen[WOOD]), len(all_days)))
    W()
    if sum(nameless.values()):
        W('  うち馬名が空の行: 坂路 %d本 / ウッド %d本 '
          '(規定のキーでは別馬が潰れるため、この行だけ行全体をキーにした)'
          % (nameless[HANRO], nameless[WOOD]))
    W()
    W('収録範囲: %s 〜 %s  (%d日)' % (cov['summary']['first_date'], cov['summary']['last_date'], len(all_days)))
    W('  坂路 %d日 / ウッド %d日' % (len(days[HANRO]), len(days[WOOD])))

    W()
    if mismatches:
        for base, named, actual in mismatches:
            W('⚠ 名前と中身が不一致: %s は名前が「%s」だが中身は %s。中身に従って取り込んだ。'
              % (base, named, actual))
    else:
        W('名前と中身の不一致: なし')

    if identical_pairs:
        for a, b in identical_pairs:
            W('⚠ バイト完全一致の重複ファイル: %s == %s' % (a, b))

    if bad_decode:
        W('⚠ CP932 として復号できないバイトを含む: %s (surrogateescape でバイトのまま保持)'
          % ', '.join(bad_decode))

    if bad_rows:
        W('⚠ 取り込めなかった行: %s' % dict(bad_rows))
        for base, why, ex in bad_examples:
            W('    %s [%s] %s' % (base, why, ex))

    W()
    W('CONFLICT (同一キーで内容が違う行) %d件' % len(conflicts))
    if conflicts:
        # どの列が食い違っているかで分類する。列が1つだけなら原因が特定できる。
        klass = collections.defaultdict(list)
        for kind, key, variants in conflicts:
            rows = [r for r, _ in variants]
            diff = tuple(i for i in range(NCOL[kind])
                         if len({r[i] for r in rows}) > 1)
            klass[(kind, diff)].append((key, variants))
        for (kind, diff), items in sorted(klass.items(), key=lambda kv: -len(kv[1])):
            names = (HANRO_COLS if kind == HANRO else
                     list(wood_header) if wood_header else [])
            label = ', '.join('%d:%s' % (i, names[i] if i < len(names) else '?') for i in diff) or '(差分なし)'
            W('  [%s] 食い違う列 %s … %d件' % (kind, label, len(items)))
            key0, variants0 = items[0]
            W('      例 %s' % ' / '.join(key0))
            for row, srcs in variants0:
                W('         %s   ← %s'
                  % (' | '.join('%s=%s' % (names[i] if i < len(names) else i, row[i]) for i in diff),
                     ','.join(sorted(set(srcs)))))
        W('  → いずれもラップ/タイム列の食い違いではない(収得賞金・調教師などの属性列のみ)。')
        W('  → 採用行は入力順に依存しないよう「空欄が少ない行、同点なら辞書順で最小」に固定した。')

    W()
    W('ウッドが欠けている日 %d日:' % len(wood_missing))
    for d in wood_missing:
        W('  %s  坂路 %d本 / ウッド [不足]' % (d, len(days[HANRO].get(d, []))))
    if hanro_missing:
        W('坂路が欠けている日 %d日: %s' % (len(hanro_missing), ', '.join(hanro_missing)))

    W()
    W('書き出し: 新規/更新 %d本 / 変更なし %d本 / 削除 %d本'
      % (len(written), len(unchanged), len(removed)))
    for p in removed:
        W('  削除 %s' % os.path.relpath(p, REPO))
    return 0


if __name__ == '__main__':
    sys.exit(main())
