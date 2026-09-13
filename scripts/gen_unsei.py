#!/usr/bin/env python3
# 騎手運勢(六星占術24グループ)の日運を、正本ツール「①日運自動」の数式どおりに算出する。
#   星数     = MOD(対象日 - DATE(1950,1,1) + 32, 60) + 1
#   基準位相 = MOD(2*星人帯 + (−:-2 / ＋:-1), 12)
#   日運     = サイクル[ MOD( MOD(星数,12) + 基準位相, 12) ]
# 霊合(霊)は記号の対応表だけが異なり、位相は本体と同じ。
import datetime, sys

CYCLE = ['種子', '緑生', '立花', '健弱', '達成', '乱気', '再会', '財成', '安定', '陰影', '停止', '減退']
BAND = {'土星': 0, '金星': 1, '火星': 2, '天王星': 3, '木星': 4, '水星': 5}
# シートの行順(3行目から26行目)
GROUPS = [
    '金星－', '金星＋', '金星霊－', '金星霊＋',
    '木星－', '木星＋', '木星霊－', '木星霊＋',
    '水星－', '水星＋', '水星霊－', '水星霊＋',
    '火星－', '火星＋', '火星霊－', '火星霊＋',
    '土星－', '土星＋', '土星霊－', '土星霊＋',
    '天王星－', '天王星＋', '天王星霊－', '天王星霊＋',
]
BASIC = {'達成': '◎◎', '立花': '◎', '財成': '◎', '安定': '◎',
         '種子': '○', '緑生': '○', '再会': '○',
         '健弱': '△', '乱気': '△',
         '陰影': '×', '停止': '×', '減退': '×'}
REIGO = {'安定': '◎◎', '陰影': '×', '停止': '×', '減退': '×'}   # 他はすべて ○

EPOCH = datetime.date(1899, 12, 30)          # Excelシリアルの基準
D1950 = (datetime.date(1950, 1, 1) - EPOCH).days   # = 18264


def serial(d):
    return (d - EPOCH).days


def parse_group(g):
    rei = '霊' in g
    sign = -1 if g.endswith('－') else +1
    star = g.replace('霊', '').rstrip('－＋')
    return BAND[star], sign, rei


def unsei(date, group):
    band, sign, rei = parse_group(group)
    seisu = (serial(date) - D1950 + 32) % 60 + 1
    phase = (2 * band + (-2 if sign < 0 else -1)) % 12
    cyc = CYCLE[(seisu % 12 + phase) % 12]
    mark = REIGO.get(cyc, '○') if rei else BASIC[cyc]
    return cyc, mark


if __name__ == '__main__':
    for ds in sys.argv[1:]:
        d = datetime.date.fromisoformat(ds)
        print(f'== {ds} (serial {serial(d)}) ==')
        for g in GROUPS:
            c, m = unsei(d, g)
            print(f'{g:<7} {m:<2} {c}')
