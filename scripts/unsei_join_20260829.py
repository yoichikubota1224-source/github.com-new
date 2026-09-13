#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""騎手運勢シート(2026.08.29)を騎手名で結合する。
運勢×は消し根拠にしない(押し上げの欠如としてのみ扱う)。照合不能は[不足]で保持。"""
import openpyxl, re, json, sys, csv
from collections import Counter

XLSX, PACK, OUT = sys.argv[1], sys.argv[2], sys.argv[3]

wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
ws = wb['2026.08.29']
entries = []          # (星人帯, 8/29マーク, 8/30マーク, 騎手トークン, ROI指数)
for row in ws.iter_rows(values_only=True):
    c = [('' if x is None else str(x)) for x in row]
    if not c or not c[0] or c[0] in ('2026年',) or '青字' in c[0]:
        continue
    band, m29, m30, names = c[0].strip(), c[1].strip(), c[2].strip(), (c[3] if len(c) > 3 else '')
    for tok in re.split(r'[、,\n]', names):
        tok = tok.strip()
        if not tok:
            continue
        m = re.match(r'^(\d{2,3})?\s*([^\（(]+)', tok)
        if not m:
            continue
        roi = int(m.group(1)) if m.group(1) else None
        nm = m.group(2).strip()
        if not nm:
            continue
        entries.append({'band': band, 'm29': m29, 'm30': m30, 'token': nm, 'roi': roi,
                        'note': tok})
wb.close()

# DE/パック側の騎手名(4〜5文字丸め)
# ⚠ IDM CSVの騎手名は3文字丸め＋[替](乗替)接尾のため結合に使えない。
#    DE出走表(4〜5文字)を騎手名の正本とする。
jockeys = sorted({r[10].strip() for r in csv.reader(open(PACK, encoding='cp932'))})

# 表記ゆれ: シート側トークン → パック側表記
ALIAS = {'Mデムーロ': 'Ｍ．デム', 'ルメール': 'ルメール', '菅原明': '菅原明良',
         '小幡育': '木幡育也', '小幡初': '木幡初也', '木幡巧': '木幡巧也',
         '河原田菜々': '河原田菜', '荻野琢真': '荻野琢真', '鮫島駿': '鮫島克駿',
         '鮫島良太': '鮫島良太', '岩田望': '岩田望来', '岩田康': '岩田康誠',
         '古川吉洋': '古川吉洋', '古川奈穂': '古川奈穂', '西村淳': '西村淳也',
         '横山和': '横山和生', '横山武': '横山武史', '横山典': '横山典弘',
         '横山琉': '横山琉人', '小林凌': '小林凌大', '小林脩': '小林脩斗',
         '小林美駒': '小林美駒', '大野拓': '大野拓弥', '長岡禎': '長岡禎仁',
         '柴田大': '柴田大知', '柴田裕一郎': '柴田裕一', '和田陽希': '和田陽希',
         '石田拓郎': '石田拓郎', '田山旺祐': '田山旺佑', '国分恭': '国分恭介',
         '国分優': '国分優作', '江田照': '江田照男', '丸山': '丸山元気',
         '丸田': '丸田恭介', '松若': '松若風馬', '菊沢': '菊沢一樹',
         '秋山稔': '秋山稔樹', '吉田隼': '吉田隼人', '小沢': '小沢大仁',
         '高倉': '高倉稜', '岡田': '岡田祥嗣', '田辺': '田辺裕信',
         '北村友一': '北村友一', '北村宏': '北村宏司', '富田': '富田暁',
         '中井': '中井裕二', '藤懸': '藤懸貴志', '石神深道': '石神深道',
         '杉原誠人': '杉原誠人', '戸崎': '戸崎圭太', '高田': '高田潤',
         '加藤祥': '加藤祥太', '丹内': '丹内祐次', '三浦': '三浦皇成',
         '小崎': '小崎綾也', '森田誠也': '森田誠也', '菱田': '菱田裕二',
         '団野': '団野大成', '酒井': '酒井学', '松本': '松本大輝',
         '内田博': '内田博幸', '津村': '津村明秀', '太宰': '太宰啓介',
         '石川': '石川倭', '泉谷': '泉谷楓真', '今村聖奈': '今村聖奈',
         '田口': '田口貫太', '高杉': '高杉史麒', '浜中': '浜中俊',
         '武藤': '武藤雅', '幸': '幸英明', '黛': '黛弘人', '嶋田': '嶋田純次',
         '川田': '川田将雅', '武豊': '武豊', '池添': '池添謙一',
         '柴田善': '柴田善臣', '坂井': '坂井瑠星', '角田大和': '角田大和',
         '川又': '川又賢治', '荻野極': '荻野極', '松山': '松山弘平',
         '石橋脩': '石橋脩', '佐藤': '佐藤翔馬', '原田': '原田和真',
         '野中': '野中悠太', '吉村': '吉村誠之', '亀田': '亀田温心',
         '斎藤新': '斎藤新', '原': '原優介', '吉田豊': '吉田豊',
         '川端': '川端海翼', '長浜': '長浜鴻緒', '上里': '上里直汰',
         '小牧加矢太': '小牧加矢', '永島まなみ': '永島まな'}

jset = set(jockeys)
res, unmatched = {}, []
for e in entries:
    cand = ALIAS.get(e['token'])
    if cand not in jset:
        cand = None
        # 完全一致 → 前方一致(3文字以上・一意) の順
        if e['token'] in jset:
            cand = e['token']
        else:
            pre = [j for j in jockeys if j.startswith(e['token'][:3])] if len(e['token']) >= 3 else []
            if len(pre) == 1:
                cand = pre[0]
    if cand:
        if cand in res and res[cand]['band'] != e['band']:
            res[cand]['conflict'] = True
        else:
            res[cand] = {'band': e['band'], 'm29': e['m29'], 'm30': e['m30'],
                         'roi': e['roi'], 'note': e['note'], 'token': e['token']}
    else:
        unmatched.append(e['token'])

miss = [j for j in jockeys if j not in res]
print(f'シート掲載トークン {len(entries)} / 結合成功 {len(res)}名')
print(f'当日騎乗 {len(jockeys)}名 中 運勢未結合 {len(miss)}名 = [不足]')
print('  未結合:', '、'.join(miss))
print(f'シート側で当日騎乗に紐づかないトークン {len(unmatched)}件(他場・非騎乗)')
print('\n8/29マーク分布(当日騎乗分):', dict(Counter(v['m29'] for v in res.values())))
json.dump({'map': res, 'unmatched_jockeys': miss}, open(OUT, 'w'), ensure_ascii=False, indent=1)
