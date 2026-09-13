<#
.SYNOPSIS
    Cドライブの空き容量と「容量を食っている場所」を洗い出します。削除は一切しません。

.DESCRIPTION
    Codexアプリなどが「容量不足で起動しない」ときの一次調査用。
    読み取りのみで、ファイルの移動・削除は行いません。

.PARAMETER Top
    大きい順に表示する件数。既定 20。

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\Get-DiskReport.ps1
#>
[CmdletBinding()]
param(
    [int]$Top = 20,
    [string]$OutFile
)

$ErrorActionPreference = 'SilentlyContinue'

function Format-Size {
    param([double]$Bytes)
    if ($Bytes -ge 1TB) { return ('{0:N2} TB' -f ($Bytes / 1TB)) }
    if ($Bytes -ge 1GB) { return ('{0:N2} GB' -f ($Bytes / 1GB)) }
    if ($Bytes -ge 1MB) { return ('{0:N2} MB' -f ($Bytes / 1MB)) }
    if ($Bytes -ge 1KB) { return ('{0:N2} KB' -f ($Bytes / 1KB)) }
    return ('{0:N0} B' -f $Bytes)
}

function Get-FolderSize {
    param([string]$FolderPath)
    if (-not (Test-Path -LiteralPath $FolderPath)) { return $null }
    $m = Get-ChildItem -LiteralPath $FolderPath -Recurse -File -Force -ErrorAction SilentlyContinue |
         Measure-Object -Property Length -Sum
    return [pscustomobject]@{
        Path  = $FolderPath
        Bytes = [double]($m.Sum)
        Files = [int]($m.Count)
    }
}

$lines = New-Object System.Collections.Generic.List[string]
function Say { param([string]$Text, [string]$Color = 'Gray')
    Write-Host $Text -ForegroundColor $Color
    [void]$lines.Add($Text)
}

Say ''
Say '============================================================' 'Cyan'
Say (' ディスク使用状況レポート  {0}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm')) 'Cyan'
Say (' マシン: {0}  ユーザー: {1}' -f $env:COMPUTERNAME, $env:USERNAME) 'Cyan'
Say '============================================================' 'Cyan'

# ---- 1. ドライブ空き容量 ------------------------------------------------
Say ''
Say '【1】ドライブ空き容量' 'Yellow'
Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | ForEach-Object {
    $free = [double]$_.FreeSpace
    $size = [double]$_.Size
    $pct  = if ($size -gt 0) { $free / $size * 100 } else { 0 }
    $flag = if ($pct -lt 5) { '  ★危険（空き5%未満）' } elseif ($pct -lt 10) { '  ▲注意（空き10%未満）' } else { '' }
    Say ('  {0}  空き {1} / 全体 {2}  ({3:N1}%){4}' -f $_.DeviceID, (Format-Size $free), (Format-Size $size), $pct, $flag)
}

# ---- 2. ユーザープロファイル直下の大きいフォルダ -----------------------
Say ''
Say ('【2】{0} 直下で大きいフォルダ TOP{1}（計測に数分かかることがあります）' -f $env:USERPROFILE, $Top) 'Yellow'
$profDirs = Get-ChildItem -LiteralPath $env:USERPROFILE -Directory -Force -ErrorAction SilentlyContinue
$profSizes = foreach ($d in $profDirs) { Get-FolderSize -FolderPath $d.FullName }
$profSizes | Where-Object { $_ } | Sort-Object Bytes -Descending | Select-Object -First $Top | ForEach-Object {
    Say ('  {0,12}  {1,8} files  {2}' -f (Format-Size $_.Bytes), $_.Files, $_.Path)
}

# ---- 3. 既知のキャッシュ／一時領域 --------------------------------------
Say ''
Say '【3】キャッシュ・一時領域（削除候補になりやすい場所）' 'Yellow'
$cachePaths = [ordered]@{
    'ユーザー一時ファイル (TEMP)'      = $env:TEMP
    'LocalAppData\Temp'                = (Join-Path $env:LOCALAPPDATA 'Temp')
    'Windows\Temp'                     = (Join-Path $env:SystemRoot 'Temp')
    'Windows Update ダウンロード'      = (Join-Path $env:SystemRoot 'SoftwareDistribution\Download')
    'ダウンロード フォルダ'            = (Join-Path $env:USERPROFILE 'Downloads')
    'npm キャッシュ'                   = (Join-Path $env:LOCALAPPDATA 'npm-cache')
    'npm キャッシュ (Roaming)'         = (Join-Path $env:APPDATA 'npm-cache')
    'pnpm ストア'                      = (Join-Path $env:LOCALAPPDATA 'pnpm')
    'Yarn キャッシュ'                  = (Join-Path $env:LOCALAPPDATA 'Yarn\Cache')
    'pip キャッシュ'                   = (Join-Path $env:LOCALAPPDATA 'pip\Cache')
    'NuGet パッケージ'                 = (Join-Path $env:USERPROFILE '.nuget\packages')
    'Codex 設定・ログ (.codex)'        = (Join-Path $env:USERPROFILE '.codex')
    'Claude 設定 (.claude)'            = (Join-Path $env:USERPROFILE '.claude')
    'VS Code キャッシュ'               = (Join-Path $env:APPDATA 'Code\Cache')
    'VS Code CachedData'               = (Join-Path $env:APPDATA 'Code\CachedData')
    'Chrome キャッシュ'                = (Join-Path $env:LOCALAPPDATA 'Google\Chrome\User Data\Default\Cache')
    'Edge キャッシュ'                  = (Join-Path $env:LOCALAPPDATA 'Microsoft\Edge\User Data\Default\Cache')
    'Teams キャッシュ'                 = (Join-Path $env:APPDATA 'Microsoft\Teams')
    'CrashDumps'                       = (Join-Path $env:LOCALAPPDATA 'CrashDumps')
    'Windows エラー報告'               = (Join-Path $env:LOCALAPPDATA 'Microsoft\Windows\WER')
    'INetCache'                        = (Join-Path $env:LOCALAPPDATA 'Microsoft\Windows\INetCache')
    'D3DSCache'                        = (Join-Path $env:LOCALAPPDATA 'D3DSCache')
}
$cacheTotal = 0.0
foreach ($k in $cachePaths.Keys) {
    $r = Get-FolderSize -FolderPath $cachePaths[$k]
    if ($r) {
        $cacheTotal += $r.Bytes
        Say ('  {0,12}  {1,-32} {2}' -f (Format-Size $r.Bytes), $k, $r.Path)
    } else {
        Say ('  {0,12}  {1,-32} (なし)' -f '-', $k)
    }
}
Say ('  ---- キャッシュ系 合計: {0}' -f (Format-Size $cacheTotal)) 'Cyan'

# ---- 4. ごみ箱 ----------------------------------------------------------
Say ''
Say '【4】ごみ箱' 'Yellow'
try {
    $shell = New-Object -ComObject Shell.Application
    $bin   = $shell.NameSpace(0xA)
    $binBytes = 0.0; $binCount = 0
    foreach ($i in $bin.Items()) { $binBytes += [double]$i.Size; $binCount++ }
    Say ('  {0}  ({1} 項目)' -f (Format-Size $binBytes), $binCount)
} catch {
    Say '  取得できませんでした'
}

# ---- 5. WSL / Docker の仮想ディスク ------------------------------------
Say ''
Say '【5】WSL / Docker 仮想ディスク（肥大しやすい）' 'Yellow'
$vhdx = Get-ChildItem -Path (Join-Path $env:LOCALAPPDATA 'Packages'), (Join-Path $env:LOCALAPPDATA 'Docker'), (Join-Path $env:USERPROFILE 'AppData\Local\wsl') `
        -Recurse -Include '*.vhdx' -File -Force -ErrorAction SilentlyContinue
if ($vhdx) {
    $vhdx | Sort-Object Length -Descending | Select-Object -First 10 | ForEach-Object {
        Say ('  {0,12}  {1}' -f (Format-Size $_.Length), $_.FullName)
    }
} else {
    Say '  該当なし'
}

# ---- 6. デスクトップ／ダウンロードの大きいファイル ----------------------
Say ''
Say ('【6】デスクトップ・ダウンロード内の大きいファイル TOP{0}' -f $Top) 'Yellow'
$scan = @([Environment]::GetFolderPath('Desktop'), (Join-Path $env:USERPROFILE 'Downloads'))
if ($env:OneDrive) { $scan += (Join-Path $env:OneDrive 'Desktop') }
$scan = $scan | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Sort-Object -Unique
$bigFiles = Get-ChildItem -LiteralPath $scan -Recurse -File -Force -ErrorAction SilentlyContinue |
            Sort-Object Length -Descending | Select-Object -First $Top
if ($bigFiles) {
    $bigFiles | ForEach-Object {
        Say ('  {0,12}  {1:yyyy-MM-dd}  {2}' -f (Format-Size $_.Length), $_.LastWriteTime, $_.FullName)
    }
} else {
    Say '  該当なし'
}

Say ''
Say '※ このスクリプトは読み取りのみです。削除は行っていません。' 'Green'
Say ''

if ($OutFile) {
    $lines | Set-Content -LiteralPath $OutFile -Encoding UTF8
    Write-Host "レポートを保存しました: $OutFile" -ForegroundColor Green
}
