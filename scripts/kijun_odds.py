#!/usr/bin/env python3
# JRDB基準オッズ(単・複)を用いた穴馬抽出 — 依頼書 v1.0 の §3〜§10 を実装する。
#
# 統治:
#   SHADOW_ONLY / RULE_PROMOTION=NONE / PURCHASE_ALLOWED=NO / LIVE_PREDICTION=NOT_AUTHORIZED
#   本スクリプトは印・軸・買い目・点数・資金配分を出力しない。
#   [不足] を 0・平均・推測で埋めない。基準オッズ単独で穴馬を昇格させない。
#
# 主キー: 対象日 + racekey + 馬番   (馬名だけの結合は禁止。馬名は一致検査にのみ使う)
import csv, io, os, sys, json, math, argparse, collections

MISSING = '[不足]'


# ---------------------------------------------------------------- 入出力
def read_csv(path):
    """CP932 / UTF-8(BOM可) を厳密復号する。errors='replace' は使わない。"""
    raw = open(path, 'rb').read()
    for enc in ('utf-8-sig', 'utf-8', 'cp932'):
        try:
            return list(csv.DictReader(io.StringIO(raw.decode(enc)))), enc
        except UnicodeDecodeError:
            continue
    raise SystemExit(f'{path}: UTF-8/CP932 のいずれでも復号できない')


def num(v):
    """0・空欄・非数値は [不足] とする(0を有効値にしない)。"""
    if v is None:
        return MISSING
    s = str(v).strip().replace(',', '')
    if s in ('', '-', '--', '―', 'なし'):
        return MISSING
    try:
        f = float(s)
    except ValueError:
        return MISSING
    return MISSING if f <= 0 else f


def ratio(a, b):
    if a == MISSING or b == MISSING:
        return MISSING
    return round(a / b, 3)


def rank_of(values, key):
    """昇順順位(小さいほど1位)。[不足] は順位を付けない。"""
    ok = sorted((v for v in values if v != MISSING))
    return MISSING if key == MISSING else ok.index(key) + 1


def spearman(pairs):
    """順位相関。numpy/scipy 無しで実装。同順位は平均順位。"""
    pairs = [(a, b) for a, b in pairs if a != MISSING and b != MISSING]
    n = len(pairs)
    if n < 3:
        return MISSING
    def rk(xs):
        s = sorted(range(len(xs)), key=lambda i: xs[i])
        r = [0.0] * len(xs)
        i = 0
        while i < len(s):
            j = i
            while j + 1 < len(s) and xs[s[j + 1]] == xs[s[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                r[s[k]] = avg
            i = j + 1
        return r
    ra, rb = rk([p[0] for p in pairs]), rk([p[1] for p in pairs])
    ma, mb = sum(ra) / n, sum(rb) / n
    va = sum((x - ma) ** 2 for x in ra)
    vb = sum((x - mb) ** 2 for x in rb)
    if va == 0 or vb == 0:
        return MISSING
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    return round(cov / math.sqrt(va * vb), 3)


# ---------------------------------------------------------------- §5 人気帯
def band(pop):
    if pop == MISSING:
        return MISSING
    if pop <= 3:
        return '本命帯'
    if pop <= 6:
        return '中穴帯'
    if pop <= 12:
        return '穴馬候補帯'
    return '大穴別枠'


# ---------------------------------------------------------------- §7 単複分類
def combo_class(win_r, place_r):
    if win_r == MISSING or place_r == MISSING:
        return 'HOLD'
    hi_w, hi_p = win_r > 1.0, place_r > 1.0
    if hi_w and hi_p:
        return '単複とも基準より高い'
    if hi_w and not hi_p:
        return '単勝高・複勝低'
    if not hi_w and hi_p:
        return '単勝低・複勝高'
    return '単複とも基準より低い'


# ---------------------------------------------------------------- §8 仕分け
VERDICTS = ['能力確認済み過小評価候補', '能力確認済み・価格消化済み', '単勝側のみ価格候補',
            '複勝側のみ価格候補', '価格だけの穴', '市場拒否疑い', '本体で本採用再判定',
            'ワイド穴として照合', '薄め相手として照合', 'HOLD_MISSING', '断念疑い']


def verdict(gate_pass, combo, win_r, place_r):
    """§8 の限定判定語のみを返す。Claude単独で本採用・軸・買いは出さない。"""
    if combo == 'HOLD' or gate_pass == MISSING:
        return 'HOLD_MISSING'
    if gate_pass:
        if combo == '単複とも基準より高い':
            return '能力確認済み過小評価候補'
        if combo == '単複とも基準より低い':
            return '能力確認済み・価格消化済み'
        return '単勝側のみ価格候補' if combo == '単勝高・複勝低' else '複勝側のみ価格候補'
    else:
        if combo == '単複とも基準より高い':
            return '市場拒否疑い'
        return '価格だけの穴'


# ---------------------------------------------------------------- 本体
def build(args):
    audit = []
    kijun, enc_k = read_csv(args.kijun)
    now, enc_n = read_csv(args.now)
    de, enc_d = read_csv(args.de) if args.de else ([], MISSING)
    ability, _ = read_csv(args.ability) if args.ability else ([], MISSING)

    def key(r):
        return (r.get('対象日', '').strip(), r.get('racekey', '').strip(), str(r.get('馬番', '')).strip())

    # ---- §3 データ監査 ----
    K = {key(r): r for r in kijun}
    audit.append(('元CSVの非変更', 'PASS(読み取り専用)', len(kijun) + len(now), ''))
    audit.append(('文字コード', f'基準={enc_k} / 現在={enc_n}', 0, ''))

    dk = {r[0] for r in K}
    audit.append(('対象日一致', 'PASS' if len(dk) == 1 else 'FAIL', len(dk),
                  '' if len(dk) == 1 else f'複数日: {sorted(dk)}'))

    dup = [k for k, c in collections.Counter(key(r) for r in kijun).items() if c > 1]
    audit.append(('同一馬重複0件', 'PASS' if not dup else 'FAIL', len(dup),
                  '' if not dup else str(dup[:5])))

    # 現在オッズは時系列で複数行。最新スナップショットと前回を取る
    snaps = collections.defaultdict(list)
    for r in now:
        snaps[key(r)].append(r)
    for v in snaps.values():
        v.sort(key=lambda r: r.get('取得時刻', ''))
    notime = sum(1 for r in now if not r.get('取得時刻', '').strip())
    audit.append(('オッズ取得時刻の存在', 'PASS' if notime == 0 else 'PARTIAL', len(now) - notime,
                  '' if notime == 0 else f'時刻欠損 {notime}行'))

    only_k = set(K) - set(snaps)
    only_n = set(snaps) - set(K)
    audit.append(('racekey・馬番一致', 'PASS' if not only_k and not only_n else 'FAIL',
                  len(set(K) & set(snaps)), f'基準のみ{len(only_k)} / 現在のみ{len(only_n)}'))

    # 馬名一致(結合には使わない。検査のみ)
    namemis = []
    for k, r in K.items():
        # 最新スナップショットだけでなく全スナップショットを検査する
        # (途中の1本だけ馬名が違う取得ミスを見逃さない)
        for sn in snaps.get(k, []):
            if sn.get('馬名') and r.get('馬名') and sn['馬名'].strip() != r['馬名'].strip():
                namemis.append((k, r['馬名'], sn['馬名'], sn.get('取得時刻', '')))
                break
    audit.append(('馬名一致', 'PASS' if not namemis else 'WARN', len(K) - len(namemis),
                  '' if not namemis else str(namemis[:3])))

    # DE出走表との頭数照合・取消除外の分離
    scratched = set()
    if de:
        DE = {key(r): r for r in de}
        for k, r in DE.items():
            st = (r.get('状態') or '').strip()
            if st in ('取消', '除外', '中止'):
                scratched.add(k)
        audit.append(('全出走馬件数一致', 'PASS' if len(DE) - len(scratched) == len(K) - len(scratched & set(K))
                      else 'FAIL', len(DE), f'DE={len(DE)} 基準={len(K)}'))
        audit.append(('取消・除外の分離', 'PASS', len(scratched), ''))
    else:
        audit.append(('全出走馬件数一致', MISSING, 0, 'DE出走表が未提供'))
        audit.append(('取消・除外の分離', MISSING, 0, 'DE出走表が未提供'))

    miss_w = sum(1 for r in kijun if num(r.get('基準単勝')) == MISSING)
    miss_p = sum(1 for r in kijun if num(r.get('基準複勝')) == MISSING
                 and num(r.get('基準複勝下限')) == MISSING)
    audit.append(('基準単勝の欠損', 'PASS' if miss_w == 0 else 'PARTIAL', len(kijun) - miss_w,
                  f'欠損{miss_w}件を{MISSING}として保持'))
    audit.append(('基準複勝の欠損', 'PASS' if miss_p == 0 else 'PARTIAL', len(kijun) - miss_p,
                  f'欠損{miss_p}件を{MISSING}として保持'))

    ABI = {key(r): r for r in ability} if ability else {}
    audit.append(('能力データ', 'PASS' if ABI else MISSING, len(ABI),
                  '' if ABI else '能力CSVが未提供 → 能力ゲートは全馬 HOLD_MISSING'))

    # ---- 馬ごとの計算 ----
    rows = []
    for k, kr in K.items():
        if k in scratched:
            continue
        s = snaps.get(k, [])
        last = s[-1] if s else {}
        prev = s[-2] if len(s) >= 2 else {}
        a = ABI.get(k, {})

        bw = num(kr.get('基準単勝'))
        bp_lo = num(kr.get('基準複勝下限'))
        bp_hi = num(kr.get('基準複勝上限'))
        bp = num(kr.get('基準複勝'))
        if bp == MISSING and bp_lo != MISSING:
            bp = bp_lo if bp_hi == MISSING else round((bp_lo + bp_hi) / 2, 2)

        cw = num(last.get('現在単勝'))
        cp_lo = num(last.get('現在複勝下限'))
        cp_hi = num(last.get('現在複勝上限'))
        cp_mid = MISSING if (cp_lo == MISSING or cp_hi == MISSING) else round((cp_lo + cp_hi) / 2, 2)
        pw = num(prev.get('現在単勝'))

        rows.append(dict(
            対象日=k[0], racekey=k[1], 馬番=int(k[2]) if k[2].isdigit() else k[2],
            馬名=(kr.get('馬名') or last.get('馬名') or '').strip(),
            基準単勝=bw, 基準複勝=bp, 現在単勝=cw, 現在複勝下限=cp_lo, 現在複勝上限=cp_hi,
            現在複勝中央=cp_mid, 前回単勝=pw,
            取得時刻=(last.get('取得時刻') or MISSING).strip() or MISSING,
            単勝基準比=ratio(cw, bw),
            複勝基準比_下限=ratio(cp_lo, bp),
            複勝基準比_中央値=ratio(cp_mid, bp),
            前回比=ratio(cw, pw),
            統合能力順位=num(a.get('統合能力順位')), IDM順位=num(a.get('IDM順位')),
            タイム順位=num(a.get('タイム指数順位')), STRIDE順位=num(a.get('STRIDE総合順位')),
            運勢=(a.get('運勢') or MISSING), ROI=(a.get('ROI') or MISSING),
            展開=(a.get('展開') or MISSING), 調教=(a.get('調教') or MISSING),
        ))

    # ---- レース内順位(現在人気・基準人気・基準比順位) ----
    byrace = collections.defaultdict(list)
    for r in rows:
        byrace[(r['対象日'], r['racekey'])].append(r)

    for g in byrace.values():
        cw = [r['現在単勝'] for r in g]
        bw = [r['基準単勝'] for r in g]
        wr = [r['単勝基準比'] for r in g]
        pr = [r['複勝基準比_中央値'] for r in g]
        for r in g:
            r['現在人気'] = rank_of(cw, r['現在単勝'])
            r['基準人気'] = rank_of(bw, r['基準単勝'])
            r['基準順位差'] = (MISSING if MISSING in (r['現在人気'], r['基準人気'])
                            else r['現在人気'] - r['基準人気'])
            # 基準比は大きいほど「基準より高い」ので降順で順位を付ける
            r['単勝基準比順位'] = (MISSING if r['単勝基準比'] == MISSING
                              else sorted((v for v in wr if v != MISSING), reverse=True).index(r['単勝基準比']) + 1)
            r['複勝基準比順位'] = (MISSING if r['複勝基準比_中央値'] == MISSING
                              else sorted((v for v in pr if v != MISSING), reverse=True).index(r['複勝基準比_中央値']) + 1)
            r['人気帯'] = band(r['現在人気'])
            r['頭数'] = len(g)
            # §6 能力ゲート(3アーム並走。統合しない)
            top5 = lambda v: v != MISSING and v <= 5
            r['ARM_B'] = top5(r['統合能力順位'])
            cnt = sum(1 for v in (r['IDM順位'], r['タイム順位'], r['STRIDE順位'], r['統合能力順位']) if top5(v))
            r['ARM_C'] = cnt >= 2
            r['能力系統数'] = cnt
            has_ability = any(v != MISSING for v in
                              (r['統合能力順位'], r['IDM順位'], r['タイム順位'], r['STRIDE順位']))
            r['能力ゲート'] = (r['ARM_B'] or r['ARM_C']) if has_ability else MISSING
            r['単複分類'] = combo_class(r['単勝基準比'], r['複勝基準比_中央値'])
            r['仕分け'] = verdict(r['能力ゲート'], r['単複分類'], r['単勝基準比'], r['複勝基準比_中央値'])
            # 時系列方向
            r['時系列'] = (MISSING if r['前回比'] == MISSING else
                        ('上昇' if r['前回比'] > 1.02 else '短縮' if r['前回比'] < 0.98 else '横ばい'))
    return rows, byrace, audit, scratched


def race_divergence(byrace):
    """§9 レース単位の市場乖離分析。"""
    out = []
    for (d, rk), g in sorted(byrace.items()):
        rho = spearman([(r['基準人気'], r['現在人気']) for r in g])
        movers = sum(1 for r in g if r['基準順位差'] != MISSING and abs(r['基準順位差']) >= 3)
        mismatch = sum(1 for r in g if r['単複分類'] in ('単勝高・複勝低', '単勝低・複勝高'))
        # 暫定の操作的定義。閾値は人間確認事項であり RULE_PROMOTION=NONE
        if rho == MISSING:
            lv = MISSING
        elif rho < 0.6 or movers >= max(3, len(g) // 4):
            lv = '高'
        elif rho < 0.85 or movers >= 2:
            lv = '中'
        else:
            lv = '低'
        top_w = sorted([r for r in g if r['単勝基準比'] != MISSING],
                       key=lambda r: -r['単勝基準比'])[:3]
        top_p = sorted([r for r in g if r['複勝基準比_中央値'] != MISSING],
                       key=lambda r: -r['複勝基準比_中央値'])[:3]
        gate_hi = [r for r in g if r['能力ゲート'] is True and r['単勝基準比順位'] != MISSING
                   and r['単勝基準比順位'] <= 3]
        out.append(dict(対象日=d, racekey=rk, 頭数=len(g), 基準順位相関=rho,
                        変動3段階以上=movers, 単複不一致=mismatch, 市場乖離度=lv,
                        単勝基準比上位3='/'.join(f"{r['馬番']}{r['馬名']}({r['単勝基準比']})" for r in top_w),
                        複勝基準比上位3='/'.join(f"{r['馬番']}{r['馬名']}({r['複勝基準比_中央値']})" for r in top_p),
                        能力PASSかつ基準比上位='/'.join(f"{r['馬番']}{r['馬名']}" for r in gate_hi) or 'なし',
                        人間確認事項=('能力データ未提供' if all(r['能力ゲート'] == MISSING for r in g)
                                else '基準比の僅差に意味を与えないこと')))
    return out


def main():
    ap = argparse.ArgumentParser(description='JRDB基準オッズ 穴馬抽出 (SHADOW_ONLY)')
    ap.add_argument('--kijun', required=True, help='基準オッズCSV')
    ap.add_argument('--now', required=True, help='現在オッズCSV(時系列可)')
    ap.add_argument('--de', help='DE出走表CSV')
    ap.add_argument('--ability', help='能力統合CSV')
    ap.add_argument('--out', default='reports/kijun', help='出力ディレクトリ')
    args = ap.parse_args()

    rows, byrace, audit, scratched = build(args)
    os.makedirs(args.out, exist_ok=True)

    def dump(name, data, cols):
        with open(f'{args.out}/{name}', 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore')
            w.writeheader()
            w.writerows(data)

    print('=== A. 入力監査 ===')
    print(f'{"項目":<22}{"状態":<12}{"件数":>7}  不足・不一致')
    for it, st, n, note in audit:
        print(f'{it:<22}{str(st):<12}{n:>7}  {note}')
    dump('A_input_audit.csv', [dict(項目=a, 状態=b, 件数=c, 不足不一致=d) for a, b, c, d in audit],
         ['項目', '状態', '件数', '不足不一致'])

    div = race_divergence(byrace)
    print('\n=== B. レース別市場乖離 ===')
    print(f'{"racekey":<10}{"頭数":>5}{"基準順位相関":>12}{"3段階以上":>10}{"単複不一致":>10}  乖離度')
    for r in div:
        print(f"{r['racekey']:<10}{r['頭数']:>5}{str(r['基準順位相関']):>12}"
              f"{r['変動3段階以上']:>10}{r['単複不一致']:>10}  {r['市場乖離度']}")
    dump('B_race_divergence.csv', div, list(div[0].keys()) if div else ['racekey'])

    COLS = ['racekey', '馬番', '馬名', '現在人気', '人気帯', '基準単勝', '現在単勝', '単勝基準比',
            '基準複勝', '現在複勝下限', '現在複勝上限', '複勝基準比_中央値', '基準順位差',
            '統合能力順位', 'IDM順位', 'タイム順位', 'STRIDE順位', '能力系統数',
            'ARM_B', 'ARM_C', '能力ゲート', '運勢', 'ROI', '展開', '調教',
            '前回比', '時系列', '取得時刻', '単複分類', '仕分け']
    ana = [r for r in rows if r['人気帯'] == '穴馬候補帯']
    dump('C_ana_candidates.csv', ana, COLS)
    dump('C_all_horses.csv', rows, COLS)
    print(f'\n=== C. 穴馬候補全頭表 ===  7〜12番人気帯 {len(ana)}頭 / 全{len(rows)}頭')
    print('  → C_ana_candidates.csv (非言及馬を作らないため全頭を記載)')

    price_only = [r for r in rows if r['仕分け'] in ('価格だけの穴', '市場拒否疑い', 'HOLD_MISSING')]
    dump('D_price_only.csv', price_only,
         ['racekey', '馬番', '馬名', '単勝基準比', '複勝基準比_中央値', '統合能力順位', '仕分け'])
    print(f'=== D. 価格だけの穴・除外候補 ===  {len(price_only)}頭')

    hand = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in ana:
        hand[r['racekey']][r['仕分け']].append(f"{r['馬番']}{r['馬名']}")
    E = []
    for rk, v in sorted(hand.items()):
        E.append(dict(racekey=rk, **{k: '/'.join(vv) for k, vv in v.items()}))
    dump('E_handoff.csv', E, sorted({k for e in E for k in e}) if E else ['racekey'])
    print(f'=== E. ChatGPT／Excelへの引き渡し ===  {len(E)}レース\n')

    print('```text\nSTATUS                   = SHADOW_ONLY\nPREDICTIVE_EFFECTIVENESS = NOT_EVALUATED\n'
          'RULE_PROMOTION           = NONE\nPURCHASE_ALLOWED         = NO\n'
          'LIVE_PREDICTION          = NOT_AUTHORIZED\n```')
    print('本出力に印・軸・買い目・点数・資金配分は含まない。最終判断は ChatGPT／Excel／羊一様。')


if __name__ == '__main__':
    main()
