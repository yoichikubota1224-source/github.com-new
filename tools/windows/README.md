# Windows メンテナンス用スクリプト（デスクトップ整理 / 容量確保）

Codex アプリが「容量不足」で起動しないときの復旧と、デスクトップの種類別仕分けを行うための
PowerShell スクリプト一式です。

> **すべて既定はドライラン（何も変更しない）です。** 実行するときだけ `-Apply` を付けます。
> デスクトップ整理は **移動のみ／削除しません**。削除するのは `Free-Space.ps1` の
> キャッシュ・一時ファイルだけで、ユーザーデータには一切触れません。

---

## 0. まず結論（推奨の実行順）

いちばん簡単なのは **`RUN_空き容量確保.bat` をダブルクリック**するだけです。
管理者昇格 → 削除見積り表示 → Y/N 確認 → 実行、まで一気に進みます。

コマンドで細かく制御したい場合：

```powershell
# 0-1. スクリプトを置いたフォルダへ移動
cd $env:USERPROFILE\Downloads\windows

# 0-2. 何が容量を食っているか調べる（読み取りのみ・削除なし）
powershell -ExecutionPolicy Bypass -File .\Get-DiskReport.ps1

# 0-3. どれだけ空くか見積もる → 実行
powershell -ExecutionPolicy Bypass -File .\Free-Space.ps1
powershell -ExecutionPolicy Bypass -File .\Free-Space.ps1 -Apply

# 0-4. それでも足りなければ管理者PowerShellで Deep（時間がかかります）
powershell -ExecutionPolicy Bypass -File .\Free-Space.ps1 -Level Deep -Apply

# 0-5. デスクトップを種類別に仕分け（まず計画を確認）
powershell -ExecutionPolicy Bypass -File .\Sort-Desktop.ps1
powershell -ExecutionPolicy Bypass -File .\Sort-Desktop.ps1 -Apply
```

C: の空きが **10GB 以上**になれば、Codex アプリは起動するはずです。

---

## 1. スクリプト一覧

| ファイル | 役割 | 削除の有無 |
|---|---|---|
| `RUN_空き容量確保.bat` | ダブルクリック用ランチャー（昇格→見積り→確認→実行） | `Free-Space.ps1` を呼ぶだけ |
| `Free-Space.ps1` | 空き容量の確保（キャッシュ・一時ファイルの削除） | あり（`-Apply` 時のみ） |
| `Get-DiskReport.ps1` | 空き容量と容量を食っている場所の洗い出し | **なし**（読み取り専用） |
| `Sort-Desktop.ps1` | デスクトップを種類別フォルダへ仕分け | **なし**（移動のみ） |
| `Undo-SortDesktop.ps1` | 仕分けを元に戻す | **なし**（移動のみ） |

---

## 2. 容量確保（`Free-Space.ps1`）

### 2-1. 3つのレベル

| レベル | 内容 | 代償 |
|---|---|---|
| `Safe` | 一時ファイル・クラッシュダンプ・シェーダーキャッシュ・Electron系アプリのキャッシュ | なし |
| `Standard`（既定） | 上記＋ごみ箱・ブラウザのHTTPキャッシュ・Windows Updateキャッシュ・Windowsログ・開発ツールのパッケージキャッシュ | ページの再読み込みが一度遅くなる／npm等が再ダウンロードになる |
| `Deep` | 上記＋DISMコンポーネントストア掃除・ディスククリーンアップ無人実行（Windows.old 含む）・シャドウコピー上限縮小・MEMORY.DMP | 更新のアンインストール不可・以前のWindowsへ戻せない・古い復元ポイントが消える |

`Deep` は管理者権限が必要で、DISM だけで 10〜60 分かかります。

### 2-2. ユーザーデータを削除しない仕組み

削除は多層のガード（`Test-SafeToDelete`）を通ったパスにしか行いません。

1. 絶対パスであること
2. 3階層以上であること（`C:\` や `C:\Windows` は問答無用で拒否）
3. **許可ルートの配下**であること（`%LOCALAPPDATA%`・`%APPDATA%`・`%TEMP%`・
   `%ProgramData%` の特定サブフォルダ・`%SystemRoot%\Temp` など。ホワイトリスト方式）
4. 許可ルート**そのもの**を消そうとしていないこと（専用の一時領域のみ例外）
5. 禁止パターンに一致しないこと
   — デスクトップ／ドキュメント／ダウンロード／ピクチャ／ビデオ／ミュージック、
   OneDrive・Dropbox・Google Drive、Outlook の `.ost` / `.pst`、
   Cookie・ログイン情報・ブックマーク・Local Storage、
   `.ssh` / `.aws` / `.gnupg` / `.kube`、証明書・資格情報ストア、`.git` など
6. リパースポイント（ジャンクション／シンボリックリンク）でないこと

さらに、

- **一時ファイルは既定で「7日より前に更新されたもの」だけ**削除します
  （実行中アプリやインストール途中の展開物を巻き込まないため）。`-TempOlderThanDays` で変更可。
- ブラウザは `Cache` / `Code Cache` / `GPUCache` だけを対象にします。
  **Cookie やログイン情報は消さないので、ログイン状態は維持されます。**
- サムネイル／アイコンキャッシュは explorer.exe の再起動が必要なため、
  既定ではスキップします（`-RestartExplorer` で有効化）。
- ディスククリーンアップの無人実行では、ダウンロードフォルダーとごみ箱のハンドラを
  明示的に無効化してから走らせます。

### 2-3. 回収量の報告について

- 削除に**成功したファイルのバイト数だけ**を積算します（失敗を握り潰して過大報告しません）。
- 最終的な数字は **C: の空き容量の実測差分**で報告します。
- 積算値と実測差分が大きく食い違う場合はその旨を表示します
  （他プロセスの書き込み・OneDrive の再同期などが原因）。
- 同じ実体を指すターゲット（`%TEMP%` と `%LOCALAPPDATA%\Temp` など）や
  入れ子になったターゲットは重複排除してから見積もります。

### 2-4. 削除しない大物（報告のみ）

自動削除すると事故りやすいものは、容量と対処方法だけ表示します。

| 対象 | 対処 |
|---|---|
| `hiberfil.sys`（休止状態） | `powercfg /h /type reduced` で縮小、`/h off` で無効化。**ノートPCは電池切れ時の退避を失う**ので注意 |
| `pagefile.sys` | 削除不可。仮想メモリを固定サイズに制限する |
| `Windows.old` | `-Level Deep` の cleanmgr 経由で削除（ロールバック不可になる） |
| Docker / WSL の `.vhdx` | `prune` だけでは C: は空きません。`wsl --shutdown` → `diskpart` の `compact vdisk` で初めて縮みます |
| OneDrive のローカル実体 | 右クリック →「空き容量を増やす」（ファイルは残りクラウドのみに）。※クラウドのみのファイルは容量に数えていません |
| ダウンロード フォルダー | ユーザーデータなので手動で確認 |
| Maven / Gradle / Cargo | 再取得可能。オフライン作業予定がなければ削除可 |

---

## 3. デスクトップ整理（種類別フォルダへ移動）

### 仕分け先フォルダ

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

- **ショートカット（.lnk）とフォルダは既定で対象外**（アイコン配置が崩れないように）
- `desktop.ini` などのシステム／隠しファイルは触りません
- 同名ファイルは上書きせず `名前_1.ext` の連番で退避
- OneDrive リダイレクト先のデスクトップも自動検出
- 開いたままロックされているファイルは移動できず、警告として記録されます

```powershell
powershell -ExecutionPolicy Bypass -File .\Sort-Desktop.ps1                       # 計画のみ
powershell -ExecutionPolicy Bypass -File .\Sort-Desktop.ps1 -Apply                # 実行
powershell -ExecutionPolicy Bypass -File .\Sort-Desktop.ps1 -Apply -OlderThanDays 30
```

### 元に戻す

移動内容は `%USERPROFILE%\DesktopSortLogs\desktop-sort_yyyyMMdd_HHmmss.csv` に残ります。

```powershell
powershell -ExecutionPolicy Bypass -File .\Undo-SortDesktop.ps1                   # 確認のみ
powershell -ExecutionPolicy Bypass -File .\Undo-SortDesktop.ps1 -Apply -RemoveEmptyCategoryFolders
```

---

## 4. Codex アプリが開かない件

Electron 系のデスクトップアプリは、起動時にキャッシュ／ログ／セッション情報を書き込みます。
**C: の空きがほぼゼロだとこの書き込みに失敗し、ウィンドウが出ないまま終了します。**

- 空き **5% 未満** → ほぼ確実にこれが原因。`Free-Space.ps1` で解消するはず
- 空き **10GB 以上あるのに起動しない** → 容量以外の原因。以下を順に

1. **完全終了してから再起動**
   タスクマネージャー →「詳細」タブ → `Codex` 関連プロセスをすべて終了 → 再度起動

2. **アプリのキャッシュだけ削除**（設定・認証情報は残す）
   ```powershell
   Get-ChildItem $env:APPDATA, $env:LOCALAPPDATA -Filter '*odex*' -Directory -ErrorAction SilentlyContinue |
       Select-Object FullName
   ```
   見つかったフォルダ配下の `Cache` / `Code Cache` / `GPUCache` のみ削除。
   **`.codex` 直下の設定ファイルや認証情報は消さないでください**（再ログインが必要になります）。

3. **再インストール**
   設定 → アプリ → Codex をアンインストール → 公式サイトから再インストール

4. 起動時のログ（`%APPDATA%` 配下の Codex フォルダ内 `logs`、または `%USERPROFILE%\.codex\log`）
   を確認。内容を貼っていただければ切り分けます

---

## 5. 実行ポリシー・文字化けなど

「このシステムではスクリプトの実行が無効になっているため…」と出たら、
コマンド側でバイパスしてください（システム設定は変更されません）。

```powershell
powershell -ExecutionPolicy Bypass -File .\Free-Space.ps1
```

インターネット経由で取得したファイルがブロックされている場合：

```powershell
Get-ChildItem .\*.ps1 | Unblock-File
```

- `.ps1` は **UTF-8 BOM + CRLF** で保存しています（Windows PowerShell 5.1 で日本語が化けないため）
- `.bat` は **ASCII のみ**にしています（cmd.exe は .bat をコンソールの OEM コードページで読むため、
  日本語を書くと環境によって化けます）

---

## 6. 注意事項

- **実機の Windows での動作確認は行っていません。** 必ず最初は `-Apply` なしのドライランで
  内容を確認してから実行してください。
- パスが 260 文字を超えるファイルは削除に失敗することがあります。失敗件数は最後に報告されます。
- 業務データ（デスクトップ・ドキュメント・ダウンロード）を削除するコードは含まれていません。
