#!/usr/bin/env python3
# §4/§5 結合監査。
#
# 指示書は主キーに血統登録番号を求めているが、現データでは実装できない:
#   - 坂路の週次CSV(18列)に血統登録番号が無い(ウッド40列にはある)
#   - 結果側(netkeiba JSON / JRA公式CSV)のどちらにも血統登録番号が無い
# したがって本監査は「馬名+競走日+競走ID」で結合し、**その曖昧さを定量化する**。
# 血統登録番号が両側に揃うまで、これは暫定である。
import csv, io, json, os, glob, collections, datetime, hashlib

GH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CH = os.path.join(GH, 'data', 'chokyo')


def read(p):
    raw = open(p, 'rb').read()
    for enc in ('cp932', 'utf-8-sig', 'utf-8'):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            pass
    return raw.decode('cp932', errors='surrogateescape'), 'cp932/surrogateescape'


def load_training():
    """正規化済みの日別ファイルを読み、追切1本=1レコードにする。"""
    recs = []
    for p in sorted(glob.glob(f'{CH}/hanro/*.csv')):
        t, _ = read(p)
        for r in csv.reader(io.StringIO(t)):
            if len(r) > 13 and r[1].isdigit():
                recs.append(dict(course='坂路', place=r[0], date=r[1], time=r[3], name=r[4],
                                 f1=r[13], ped=''))
    for p in sorted(glob.glob(f'{CH}/wood/*.csv')):
        t, _ = read(p)
        rows = [r for r in csv.reader(io.StringIO(t)) if r]
        body = rows[1:] if rows and rows[0][0] == '場所' else rows
        for r in body:
            if len(r) > 31 and r[3].isdigit():
                recs.append(dict(course='ウッド', place=r[0], date=r[3], time=r[5], name=r[6],
                                 f1=r[21], ped=r[31]))
    return recs


def d(s):
    return datetime.date(int(s[:4]), int(s[4:6]), int(s[6:]))


def weeks(raceday):
    """W0=レース直前の月〜金 / W1=その前週の月〜金。いずれも 調教日 < 競走日 を満たす。"""
    mon = raceday - datetime.timedelta(days=raceday.weekday())
    w0 = {(mon + datetime.timedelta(days=i)) for i in range(5)}
    w1 = {(mon - datetime.timedelta(days=7 - i)) for i in range(5)}
    return {x for x in w0 if x < raceday}, {x for x in w1 if x < raceday}


def load_results():
    rows = []
    for p in sorted(glob.glob(f'{GH}/data/results/official_results_*.csv')):
        for r in csv.DictReader(io.StringIO(open(p, encoding='utf-8-sig').read())):
            rows.append(dict(day=r['date'], venue=r['track'], race=int(r['race_no']),
                             name=r['horse_name'], status=r['status'],
                             chaku=int(float(r['finish_numeric'])) if r['finish_numeric'] else None,
                             pop=int(float(r['popularity'])) if r['popularity'] else None,
                             odds=None, src='JRA公式'))
    for day, path in [('2026-08-16', f'{GH}/predictions/20260816/results確定_20260816.json'),
                      ('2026-08-22', f'{GH}/predictions/20260823/results_20260822.json'),
                      ('2026-08-23', f'{GH}/predictions/20260823/results_20260823.json')]:
        j = json.load(open(path))
        for x in (j if isinstance(j, list) else list(j.values())):
            for h in x['horses']:
                rows.append(dict(day=day, venue=x['venue'], race=x['r'], name=h['name'],
                                 status='COMPLETED' if h.get('chakujun') is not None else '取消等',
                                 chaku=h.get('chakujun'), pop=h.get('pop'),
                                 odds=h.get('odds'), src='netkeiba'))
    return rows


def main():
    tr = load_training()
    res = load_results()
    bydate = collections.defaultdict(list)
    for x in tr:
        bydate[d(x['date'])].append(x)

    # --- duplicate_audit: 同一窓の中で同名馬が複数いるか(馬名結合の曖昧さ) ---
    dup_rows = []
    # --- join_audit / unmatched ---
    join_rows, unmatched = [], []
    joined = []

    for day in sorted({r['day'] for r in res}):
        rd = d(day.replace('-', ''))
        w0, w1 = weeks(rd)
        pool0 = [x for xs in (bydate[k] for k in w0) for x in xs]
        pool1 = [x for xs in (bydate[k] for k in w1) for x in xs]
        by0 = collections.defaultdict(list)
        for x in pool0:
            by0[x['name']].append(x)
        by1 = collections.defaultdict(list)
        for x in pool1:
            by1[x['name']].append(x)

        starters = [r for r in res if r['day'] == day and r['status'] == 'COMPLETED']
        n_join = n_h = n_w = n_ped = 0
        for r in starters:
            cand = by0.get(r['name'], [])
            if not cand:
                unmatched.append(dict(day=day, venue=r['venue'], race=r['race'], name=r['name'],
                                      pop=r['pop'], chaku=r['chaku'], reason='W0に追切なし'))
                continue
            # 同名が複数 → 曖昧。最終追切は最も遅い日、同日なら最長距離ではなく最も遅い時刻を採る
            if len({(c['course'], c['date'], c['time']) for c in cand}) > 1:
                same_day = collections.Counter(c['date'] for c in cand)
                if any(v > 1 for v in same_day.values()):
                    dup_rows.append(dict(day=day, name=r['name'], n_rows=len(cand),
                                         dates=';'.join(sorted(c['date'] for c in cand)),
                                         courses=';'.join(sorted({c['course'] for c in cand}))))
            last = max(cand, key=lambda c: (c['date'], c['time']))
            assert d(last['date']) < rd, '未来情報混入'
            prev = by1.get(r['name'], [])
            n_join += 1
            n_h += last['course'] == '坂路'
            n_w += last['course'] == 'ウッド'
            n_ped += 1 if last['ped'] else 0
            joined.append(dict(day=day, venue=r['venue'], race=r['race'], name=r['name'],
                               chaku=r['chaku'], pop=r['pop'], odds=r['odds'], src=r['src'],
                               last_course=last['course'], last_date=last['date'], last_f1=last['f1'],
                               ped=last['ped'],
                               prev_date=max((p['date'] for p in prev), default=''),
                               n_other=max(0, len(cand) - 1)))
        # 土曜単日ファイル・週次初日の点検
        sat = rd - datetime.timedelta(days=rd.weekday()) + datetime.timedelta(days=5)
        satfile_h = os.path.exists(f'{CH}/hanro/{sat.strftime("%Y%m%d")}.csv')
        satfile_w = os.path.exists(f'{CH}/wood/{sat.strftime("%Y%m%d")}.csv')
        join_rows.append(dict(race_day=day, starters=len(starters), joined=n_join,
                              unmatched=len(starters) - n_join,
                              join_rate=f'{100*n_join/max(1,len(starters)):.1f}%',
                              hanro=n_h, wood=n_w, ped_missing=n_join - n_ped,
                              w0_days=len(w0), w0_hanro_rows=sum(1 for x in pool0 if x['course'] == '坂路'),
                              w0_wood_rows=sum(1 for x in pool0 if x['course'] == 'ウッド'),
                              sat_hanro_file=satfile_h, sat_wood_file=satfile_w))

    os.makedirs(f'{GH}/reports', exist_ok=True)
    def dump(name, rows, cols):
        with open(f'{GH}/reports/{name}', 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore')
            w.writeheader()
            w.writerows(rows)
        print(f'  {name}: {len(rows)}行')

    print('=== §5 データ完全性監査 ===')
    dump('join_audit.csv', join_rows, list(join_rows[0].keys()))
    dump('unmatched_horses.csv', unmatched, ['day', 'venue', 'race', 'name', 'pop', 'chaku', 'reason'])
    dump('duplicate_audit.csv', dup_rows, ['day', 'name', 'n_rows', 'dates', 'courses'])
    json.dump(joined, open(f'{GH}/reports/joined_strict.json', 'w'), ensure_ascii=False)
    print(f'  joined_strict.json: {len(joined)}頭')

    print('\n競走日   出走  結合   未結合  結合率  坂路  ウッド 血番欠 土曜坂/ウ')
    for r in join_rows:
        print(f"  {r['race_day']} {r['starters']:>4} {r['joined']:>5} {r['unmatched']:>6}  "
              f"{r['join_rate']:>6}  {r['hanro']:>4} {r['wood']:>5} {r['ped_missing']:>5}  "
              f"{'有' if r['sat_hanro_file'] else '無'}/{'有' if r['sat_wood_file'] else '無'}")
    tot_s = sum(r['starters'] for r in join_rows); tot_j = sum(r['joined'] for r in join_rows)
    print(f"  {'合計':<10} {tot_s:>4} {tot_j:>5} {tot_s-tot_j:>6}  {100*tot_j/tot_s:>5.1f}%  "
          f"{sum(r['hanro'] for r in join_rows):>4} {sum(r['wood'] for r in join_rows):>5} "
          f"{sum(r['ped_missing'] for r in join_rows):>5}")
    print(f"\n  ⚠ 血統登録番号が取れたのは {tot_j - sum(r['ped_missing'] for r in join_rows)}/{tot_j}頭"
          f"(最終追切がウッドだった馬のみ)。坂路の週次CSVには血統登録番号が無い。")
    print(f"  ⚠ 結果側(netkeiba JSON / JRA公式CSV)には**どちらにも血統登録番号が無い**。")
    print(f"     → 指示書§4の主キー(血統登録番号)は現データでは実装不能。馬名結合の暫定である。")
    print(f"  同一窓に同名馬が複数: {len(dup_rows)}件(馬名結合が曖昧になりうるケース)")


if __name__ == '__main__':
    main()
