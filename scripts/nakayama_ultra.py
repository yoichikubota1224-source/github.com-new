# -*- coding: utf-8 -*-
"""中山のウルトラ条件(No.017〜030)の照合。
出所: ウルトラ回収率テンプレート_東京京都阪神中山追記版..._札幌函館追記.csv (Drive自己取得)
      当方が最初に使った ウルトラ回収率2026.02.22.xlsx には 017〜030 が存在しなかった(欠落版)。
      NotebookLMは本拡張版を参照していた。
"""
import csv, json
SP="/tmp/claude-0/-home-user-github-com-new/84a20921-3b38-53dd-8669-b122c897a190/scratchpad/umb"
E="/root/.claude/uploads/84a20921-3b38-53dd-8669-b122c897a190/2c3472cb-DE260912.CSV"
prev=json.load(open(f'{SP}/prev.json'))
wa={(x['venue'],x['r'],x['umaban']):x for x in json.load(open(f'{SP}/weight_allow.json')).values()}
rows=[r for r in csv.reader(open(E,encoding='cp932')) if r[1]=='中山' and '障害' not in r[4]]
IO={1600:'外',2000:'内',2500:'内',1200:'',1800:''}
# (No, 芝ダ, 距離集合, 内外, ターゲット判定, 条件②判定, 条件テキスト, t3, 単, 複, 券種)
def sire(n): return lambda h,p: (h[16].strip()==n, f"父={h[16].strip()}")
def jk(n):  return lambda h,p: (h[10].strip().startswith(n[:4]) or n.startswith(h[10].strip()), f"騎手={h[10].strip()}")
# 条件定義(中山ウルトラ017〜030)はこのファイルに含めません。
# 理由: 書籍(Kindle)由来の条件文と回収率が同一行にあり、本リポジトリは public です。
#       羊一様の常設指示「ROI原数値や資料の公開範囲は未確認として扱い、
#       新規公開先への転載・アップロードをしない」に従い外部化しました。
# 完全な定義は ChatGPT渡しパック `07_条件定義_中山ウルトラ.py.txt` にあります。
# 再現するにはそのファイルを同ディレクトリに置いて下記で読み込んでください。
import os, ast
_def = os.environ.get('ULTRA_COND_FILE', '07_条件定義_中山ウルトラ.py.txt')
if not os.path.exists(_def):
    raise SystemExit(f"条件定義ファイルがありません: {_def}\n"
                     "非公開資料のためリポジトリには含まれていません。"
                     "ChatGPT渡しパックから取得してください。")
_ns={'sire':sire,'jk':jk}
exec(open(_def,encoding='utf-8').read(), _ns)
COND=_ns['COND']
CENTRAL={'札幌','函館','福島','新潟','東京','中山','中京','京都','阪神','小倉'}
def eval2(kind,h,p,R):
    if kind is None: return None,'条件②の機械判定を実装せず(要確認)'
    u=int(h[3]); fld=int(h[26]); age=int(h[9])
    w=wa.get(('中山',R,u))
    if kind=='prev9_central':
        if not p.get('found'): return False,f"前走なし({p.get('reason')})"
        return (p['chaku'] is not None and p['chaku']<=9 and p['venue'] in CENTRAL), f"前走{p['chaku']}着/{p['venue']}"
    if kind=='noded_miho':
        if w is None or w['deduction'] is None: return None,'減量導出不可'
        return (w['deduction']==0 and h[13]=='美'), f"減量{w['deduction']}kg/所属{h[13]}"
    if kind=='prev3f5_uma12':
        if not p.get('found'): return False,f"前走なし({p.get('reason')})"
        return (p['rank3f'] is not None and p['rank3f']<=5 and 1<=u<=12), f"前走上り{p['rank3f']}位/馬番{u}"
    if kind=='prev10_naka4w':
        if not p.get('found'): return False,f"前走なし({p.get('reason')})"
        return (p['chaku'] is not None and p['chaku']<=10 and p['weeks']>=4), f"前走{p['chaku']}着/中{p['weeks']:.0f}週"
    if kind=='uma13_field11':
        return (1<=u<=13 and fld>=11), f"馬番{u}/{fld}頭"
    if kind=='noded_prevdirt':
        if w is None or w['deduction'] is None: return None,'減量導出不可'
        if not p.get('found'): return False,f"前走なし({p.get('reason')})"
        return (w['deduction']==0 and p['sd']=='ダ'), f"減量{w['deduction']}kg/前走{p['sd']}"
    if kind=='prev11':
        if not p.get('found'): return False,f"前走なし({p.get('reason')})"
        return (p['chaku'] is not None and p['chaku']<=11), f"前走{p['chaku']}着"
    if kind=='age4_prev4c4':
        if not p.get('found'): return False,f"前走なし({p.get('reason')})"
        return (age<=4 and p['corner4'] is not None and p['corner4']<=4), f"{age}歳/前走4角{p['corner4']}"
    if kind=='field16':
        return (fld==16), f"{fld}頭"
    if kind=='prevbw470_10w':
        if not p.get('found'): return False,f"前走なし({p.get('reason')})"
        return (p['bodyweight'] is not None and p['bodyweight']>=470 and p['weeks']<=10), f"前走{p['bodyweight']:.0f}kg/中{p['weeks']:.0f}週"
    return None,'?'
byk={r[32]:r for r in rows}
print("="*118); print("中山ウルトラ 017〜030 の照合（当日の中山12Rに対して）"); print("="*118)
hits=[]; pend=[]
for no,sd,dists,io,tgt,c2,txt,t3,tan,fuku,ken in COND:
    applies=[r for r in rows if r[5].strip()==sd and int(r[6]) in dists and (io is None or IO.get(int(r[6],10) if False else int(r[6]),'')==io)]
    rs=sorted(set(int(r[2]) for r in applies))
    if not rs:
        print(f"\nU{no} {sd}{'/'.join(map(str,sorted(dists)))}{io or ''}  → 当日該当レースなし（範囲外）"); continue
    print(f"\nU{no} {sd}{'/'.join(map(str,sorted(dists)))}{io or ''}  適用R={rs}  条件: {txt}  (3着内{t3}% 単{tan} 複{fuku} {ken})")
    if tgt is None:
        print("   → ターゲットが父系(ディープインパクト系)で当方の判定対象外 → 保留"); continue
    n=0
    for r in applies:
        R=int(r[2]); ok,why = tgt(r,None) if callable(tgt) else (None,'')
        if ok is None:
            continue
        if not ok: continue
        p=prev.get(r[32],{})
        v2,why2 = eval2(c2,r,p,R)
        n+=1
        mark = '**確定**' if v2 is True else ('除外' if v2 is False else '保留(判定不能)')
        print(f"   {R:>2}R {r[3]:>3}番 枠{r[22]} {r[7]:<14}{r[8]}{r[9]} {r[10]:<9} {why} / {why2} → {mark}")
        if v2 is True: hits.append((no,R,int(r[3]),r[7],r[8]+r[9],r[10],txt,t3,tan,fuku,ken))
        elif v2 is None: pend.append((no,R,int(r[3]),r[7],why2))
    if n==0: print("   → ターゲット一致馬なし")
print()
print("="*118); print(f"【中山ウルトラの確定該当 {len(hits)}件】"); print("="*118)
for no,R,u,nm,sa,j,txt,t3,tan,fuku,ken in hits:
    warn = "  ※単勝回収率100未満＝複勝向き" if tan<100 else ""
    print(f"  U{no}  中山{R}R {u:>2}番 {nm:<14}{sa:<5}{j:<9} 3着内{t3}% 単{tan} 複{fuku} 推奨={ken}{warn}")
    print(f"        条件={txt}")
if pend:
    print(f"\n【保留 {len(pend)}件】")
    for no,R,u,nm,why in pend: print(f"  U{no} 中山{R}R {u}番 {nm} — {why}")
json.dump([dict(no=h[0],r=h[1],umaban=h[2],name=h[3],sa=h[4],jk=h[5],cond=h[6],t3=h[7],tan=h[8],fuku=h[9],ken=h[10]) for h in hits],
          open(f'{SP}/nakayama_ultra_hits.json','w'), ensure_ascii=False, indent=1)
