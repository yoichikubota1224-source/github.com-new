# Windows メンテナンス用スクリプト（デスクトップ整理 / 容量確保）

Codex アプリが「容量不足」で起動しないときの復旧と、デスクトップの種類別仕分けを行うための
PowerShell スクリプト一式です。

> **すべて既定はドライラン（何も変更しない）です。** 実行するときだけ `-Apply` を付けます。
> デスクトップ整理は **移動のみ／削除しません**。削除するのは `Clear-SafeCache.ps1` の
> 一時ファイル・キャッシュだけです。

---

## 0. まず結論（推奨の実行順）

```powershell
# 0-1. スクリプトを置いたフォルダへ移動
cd $env:USERPROFILE\Downloads\windows

# 0-2. 何が容量を食っているか調べる（読み取りのみ・削除なし）
powershell -ExecutionPolicy Bypass -File .\Get-DiskReport.ps1

# 0-3. 安全なキャッシュだけ削除して空きを作る（まず見積り）
powershell -ExecutionPolicy Bypass -File .\Clear-SafeCache.ps1
powershell -ExecutionPolicy Bypass -File .\Clear-SafeCache.ps1 -Apply -PackageCaches -EmptyRecycleBin

# 0-4. デスクトップを種類別に仕分け（まず計画を確認）
powershell -ExecutionPolicy Bypass -File .\Sort-Desktop.ps1
powershell -ExecutionPolicy Bypass -File .\Sort-Desktop.ps1 -Apply
```

`0-3` で **C: の空きが最低 5GB、できれば 10GB 以上**になれば、Codex アプリは起動するはずです。

---

## 1. スクリプト一覧

| ファイル | 役割 | 削除の有無 |
|---|---|---|
| `Get-DiskReport.ps1` | 空き容量と容量を食っている場所の洗い出し | **なし**（読み取り専用） |
| `Clear-SafeCache.ps1` | 一時ファイル・キャッシュ・ごみ箱の削除 | あり（`-Apply` 時のみ） |
| `Sort-Desktop.ps1` | デスクトップを種類別フォルダへ仕分け | **なし**（移動のみ） |
| `Undo-SortDesktop.ps1` | 仕分けを元に戻す | **なし**（移動のみ） |

---

## 2. デスクトップ整理（種類別フォルダへ移動）

### 仕分け先フォルダ

デスクトップ直下に以下が作られ、そこへ移動します。

| フォルダ | 対象拡張子 |
|---|---|
| `01_画像` | jpg, jpeg, png, gif, bmp, webp, heic, tif, svg, ico |
| `02_PDF` | pdf |
| `03_Excel` | xlsx, xls, xlsm, xlsb, xltx, ods |
| `04_CSV・テキスト` | csv, tsv, txt, log, json, xml, md, yaml |
| `05_文書` | doc, docx, rtf, odt, ppt, pptx, one, epub |
| `06_圧縮` | zip, 7z, rar, tar, gz, lzh, cab, iso |
| `07_インストーラ` | exe, msi, msix, appx, msu |
| `08_動画・音声` | mp4, mov, avi, mkv, wmv, mp3, wav, m4a, flac |
| `09_ショートカット` | lnk, url（`-IncludeShortcuts` 指定時のみ） |
| `10_フォルダ` | フォルダ（`-IncludeFolders` 指定時のみ） |
| `99_その他` | 上記以外 |

### 動作の前提

- **ショートカット（.lnk）は既定で対象外**です。アイコン配置が崩れないようにするためです。
  まとめたい場合は `-IncludeShortcuts` を付けてください。
- **フォルダは既定で対象外**です。まとめたい場合は `-IncludeFolders`。
- `desktop.ini` などのシステムファイル、隠しファイルは触りません。
- 同名ファイルがあった場合は `名前_1.ext` のように連番を付けて退避します（上書きしません）。
- OneDrive でデスクトップがバックアップされている場合も自動検出します
  （`%OneDrive%\Desktop` / `%OneDrive%\デスクトップ`）。
- 開いたままでロックされているファイルは移動できず、警告として記録されます。
  ファイルを閉じてから再実行してください。

### 使い方

```powershell
# 計画だけ表示（何も動かさない）
powershell -ExecutionPolicy Bypass -File .\Sort-Desktop.ps1

# 実行
powershell -ExecutionPolicy Bypass -File .\Sort-Desktop.ps1 -Apply

# 30日より前に更新したものだけ仕分ける
powershell -ExecutionPolicy Bypass -File .\Sort-Desktop.ps1 -Apply -OlderThanDays 30

# ショートカットとフォルダも含めて全部まとめる
powershell -ExecutionPolicy Bypass -File .\Sort-Desktop.ps1 -Apply -IncludeShortcuts -IncludeFolders
```

### 元に戻す

移動内容は `%USERPROFILE%\DesktopSortLogs\desktop-sort_yyyyMMdd_HHmmss.csv` に残ります。

```powershell
# 最新ログの内容で「何を戻すか」だけ確認
powershell -ExecutionPolicy Bypass -File .\Undo-SortDesktop.ps1

# 実際に戻す（空になったカテゴリフォルダも削除）
powershell -ExecutionPolicy Bypass -File .\Undo-SortDesktop.ps1 -Apply -RemoveEmptyCategoryFolders
```

---

## 3. 容量確保（Codex アプリが開かない件）

### 3-1. 原因の切り分け

Electron 系のデスクトップアプリ（Codex アプリを含む）は、起動時に
キャッシュ／ログ／セッション情報を書き込みます。**C: の空きがほぼゼロだと
この書き込みに失敗し、ウィンドウが出ないまま終了します。**

まず `Get-DiskReport.ps1` で C: の空きを確認してください。

- 空き **5% 未満** → ほぼ確実にこれが原因
- 空き **10GB 以上あるのに起動しない** → 容量以外の原因（後述 3-4）

### 3-2. 安全に空けられる場所（`Clear-SafeCache.ps1` の対象）

| 対象 | 備考 |
|---|---|
| ユーザー一時ファイル `%TEMP%` | 3日より古いものだけ |
| `%LOCALAPPDATA%\Temp` | 同上 |
| `C:\Windows\Temp` | 管理者権限があるときだけ |
| CrashDumps / Windows エラー報告 | 数GBになっていることがある |
| npm / yarn / pip キャッシュ | `-PackageCaches` 指定時 |
| ごみ箱 | `-EmptyRecycleBin` 指定時 |

```powershell
# 見積りだけ
powershell -ExecutionPolicy Bypass -File .\Clear-SafeCache.ps1

# 実行（管理者PowerShellで実行すると Windows\Temp まで消せて効果大）
powershell -ExecutionPolicy Bypass -File .\Clear-SafeCache.ps1 -Apply -PackageCaches -EmptyRecycleBin
```

### 3-3. スクリプトでは消さない／手動で判断する場所

自動削除すると事故りやすいので、レポートで大きかったものだけ手で対処してください。

1. **Windows Update のダウンロードキャッシュ / 以前のWindows**
   `Win + R` → `cleanmgr` → C: → 「システム ファイルのクリーンアップ」
   → 「Windows Update のクリーンアップ」「以前の Windows のインストール」にチェック。
   Windows 10/11 のアップグレード後は **10〜30GB** 空くことがあります。

2. **OneDrive がローカルに全部ダウンロードされている**
   エクスプローラーで OneDrive フォルダを右クリック →「空き容量を増やす」
   （ファイル オンデマンド）。数十GB空くことがあります。
   設定 → OneDrive → 「すべてのファイルをダウンロード」がONだと再び埋まります。

3. **WSL / Docker の仮想ディスク（.vhdx）**
   レポートの【5】に出たものが数十GBなら、
   `wsl --shutdown` の後に `diskpart` の `compact vdisk` で圧縮できます。
   Docker Desktop なら Settings → Resources → 「Clean / Purge data」。

4. **`node_modules` の山**
   作業用フォルダに大量にある場合、使っていないプロジェクトのものは削除して構いません
   （`npm install` で復元できます）。

5. **ストレージセンサーを有効化（再発防止）**
   設定 → システム → 記憶域 → 「ストレージ センサー」をオン、
   「一時ファイル」「ごみ箱 30日」を自動削除に。

### 3-4. 容量を空けても Codex アプリが起動しない場合

C: に 10GB 以上の空きを作った上で、上から順に試してください。

1. **アプリを完全終了してから再起動**
   タスクマネージャー → 「詳細」タブ → `Codex` 関連プロセスをすべて終了 → 再度起動。

2. **アプリのキャッシュだけ削除**（設定は残ります）
   ```powershell
   # 該当フォルダの場所を確認（消す前に必ず中身を確認）
   Get-ChildItem $env:APPDATA, $env:LOCALAPPDATA -Filter '*odex*' -Directory -ErrorAction SilentlyContinue |
       Select-Object FullName
   ```
   見つかったフォルダ配下の `Cache` / `Code Cache` / `GPUCache` のみ削除。
   **`.codex` 直下の設定ファイルや認証情報は消さないでください**（再ログインが必要になります）。

3. **再インストール**
   設定 → アプリ → Codex をアンインストール → 公式サイトから再インストール。

4. それでも起動しない場合は、起動時のエラーログ
   （`%APPDATA%` 配下の Codex フォルダ内 `logs`、または `%USERPROFILE%\.codex\log`）
   を確認してください。ログの中身を貼っていただければ切り分けます。

---

## 4. 実行ポリシーで止まる場合

「このシステムではスクリプトの実行が無効になっているため…」と出たら、
コマンド側で明示的にバイパスしてください（設定は変更されません）。

```powershell
powershell -ExecutionPolicy Bypass -File .\Sort-Desktop.ps1
```

ファイルがインターネット経由でブロックされている場合は、次で解除できます。

```powershell
Get-ChildItem .\*.ps1 | Unblock-File
```

---

## 5. 注意事項

- スクリプトは **Windows PowerShell 5.1 / PowerShell 7 の両方**で動作します。
- `Clear-SafeCache.ps1` を管理者で実行すると `C:\Windows\Temp` まで対象になり効果が大きいですが、
  まず必ずドライラン（`-Apply` なし）で削除見込みを確認してください。
- 業務データ（デスクトップ・ドキュメント・ダウンロード）を削除するスクリプトは含まれていません。
