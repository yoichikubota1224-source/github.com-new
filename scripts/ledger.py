# -*- coding: utf-8 -*-
"""判定台帳の生成。ChatGPT監査 A01〜A08 への対策実装。

設計の要点（従前の抽出スクリプトとの違い）:
  1. 出力の単位は「馬 × ルール × 条件」の1行。集約結果ではなく条件単位で残す。
  2. 各条件は TRUE / FALSE / UNKNOWN の3値。UNKNOWN を FALSE に落とさない。
  3. すべての行に 観測値・単位・出所タグ・理由コード を持たせる。
  4. 未実装は UNKNOWN(UNK_NOT_IMPLEMENTED)。「該当なし」と混同させない。
  5. 「中N週」は JRA 定義（前走の翌週開催=連闘、次々週=中1週）。連闘は -1 ではなく 'RENTOU'。
  6. 回収率は倍率で保持し、百分率は出力時に一度だけ変換する（列内で単位を混在させない）。

入力はいずれもこのリポジトリの外にある。パスは環境変数で与える。
  LEDGER_ENTRY  出走表CSV(CP932・ヘッダなし33列)
  LEDGER_HIST   過去1年の全レース全頭CSV(前走の供給源)
  LEDGER_RULES  正規化した条件定義JSON。複数ある場合はカンマ区切り
                (書籍由来の条件文を含むため公開リポジトリへ置かない)
  LEDGER_SIRE   父系の合議結果JSON(任意。無ければ父系条件は UNKNOWN)
  LEDGER_KINRYO 減量記号を持つCSV(任意)。JRDB IDM の「斤量」列に ☆★▲△◇ が入っている。
                与えられた場合、減量条件は推定ではなく記号で判定する。
  LEDGER_STRIDE 同日スライド競馬新聞CSV(騎手の正式名。氏名照合の解決に使う)
  LEDGER_OUT    出力ディレクトリ
原本は読み取りのみ。値の書き戻しはしない。
"""
import csv, json, os, sys, collections, datetime, unicodedata

E   = os.environ.get('LEDGER_ENTRY')
H   = os.environ.get('LEDGER_HIST')
RJ  = os.environ.get('LEDGER_RULES')
SJ  = os.environ.get('LEDGER_SIRE')
KJ  = os.environ.get('LEDGER_KINRYO')
SD  = os.environ.get('LEDGER_STRIDE')   # 同日STRIDEの正式名(騎手)の供給元
OUT = os.environ.get('LEDGER_OUT', '.')
for k, v in [('LEDGER_ENTRY', E), ('LEDGER_HIST', H)]:
    if not v or not os.path.exists(v):
        raise SystemExit(f"{k} が未設定または存在しません: {v!r}")
if not RJ:
    raise SystemExit('LEDGER_RULES が未設定です')
for _p in RJ.split(','):
    if not os.path.exists(_p.strip()):
        raise SystemExit(f"LEDGER_RULES の要素が存在しません: {_p!r}")

TODAY = datetime.date(2026, 9, 12)
COL = dict(date=0, venue=1, r=2, umaban=3, cond=4, sd=5, dist=6, name=7, sex=8, age=9,
           jockey=10, kin=11, trainer=12, base=13, waku=22, field=26, key=32)

# 出走表(DE260912.CSV)に存在しない列。別ファイルで供給されればそちらを使う。
ABSENT_COLUMNS = {'減量記号(出走表側)'}
KINRYO_SYMBOLS = set('☆★▲△◇◆')

def nfkc(s): return unicodedata.normalize('NFKC', (s or '').strip())

# ---------- 入力 ----------
rows = [r for r in csv.reader(open(E, encoding='cp932'))]
if len({len(r) for r in rows}) != 1:
    raise SystemExit('出走表の列数が揃っていません')
RULES, IO_TABLE, CLASS_RANK, VERSIONS = [], {}, {}, {}
for path in RJ.split(','):
    sp = json.load(open(path.strip(), encoding='utf-8'))
    IO_TABLE.update(sp.get('course_io') or {})
    CLASS_RANK.update(sp.get('class_rank') or {})
    for rl in sp['rules']:
        if 'dist_io' not in rl:
            rl['dist_io'] = [[d, rl.get('io')] for d in rl['dists']]
        VERSIONS[rl['id']] = sp['_meta']['版']
        RULES.append(rl)
if len({r['id'] for r in RULES}) != len(RULES):
    raise SystemExit('ルールIDが重複しています')
# 減量記号。JRDB IDM の「斤量」列に記号が同梱されている（出走表側には列がない）。
kinryo = {}
if KJ and os.path.exists(KJ):
    for r in csv.DictReader(open(KJ, encoding='utf-8-sig')):
        m = ''.join(ch for ch in (r.get('斤量') or '') if ch in KINRYO_SYMBOLS)
        kinryo[(r['開催場'], int(r['R']), int(r['馬番']))] = m

# 氏名の正式名。出走表の騎手・調教師名は4文字で切られるため、前方一致では
# 「検査氏名」が「検査氏名甲」と「検査氏名乙」の双方に同時一致しうる。
# 同日STRIDEの racekey+馬番+馬名 で正式名を取り、完全一致で解く。
# 解けない氏名は UNKNOWN にする（文字数の閾値では解決しない）。
# 調教師の正式名は同日STRIDEの「厩舎」列にある（提供名。公式マスタとは未照合）。
official_name = {}
if SD and os.path.exists(SD):
    for r in csv.DictReader(open(SD, encoding='utf-8-sig')):
        k = (r['開催場'], int(r['R']), int(r['馬番']))
        v = {'馬名': (r.get('馬名') or '').strip(),
             '騎手': (r.get('騎手') or '').strip(),
             '調教師': (r.get('厩舎') or r.get('調教師') or '').strip(),
             '衝突': False}
        if k in official_name and official_name[k] != v:
            # 同じキーに別の行が来たら上書きしない。結合が一意でないことを残す。
            official_name[k]['衝突'] = True
        else:
            official_name[k] = v

sire_line = {}
if SJ and os.path.exists(SJ):
    for line, sires in json.load(open(SJ, encoding='utf-8')).items():
        for s, votes in sires.items():
            vs = {v[0] for v in votes}
            sire_line[(line, s)] = ('YES' if vs == {'YES'} else 'NO' if vs == {'NO'} else 'SPLIT')

# ---------- レース単位の実測 ----------
races = collections.defaultdict(list)
for r in rows: races[(r[COL['venue']], int(r[COL['r']]))].append(r)
def class_code(cond):
    """出走表のレース条件表記をJV-Data条件コードへ写す。
       (判定に使うのは順序のみ。順序は正規化JSONの class_rank が持つ)"""
    c = nfkc(cond)
    if '3勝' in c: return '016'
    if '2勝' in c: return '010'
    if '1勝' in c: return '005'
    if '新馬' in c: return '701'
    if '未勝利' in c: return '703'
    return '999'   # オープン以上（重賞・特別）

race_meta = {}
for k, hs in races.items():
    decl = {int(h[COL['field']]) for h in hs}
    race_meta[k] = dict(cond=hs[0][COL['cond']], sd=hs[0][COL['sd']].strip(),
                        dist=int(hs[0][COL['dist']]), n_csv=len(hs),
                        n_decl=(list(decl)[0] if len(decl) == 1 else None),
                        jump=('障害' in hs[0][COL['cond']]),
                        klass=class_code(hs[0][COL['cond']]),
                        venue=k[0], R=k[1])

# ---------- 前走（当該日より厳密に前の最新出走のみ。リークなし） ----------
hist = collections.defaultdict(list)
hrows = list(csv.DictReader(open(H, encoding='utf-8-sig')))
byrace = collections.defaultdict(list)
for r in hrows: byrace[r['racekey']].append(r)
rank3f = {}
for rk, hs in byrace.items():
    kn = sorted([(float(h['上がり3F_秒']), h) for h in hs if (h['上がり3F_秒'] or '').strip()],
                key=lambda t: t[0])
    for i, (_, h) in enumerate(kn, 1): rank3f[(rk, h['馬番'])] = i
for r in hrows: hist[r['馬名'].strip()].append(r)
for k in hist: hist[k].sort(key=lambda r: r['日付'])

def monday(d): return d - datetime.timedelta(days=d.weekday())

def naka_weeks(prev_date):
    """JRA のレース間隔。開催週の差-1。連闘は 'RENTOU' を返す。"""
    wk = (monday(TODAY) - monday(prev_date)).days // 7
    if wk <= 0: return None
    return 'RENTOU' if wk == 1 else wk - 1

def fnum(v):
    v = (v or '').strip()
    try: return float(v)
    except Exception: return None

def last_corner(h):
    last = None
    for c in ['通過順1', '通過順2', '通過順3', '通過順4']:
        v = fnum(h[c])
        if v is not None: last = v
    return last

prev = {}
for r in rows:
    hs = [h for h in hist.get(r[COL['name']].strip(), []) if h['日付'] < '2026-09-12']
    if not hs:
        # 新馬戦の出走馬は初出走が確定する。前走条件は「入力不足」ではなく「充足不能」。
        debut = '新馬' in nfkc(r[COL['cond']])
        prev[r[COL['key']]] = dict(found=False, debut=debut,
                                   reason=('DEBUT_NO_PREV_RACE' if debut else 'PREV_ROW_OUT_OF_WINDOW'))
        continue
    h = hs[-1]
    d = datetime.date(*map(int, h['日付'].split('-')))
    prev[r[COL['key']]] = dict(
        found=True, date=h['日付'], venue=h['開催場'], sd=h['芝ダ障'], dist=int(float(h['距離_m'])),
        finish=fnum(h['着順']), corner4=last_corner(h), field=int(float(h['出走頭数'])),
        bw=fnum(h['馬体重_kg']), rank3f=rank3f.get((h['racekey'], h['馬番'])),
        klass=h['条件コード'], naka=naka_weeks(d))

# ---------- 減量: 出走表に記号列が無い。斤量差からの導出は推定にとどめる ----------
def weight_note(hs, r, vr=None):
    """(判定, 観測値, 出所タグ, 理由コード)。
       減量記号が供給されていれば記号で確定する。無ければ斤量差からの推定にとどめる。"""
    if vr is not None and vr in kinryo:
        m = kinryo[vr]
        return (('FALSE' if m else 'TRUE'),
                f"斤量{r[COL['kin']]}kg/減量記号={m or 'なし'}", '[実:提供値]',
                ('OK_FALSE' if m else 'OK_TRUE'))
    cond = hs[0][COL['cond']]
    fixed = any(w in cond for w in ('新馬', '未勝利')) or cond.strip().endswith('ｸﾗｽ')
    bysex = collections.defaultdict(list)
    for h in hs: bysex[h[COL['sex']]].append(float(h[COL['kin']]))
    ws = bysex[r[COL['sex']]]
    c = collections.Counter(ws); top, cnt = c.most_common(1)[0]
    mine = float(r[COL['kin']])
    if not fixed or cnt < 2 or cnt / len(ws) < 0.5:
        return 'UNKNOWN', f'斤量{mine}kg/基準不確定({cond})', '[不足]', 'UNK_NOT_FIXED_WEIGHT_RACE'
    diff = round(top - mine, 1)
    obs = f'斤量{mine}kg/同性最多{top}kg({cnt}/{len(ws)}頭)/差{diff:+.1f}kg'
    # 差<=0 は基準以上を背負う = 減量がないことと整合。差>0 は減量の疑い。
    return 'UNKNOWN', obs, '[推:斤量差]', ('UNK_NO_ALLOWANCE_COLUMN_LIKELY_NONE' if diff <= 0
                                          else 'UNK_NO_ALLOWANCE_COLUMN_LIKELY_REDUCED')

# ---------- 条件の評価 ----------
T, F, U = 'TRUE', 'FALSE', 'UNKNOWN'

# 限定判定語。ここに無い語を出力してはいけない。
VERDICT_WORDS = ('本体で本採用再判定', '保留論点あり', '断念疑い', '軸不可疑い',
                 'ワイド穴として照合', '薄め相手として照合', '人間確認必須')

# ===== 必須ゲートの唯一の定義 =====
# 順序は 対象日/キー → 騎手AB → ROI指定範囲 → CB → CJ → DA。
# 調教師FB列は必須ゲートに含めない（参照は可能だがゲートには数えない）。
MANDATORY_GATE_ORDER = [
    '1_対象日とracekey/馬番の確定',
    '2_騎手六星運勢 RaceInput!AB',
    '3_ROI 指定範囲(AZ:BA等)',
    '4_RaceInput!CB',
    '5_RaceInput!CJ',
    '6_RaceInput!DA',
]
FORBIDDEN_IN_MANDATORY_GATE = ('調教師', 'FB')   # 混入検査用

# ゲートとは別に管理する状態。ここに置いたものは必須ゲートに数えない。
def build_states(kinryo_supplied):
    return {
        'ULMBルール条件一致': 'PASS(ルール条件の一致。ROI実数の照合完了ではない)',
        'ROI実数の照合': 'HOLD',
        'ROI集計期間': '未取得',
        'ROI使用可否列': '一部取得',
        '減量記号': ('確認済(JRDB IDMの斤量列)' if kinryo_supplied else '未取得'),
        '調教師FB列': '必須ゲート外(参照可・ゲートに数えない)',
        '能力(足切り)': '未取得',
        '当日馬場とトラックバイアス': '未取得',
        '追切原時計と短評': '未取得',
    }

def build_gates():
    """必須ゲートの供給状況。キーは MANDATORY_GATE_ORDER と1対1。"""
    g = {
        '1_対象日とracekey/馬番の確定': 'PASS',
        '2_騎手六星運勢 RaceInput!AB': 'HOLD_UNVERIFIED',
        '3_ROI 指定範囲(AZ:BA等)': 'HOLD_UNVERIFIED',
        '4_RaceInput!CB': 'HOLD_UNVERIFIED',
        '5_RaceInput!CJ': 'HOLD_UNVERIFIED',
        '6_RaceInput!DA': 'HOLD_UNVERIFIED',
    }
    assert list(g) == MANDATORY_GATE_ORDER, '必須ゲートのキーが順序定義と一致しない'
    for k in g:
        for bad in FORBIDDEN_IN_MANDATORY_GATE:
            assert bad not in k, f'必須ゲートに {bad} が混入: {k}'
    return g

GATES = build_gates()
STATES = build_states(bool(kinryo))
# 確認済系統は「ゲートとは別に管理する状態」のうちULMBの条件一致のみ。
CONFIRMED_SYSTEMS = sum(1 for k, v in STATES.items() if k == 'ULMBルール条件一致' and v.startswith('PASS'))

def verdict_word(agg):
    """限定判定語の割り当て。
       「本体で本採用再判定」は能力・運勢・ROI・本シート判定のうち2系統以上が
       確認済みのときだけ使える。本日はROI(ウルトラ/マストバイ)の1系統のみなので
       救済レイヤーの目安に従い「ワイド穴として照合」に留める。"""
    if agg == T:
        return ('本体で本採用再判定' if CONFIRMED_SYSTEMS >= 2 else 'ワイド穴として照合')
    if agg == U:
        return '保留論点あり / 人間確認必須'
    return '断念疑い'

def need_prev(p, label):
    if p.get('found'): return None
    if p.get('debut'):
        # 初出走が確定 → 前走を要求する条件は definitively 成立しない
        return (F, '新馬(初出走)のため前走なし', '[実]', 'FALSE_DEBUT_NO_PREV_RACE')
    return (U, '前走行が収録窓外', '[不足]', 'UNK_PREV_ROW_OUT_OF_WINDOW')

def evaluate(op, arg, r, hs, p, meta):
    """(判定, 必要条件, 観測値, 単位, 出所タグ, 理由コード)"""
    u = int(r[COL['umaban']]); age = int(r[COL['age']]); sex = r[COL['sex']]
    waku = int(r[COL['waku']]); fld = meta['n_csv']

    def ok(v, req, obs, unit, tag='[実]'):
        return ((T if v else F), req, obs, unit, tag, ('OK_TRUE' if v else 'OK_FALSE'))
    def unk(req, obs, unit, tag, code): return (U, req, obs, unit, tag, code)

    MIN_PREFIX_CHARS = 3   # これ未満の前方一致は「曖昧」として別の理由コードにする
    def name_match(label, want, got):
        """氏名の照合。前方一致だけでは確定しない。

           出走表の騎手・調教師名は4文字で切られるため完全一致だけでは落ちるが、
           切られた名は複数の正式名に同時一致しうる（「検査氏名」は「検査氏名甲」
           にも「検査氏名乙」にも前方一致する）。そのため前方一致は TRUE にせず、
           同日の正式名を meta['正式名'] から引けたときだけ完全一致で確定する。
           空文字列は str.startswith('') が常に True になるため必ず除外する。
           この関数は evaluate 内に置き、外部の補助関数に依存させない（外部検査が
           nfkc と evaluate だけを読み込んでも成立させるため）。"""
        a, b = nfkc(want), nfkc(got)
        if not a:
            return unk(f'{label}{want}', '条件側の氏名が空', '名', '[不足]', 'UNK_NAME_ABSENT_IN_RULE')
        if not b:
            return unk(f'{label}{want}', f'{label}欄が空欄', '名', '[不足]', 'UNK_NAME_ABSENT_IN_ENTRY')
        # 同日の正式名で解決する。正式名を先に見る。出走表は4文字で切られるため、
        # 切られた表記が条件名と一致していても、正式名が別人(4文字が同じで5文字目が
        # 違う)でありうる。
        # 正式名が存在するのに結合キーが合わないときは、原略名の完全一致へ戻さず
        # その場で止める(フォールバック禁止)。
        src = (meta.get('正式名') or {}).get(u) or {}
        full = nfkc(src.get(label, ''))
        if full:
            if src.get('衝突'):
                return unk(f'{label}{want}', f'{label}{got}(同一キーに複数の正式名行があり結合が一意でない)',
                           '名', '[不足]', 'UNK_NAME_JOIN_NOT_UNIQUE')
            if nfkc(src.get('馬名', '')) != nfkc(r[COL['name']]):
                return unk(f'{label}{want}',
                           f"{label}{got}(正式名行の馬名{src.get('馬名') or '(空)'}が出走表の馬名"
                           f"{r[COL['name']] or '(空)'}と一致しない。結合キー不一致のため停止)",
                           '名', '[不足]', 'UNK_NAME_JOIN_KEY_MISMATCH')
            # 出走表は4文字で切るため、外国人騎手は頭文字が落ちる（Ｍ．ミシェル→ミシェル）。
            # 前方一致に限らず、切られた表記が正式名に含まれていれば同一人とみなす。
            if not (full.startswith(b) or b in full):
                return unk(f'{label}{want}', f'{label}{got}(正式名{src[label]}と出走表の表記が整合しない)',
                           '名', '[不足]', 'UNK_NAME_OFFICIAL_MISMATCH')
            return ((T if a == full else F), f'{label}{want}',
                    f"{label}{src[label]}(正式名で{'一致' if a == full else '不一致'}。出走表は{got})",
                    '名', '[実:提供値]', ('OK_TRUE' if a == full else 'OK_FALSE'))
        if a == b:
            return ok(True, f'{label}{want}', f'{label}{got}(完全一致。正式名は未取得)', '名')
        if a.startswith(b) or b.startswith(a):
            short = a if len(a) < len(b) else b
            code = ('UNK_NAME_AMBIGUOUS_PREFIX' if len(short) < MIN_PREFIX_CHARS
                    else 'UNK_NAME_PREFIX_NOT_UNIQUE')
            return unk(f'{label}{want}',
                       f'{label}{got}(前方一致{len(short)}文字。正式名が引けず一意に解決できない)',
                       '名', '[不足]', code)
        return ok(False, f'{label}{want}', f'{label}{got}(不一致)', '名')

    if op == 'umaban_range':
        lo, hi = arg; hi = hi if hi is not None else 99
        return ok(lo <= u <= hi, f'馬番{lo}〜{hi}', f'馬番{u}', '番')
    if op == 'waku_range':
        lo, hi = arg
        return ok(lo <= waku <= hi, f'枠番{lo}〜{hi}', f'枠番{waku}', '枠')
    if op == 'age_max':  return ok(age <= arg, f'{arg}歳以下', f'{age}歳', '歳')
    if op == 'age_min':  return ok(age >= arg, f'{arg}歳以上', f'{age}歳', '歳')
    if op == 'sex_in':   return ok(sex in arg, '性が' + '・'.join(arg), f'性{sex}', '性')
    if op == 'base_eq':  return ok(r[COL['base']] == arg, f'所属{arg}', f"所属{r[COL['base']]}", '所属')
    if op == 'field_eq': return ok(fld == arg, f'{arg}頭立て', f'{fld}頭', '頭')
    if op == 'field_min':return ok(fld >= arg, f'{arg}頭立て以上', f'{fld}頭', '頭')
    if op == 'field_max':return ok(fld <= arg, f'{arg}頭立て以下', f'{fld}頭', '頭')
    if op == 'jockey_eq':
        return name_match('騎手', arg, r[COL['jockey']])
    if op == 'sire_eq':
        return ok(nfkc(r[16]) == nfkc(arg), f'父{arg}', f'父{r[16]}', '名')
    if op == 'sire_line':
        st = sire_line.get((arg, r[16].strip()))
        if st is None:
            return unk(f'父系{arg}', f'父{r[16]}', '系統', '[不足]', 'UNK_SIRELINE_NOT_RESOLVED')
        if st == 'SPLIT':
            return unk(f'父系{arg}', f'父{r[16]}(合議不一致)', '系統', '[不足]', 'UNK_SIRELINE_SPLIT_VOTE')
        return ((T if st == 'YES' else F), f'父系{arg}', f'父{r[16]}(合議一致)', '系統', '[実:合議]',
                ('OK_TRUE' if st == 'YES' else 'OK_FALSE'))
    if op == 'no_condition':
        return ok(True, '無条件', '条件②なし', '-')
    if op == 'trainer_eq':
        return name_match('調教師', arg, r[COL['trainer']])
    if op == 'producer_not':
        return ok(nfkc(r[15]) != nfkc(arg), f'生産者が{arg}以外', f'生産者{r[15]}', '名')
    if op == 'UNMAPPED_TARGET':
        return unk(f'ターゲット種別{arg}', '正規化で写像できず', '-', '[不足]', 'UNK_TARGET_NOT_MAPPED')
    if op == 'no_weight_allowance':
        v, obs, tag, code = weight_note(hs, r, (meta.get('venue'), meta.get('R'), int(r[COL['umaban']])))
        if v in ('TRUE', 'FALSE'):
            return (v, '負担重量の減量なし', obs, 'kg', tag, code)
        return unk('負担重量の減量なし', obs, 'kg', tag, code)
    if op == 'prev_venue_central_AMBIGUOUS':
        m = need_prev(p, op)
        if m: return (m[0], '前走が中央場所', m[1], '場', m[2], m[3])
        return unk('前走が中央場所(語義二義)', f"前走{p['venue']}", '場', '[実]',
                   'UNK_DEF_AMBIGUOUS_CENTRAL')
    if op.startswith('prev_') or op.startswith('weeks_'):
        m = need_prev(p, op)
        if m: return (m[0], op, m[1], '-', m[2], m[3])
    if op == 'prev_finish_max':
        v = p['finish']
        if v is None: return unk(f'前走{arg}着以内', '前走着順なし', '着', '[不足]', 'UNK_PREV_FINISH_ABSENT')
        return ok(v <= arg, f'前走{arg}着以内', f'前走{v:.0f}着', '着')
    if op == 'prev_corner4_max':
        v = p['corner4']
        if v is None: return unk(f'前走4角{arg}番手以内', '前走通過順なし', '番手', '[不足]', 'UNK_PREV_CORNER_ABSENT')
        return ok(v <= arg, f'前走4角{arg}番手以内', f'前走4角{v:.0f}番手', '番手')
    if op == 'prev_corner4_eq':
        v = p['corner4']
        if v is None: return unk(f'前走4角{arg}番手', '前走通過順なし', '番手', '[不足]', 'UNK_PREV_CORNER_ABSENT')
        return ok(v == arg, f'前走4角{arg}番手', f'前走4角{v:.0f}番手', '番手')
    if op == 'prev_rank3f_max':
        v = p['rank3f']
        if v is None: return unk(f'前走上がり3F{arg}位以内', '前走上がり順位なし', '位', '[不足]', 'UNK_PREV_3F_ABSENT')
        return ok(v <= arg, f'前走上がり3F{arg}位以内', f'前走上がり{v}位', '位')
    if op == 'prev_bw_min':
        v = p['bw']
        if v is None: return unk(f'前走馬体重{arg}kg以上', '前走馬体重なし(計不)', 'kg', '[不足]', 'UNK_PREV_BW_ABSENT')
        return ok(v >= arg, f'前走馬体重{arg}kg以上', f'前走{v:.0f}kg', 'kg')
    if op == 'prev_bw_max_excl':
        v = p['bw']
        if v is None: return unk(f'前走馬体重{arg}kg未満', '前走馬体重なし(計不)', 'kg', '[不足]', 'UNK_PREV_BW_ABSENT')
        return ok(v < arg, f'前走馬体重{arg}kg未満', f'前走{v:.0f}kg', 'kg')
    if op == 'prev_finish_min_AMBIGUOUS':
        v = p['finish']
        if v is None: return unk(f'前走{arg}着以下', '前走着順なし', '着', '[不足]', 'UNK_PREV_FINISH_ABSENT')
        a = (v >= arg)   # 読みA「{arg}着より下位」
        b = (v <= arg)   # 読みB「{arg}着以内」
        return unk(f'前走{arg}着以下(語義二義)',
                   f'前走{v:.0f}着 → 読みA(下位)={"成立" if a else "不成立"}/読みB(以内)={"成立" if b else "不成立"}',
                   '着', '[実]', 'UNK_DEF_AMBIGUOUS_FINISH')
    if op == 'prev_dist_min':
        return ok(p['dist'] >= arg, f'前走{arg}m以上', f"前走{p['dist']}m", 'm')
    if op == 'prev_dist_ge_current':
        return ok(p['dist'] >= meta['dist'], '前走が今回以上の距離', f"前走{p['dist']}m/今回{meta['dist']}m", 'm')
    if op == 'prev_dist_le_current':
        return ok(p['dist'] <= meta['dist'], '前走が今回以下の距離', f"前走{p['dist']}m/今回{meta['dist']}m", 'm')
    if op == 'prev_venue_ne_current':
        return ok(p['venue'] != r[COL['venue']], '前走が今回と別開催場',
                  f"前走{p['venue']}/今回{r[COL['venue']]}", '場')
    if op == 'prev_sd_eq':
        return ok(p['sd'] == arg, f'前走{arg}', f"前走{p['sd']}", '芝ダ')
    if op == 'prev_dist_eq':
        return ok(p['dist'] == arg, f'前走{arg}m', f"前走{p['dist']}m", 'm')
    if op == 'prev_field_min':
        return ok(p['field'] >= arg, f'前走{arg}頭立て以上', f"前走{p['field']}頭", '頭')
    if op == 'prev_field_ge_current':
        return ok(p['field'] >= fld, '前走が今回と同頭数以上', f"前走{p['field']}頭/今回{fld}頭", '頭')
    if op == 'prev_class_ge_current':
        cur = meta.get('klass')
        if cur is None or p['klass'] not in CLASS_RANK or cur not in CLASS_RANK:
            return unk('前走が今回と同クラス以上', f"前走コード{p['klass']}/今回コード{cur}", 'クラス',
                       '[不足]', 'UNK_CLASS_CODE_UNRESOLVED')
        v = CLASS_RANK[p['klass']] >= CLASS_RANK[cur]
        return ok(v, '前走が今回と同クラス以上', f"前走コード{p['klass']}/今回コード{cur}", 'クラス')
    if op == 'weeks_min':
        w = p['naka']
        if w is None: return unk(f'中{arg}週以上', '前走日不明', '週', '[不足]', 'UNK_PREV_DATE_ABSENT')
        if w == 'RENTOU': return ok(False, f'中{arg}週以上', '連闘', '週')
        return ok(w >= arg, f'中{arg}週以上', f'中{w}週', '週')
    if op == 'weeks_max':
        w = p['naka']
        if w is None: return unk(f'中{arg}週以内', '前走日不明', '週', '[不足]', 'UNK_PREV_DATE_ABSENT')
        if w == 'RENTOU': return ok(True, f'中{arg}週以内', '連闘', '週')
        return ok(w <= arg, f'中{arg}週以内', f'中{w}週', '週')
    return (U, op, '評価関数が未実装', '-', '[不足]', 'UNK_NOT_IMPLEMENTED')

# ---------- 台帳の生成 ----------
cond_rows, horse_rows = [], []
scope_log = []
for rule in RULES:
    def in_scope(k):
        m = race_meta[k]
        if k[0] != rule['venue'] or m['sd'] != rule['sd'] or m['jump']: return False
        for d, io in rule['dist_io']:
            if m['dist'] != d: continue
            if io is None: return True
            return IO_TABLE.get(f"{k[0]}|{rule['sd']}|{m['dist']}") == io
        return False
    tgt = [k for k in races if in_scope(k)]
    scope_log.append(dict(rule=rule['id'], 適用レース=sorted(f"{k[0]}{k[1]}R" for k in tgt),
                          対象頭数=sum(race_meta[k]['n_csv'] for k in tgt),
                          条件数=len(rule['conds']),
                          io要求=','.join(str(io or '-') for _, io in rule['dist_io']),
                          # 内外テーブルは原典のコース表記(例「中山芝1200m外」)と突合済み。
                          # 突合できた8件は[実:原典表記]、原典が内外を書いていない距離は[推:コース]のまま。
                          io出所=('[実:原典表記]' if any(io for _, io in rule['dist_io']) else '-')))
    for k in tgt:
        hs = races[k]; meta = dict(race_meta[k])
        # 同日STRIDEの正式名を馬番で引けるようにレース単位で渡す
        meta['正式名'] = {u2: v for (vn, rn, u2), v in official_name.items()
                       if (vn, rn) == k}
        for r in hs:
            p = prev.get(r[COL['key']], dict(found=False, reason='NO_PREV_ROW'))
            verds = []
            for op, arg in rule['conds']:
                v, req, obs, unit, tag, code = evaluate(op, arg, r, hs, p, meta)
                verds.append(v)
                cond_rows.append(dict(
                    出走馬ID=r[COL['key']], レースID=f"{k[0]}{k[1]}R", 開催場=k[0], R=k[1],
                    馬番=int(r[COL['umaban']]), 馬名=r[COL['name']], ルールID=rule['id'],
                    ルール版=VERSIONS[rule['id']], 原典参照=rule['原典'], 条件演算子=op,
                    必要条件=req, 観測値=obs, 単位=unit, 出所タグ=tag, 判定=v, 理由コード=code))
            agg = T if all(v == T for v in verds) else (F if any(v == F for v in verds) else U)
            if agg == F: continue   # 明確な不成立は馬別台帳に載せない（条件別台帳には残る）
            nn = rule.get('n'); ch = rule.get('chaku')
            horse_rows.append(dict(
                出走馬ID=r[COL['key']], レースID=f"{k[0]}{k[1]}R", 開催場=k[0], R=k[1],
                馬番=int(r[COL['umaban']]), 馬名=r[COL['name']], 性齢=r[COL['sex']] + r[COL['age']],
                騎手=r[COL['jockey']], ルールID=rule['id'], 集約判定=agg,
                条件数=len(verds), TRUE数=verds.count(T), UNKNOWN数=verds.count(U),
                標本数n=(nn if nn else '未取得'),
                三着内数=(sum(ch[:3]) if ch else '未取得'),
                原典3着内率=(rule.get('t3') if rule.get('t3') is not None else '未取得'),
                使用可否=(rule.get('kahi') or '(空欄)'),
                原典推奨券種=(rule.get('ken') or '(空欄)'),
                限定判定語=verdict_word(agg),
                確認済系統数=CONFIRMED_SYSTEMS,
                UNKNOWN理由=';'.join(sorted({c['理由コード'] for c in cond_rows
                                            if c['出走馬ID'] == r[COL['key']]
                                            and c['ルールID'] == rule['id']
                                            and c['判定'] == U})) or '-'))

os.makedirs(OUT, exist_ok=True)
def dump(path, data, fields):
    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader()
        for d in data: w.writerow(d)
    return path
f1 = dump(os.path.join(OUT, '判定台帳_条件別_20260912.csv'), cond_rows, list(cond_rows[0].keys()))
f2 = dump(os.path.join(OUT, '判定台帳_馬別_20260912.csv'), horse_rows, list(horse_rows[0].keys()))
json.dump(scope_log, open(os.path.join(OUT, '適用範囲ログ_20260912.json'), 'w'),
          ensure_ascii=False, indent=1)
_gate_json = dict(必須ゲートの順序=MANDATORY_GATE_ORDER, 必須ゲート=GATES,
                  ゲートとは別に管理する状態=STATES,
                  必須ゲートの注記='調教師FB列は必須ゲートに含めない。唯一の定義は scripts/ledger.py の MANDATORY_GATE_ORDER / build_gates()')
# 生成直後の自己検査（X02の回帰）
for _k in list(_gate_json['必須ゲート']) + _gate_json['必須ゲートの順序']:
    for _bad in FORBIDDEN_IN_MANDATORY_GATE:
        assert _bad not in _k, f'生成JSONの必須ゲートに {_bad} が混入: {_k}'
json.dump(dict(**_gate_json, 確認済系統数=CONFIRMED_SYSTEMS,
               限定判定語の語彙=list(VERDICT_WORDS),
               不在の列=sorted(ABSENT_COLUMNS),
               レース=[dict(レースID=f'{k[0]}{k[1]}R', 条件=m['cond'], 芝ダ=m['sd'], 距離=m['dist'],
                          CSV頭数=m['n_csv'], 列26頭数=m['n_decl'], 障害=m['jump'],
                          クラスコード=m['klass']) for k, m in sorted(race_meta.items())])
          , open(os.path.join(OUT, 'ゲートとレース台帳_20260912.json'), 'w'), ensure_ascii=False, indent=1)

# ---------- 標準出力の要約 ----------
print('=' * 100)
print('判定台帳の生成')
print('=' * 100)
print(f"出走表 {len(rows)}行 / {len(races)}レース  障害={sum(1 for m in race_meta.values() if m['jump'])}レース")
mism = [k for k, m in race_meta.items() if m['n_decl'] is None or m['n_decl'] != m['n_csv']]
print(f"出走頭数(列26)とCSV行数の不一致: {len(mism)}レース  {mism if mism else '(なし)'}")
print(f"ルール {len(RULES)}件 / 条件 {sum(len(r['conds']) for r in RULES)}件")
print(f"条件別台帳 {len(cond_rows)}行 → {f1}")
print(f"馬別台帳   {len(horse_rows)}行 → {f2}")
print()
c = collections.Counter(r['判定'] for r in cond_rows)
print('条件別台帳の判定分布:', dict(c))
print('UNKNOWN の理由コード:')
for code, v in collections.Counter(r['理由コード'] for r in cond_rows if r['判定'] == U).most_common():
    print(f"   {code:<42} {v:>5}行")
print()
print('馬別台帳: 集約=TRUE（全条件が実測でTRUE）')
for h in sorted([h for h in horse_rows if h['集約判定'] == T], key=lambda x: (x['開催場'], x['R'], x['馬番'])):
    print(f"   {h['ルールID']}  {h['レースID']:>7} {h['馬番']:>2}番 {h['馬名']:<15}{h['性齢']:<4}"
          f" n={h['標本数n']!s:>6} 使用可否={h['使用可否']} 原典券種={h['原典推奨券種']}")
print()
print('馬別台帳: 集約=UNKNOWN（未取得・語義未確定を含み確定できない）')
for h in sorted([h for h in horse_rows if h['集約判定'] == U], key=lambda x: (x['開催場'], x['R'], x['馬番'])):
    print(f"   {h['ルールID']}  {h['レースID']:>7} {h['馬番']:>2}番 {h['馬名']:<15}"
          f" TRUE{h['TRUE数']}/UNK{h['UNKNOWN数']}/計{h['条件数']}  {h['UNKNOWN理由']}")
print()
print('必須ゲートの供給状況（順序は 対象日/キー→騎手AB→ROI指定範囲→CB→CJ→DA。調教師FBは含めない）:')
for k, v in GATES.items(): print(f"   {k:<34} {v}")
print('ゲートとは別に管理する状態:')
for k, v in STATES.items(): print(f"   {k:<34} {v}")
print(f"   → 確認済系統数={CONFIRMED_SYSTEMS} のため限定判定語は「ワイド穴として照合」までに留める")
print()
print('適用範囲が空だったルール（当日に該当コースなし = 「該当馬なし」ではない）:')
for s in scope_log:
    if not s['適用レース']: print(f"   {s['rule']}  io要求={s['io要求']}")
