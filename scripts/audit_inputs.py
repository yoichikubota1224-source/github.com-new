#!/usr/bin/env python3
# §3 入力ファイル監査。
#   - ファイル名の種別(source_type)と中身の種別(detected_type)を別々に保持する
#   - errors="replace" は使わない。CP932 で読めなければ UTF-8 / UTF-8-BOM / UTF-16 を順に試し、
#     どれでも読めない場合だけ ENCODING_UNRESOLVED とする
#   - 種別不一致は QUARANTINE_TYPE_MISMATCH として隔離対象に印を付ける(正常データへ自動混入させない)
import csv, io, os, sys, glob, hashlib, json

CANDIDATE_ENCODINGS = ['cp932', 'utf-8-sig', 'utf-8', 'utf-16']


def detect_encoding(raw):
    """errors='replace' を使わず、厳密に復号できる符号化を探す。"""
    for enc in CANDIDATE_ENCODINGS:
        try:
            return enc, raw.decode(enc), None
        except (UnicodeDecodeError, UnicodeError) as e:
            last = f'{enc}: {e.reason} at byte {getattr(e, "start", "?")}'
    # どれでも読めない → 行単位でどこが壊れているかを特定する(黙って捨てない)
    bad = []
    for i, line in enumerate(raw.split(b'\r\n')):
        try:
            line.decode('cp932')
        except UnicodeDecodeError:
            bad.append(i)
    return None, None, {'reason': last, 'undecodable_lines': bad}


def detect_type(rows):
    """中身で判定する。ファイル名は見ない。"""
    if not rows:
        return None, 0, False
    has_header = rows[0] and rows[0][0] == '場所'
    body = rows[1:] if has_header else rows
    if not body:
        return None, 0, has_header
    cols = max(len(r) for r in body[:200])
    return ('wood' if (has_header or cols >= 35) else 'hanro'), cols, has_header


def source_type_from_name(name):
    if name.startswith('ウッド'):
        return 'wood'
    if name.startswith('坂路'):
        return 'hanro'
    return 'unknown'


def audit(paths):
    out = []
    for p in sorted(paths):
        raw = open(p, 'rb').read()
        name = os.path.basename(p)
        enc, text, encfail = detect_encoding(raw)
        rec = {
            'file': name,
            'bytes': len(raw),
            'sha256': hashlib.sha256(raw).hexdigest(),
            'encoding': enc or 'UNRESOLVED',
            'source_type': source_type_from_name(name),
        }
        if enc is None:
            # 復号不能でも捨てない。壊れた行だけを分離し、残りは surrogateescape で保持する
            rec['status'] = 'ENCODING_UNRESOLVED'
            rec['encoding_error'] = encfail['reason']
            rec['undecodable_lines'] = ';'.join(map(str, encfail['undecodable_lines']))
            text = raw.decode('cp932', errors='surrogateescape')
        else:
            rec['undecodable_lines'] = ''
        rows = [r for r in csv.reader(io.StringIO(text)) if r]
        dtype, cols, hdr = detect_type(rows)
        body = rows[1:] if hdr else rows
        rec['detected_type'] = dtype or 'UNKNOWN'
        rec['columns'] = cols
        rec['has_header'] = hdr
        rec['data_rows'] = len(body)
        dcol = 3 if dtype == 'wood' else 1
        dates = sorted({r[dcol] for r in body if len(r) > dcol and r[dcol].isdigit() and len(r[dcol]) == 8})
        rec['min_date'] = dates[0] if dates else ''
        rec['max_date'] = dates[-1] if dates else ''
        rec['n_dates'] = len(dates)
        if rec.get('status') != 'ENCODING_UNRESOLVED':
            rec['status'] = ('QUARANTINE_TYPE_MISMATCH'
                             if rec['source_type'] != 'unknown' and rec['source_type'] != rec['detected_type']
                             else 'OK')
        out.append(rec)
    return out


if __name__ == '__main__':
    src = sys.argv[1] if len(sys.argv) > 1 else \
        '/tmp/claude-0/-home-user-github-com-new/47c1892c-ddc4-50e4-8b6f-3403a9782673/scratchpad/dl'
    recs = audit(glob.glob(os.path.join(src, '*.csv')))

    # バイト完全一致の重複を検出する
    bysha = {}
    for r in recs:
        bysha.setdefault(r['sha256'], []).append(r['file'])
    dups = {k: v for k, v in bysha.items() if len(v) > 1}

    cols = ['file', 'bytes', 'sha256', 'encoding', 'source_type', 'detected_type', 'status',
            'columns', 'has_header', 'data_rows', 'min_date', 'max_date', 'n_dates', 'undecodable_lines']
    outp = 'reports/archive_manifest.csv'
    with open(outp, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore')
        w.writeheader()
        for r in recs:
            w.writerow(r)

    print(f'監査 {len(recs)}ファイル → {outp}\n')
    for st in ('QUARANTINE_TYPE_MISMATCH', 'ENCODING_UNRESOLVED'):
        hit = [r for r in recs if r['status'] == st]
        print(f'{st}: {len(hit)}件')
        for r in hit:
            print(f"   {r['file']}  source_type={r['source_type']} detected_type={r['detected_type']} "
                  f"enc={r['encoding']} 壊れ行={r['undecodable_lines'] or '—'}")
    print(f'\nバイト完全一致の重複: {len(dups)}組')
    for k, v in dups.items():
        print(f'   {k[:16]}…  {v}')
    enc = {}
    for r in recs:
        enc[r['encoding']] = enc.get(r['encoding'], 0) + 1
    print(f'\n文字コードの内訳: {enc}')
    print(f"種別(中身): hanro={sum(1 for r in recs if r['detected_type']=='hanro')} "
          f"wood={sum(1 for r in recs if r['detected_type']=='wood')}")
    print(f"合計データ行: {sum(r['data_rows'] for r in recs):,}")
