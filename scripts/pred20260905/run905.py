#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2026-09-05 パイプラインを実行証跡付きで順に走らせる（第7報）。
build905.py → unsei905.py → composite905.py の順。各ステップについて 開始/終了(UTC)・終了コード・
スクリプトsha256・入力sha256(実行前)・出力sha256/bytes(実行後)・標準出力末尾 を run_log_20260905.json に残す。
⚠ 原本(6CSV・xlsx・調教CSV)は読むだけで書き換えない。凍結モデル are_score_v21 本体は実行も変更もしない。"""
import subprocess, hashlib, json, os, sys, datetime
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
D = os.path.join(REPO, 'predictions', '20260905')
SP = '/tmp/claude-0/-home-user-github-com-new/47c1892c-ddc4-50e4-8b6f-3403a9782673/scratchpad'
PACK = os.environ.get('PACK905', os.path.join(SP, 'd0905', 'pack.json'))
RAW = os.path.join(SP, 'd0905', 'pack')   # 6CSV原本の作業コピー（リポジトリには置かない）

def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()
def fp(p):
    return dict(path=os.path.relpath(p, REPO) if p.startswith(REPO) else p, bytes=os.path.getsize(p), sha256=sha(p)) if os.path.exists(p) else dict(path=p, missing=True)
def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')

j = lambda *a: os.path.join(D, *a)
STEPS = [
    dict(script='build905.py',
         inputs=[PACK, j('shutuba_20260905.json'), j('hits_20260905.json'), j('jisou905.json')],
         outputs=[j('toukei_20260905.json')]),
    dict(script='unsei905.py',
         inputs=[j('toukei_20260905.json'), j('運勢_20260905-06_結合用.csv'), os.path.join(SP, 'trainer_seijin.tsv'), PACK],
         outputs=[j('unsei_20260905.json'), j('unsei_4kubun_20260905.csv')]),
    dict(script='composite905.py',
         inputs=[j('toukei_20260905.json'), j('chokyo_20260905.json'), j('unsei_20260905.json'), j('jisou905.json')],
         outputs=[j('composite.json')]),
]
git = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=REPO, capture_output=True, text=True).stdout.strip()
log = dict(version='run905_v1', raceday='20260905', started=now(), git_head_before=git,
           python=sys.version.split()[0], numpy_pandas='未使用（環境に無い。凍結版はpandas/numpy依存のため実行していない）',
           source_csv=[fp(os.path.join(RAW, f)) for f in sorted(os.listdir(RAW))] if os.path.isdir(RAW) else '[不足] 原本作業コピー無し',
           steps=[])
ok = True
for s in STEPS:
    sp = os.path.join(HERE, s['script'])
    rec = dict(script=fp(sp), inputs=[fp(p) for p in s['inputs']], started=now())
    r = subprocess.run([sys.executable, sp], cwd=REPO, capture_output=True, text=True, env=dict(os.environ, PACK905=PACK))
    rec.update(finished=now(), exit_code=r.returncode, stdout_tail=r.stdout.strip().splitlines()[-12:], stderr_tail=r.stderr.strip().splitlines()[-5:],
               outputs=[fp(p) for p in s['outputs']])
    log['steps'].append(rec)
    print(f"[{'OK' if r.returncode == 0 else 'FAIL'}] {s['script']} exit={r.returncode} {rec['started']}→{rec['finished']}")
    if r.returncode != 0:
        ok = False; print(r.stderr[-2000:]); break
log['finished'] = now(); log['all_ok'] = ok
out = j('run_log_20260905.json')
json.dump(log, open(out, 'w'), ensure_ascii=False, indent=1)
print('書き出し:', out, '/ all_ok =', ok)
