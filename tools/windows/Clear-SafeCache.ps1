<#
.SYNOPSIS
    比較的安全な一時ファイル／キャッシュだけを削除して空き容量を作ります。

.DESCRIPTION
    既定はドライラン（削除量の見積りのみ）。実削除は -Apply が必要です。
    対象は「消してもアプリが壊れない」ものに限定しています。
      - ユーザー一時ファイル（-OlderThanDays 日より古いものだけ）
      - Windows\Temp（管理者権限がある場合のみ／古いものだけ）
      - クラッシュダンプ・エラー報告
      - -PackageCaches 指定時: npm / yarn / pip のキャッシュ
      - -EmptyRecycleBin 指定時: ごみ箱

    ドキュメント・デスクトップ・ダウンロード等のユーザーデータには一切触りません。

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\Clear-SafeCache.ps1
    どれだけ空くか見積もるだけ（推奨・最初はこれ）

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\Clear-SafeCache.ps1 -Apply -PackageCaches -EmptyRecycleBin
#>
[CmdletBinding()]
param(
    [switch]$Apply,
    [int]$OlderThanDays = 3,
    [switch]$PackageCaches,
    [switch]$EmptyRecycleBin
)

$ErrorActionPreference = 'SilentlyContinue'

function Format-Size {
    param([double]$Bytes)
    if ($Bytes -ge 1GB) { return ('{0:N2} GB' -f ($Bytes / 1GB)) }
    if ($Bytes -ge 1MB) { return ('{0:N2} MB' -f ($Bytes / 1MB)) }
    if ($Bytes -ge 1KB) { return ('{0:N2} KB' -f ($Bytes / 1KB)) }
    return ('{0:N0} B' -f $Bytes)
}

$cutoff = (Get-Date).AddDays(-$OlderThanDays)
$mode   = if ($Apply) { '実行モード (-Apply)' } else { 'ドライラン（削除しません）' }

Write-Host ''
Write-Host '============================================================' -ForegroundColor Cyan
Write-Host ' 安全キャッシュ削除' -ForegroundColor Cyan
Write-Host " モード     : $mode" -ForegroundColor Cyan
Write-Host " 対象の古さ : $OlderThanDays 日より前に更新されたもの" -ForegroundColor Cyan
Write-Host '============================================================' -ForegroundColor Cyan

$targets = [ordered]@{
    'ユーザー一時ファイル' = $env:TEMP
    'LocalAppData\Temp'    = (Join-Path $env:LOCALAPPDATA 'Temp')
    'Windows\Temp'         = (Join-Path $env:SystemRoot 'Temp')
    'CrashDumps'           = (Join-Path $env:LOCALAPPDATA 'CrashDumps')
    'Windows エラー報告'   = (Join-Path $env:LOCALAPPDATA 'Microsoft\Windows\WER\ReportArchive')
    'D3DSCache'            = (Join-Path $env:LOCALAPPDATA 'D3DSCache')
}

# 同じ実体を指すパスを除外（%TEMP% と %LOCALAPPDATA%\Temp は同一のことが多い）
$seen = New-Object System.Collections.Generic.HashSet[string]
$unique = [ordered]@{}
foreach ($k in $targets.Keys) {
    $v = $targets[$k]
    if (-not $v) { $unique[$k] = $v; continue }
    $norm = $v.TrimEnd('\').ToLowerInvariant()
    if ($seen.Add($norm)) { $unique[$k] = $v }
}
$targets = $unique

$grandTotal = 0.0
$deleted    = 0.0

foreach ($name in $targets.Keys) {
    $path = $targets[$name]
    if (-not $path -or -not (Test-Path -LiteralPath $path)) {
        Write-Host ('  {0,-22} (なし)' -f $name)
        continue
    }

    $files = Get-ChildItem -LiteralPath $path -Recurse -File -Force -ErrorAction SilentlyContinue |
             Where-Object { $_.LastWriteTime -lt $cutoff }
    $sum   = ($files | Measure-Object Length -Sum).Sum
    $sum   = if ($sum) { [double]$sum } else { 0.0 }
    $grandTotal += $sum

    Write-Host ('  {0,-22} {1,12}  ({2} ファイル)' -f $name, (Format-Size $sum), @($files).Count)

    if ($Apply -and @($files).Count -gt 0) {
        foreach ($f in $files) {
            try { Remove-Item -LiteralPath $f.FullName -Force -ErrorAction Stop; $deleted += $f.Length } catch { }
        }
        # 空になったフォルダを掃除
        Get-ChildItem -LiteralPath $path -Recurse -Directory -Force -ErrorAction SilentlyContinue |
            Sort-Object { $_.FullName.Length } -Descending | ForEach-Object {
                if (-not (Get-ChildItem -LiteralPath $_.FullName -Force -ErrorAction SilentlyContinue)) {
                    Remove-Item -LiteralPath $_.FullName -Force -ErrorAction SilentlyContinue
                }
            }
    }
}

if ($PackageCaches) {
    Write-Host ''
    Write-Host '  --- パッケージマネージャのキャッシュ ---'
    $cmds = @(
        @{ Name = 'npm';  Exe = 'npm';  Args = @('cache','clean','--force') },
        @{ Name = 'yarn'; Exe = 'yarn'; Args = @('cache','clean') },
        @{ Name = 'pip';  Exe = 'pip';  Args = @('cache','purge') }
    )
    foreach ($c in $cmds) {
        if (Get-Command $c.Exe -ErrorAction SilentlyContinue) {
            if ($Apply) {
                Write-Host ('  {0} キャッシュを削除中...' -f $c.Name)
                & $c.Exe @($c.Args) 2>&1 | Out-Null
            } else {
                Write-Host ('  {0} : -Apply 時に `{1} {2}` を実行します' -f $c.Name, $c.Exe, ($c.Args -join ' '))
            }
        } else {
            Write-Host ('  {0} : 未インストール' -f $c.Name)
        }
    }
}

if ($EmptyRecycleBin) {
    Write-Host ''
    if ($Apply) {
        try {
            Clear-RecycleBin -Force -ErrorAction Stop
            Write-Host '  ごみ箱を空にしました' -ForegroundColor Green
        } catch {
            Write-Warning ('  ごみ箱を空にできませんでした: {0}' -f $_.Exception.Message)
        }
    } else {
        Write-Host '  -Apply 時にごみ箱を空にします'
    }
}

Write-Host ''
if ($Apply) {
    Write-Host ('削除しました: 約 {0}' -f (Format-Size $deleted)) -ForegroundColor Green
} else {
    Write-Host ('削除見込み: 約 {0}' -f (Format-Size $grandTotal)) -ForegroundColor Yellow
    Write-Host '※ ドライランです。何も削除していません。実行するには -Apply を付けてください。' -ForegroundColor Green
}

Write-Host ''
Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'" | ForEach-Object {
    Write-Host ('現在の C: 空き容量: {0} / {1}' -f (Format-Size $_.FreeSpace), (Format-Size $_.Size)) -ForegroundColor Cyan
}
