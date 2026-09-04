#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""netkeiba 出馬表(5走表示)から【全出走馬】を取り出す。
規約: 文字化けを黙認しない / 取れなければ None（0で埋めない） / 列はCSSクラスで同定。
⚠ オッズ・人気は出馬表時点では未確定(---.- / **)のため取り込まない＝未来情報混入の防止。
"""
import re, html, json, sys, os, glob, collections

def txt(s):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', s))).replace('\xa0', ' ').strip()

def iv(s):
    s = (s or '').strip()
    return int(s) if re.fullmatch(r'\d+', s) else None

def fv(s):
    try: return float((s or '').strip())
    except (TypeError, ValueError): return None

BA = {'01':'札幌','02':'函館','03':'福島','04':'新潟','05':'東京',
      '06':'中山','07':'中京','08':'京都','09':'阪神','10':'小倉'}

def parse_past(raw):
    """過去走1件。着順は Data01>span.Num。"""
    o = {}
    d1 = re.search(r'<div class="Data01">(.*?)</div>', raw, re.S)
    if d1:
        # 構造: <span>YYYY.MM.DD&nbsp;場</span><span class="Num">着順</span>
        head = re.search(r'<span(?![^>]*class)[^>]*>(.*?)</span>', d1.group(1), re.S)
        if head:
            m = re.match(r'(\d{4}\.\d{2}\.\d{2})\s*(\S+)?', txt(head.group(1)))
            if m: o['date'], o['ba'] = m.group(1), m.group(2)
        num = re.search(r'<span class="Num">(.*?)</span>', d1.group(1), re.S)
        o['chaku'] = iv(txt(num.group(1))) if num else None      # 着順(降着等は数値化されない=None)
    d2 = re.search(r'<div class="Data02">(.*?)</div>', raw, re.S)
    if d2:
        rid = re.search(r'/race/(\d{12})', d2.group(1))
        o['race_id'] = rid.group(1) if rid else None   # 前走のrace_id(5年データと直接結合できる)
        g = re.search(r'Icon_GradeType\d*"[^>]*>(.*?)</span>', d2.group(1), re.S)
        o['grade'] = txt(g.group(1)) if g else None
        o['race_name'] = txt(re.sub(r'<span.*?</span>', '', d2.group(1), flags=re.S))
    d5 = re.search(r'<div class="Data05">(.*?)</div>', raw, re.S)
    if d5:
        t = txt(d5.group(1))
        m = re.match(r'(芝|ダ|障)(\d+)(?:\(([^)]*)\))?\s+(\S+)?\s*(\S+)?', t)
        if m:
            o['td'], o['dist'] = m.group(1), iv(m.group(2))
            o['time'], o['baba'] = m.group(4), m.group(5)
    d3 = re.search(r'<div class="Data03">(.*?)</div>', raw, re.S)
    if d3:
        t = txt(d3.group(1))
        m = re.search(r'(\d+)頭\s*(\d+)番\s*(\d+)人\s*(\S+)\s+([\d.]+)', t)
        if m:
            o['n_start'], o['uma'], o['pop'] = iv(m.group(1)), iv(m.group(2)), iv(m.group(3))
            o['jockey'], o['kin'] = m.group(4), fv(m.group(5))
        else:
            o['raw_data03'] = t
    d6 = re.search(r'<div class="Data06">(.*?)</div>', raw, re.S)
    if d6:
        t = txt(d6.group(1))
        m = re.match(r'([\d\-]*)\s*\(([\d.]+)\)\s*(\d+)?\(([+-]?\d+)\)?', t)
        o['passing'] = (m.group(1) or None) if m else None
        o['last3f'] = fv(m.group(2)) if m else None
        o['weight'] = iv(m.group(3)) if m and m.group(3) else None
    d7 = re.search(r'<div class="Data07">(.*?)</div>', raw, re.S)
    if d7:
        t = txt(d7.group(1))
        m = re.match(r'(.*?)\(([-\d.]+)\)$', t)
        o['aite'] = m.group(1).strip() if m else t
        o['diff'] = fv(m.group(2)) if m else None
    return o

def parse(doc, rid):
    o = {'race_id': rid, 'ba': BA.get(rid[4:6]), 'r': int(rid[10:12])}
    t = re.search(r'<title>(.*?)</title>', doc, re.S)
    title = html.unescape(t.group(1)).strip() if t else ''
    o['title'] = title.split('|')[0].replace('5走表示', '').strip()
    rd = re.search(r'<div[^>]*class="RaceData01"[^>]*>(.*?)</div>', doc, re.S)
    meta = txt(rd.group(1)) if rd else ''
    o['meta'] = meta
    m = re.search(r'(芝|ダ|障)(\d+)m', meta)
    o['td'], o['dist'] = (m.group(1), int(m.group(2))) if m else (None, None)
    o['jump'] = ('障' in meta) or ('障害' in title)
    rd2 = re.search(r'<div[^>]*class="RaceData02"[^>]*>(.*?)</div>', doc, re.S)
    o['cond'] = txt(rd2.group(1)) if rd2 else None

    horses = []
    for tr in re.findall(r'<tr[^>]*class="[^"]*HorseList[^"]*"[^>]*>(.*?)</tr>', doc, re.S):
        cells = []
        for _t, attr, val in re.findall(r'<(t[dh])([^>]*)>(.*?)</\1>', tr, re.S):
            c = re.search(r'class="([^"]*)"', attr)
            cells.append(((c.group(1) if c else ''), val))
        get = lambda pred: next((v for cls, v in cells if pred(cls)), None)
        waku = iv(txt(get(lambda k: re.fullmatch(r'Waku\d*', k.split()[0]) if k.split() else False) or ''))
        nums = [iv(txt(v)) for cls, v in cells if cls.split() and re.fullmatch(r'Waku\d*|Umaban\d*', cls.split()[0])]
        hi = get(lambda k: k.startswith('Horse_Info'))
        if hi is None: continue
        if '/horse/' not in hi: continue      # 各レース先頭の凡例行を除外
        h = {}
        h['waku'] = nums[0] if nums else None
        h['uma']  = nums[1] if len(nums) > 1 else None
        def dv(cls_name, src=hi):
            m = re.search(r'<div class="%s[^"]*">(.*?)</div>' % cls_name, src, re.S)
            return txt(m.group(1)) if m else None
        h['sire']   = dv('Horse01')                      # 父
        nm = dv('Horse02')
        h['name'] = re.sub(r'\s+B$', '', nm) if nm else None
        h['blinker'] = bool(nm and nm.endswith(' B'))    # ブリンカー
        h['dam']    = dv('Horse03')                      # 母
        bms = dv('Horse04')
        h['bms']    = bms.strip('()') if bms else None   # 母父
        h['stable'] = dv('Horse05')                      # 所属・調教師
        hid = re.search(r'/horse/(\d+)', hi)
        h['horse_id'] = hid.group(1) if hid else None
        h06 = re.search(r'<div class="Horse06[^"]*">(.*?)</div>', hi, re.S)
        if h06:
            ky = re.search(r'class="kyakusitu">(.*?)</span>', h06.group(1), re.S)
            h['kyakushitsu'] = txt(ky.group(1)) if ky else None      # 脚質
            h['rotation'] = txt(re.sub(r'<span.*?</span>', '', h06.group(1), flags=re.S)) or None  # 中N週/連闘等
        jk = get(lambda k: k.startswith('Jockey'))
        if jk:
            # ⚠ Barei は「性齢+毛色」(例: 牝3黒鹿)。所属ではない。
            #    初版は毛色の「栗毛」を所属「栗東」と誤読していた＝訂正。
            b = re.search(r'<span class="Barei">(.*?)</span>', jk, re.S)
            if b:
                m = re.match(r'([牡牝セセン]+)\s*(\d+)\s*(.*)$', txt(b.group(1)))
                if m:
                    h['sex'], h['age'] = m.group(1), iv(m.group(2))
                    h['coat'] = m.group(3) or None      # 毛色
            jn = re.search(r'/jockey/[^>]*>(.*?)</a>', jk, re.S)
            h['jockey'] = txt(jn.group(1)) if jn else None
            kins = re.findall(r'<span>([\d.]+)</span>', jk)
            h['kin'] = fv(kins[-1]) if kins else None
            jid = re.search(r'/jockey/[^"]*?/(\d+)', jk)
            h['jockey_id'] = jid.group(1) if jid else None
        # 所属は Horse05(調教師)から取る = 正しい出所
        if h.get('stable'):
            h['belong'] = h['stable'].split('・')[0] or None
            h['trainer'] = (h['stable'].split('・')[1] if '・' in h['stable'] else None)
        h['past'] = [parse_past(v) for cls, v in cells if cls.split() and cls.split()[0] == 'Past']
        h['past'] = [p for p in h['past'] if p.get('date')]
        horses.append(h)
    o['horses'] = horses
    o['n_entry'] = len(horses)
    return o

def main():
    src = sys.argv[1]; out = sys.argv[2]
    races = []
    for f in sorted(glob.glob(os.path.join(src, '*.html'))):
        rid = os.path.basename(f)[:-5]
        doc = open(f, encoding='utf-8').read()
        races.append(parse(doc, rid))
    races.sort(key=lambda r: (r['ba'] or '', r['r']))
    json.dump(races, open(out, 'w'), ensure_ascii=False, indent=1)
    nh = sum(r['n_entry'] for r in races)
    print(f'[実] {len(races)}R / 延べ{nh}頭 -> {out}')
    fld = collections.Counter()
    for r in races:
        for h in r['horses']:
            for k in ('waku','uma','sire','name','dam','bms','stable','horse_id',
                      'kyakushitsu','rotation','sex','age','jockey','kin','jockey_id',
                      'belong','trainer','coat'):
                if h.get(k) not in (None, ''): fld[k] += 1
            if h['past']: fld['past>=1'] += 1
            fld['past_n'] += len(h['past'])
    print('[実] 充足率:')
    for k, v in fld.items():
        if k == 'past_n': print(f'   past 総件数 {v} (平均 {v/nh:.2f}走/頭)')
        else: print(f'   {k:<12} {v}/{nh} = {v/nh*100:.2f}%')

main()
