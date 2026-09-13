<#
.SYNOPSIS
    C: ドライブの空き容量を確保します（キャッシュ・一時ファイルのみ削除）。

.DESCRIPTION
    既定はドライラン（削除見込みの表示のみ）。実際に削除するには -Apply を付けます。

    ユーザーデータ（デスクトップ／ドキュメント／ダウンロード／ピクチャ／OneDrive の実ファイル・
    Outlook の OST/PST・認証情報）には一切触れません。多層のガードで、許可されたルート配下
    かつ禁止パターンに一致しないパスしか削除しません。

    Level で削除の強さを選びます。
      Safe     : 副作用ゼロ。純粋なゴミのみ（一時ファイル・クラッシュダンプ・シェーダーキャッシュ等）
      Standard : 既定。上記＋ごみ箱・ブラウザHTTPキャッシュ・Windows Updateキャッシュ・
                 開発ツールのパッケージキャッシュ（再ダウンロードで復元可能なもの）
      Deep     : 上記＋DISMコンポーネントストア掃除・ディスククリーンアップ無人実行
                 （Windows.old を含む）・シャドウコピー上限縮小。管理者権限が必要で時間がかかります。

    削除しない大物（休止ファイル・ページファイル・Docker/WSL の仮想ディスク・OneDrive の
    ローカル実体など）は、最後に「手動判断が必要な大物」として容量だけ報告します。

.PARAMETER Level
    Safe / Standard / Deep。既定は Standard。

.PARAMETER Apply
    実際に削除します。付けない場合は見積りのみ。

.PARAMETER Interactive
    見積りを表示してから Y/N で確認し、Y なら削除します（バッチランチャー用）。

.PARAMETER TempOlderThanDays
    一時ファイルは「最終更新がこの日数より前」のものだけ削除します。既定 7。
    実行中アプリの一時ファイルを巻き込まないための安全弁です。0 にはできません。

.PARAMETER RestartExplorer
    サムネイル／アイコンキャッシュを削除するために explorer.exe を再起動します。
    デスクトップが一瞬消えて再描画されます。既定は無効（該当ターゲットはスキップ）。

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\Free-Space.ps1
    どれだけ空くか見積もるだけ（推奨・最初はこれ）

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\Free-Space.ps1 -Apply
    Standard レベルで実際に削除

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\Free-Space.ps1 -Level Deep -Apply
    管理者 PowerShell で実行。Windows.old や WinSxS まで掃除（時間がかかります）
#>
[CmdletBinding()]
param(
    [ValidateSet('Safe', 'Standard', 'Deep')]
    [string]$Level = 'Standard',

    [switch]$Apply,
    [switch]$Interactive,

    [ValidateRange(1, 365)]
    [int]$TempOlderThanDays = 7,

    [switch]$RestartExplorer,

    [string]$LogDir = (Join-Path $env:USERPROFILE 'DesktopSortLogs')
)

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

# =====================================================================
#  1. 基本ユーティリティ
# =====================================================================

function Format-Size {
    param([double]$Bytes)
    if ($Bytes -ge 1TB) { return ('{0,8:N2} TB' -f ($Bytes / 1TB)) }
    if ($Bytes -ge 1GB) { return ('{0,8:N2} GB' -f ($Bytes / 1GB)) }
    if ($Bytes -ge 1MB) { return ('{0,8:N1} MB' -f ($Bytes / 1MB)) }
    if ($Bytes -ge 1KB) { return ('{0,8:N0} KB' -f ($Bytes / 1KB)) }
    return ('{0,8:N0} B ' -f $Bytes)
}

function Get-FreeBytes {
    try {
        $d = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='$env:SystemDrive'" -ErrorAction Stop
        return [double]$d.FreeSpace
    } catch { return $null }
}

function Get-TotalBytes {
    try {
        $d = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='$env:SystemDrive'" -ErrorAction Stop
        return [double]$d.Size
    } catch { return $null }
}

$script:IsAdmin = $false
try {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $script:IsAdmin = (New-Object Security.Principal.WindowsPrincipal($id)).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)
} catch { $script:IsAdmin = $false }

function Test-ProcessRunning {
    param([string]$NameCsv)
    if (-not $NameCsv) { return @() }
    $hits = @()
    foreach ($n in ($NameCsv -split ',')) {
        $n = $n.Trim()
        if (-not $n) { continue }
        $base = [System.IO.Path]::GetFileNameWithoutExtension($n)
        if (Get-Process -Name $base -ErrorAction SilentlyContinue) { $hits += $base }
    }
    return @($hits | Sort-Object -Unique)
}

# =====================================================================
#  2. 削除ガード（ここが安全性の要）
# =====================================================================

function Normalize-Path {
    param([string]$P)
    if ([string]::IsNullOrWhiteSpace($P)) { return $null }
    try {
        $full = [System.IO.Path]::GetFullPath($P)
    } catch { return $null }
    return $full.TrimEnd('\')
}

# 削除を許可するルート。ここ「配下」でなければ何があっても削除しない。
function Get-AllowedRoots {
    $roots = @(
        $env:LOCALAPPDATA,
        $env:APPDATA,
        $env:TEMP,
        (Join-Path $env:USERPROFILE '.cache'),
        (Join-Path $env:USERPROFILE '.cargo'),
        (Join-Path $env:USERPROFILE '.rustup'),
        (Join-Path $env:USERPROFILE '.gradle'),
        (Join-Path $env:USERPROFILE '.nuget'),
        (Join-Path $env:USERPROFILE '.bun'),
        (Join-Path $env:USERPROFILE '.codex'),
        (Join-Path $env:USERPROFILE '.claude'),
        (Join-Path $env:USERPROFILE 'go\pkg\mod'),
        (Join-Path $env:ProgramData 'Microsoft\Windows\WER'),
        (Join-Path $env:ProgramData 'Package Cache\.unverified'),
        (Join-Path $env:ProgramData 'chocolatey\lib-bad'),
        (Join-Path $env:ProgramData 'chocolatey\lib-bkp'),
        (Join-Path $env:ProgramData 'Adobe\ARM'),
        (Join-Path $env:SystemRoot 'Temp'),
        (Join-Path $env:SystemRoot 'Logs'),
        (Join-Path $env:SystemRoot 'Panther'),
        (Join-Path $env:SystemRoot 'Minidump'),
        (Join-Path $env:SystemRoot 'LiveKernelReports'),
        (Join-Path $env:SystemRoot 'IMECache'),
        (Join-Path $env:SystemRoot 'SoftwareDistribution\Download'),
        (Join-Path $env:SystemRoot 'SoftwareDistribution\DeliveryOptimization')
    )
    return @($roots | ForEach-Object { Normalize-Path $_ } | Where-Object { $_ } | Sort-Object -Unique)
}

# 許可ルート配下であっても絶対に触らないパターン（小文字で比較）
$script:DenyPatterns = @(
    '\\desktop$', '\\desktop\\',
    '\\documents$', '\\documents\\',
    '\\downloads$', '\\downloads\\',
    '\\pictures$', '\\pictures\\',
    '\\videos$', '\\videos\\',
    '\\music$', '\\music\\',
    '\\favorites$', '\\favorites\\',
    '\\saved games', '\\searches', '\\contacts', '\\links',
    '\\onedrive', '\\dropbox', '\\google\\drivefs', '\\googledrive', '\\box\\box',
    '\\microsoft\\outlook', '\.ost$', '\.pst$',
    '\\microsoft\\signatures', '\\microsoft\\templates',
    '\\microsoft\\crypto', '\\microsoft\\protect', '\\microsoft\\credentials',
    '\\microsoft\\vault', '\\microsoft\\systemcertificates',
    '\\\.ssh', '\\\.aws', '\\\.gnupg', '\\\.kube', '\\\.docker\\config',
    '\\cookies', '\\login data', '\\web data', '\\bookmarks',
    '\\local storage', '\\session storage', '\\indexeddb', '\\databases',
    '\\user data\\local state', '\\preferences$',
    '\\mobilesync\\backup',
    '\\windows\\system32', '\\windows\\syswow64', '\\windows\\winsxs',
    '\\program files', '\\programdata\\microsoft\\search\\data',
    '\\\.git$', '\\\.git\\',
    '\\repos\\', '\\source\\repos'
)

function Test-SafeToDelete {
    <#
      多層ガード。1つでも引っかかれば削除しない。
      戻り値: $null なら安全、文字列なら拒否理由。
    #>
    param([string]$Target)

    $p = Normalize-Path $Target
    if (-not $p) { return 'パスが空、または解決できません' }

    if ($p -notmatch '^[A-Za-z]:\\') { return "絶対パスではありません: $p" }

    # ルート直下や2階層は問答無用で拒否（C:\ , C:\Windows , C:\Users など）
    $segments = @($p -split '\\' | Where-Object { $_ })
    if ($segments.Count -lt 3) { return "階層が浅すぎます（3階層以上必須）: $p" }

    $lower = $p.ToLowerInvariant()

    # 許可ルート配下か
    $allowed = $false
    foreach ($r in $script:AllowedRoots) {
        $rl = $r.ToLowerInvariant()
        if ($lower -eq $rl -or $lower.StartsWith($rl + '\')) { $allowed = $true; break }
    }
    if (-not $allowed) { return "許可ルート外: $p" }

    # 許可ルートそのものを丸ごと消そうとしていないか
    foreach ($r in $script:AllowedRoots) {
        if ($lower -eq $r.ToLowerInvariant()) {
            # ルート自体を対象にしてよいのは、専用の一時領域だけ
            $selfOk = @(
                (Normalize-Path $env:TEMP),
                (Normalize-Path (Join-Path $env:LOCALAPPDATA 'Temp')),
                (Normalize-Path (Join-Path $env:SystemRoot 'Temp')),
                (Normalize-Path (Join-Path $env:SystemRoot 'Minidump')),
                (Normalize-Path (Join-Path $env:SystemRoot 'LiveKernelReports')),
                (Normalize-Path (Join-Path $env:SystemRoot 'Panther')),
                (Normalize-Path (Join-Path $env:SystemRoot 'Logs')),
                (Normalize-Path (Join-Path $env:SystemRoot 'IMECache')),
                (Normalize-Path (Join-Path $env:SystemRoot 'SoftwareDistribution\Download')),
                (Normalize-Path (Join-Path $env:SystemRoot 'SoftwareDistribution\DeliveryOptimization')),
                (Normalize-Path (Join-Path $env:ProgramData 'Microsoft\Windows\WER')),
                (Normalize-Path (Join-Path $env:ProgramData 'Package Cache\.unverified')),
                (Normalize-Path (Join-Path $env:ProgramData 'chocolatey\lib-bad')),
                (Normalize-Path (Join-Path $env:ProgramData 'chocolatey\lib-bkp')),
                (Normalize-Path (Join-Path $env:ProgramData 'Adobe\ARM')),
                (Normalize-Path (Join-Path $env:USERPROFILE 'go\pkg\mod'))
            ) | Where-Object { $_ }
            if ($selfOk -notcontains $p) { return "許可ルート自体は削除できません: $p" }
        }
    }

    # ユーザーデータ・認証情報などの禁止パターン
    foreach ($pat in $script:DenyPatterns) {
        if ($lower -match $pat) { return "禁止パターンに一致 ($pat): $p" }
    }

    # リパースポイント（ジャンクション/シンボリックリンク）は追跡しない
    try {
        $item = Get-Item -LiteralPath $p -Force -ErrorAction Stop
        if ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
            return "リパースポイントのため対象外: $p"
        }
    } catch { }

    return $null
}

# =====================================================================
#  3. 走査と削除
# =====================================================================

function Resolve-TargetPaths {
    <# ワイルドカードを含むパスを実体に展開し、1件ずつガードにかける #>
    param([string]$Pattern)
    if ([string]::IsNullOrWhiteSpace($Pattern)) { return @() }

    $candidates = @()
    if ($Pattern -match '[\*\?]') {
        try {
            $candidates = @(Get-Item -Path $Pattern -Force -ErrorAction SilentlyContinue |
                            Where-Object { $_.PSIsContainer } | ForEach-Object { $_.FullName })
        } catch { $candidates = @() }
    } else {
        if (Test-Path -LiteralPath $Pattern -PathType Container) { $candidates = @($Pattern) }
    }

    $ok = @()
    foreach ($c in $candidates) {
        $reason = Test-SafeToDelete -Target $c
        if ($reason) {
            Write-Verbose "スキップ: $reason"
            $script:Blocked += [pscustomobject]@{ Path = $c; Reason = $reason }
        } else {
            $ok += (Normalize-Path $c)
        }
    }
    return @($ok | Sort-Object -Unique)
}

function Measure-TargetFiles {
    <# 対象配下の（年齢条件を満たす）ファイル一覧とサイズを返す #>
    param([string]$Root, [int]$MinAgeDays = 0)

    $cutoff = if ($MinAgeDays -gt 0) { (Get-Date).AddDays(-$MinAgeDays) } else { $null }
    $files = @()
    try {
        $files = @(Get-ChildItem -LiteralPath $Root -Recurse -File -Force -ErrorAction SilentlyContinue |
                   Where-Object { -not $cutoff -or $_.LastWriteTime -lt $cutoff })
    } catch { $files = @() }

    $sum = 0.0
    foreach ($f in $files) { $sum += [double]$f.Length }
    return [pscustomobject]@{ Files = $files; Bytes = $sum; Count = $files.Count }
}

function Remove-TargetFiles {
    <# 実際に削除。成功したファイルのバイト数だけを積算する（失敗を握り潰して過大報告しない） #>
    param([string]$Root, $Files)

    $freed = 0.0; $ok = 0; $fail = 0
    foreach ($f in $Files) {
        try {
            $len = [double]$f.Length
            if ($f.Attributes -band [System.IO.FileAttributes]::ReadOnly) {
                try { Set-ItemProperty -LiteralPath $f.FullName -Name IsReadOnly -Value $false -ErrorAction Stop } catch { }
            }
            Remove-Item -LiteralPath $f.FullName -Force -ErrorAction Stop
            $freed += $len; $ok++
        } catch { $fail++ }
    }

    # 空になったサブフォルダを片付ける（ルート自体は残す）
    try {
        Get-ChildItem -LiteralPath $Root -Recurse -Directory -Force -ErrorAction SilentlyContinue |
            Sort-Object { $_.FullName.Length } -Descending |
            ForEach-Object {
                if ($_.Attributes -band [System.IO.FileAttributes]::ReparsePoint) { return }
                if (-not (Get-ChildItem -LiteralPath $_.FullName -Force -ErrorAction SilentlyContinue)) {
                    Remove-Item -LiteralPath $_.FullName -Force -ErrorAction SilentlyContinue
                }
            }
    } catch { }

    return [pscustomobject]@{ Freed = $freed; Ok = $ok; Fail = $fail }
}

# =====================================================================
#  4. 削除ターゲット定義
#     Level: Safe < Standard < Deep（上位レベルは下位を含む）
# =====================================================================

function New-Target {
    param(
        [string]$Name, [string]$Level, [string]$Path,
        [int]$MinAge = 0, [bool]$Admin = $false,
        [string]$Close = '', [string]$FileFilter = '',
        [bool]$NeedsExplorerRestart = $false
    )
    [pscustomobject]@{
        Name = $Name; Level = $Level; Path = $Path; MinAge = $MinAge
        Admin = $Admin; Close = $Close; FileFilter = $FileFilter
        NeedsExplorerRestart = $NeedsExplorerRestart
    }
}

$LA = $env:LOCALAPPDATA
$RA = $env:APPDATA
$UP = $env:USERPROFILE
$PD = $env:ProgramData
$WR = $env:SystemRoot

$FileTargets = @(
    # ---------------- Safe ----------------
    (New-Target '一時ファイル (LocalAppData\Temp)' 'Safe' (Join-Path $LA 'Temp') -MinAge 1)
    (New-Target 'クラッシュダンプ'                 'Safe' (Join-Path $LA 'CrashDumps'))
    (New-Target 'エラー報告 (ユーザー)'            'Safe' (Join-Path $LA 'Microsoft\Windows\WER'))
    (New-Target 'DirectX シェーダーキャッシュ'     'Safe' (Join-Path $LA 'D3DSCache'))
    (New-Target 'NVIDIA DXCache'                   'Safe' (Join-Path $LA 'NVIDIA\DXCache'))
    (New-Target 'NVIDIA GLCache'                   'Safe' (Join-Path $LA 'NVIDIA\GLCache'))
    (New-Target 'NVIDIA NV_Cache'                  'Safe' (Join-Path $LA 'NVIDIA Corporation\NV_Cache'))
    (New-Target 'AMD シェーダーキャッシュ'         'Safe' (Join-Path $LA 'AMD\DxCache'))
    (New-Target 'AMD GLCache'                      'Safe' (Join-Path $LA 'AMD\GLCache'))
    (New-Target 'AMD VkCache'                      'Safe' (Join-Path $LA 'AMD\VkCache'))
    (New-Target 'Intel シェーダーキャッシュ'       'Safe' (Join-Path $LA 'Intel\ShaderCache'))
    (New-Target 'Squirrel 更新の一時展開'          'Safe' (Join-Path $LA 'SquirrelTemp'))
    (New-Target 'INetCache'                        'Safe' (Join-Path $LA 'Microsoft\Windows\INetCache'))
    (New-Target 'VS Code キャッシュ'               'Safe' (Join-Path $RA 'Code\Cache')            -Close 'Code.exe')
    (New-Target 'VS Code CachedData'               'Safe' (Join-Path $RA 'Code\CachedData')       -Close 'Code.exe')
    (New-Target 'VS Code 拡張VSIX'                 'Safe' (Join-Path $RA 'Code\CachedExtensionVSIXs') -Close 'Code.exe')
    (New-Target 'VS Code ログ'                     'Safe' (Join-Path $RA 'Code\logs')             -Close 'Code.exe')
    (New-Target 'Codex CLI ログ'                   'Safe' (Join-Path $UP '.codex\log')            -Close 'codex.exe')
    (New-Target 'Codex アプリ キャッシュ (MSIX)'   'Safe' (Join-Path $LA 'Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Roaming\Codex\Cache') -Close 'Codex.exe')
    (New-Target 'Codex アプリ キャッシュ (Electron)' 'Safe' (Join-Path $RA 'Codex\Cache')         -Close 'Codex.exe')
    (New-Target 'Codex アプリ Code Cache'          'Safe' (Join-Path $RA 'Codex\Code Cache')      -Close 'Codex.exe')
    (New-Target 'Codex アプリ GPUCache'            'Safe' (Join-Path $RA 'Codex\GPUCache')        -Close 'Codex.exe')
    (New-Target 'Claude Desktop キャッシュ'        'Safe' (Join-Path $RA 'Claude\Cache')          -Close 'Claude.exe')
    (New-Target 'Claude Desktop Code Cache'        'Safe' (Join-Path $RA 'Claude\Code Cache')     -Close 'Claude.exe')
    (New-Target 'Claude Code シェルスナップショット' 'Safe' (Join-Path $UP '.claude\shell-snapshots'))
    (New-Target 'Slack キャッシュ'                 'Safe' (Join-Path $RA 'Slack\Cache')           -Close 'slack.exe')
    (New-Target 'Slack Code Cache'                 'Safe' (Join-Path $RA 'Slack\Code Cache')      -Close 'slack.exe')
    (New-Target 'Slack GPUCache'                   'Safe' (Join-Path $RA 'Slack\GPUCache')        -Close 'slack.exe')
    (New-Target 'Discord キャッシュ'               'Safe' (Join-Path $RA 'discord\Cache')         -Close 'Discord.exe')
    (New-Target 'Discord Code Cache'               'Safe' (Join-Path $RA 'discord\Code Cache')    -Close 'Discord.exe')
    (New-Target 'Teams (新) WebView2 キャッシュ'   'Safe' (Join-Path $LA 'Packages\MSTeams_8wekyb3d8bbwe\LocalCache\Microsoft\MSTeams\EBWebView\*\Cache') -Close 'ms-teams.exe')
    (New-Target 'Teams (新) Code Cache'            'Safe' (Join-Path $LA 'Packages\MSTeams_8wekyb3d8bbwe\LocalCache\Microsoft\MSTeams\EBWebView\*\Code Cache') -Close 'ms-teams.exe')
    (New-Target 'Teams (旧) キャッシュ'            'Safe' (Join-Path $RA 'Microsoft\Teams\Cache') -Close 'Teams.exe')
    (New-Target 'Teams (旧) 旧バージョン'          'Safe' (Join-Path $LA 'Microsoft\Teams\previous') -Close 'Teams.exe')
    (New-Target 'WebView2 共有ランタイム キャッシュ' 'Safe' (Join-Path $LA 'Microsoft\EdgeWebView\User Data\*\Cache') -Close 'msedgewebview2.exe')
    (New-Target 'Zoom ログ'                        'Safe' (Join-Path $RA 'Zoom\logs')             -Close 'Zoom.exe')
    (New-Target 'OneDrive ログ'                    'Safe' (Join-Path $LA 'Microsoft\OneDrive\logs'))
    (New-Target 'Office アドインキャッシュ'        'Safe' (Join-Path $LA 'Microsoft\Office\16.0\Wef') -Close 'WINWORD.EXE,EXCEL.EXE,POWERPNT.EXE,OUTLOOK.EXE')
    (New-Target 'Electron ダウンロードキャッシュ'  'Safe' (Join-Path $LA 'electron\Cache'))
    (New-Target 'electron-builder キャッシュ'      'Safe' (Join-Path $LA 'electron-builder\Cache'))

    # ---------------- Standard ----------------
    (New-Target 'Windows 一時ファイル'             'Standard' (Join-Path $WR 'Temp') -MinAge 1 -Admin $true)
    (New-Target 'エラー報告 (全ユーザー)'          'Standard' (Join-Path $PD 'Microsoft\Windows\WER') -Admin $true)
    (New-Target 'Windows ログ'                     'Standard' (Join-Path $WR 'Logs') -MinAge 3 -Admin $true)
    (New-Target 'セットアップログ (Panther)'       'Standard' (Join-Path $WR 'Panther') -Admin $true)
    (New-Target '小メモリダンプ (Minidump)'        'Standard' (Join-Path $WR 'Minidump') -Admin $true)
    (New-Target 'ライブカーネルレポート'           'Standard' (Join-Path $WR 'LiveKernelReports') -Admin $true)
    (New-Target 'Package Cache 未検証ペイロード'   'Standard' (Join-Path $PD 'Package Cache\.unverified') -Admin $true)
    (New-Target 'Adobe 更新キャッシュ'             'Standard' (Join-Path $PD 'Adobe\ARM') -Admin $true -Close 'Acrobat.exe,AcroRd32.exe')
    (New-Target 'Chocolatey 失敗パッケージ残骸'    'Standard' (Join-Path $PD 'chocolatey\lib-bad') -Admin $true)
    (New-Target 'Chocolatey バックアップ残骸'      'Standard' (Join-Path $PD 'chocolatey\lib-bkp') -Admin $true)
    (New-Target 'Chocolatey ダウンロードキャッシュ' 'Standard' (Join-Path $LA 'Temp\chocolatey'))
    # ブラウザ: HTTP/コード/GPU キャッシュのみ。Cookie・ログイン情報・ブックマークは対象外。
    (New-Target 'Chrome HTTPキャッシュ'            'Standard' (Join-Path $LA 'Google\Chrome\User Data\*\Cache') -Close 'chrome.exe')
    (New-Target 'Chrome Code Cache'                'Standard' (Join-Path $LA 'Google\Chrome\User Data\*\Code Cache') -Close 'chrome.exe')
    (New-Target 'Chrome GPUCache'                  'Standard' (Join-Path $LA 'Google\Chrome\User Data\*\GPUCache') -Close 'chrome.exe')
    (New-Target 'Edge HTTPキャッシュ'              'Standard' (Join-Path $LA 'Microsoft\Edge\User Data\*\Cache') -Close 'msedge.exe')
    (New-Target 'Edge Code Cache'                  'Standard' (Join-Path $LA 'Microsoft\Edge\User Data\*\Code Cache') -Close 'msedge.exe')
    (New-Target 'Edge GPUCache'                    'Standard' (Join-Path $LA 'Microsoft\Edge\User Data\*\GPUCache') -Close 'msedge.exe')
    (New-Target 'Firefox ディスクキャッシュ'       'Standard' (Join-Path $LA 'Mozilla\Firefox\Profiles\*\cache2') -Close 'firefox.exe')
    (New-Target 'Firefox 起動キャッシュ'           'Standard' (Join-Path $LA 'Mozilla\Firefox\Profiles\*\startupCache') -Close 'firefox.exe')
    # 開発ツール（再ダウンロードで復元可能）
    (New-Target 'npm キャッシュ'                   'Standard' (Join-Path $LA 'npm-cache\_cacache'))
    (New-Target 'npx キャッシュ'                   'Standard' (Join-Path $LA 'npm-cache\_npx'))
    (New-Target 'Yarn v1 キャッシュ'               'Standard' (Join-Path $LA 'Yarn\Cache'))
    (New-Target 'Yarn Berry キャッシュ'            'Standard' (Join-Path $LA 'Yarn\Berry\cache'))
    (New-Target 'pip キャッシュ'                   'Standard' (Join-Path $LA 'pip\Cache'))
    (New-Target 'NuGet HTTPキャッシュ'             'Standard' (Join-Path $LA 'NuGet\v3-cache') -Close 'devenv.exe')
    (New-Target 'NuGet プラグインキャッシュ'       'Standard' (Join-Path $LA 'NuGet\plugins-cache') -Close 'devenv.exe')
    (New-Target 'node-gyp ヘッダキャッシュ'        'Standard' (Join-Path $LA 'node-gyp\Cache'))
    (New-Target 'Go ビルドキャッシュ'              'Standard' (Join-Path $LA 'go-build') -Close 'go.exe,gopls.exe')
    (New-Target 'Cypress バイナリキャッシュ'       'Standard' (Join-Path $LA 'Cypress\Cache') -Close 'Cypress.exe')
    (New-Target 'Playwright ブラウザ'              'Standard' (Join-Path $LA 'ms-playwright'))
    (New-Target 'Puppeteer ブラウザ'               'Standard' (Join-Path $UP '.cache\puppeteer'))
    (New-Target 'Poetry アーティファクト'          'Standard' (Join-Path $LA 'pypoetry\Cache\artifacts'))
    (New-Target 'Gradle Wrapper ディストリ'        'Standard' (Join-Path $UP '.gradle\wrapper\dists') -Close 'java.exe')
    (New-Target 'rustup ダウンロード'              'Standard' (Join-Path $UP '.rustup\downloads') -Close 'cargo.exe')
    (New-Target 'bun インストールキャッシュ'       'Standard' (Join-Path $UP '.bun\install\cache'))
    (New-Target 'JetBrains Toolbox キャッシュ'     'Standard' (Join-Path $LA 'JetBrains\Toolbox\cache') -Close 'jetbrains-toolbox.exe')
    (New-Target 'Visual Studio ComponentModelCache' 'Standard' (Join-Path $LA 'Microsoft\VisualStudio\*\ComponentModelCache') -Close 'devenv.exe')
    # サムネイル/アイコンキャッシュ（explorer.exe の再起動が必要）
    (New-Target 'サムネイル/アイコンキャッシュ'    'Standard' (Join-Path $LA 'Microsoft\Windows\Explorer') -FileFilter '*cache*.db' -NeedsExplorerRestart $true)
)

# ---- コマンド方式のターゲット ----
$CommandTargets = @(
    [pscustomobject]@{
        Name = 'ごみ箱を空にする'; Level = 'Standard'; Admin = $false
        Note = 'ごみ箱の中身が完全に消えます'
        Script = { Clear-RecycleBin -DriveLetter $env:SystemDrive.TrimEnd(':') -Force -ErrorAction SilentlyContinue }
    }
    [pscustomobject]@{
        Name = 'Windows Update ダウンロードキャッシュ'; Level = 'Standard'; Admin = $true
        Note = '必要な更新は次回スキャンで再取得されます'
        Script = {
            Stop-Service -Name wuauserv, bits -Force -ErrorAction SilentlyContinue
            $d = Join-Path $env:SystemRoot 'SoftwareDistribution\Download'
            if (Test-Path -LiteralPath $d) {
                Get-ChildItem -LiteralPath $d -Force -ErrorAction SilentlyContinue |
                    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
            }
            Start-Service -Name wuauserv, bits -ErrorAction SilentlyContinue
        }
    }
    [pscustomobject]@{
        Name = '配信の最適化キャッシュ'; Level = 'Standard'; Admin = $true
        Note = 'LAN内ピア配信用の一時データ'
        Script = {
            if (Get-Command Delete-DeliveryOptimizationCache -ErrorAction SilentlyContinue) {
                Delete-DeliveryOptimizationCache -Force -ErrorAction SilentlyContinue
            } else {
                Stop-Service -Name DoSvc -Force -ErrorAction SilentlyContinue
                $p1 = Join-Path $env:SystemRoot 'SoftwareDistribution\DeliveryOptimization'
                $p2 = Join-Path $env:SystemRoot 'ServiceProfiles\NetworkService\AppData\Local\Microsoft\Windows\DeliveryOptimization\Cache'
                foreach ($p in @($p1, $p2)) {
                    if (Test-Path -LiteralPath $p) {
                        Get-ChildItem -LiteralPath $p -Force -ErrorAction SilentlyContinue |
                            Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
                    }
                }
                Start-Service -Name DoSvc -ErrorAction SilentlyContinue
            }
        }
    }
    [pscustomobject]@{
        Name = 'Go モジュールキャッシュ (go clean -modcache)'; Level = 'Standard'; Admin = $false
        Note = '読み取り専用属性のため専用コマンドで削除。再取得可能'
        Script = {
            if (Get-Command go -ErrorAction SilentlyContinue) { & go clean -modcache 2>&1 | Out-Null }
        }
    }
    [pscustomobject]@{
        Name = 'pnpm ストアの整理 (store prune)'; Level = 'Standard'; Admin = $false
        Note = '参照されていないパッケージのみ削除'
        Script = { if (Get-Command pnpm -ErrorAction SilentlyContinue) { & pnpm store prune 2>&1 | Out-Null } }
    }
    [pscustomobject]@{
        Name = 'conda の未使用パッケージ'; Level = 'Standard'; Admin = $false
        Note = '再取得可能'
        Script = { if (Get-Command conda -ErrorAction SilentlyContinue) { & conda clean --all -y 2>&1 | Out-Null } }
    }
    [pscustomobject]@{
        Name = 'uv キャッシュ'; Level = 'Standard'; Admin = $false
        Note = '再取得可能'
        Script = { if (Get-Command uv -ErrorAction SilentlyContinue) { & uv cache clean 2>&1 | Out-Null } }
    }
    [pscustomobject]@{
        Name = 'カーネルメモリダンプ (MEMORY.DMP)'; Level = 'Deep'; Admin = $true
        Note = 'ブルースクリーンの調査資料を失います。IT部門が調査中なら実行しないこと'
        Script = {
            $p = Join-Path $env:SystemRoot 'MEMORY.DMP'
            if (Test-Path -LiteralPath $p) { Remove-Item -LiteralPath $p -Force -ErrorAction SilentlyContinue }
        }
    }
    [pscustomobject]@{
        Name = 'コンポーネントストア掃除 (DISM)'; Level = 'Deep'; Admin = $true
        Note = '10〜60分かかります。対象になった更新はアンインストール不可になります'
        Script = {
            & "$env:SystemRoot\System32\Dism.exe" /Online /Cleanup-Image /StartComponentCleanup 2>&1 | Out-Null
        }
    }
    [pscustomobject]@{
        Name = 'ディスククリーンアップ無人実行 (Windows.old 含む)'; Level = 'Deep'; Admin = $true
        Note = '以前のWindowsへのロールバックが不可になります。ダウンロードフォルダーは対象外にしています'
        Script = {
            $vc = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\VolumeCaches'
            # ユーザーデータを巻き込むハンドラは明示的に除外する
            $blocked = @('DownloadsFolder', 'Recycle Bin')
            $allow = @(
                'Active Setup Temp Folders', 'BranchCache', 'D3D Shader Cache',
                'Delivery Optimization Files', 'Device Driver Packages',
                'Diagnostic Data Viewer database files', 'Downloaded Program Files',
                'Internet Cache Files', 'Language Pack', 'Old ChkDsk Files',
                'Previous Installations', 'Setup Log Files', 'System error memory dump files',
                'System error minidump files', 'Temporary Files', 'Temporary Setup Files',
                'Thumbnail Cache', 'Update Cleanup', 'Upgrade Discarded Files',
                'Windows Defender', 'Windows Error Reporting Files',
                'Windows ESD installation files', 'Windows Upgrade Log Files'
            )
            Get-ChildItem -Path $vc -ErrorAction SilentlyContinue | ForEach-Object {
                $n = $_.PSChildName
                $v = 0
                if (($allow -contains $n) -and ($blocked -notcontains $n)) { $v = 2 }
                New-ItemProperty -Path $_.PSPath -Name 'StateFlags0177' -PropertyType DWord -Value $v -Force -ErrorAction SilentlyContinue | Out-Null
            }
            Start-Process -FilePath "$env:SystemRoot\System32\cleanmgr.exe" -ArgumentList '/sagerun:177' -Wait -ErrorAction SilentlyContinue
        }
    }
    [pscustomobject]@{
        Name = 'シャドウコピー領域の上限を 5% に縮小'; Level = 'Deep'; Admin = $true
        Note = '古い復元ポイントから自動削除されます。最新の復元ポイントは残ります'
        Script = {
            & vssadmin.exe resize shadowstorage /For=$env:SystemDrive /On=$env:SystemDrive /MaxSize=5% 2>&1 | Out-Null
        }
    }
)

# =====================================================================
#  5. 手動判断が必要な大物（報告のみ・絶対に削除しない）
# =====================================================================

function Show-BigItemsReport {
    Write-Host ''
    Write-Host '【手動判断が必要な大物】（このスクリプトは触りません）' -ForegroundColor Yellow

    $rows = @()

    function Add-Row { param([string]$Name, [double]$Bytes, [string]$How)
        if ($Bytes -gt 0) { $script:bigRows += [pscustomobject]@{ Name = $Name; Bytes = $Bytes; How = $How } }
    }
    $script:bigRows = @()

    function Get-FileBytes { param([string]$P)
        try { if (Test-Path -LiteralPath $P) { return [double](Get-Item -LiteralPath $P -Force -ErrorAction Stop).Length } } catch { }
        return 0
    }
    function Get-DirBytes { param([string]$P)
        try {
            if (-not (Test-Path -LiteralPath $P)) { return 0 }
            $m = Get-ChildItem -LiteralPath $P -Recurse -File -Force -ErrorAction SilentlyContinue | Measure-Object Length -Sum
            return [double]($m.Sum)
        } catch { return 0 }
    }

    Add-Row '休止状態ファイル hiberfil.sys' (Get-FileBytes (Join-Path $env:SystemDrive '\hiberfil.sys')) `
        '縮小: powercfg /h /type reduced ／ 無効化: powercfg /h off（ノートPCは電池切れ時の退避を失うので注意）'
    Add-Row 'ページファイル pagefile.sys' (Get-FileBytes (Join-Path $env:SystemDrive '\pagefile.sys')) `
        '削除不可。システムのプロパティ→詳細設定→仮想メモリ で固定サイズに制限する'
    Add-Row 'Windows.old' (Get-DirBytes (Join-Path $env:SystemDrive '\Windows.old')) `
        '-Level Deep で cleanmgr 経由で削除（ロールバック不可になります）'
    Add-Row 'カーネルダンプ MEMORY.DMP' (Get-FileBytes (Join-Path $env:SystemRoot 'MEMORY.DMP')) `
        '-Level Deep で削除'

    $docker = Join-Path $env:LOCALAPPDATA 'Docker\wsl'
    Add-Row 'Docker の仮想ディスク (WSL2)' (Get-DirBytes $docker) `
        'docker system prune -a の後、wsl --shutdown → diskpart の compact vdisk で初めて C: が空きます'

    $wslPkgs = Join-Path $env:LOCALAPPDATA 'Packages'
    $wslBytes = 0.0
    try {
        Get-ChildItem -LiteralPath $wslPkgs -Directory -Force -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match 'Ubuntu|Debian|Kali|SUSE|Oracle|WindowsSubsystem' } |
            ForEach-Object { $wslBytes += (Get-DirBytes $_.FullName) }
    } catch { }
    Add-Row 'WSL ディストロの仮想ディスク' $wslBytes `
        'wsl --shutdown → diskpart の compact vdisk、または wsl --manage <Distro> --set-sparse true'

    foreach ($p in @(
        (Join-Path $env:APPDATA 'Apple Computer\MobileSync\Backup'),
        (Join-Path $env:USERPROFILE 'Apple\MobileSync\Backup')
    )) { Add-Row 'iPhone/iPad バックアップ' (Get-DirBytes $p) 'iTunes / Apple デバイス アプリから不要な世代を削除' }

    foreach ($od in @($env:OneDrive, $env:OneDriveCommercial, $env:OneDriveConsumer)) {
        if ($od -and (Test-Path -LiteralPath $od)) {
            Add-Row "OneDrive ローカル実体 ($([IO.Path]::GetFileName($od)))" (Get-DirBytes $od) `
                'エクスプローラーで右クリック→「空き容量を増やす」（ファイルは残り、クラウドのみに）'
        }
    }

    Add-Row 'ダウンロード フォルダー' (Get-DirBytes (Join-Path $env:USERPROFILE 'Downloads')) `
        '中身はユーザーデータです。自分で確認して不要なインストーラを削除'

    Add-Row 'Cargo レジストリ' (Get-DirBytes (Join-Path $env:USERPROFILE '.cargo\registry')) `
        '再取得可能ですが大きいので任意: Remove-Item で cache / src を削除'
    Add-Row 'Maven ローカルリポジトリ' (Get-DirBytes (Join-Path $env:USERPROFILE '.m2\repository')) `
        '再取得可能。オフライン作業予定がなければ削除可'
    Add-Row 'Gradle キャッシュ' (Get-DirBytes (Join-Path $env:USERPROFILE '.gradle\caches')) `
        '再取得可能。ビルドが遅くなるだけ'

    if ($script:bigRows.Count -eq 0) {
        Write-Host '  該当なし'
        return
    }
    foreach ($r in ($script:bigRows | Sort-Object Bytes -Descending)) {
        Write-Host ('  {0}  {1}' -f (Format-Size $r.Bytes), $r.Name) -ForegroundColor Gray
        Write-Host ('              → {0}' -f $r.How) -ForegroundColor DarkGray
    }
}

# =====================================================================
#  6. メイン
# =====================================================================

$script:AllowedRoots = Get-AllowedRoots
$script:Blocked = @()

$LevelRank = @{ 'Safe' = 1; 'Standard' = 2; 'Deep' = 3 }
$want = $LevelRank[$Level]

$freeBefore = Get-FreeBytes
$totalBytes = Get-TotalBytes

Write-Host ''
Write-Host '============================================================' -ForegroundColor Cyan
Write-Host ' 空き容量の確保' -ForegroundColor Cyan
Write-Host ("  レベル      : $Level") -ForegroundColor Cyan
Write-Host ("  管理者権限  : " + $(if ($script:IsAdmin) { 'あり' } else { 'なし（一部の項目はスキップされます）' })) -ForegroundColor Cyan
Write-Host ("  一時ファイル: {0} 日より前に更新されたものだけ削除" -f $TempOlderThanDays) -ForegroundColor Cyan
if ($freeBefore -ne $null -and $totalBytes) {
    $pct = $freeBefore / $totalBytes * 100
    Write-Host ("  現在の空き  : {0} / {1}  ({2:N1}%)" -f (Format-Size $freeBefore), (Format-Size $totalBytes), $pct) -ForegroundColor Cyan
}
Write-Host '============================================================' -ForegroundColor Cyan

# ---- 走査 ----
Write-Host ''
Write-Host '対象を走査しています...' -ForegroundColor DarkGray

$plan = @()
$skippedAdmin = @()
$skippedExplorer = @()

foreach ($t in ($FileTargets | Where-Object { $LevelRank[$_.Level] -le $want })) {
    if ($t.Admin -and -not $script:IsAdmin) { $skippedAdmin += $t.Name; continue }
    if ($t.NeedsExplorerRestart -and -not $RestartExplorer) { $skippedExplorer += $t.Name; continue }

    $roots = Resolve-TargetPaths -Pattern $t.Path
    if ($roots.Count -eq 0) { continue }

    $minAge = 0
    if ($t.MinAge -gt 0) { $minAge = [Math]::Max([int]$t.MinAge, $TempOlderThanDays) }

    foreach ($r in $roots) {
        $m = Measure-TargetFiles -Root $r -MinAgeDays $minAge
        $files = $m.Files
        if ($t.FileFilter) { $files = @($files | Where-Object { $_.Name -like $t.FileFilter }) }
        if ($files.Count -eq 0) { continue }

        $sum = 0.0
        foreach ($f in $files) { $sum += [double]$f.Length }

        $plan += [pscustomobject]@{
            Name    = $t.Name
            Root    = $r
            Files   = $files
            Bytes   = $sum
            Count   = $files.Count
            Close   = $t.Close
            Running = @(Test-ProcessRunning -NameCsv $t.Close)
            Explorer = $t.NeedsExplorerRestart
        }
    }
}

$cmds = @($CommandTargets | Where-Object { $LevelRank[$_.Level] -le $want })
$cmdsRunnable = @($cmds | Where-Object { -not $_.Admin -or $script:IsAdmin })
$cmdsBlocked = @($cmds | Where-Object { $_.Admin -and -not $script:IsAdmin })

# ---- 見積りの表示 ----
$estimate = 0.0
foreach ($p in $plan) { $estimate += $p.Bytes }

Write-Host ''
Write-Host '--- 削除対象（ファイル） ---' -ForegroundColor Yellow
if ($plan.Count -eq 0) {
    Write-Host '  該当なし'
} else {
    foreach ($p in ($plan | Sort-Object Bytes -Descending)) {
        $warn = if ($p.Running.Count -gt 0) { '  ※ ' + ($p.Running -join ',') + ' 起動中（一部が消せません）' } else { '' }
        Write-Host ('  {0}  {1,-38} {2,6} 件{3}' -f (Format-Size $p.Bytes), $p.Name, $p.Count, $warn)
    }
}

Write-Host ''
Write-Host '--- 削除対象（コマンド実行） ---' -ForegroundColor Yellow
if ($cmdsRunnable.Count -eq 0) {
    Write-Host '  該当なし'
} else {
    foreach ($c in $cmdsRunnable) { Write-Host ('  [{0}] {1}' -f $c.Level, $c.Name); Write-Host ("        {0}" -f $c.Note) -ForegroundColor DarkGray }
}

if ($skippedAdmin.Count -gt 0 -or $cmdsBlocked.Count -gt 0) {
    Write-Host ''
    Write-Host '--- 管理者権限がないためスキップ ---' -ForegroundColor DarkYellow
    foreach ($n in $skippedAdmin) { Write-Host "  - $n" -ForegroundColor DarkYellow }
    foreach ($c in $cmdsBlocked) { Write-Host ("  - {0}" -f $c.Name) -ForegroundColor DarkYellow }
    Write-Host '  → 管理者として PowerShell を開いて再実行すると、これらも処理されます' -ForegroundColor DarkYellow
}
if ($skippedExplorer.Count -gt 0) {
    Write-Host ''
    foreach ($n in $skippedExplorer) {
        Write-Host ("  - {0} は explorer.exe の再起動が必要なためスキップ（-RestartExplorer で有効化）" -f $n) -ForegroundColor DarkYellow
    }
}
if ($script:Blocked.Count -gt 0) {
    Write-Host ''
    Write-Host ('--- ガードによりブロック: {0} 件（-Verbose で詳細）---' -f $script:Blocked.Count) -ForegroundColor DarkGray
}

Write-Host ''
Write-Host ('ファイル削除の見込み: 約 {0}' -f (Format-Size $estimate)) -ForegroundColor Yellow
Write-Host '（コマンド実行分は事前に見積もれません。実行後の実測値で報告します）' -ForegroundColor DarkGray

# ---- 実行するかどうか ----
$doApply = [bool]$Apply
if ($Interactive -and -not $Apply) {
    Write-Host ''
    $ans = Read-Host '実際に削除しますか？ (Y = 実行 / それ以外 = 中止)'
    if ($ans -match '^[Yy]') { $doApply = $true }
}

if (-not $doApply) {
    Show-BigItemsReport
    Write-Host ''
    Write-Host '※ ドライランです。何も削除していません。' -ForegroundColor Green
    Write-Host '   実行するには -Apply を付けてください:' -ForegroundColor Green
    Write-Host ('   powershell -ExecutionPolicy Bypass -File .\Free-Space.ps1 -Level {0} -Apply' -f $Level) -ForegroundColor Green
    exit 0
}

# ---- 削除の実行 ----
Write-Host ''
Write-Host '削除を実行します...' -ForegroundColor Cyan

$explorerStopped = $false
if ($RestartExplorer -and ($plan | Where-Object { $_.Explorer })) {
    try {
        Stop-Process -Name explorer -Force -ErrorAction Stop
        $explorerStopped = $true
        Write-Host '  explorer.exe を停止しました' -ForegroundColor DarkGray
    } catch {
        Write-Warning '  explorer.exe を停止できませんでした。サムネイルキャッシュはスキップされます。'
    }
}

$log = @()
$freedTotal = 0.0
$failTotal = 0

foreach ($p in ($plan | Sort-Object Bytes -Descending)) {
    if ($p.Explorer -and -not $explorerStopped) { continue }
    $r = Remove-TargetFiles -Root $p.Root -Files $p.Files
    $freedTotal += $r.Freed
    $failTotal += $r.Fail
    $mark = if ($r.Fail -gt 0) { (' 失敗 {0} 件' -f $r.Fail) } else { '' }
    Write-Host ('  {0}  {1}{2}' -f (Format-Size $r.Freed), $p.Name, $mark)
    $log += [pscustomobject]@{
        Kind = 'files'; Name = $p.Name; Root = $p.Root
        PlannedBytes = $p.Bytes; FreedBytes = $r.Freed; Ok = $r.Ok; Fail = $r.Fail
    }
}

if ($explorerStopped) {
    try { Start-Process explorer.exe | Out-Null; Write-Host '  explorer.exe を再起動しました' -ForegroundColor DarkGray } catch { }
}

foreach ($c in $cmdsRunnable) {
    Write-Host ('  実行中: {0} ...' -f $c.Name)
    $before = Get-FreeBytes
    $err = ''
    try { & $c.Script } catch { $err = $_.Exception.Message; Write-Warning ('    失敗: {0}' -f $err) }
    $after = Get-FreeBytes
    $delta = if ($before -ne $null -and $after -ne $null) { $after - $before } else { 0 }
    if ($delta -gt 0) { Write-Host ('    → {0} 解放' -f (Format-Size $delta)) -ForegroundColor Green }
    $log += [pscustomobject]@{
        Kind = 'command'; Name = $c.Name; Root = ''
        PlannedBytes = 0; FreedBytes = $delta; Ok = $(if ($err) { 0 } else { 1 }); Fail = $(if ($err) { 1 } else { 0 })
    }
}

# ---- 結果 ----
$freeAfter = Get-FreeBytes

Write-Host ''
Write-Host '============================================================' -ForegroundColor Green
Write-Host ' 完了' -ForegroundColor Green
Write-Host '============================================================' -ForegroundColor Green
if ($freeBefore -ne $null -and $freeAfter -ne $null) {
    Write-Host ('  実行前の空き : {0}' -f (Format-Size $freeBefore))
    Write-Host ('  実行後の空き : {0}' -f (Format-Size $freeAfter))
    Write-Host ('  実際の増加   : {0}' -f (Format-Size ($freeAfter - $freeBefore))) -ForegroundColor Green
    if ($totalBytes) {
        $pct = $freeAfter / $totalBytes * 100
        Write-Host ('  空き率       : {0:N1}%' -f $pct)
        if ($freeAfter -lt 10GB) {
            Write-Host ''
            Write-Host '  ▲ 空きが 10GB 未満です。下の「手動判断が必要な大物」か、' -ForegroundColor Yellow
            Write-Host '     -Level Deep（管理者権限）での再実行を検討してください。' -ForegroundColor Yellow
        }
    }
}
if ($failTotal -gt 0) {
    Write-Host ('  削除できなかったファイル: {0} 件（使用中／権限不足）' -f $failTotal) -ForegroundColor DarkYellow
    Write-Host '  → 対象アプリを終了してから再実行すると、さらに空きます' -ForegroundColor DarkYellow
}

# ---- ログ ----
try {
    if (-not (Test-Path -LiteralPath $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }
    $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
    $logPath = Join-Path $LogDir "free-space_$stamp.csv"
    $log | Export-Csv -LiteralPath $logPath -NoTypeInformation -Encoding UTF8
    Write-Host ("  ログ: $logPath") -ForegroundColor DarkGray
} catch {
    Write-Warning ('ログを保存できませんでした: {0}' -f $_.Exception.Message)
}

Show-BigItemsReport
Write-Host ''
