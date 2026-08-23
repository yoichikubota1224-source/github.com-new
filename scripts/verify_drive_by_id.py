#!/usr/bin/env python3
# Drive登録の無破損検証(fileIdキー版)。
# ファイル名は一意な識別子ではない — Drive の update_file は内容を更新できず、
# 「新規create + 旧版リネーム」で版を重ねるため、同名の複数版が併存しうる。
# また 8/22 と 8/23 で同名ファイル(compi_chukyo.json 等)が存在する。
# 名前キーで照合すると旧版・別日を拾って誤判定するので、常に fileId をキーにする。
#
# 使い方: verify_drive_by_id.py <fileId>=<ローカルパス> ...
import base64, hashlib, json, glob, os, sys

PROJ = '/root/.claude/projects/-home-user-github-com-new/47c1892c-ddc4-50e4-8b6f-3403a9782673'
PATHS = [PROJ + '.jsonl'] + sorted(glob.glob(os.path.join(PROJ, 'subagents', '*.jsonl')))

want = dict(a.split('=', 1) for a in sys.argv[1:])
seen = {}


def harvest(payload):
    if isinstance(payload, list):
        payload = ''.join(b.get('text', '') for b in payload if isinstance(b, dict))
    if not isinstance(payload, str):
        return
    s = payload.strip()
    # ツール結果が別ファイルへ退避されている場合はそれを読む
    if 'tool-results' in s and len(s) < 4000:
        for tok in s.replace('"', ' ').replace("'", ' ').split():
            if tok.endswith('.txt') and os.path.exists(tok):
                s = open(tok, errors='replace').read().strip()
                break
    if '"content"' not in s or '"id"' not in s:
        return
    try:
        obj = json.loads(s)
        fid = obj.get('id')
        if fid not in want:
            return
        raw = base64.b64decode(obj['content'], validate=True)
    except Exception:
        return
    # 同一fileIdで複数のSHAが観測されたら異本衝突として検出する
    seen.setdefault(fid, {})[hashlib.sha256(raw).hexdigest()] = len(raw)


for path in PATHS:
    uses = {}
    try:
        fh = open(path, errors='replace')
    except Exception:
        continue
    for line in fh:
        try:
            o = json.loads(line)
        except Exception:
            continue
        c = (o.get('message') or {}).get('content')
        if not isinstance(c, list):
            continue
        for it in c:
            if not isinstance(it, dict):
                continue
            if it.get('type') == 'tool_use':
                uses[it.get('id')] = it.get('name')
            elif it.get('type') == 'tool_result' and \
                    uses.get(it.get('tool_use_id')) == 'mcp__Google_Drive__download_file_content':
                harvest(it.get('content'))

rc = 0
for fid, local in want.items():
    if not os.path.exists(local):
        print(f'MISSING_LOCAL {local}')
        rc = 1
        continue
    lb = open(local, 'rb').read()
    lh = hashlib.sha256(lb).hexdigest()
    v = seen.get(fid)
    name = os.path.basename(local)
    if not v:
        print(f'NO_DOWNLOAD   {name}  (fileId {fid} は本セッションで未取得)')
        rc = 1
    elif len(v) > 1:
        print(f'VARIANTS      {name}  同一fileIdで異本 {v}')
        rc = 1
    else:
        dh, db = list(v.items())[0]
        tag = 'OK        ' if dh == lh else 'MISMATCH  '
        print(f'{tag}    {name}  local={len(lb)}B drive={db}B sha={dh[:16]}')
        if dh != lh:
            rc = 1
print('\nRESULT:', 'ALL MATCH' if rc == 0 else 'ERRORS')
sys.exit(rc)
