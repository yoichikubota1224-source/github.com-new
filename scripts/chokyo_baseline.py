#!/usr/bin/env python3
# 坂路/ウッドの生ラップCSV(その週に追い切った全馬)を読み、
# 「日 × 調教場 × コース」ごとの終い1Fベースラインを自前で作る。
# JRDBのCHA(馬場差・位置補正済み指数)が使えないので、補正を自分で作れるかを確かめるのが目的。
import csv, io, json, os, glob, sys, statistics as st, collections
import os
# 中間成果物の置き場。作業領域が変わる場合は CHOKYO_WORK で上書きする。
WORK = os.environ.get("CHOKYO_WORK", "/tmp/claude-0/-home-user-github-com-new/47c1892c-ddc4-50e4-8b6f-3403a9782673/scratchpad/rev")
os.makedirs(WORK, exist_ok=True)

# 入力CSVの置き場。既定はリポジトリに取り込んだ data/chokyo。
# レイアウトは scripts/chokyo_ingest.py が作る hanro/YYYYMMDD.csv と wood/YYYYMMDD.csv。
# 週次ファイルは範囲が重複するので、日付単位に割り直したものを読む。
SP = os.environ.get('CHOKYO_CSV',
                    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'chokyo'))
# 期間を絞りたいときは CHOKYO_SINCE / CHOKYO_UNTIL (YYYYMMDD, 両端を含む)。既定は全期間。
SINCE = os.environ.get('CHOKYO_SINCE') or '00000000'
UNTIL = os.environ.get('CHOKYO_UNTIL') or '99999999'

FILES = ([(p, 'HANRO') for p in sorted(glob.glob(os.path.join(SP, 'hanro', '*.csv')))] +
         [(p, 'WOOD') for p in sorted(glob.glob(os.path.join(SP, 'wood', '*.csv')))])
FILES = [(p, k) for p, k in FILES
         if SINCE <= os.path.splitext(os.path.basename(p))[0] <= UNTIL]
if not FILES:
    sys.exit('入力CSVが無い: %s/{hanro,wood}/*.csv  '
             '(先に python3 scripts/chokyo_ingest.py を実行すること)' % SP)


def f(x):
    try:
        v = float(x)
        return v if v > 0 else None
    except (TypeError, ValueError):
        return None


rows = []
for path, kind in FILES:
    data = open(path, 'rb').read().decode('cp932', errors='replace')
    rr = list(csv.reader(io.StringIO(data)))
    if kind == 'WOOD':
        rr = rr[1:]                                    # ウッドだけヘッダ行がある
    for r in rr:
        if kind == 'HANRO':
            # 場,日付,曜,時刻,馬名,C,性,齢,クラス,調教師,4F,3F,2F,1F,lap1..lap4
            if len(r) < 18:
                continue
            rec = dict(place=r[0], date=r[1], name=r[4], trainer=r[9], surface='坂路', course='坂路',
                       f4=f(r[10]), f3=f(r[11]), f2=f(r[12]), f1=f(r[13]))
        else:
            # 場所,コース,回り,年月日,曜日,時刻,馬名,C,性別,年齢,収得賞金,調教師,10F..1F(12..21),Lap9..Lap1(22..30)
            if len(r) < 31:
                continue
            rec = dict(place=r[0], date=r[3], name=r[6], trainer=r[11], surface='ウッド', course=r[1],
                       f4=f(r[18]), f3=f(r[19]), f2=f(r[20]), f1=f(r[21]))
        if rec['name'] and rec['date'] and rec['f1']:
            rows.append(rec)

span = ('全期間' if (SINCE, UNTIL) == ('00000000', '99999999') else f'{SINCE}〜{UNTIL}')
print(f'入力 {len(FILES)}ファイル ({span}): '
      f"坂路{sum(1 for _, k in FILES if k == 'HANRO')}日 / ウッド{sum(1 for _, k in FILES if k == 'WOOD')}日")
print(f'読み込み {len(rows)}本 (終い1Fが取れた追切のみ)')
by_day = collections.Counter((x['date'], x['place'], x['surface']) for x in rows)
print('日×場×コース種別の本数(上位10):')
for k, v in by_day.most_common(10):
    print('   ', k, v)

# --- 馬場差ベースライン: その日・その場・そのコースで追った全馬の終い1F ---
grp = collections.defaultdict(list)
for x in rows:
    grp[(x['date'], x['place'], x['surface'], x['course'])].append(x['f1'])

base = {}
for k, v in grp.items():
    if len(v) >= 20:                                   # 平均が意味を持つ最小本数
        base[k] = (st.mean(v), st.pstdev(v), len(v))

print(f'\nベースライン成立 {len(base)}群 (n>=20)')
for k in sorted(base, key=lambda k: -base[k][2])[:12]:
    m, s, n = base[k]
    print(f'   {k[0]} {k[1]:<4} {k[2]:<4} {k[3]:<3} n={n:>4}  終い1F 平均{m:5.2f} SD{s:4.2f}')

# --- 同じ日・同じ場でも、坂路とウッドで水準がまるで違うことを示す ---
print('\n【第2〜4報の交絡の確認】同一日・同一場での終い1F水準')
for d in ('20260819', '20260820', '20260821'):
    for p in ('美浦', '栗東'):
        line = []
        for k, (m, s, n) in base.items():
            if k[0] == d and k[1] == p:
                line.append(f'{k[2]}/{k[3]} 平均{m:.2f}(n={n})')
        if line:
            print(f'  {d} {p}: ' + ' | '.join(line))

ok = 0
for x in rows:
    k = (x['date'], x['place'], x['surface'], x['course'])
    if k in base:
        m, s, n = base[k]
        x['z1f'] = (x['f1'] - m) / s if s > 0 else None
        ok += x['z1f'] is not None
    else:
        x['z1f'] = None
print(f'\nz化できた追切 {ok}/{len(rows)}本')
json.dump(rows, open(WORK + '/chokyo_raw.json', 'w'), ensure_ascii=False)
