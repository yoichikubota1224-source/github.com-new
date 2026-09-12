# -*- coding: utf-8 -*-
import datetime, sys
CYCLE=["種子","緑生","立花","健弱","達成","乱気","再会","財成","安定","陰影","停止","減退"]
BAND={"土星":0,"金星":1,"火星":2,"天王星":3,"木星":4,"水星":5}
BASIC={"達成":"◎◎","立花":"◎","財成":"◎","安定":"◎","種子":"○","緑生":"○","再会":"○",
       "健弱":"△","乱気":"△","陰影":"×","停止":"×","減退":"×"}
def rei(c): return "◎◎" if c=="安定" else ("×" if c in ("陰影","停止","減退") else "○")
EPOCH=datetime.date(1899,12,30)                      # Excelシリアル基準
def serial(d): return (d-EPOCH).days
D1950=serial(datetime.date(1950,1,1))                # 18264
def parse_group(g):
    reigou = "霊" in g
    sign = -2 if ("－" in g or "-" in g) else -1      # －: -2 / ＋: -1
    base = g.replace("霊","").replace("－","").replace("＋","").replace("-","").replace("+","")
    return base, BAND[base], reigou, sign
def unsei(group, d):
    base, band, reigou, sign = parse_group(group)
    seisu = (serial(d) - D1950 + 32) % 60 + 1
    phase = (2*band + sign) % 12
    cyc = CYCLE[(seisu % 12 + phase) % 12]
    return cyc, (rei(cyc) if reigou else BASIC[cyc]), seisu

# 検証用の既知値: 騎手運勢2026.09.12.xlsx 先頭シート B列(9/12)・C列(9/13)
KNOWN = {
 "金星－":("◎","△"),   "金星＋":("△","◎◎"), "金星霊－":("○","○"),  "金星霊＋":("○","○"),
 "木星－":("◎","×"),   "木星＋":("×","×"),   "木星霊－":("◎◎","×"), "木星霊＋":("×","×"),
 "水星－":("×","×"),   "水星＋":("×","○"),   "水星霊－":("×","×"),  "水星霊＋":("×","○"),
 "火星－":("◎◎","△"),  "火星＋":("△","○"),   "火星霊－":("○","○"),  "火星霊＋":("○","○"),
 "土星－":("○","○"),   "土星＋":("○","◎"),   "土星霊－":("○","○"),  "土星霊＋":("○","○"),
 "天王星－":("○","◎"),  "天王星＋":("◎","◎"),  "天王星霊－":("○","○"), "天王星霊＋":("○","◎◎"),
}

def selftest():
    d1, d2 = datetime.date(2026, 9, 12), datetime.date(2026, 9, 13)
    ok = ng = 0
    for g, (b, c) in KNOWN.items():
        s1 = unsei(g, d1)[1]; s2 = unsei(g, d2)[1]
        ok += (s1 == b) + (s2 == c); ng += (s1 != b) + (s2 != c)
        if s1 != b or s2 != c:
            print(f"  NG {g}: 計算 {s1}/{s2} vs 実 {b}/{c}")
    print(f"自己検証: {ok}/{ok+ng} 一致 (星数 9/12={unsei('土星－', d1)[2]} 9/13={unsei('土星－', d2)[2]})")
    return ng == 0

if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.exit(0 if selftest() else 1)
    # 使い方: python3 scripts/rokusei_unsei.py YYYY-MM-DD [YYYY-MM-DD ...]
    for a in sys.argv[1:]:
        d = datetime.date(*map(int, a.split("-")))
        print(f"\n== {a} (星数 {unsei('土星－', d)[2]}) ==")
        for g in KNOWN:
            cyc, sym, _ = unsei(g, d)
            print(f"  {g:<9}{sym:<3}{cyc}")

