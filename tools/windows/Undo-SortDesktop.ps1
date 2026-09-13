<#
.SYNOPSIS
    Sort-Desktop.ps1 が出力したログCSVを読み、移動したファイルを元の場所へ戻します。

.DESCRIPTION
    既定はドライラン。実際に戻すには -Apply を付けます。
    LogPath 省略時は %USERPROFILE%\DesktopSortLogs の最新ログを使います。

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\Undo-SortDesktop.ps1
    最新ログの内容で「何を戻すか」だけ確認する

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\Undo-SortDesktop.ps1 -Apply
    実際に元へ戻す
#>
[CmdletBinding()]
param(
    [string]$LogPath,
    [switch]$Apply,
    [switch]$RemoveEmptyCategoryFolders,
    [string]$LogDir = (Join-Path $env:USERPROFILE 'DesktopSortLogs')
)

$ErrorActionPreference = 'Stop'

if (-not $LogPath) {
    if (-not (Test-Path -LiteralPath $LogDir)) {
        Write-Warning "ログフォルダが見つかりません: $LogDir"
        exit 1
    }
    $latest = Get-ChildItem -LiteralPath $LogDir -Filter 'desktop-sort_*.csv' -File |
              Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $latest) {
        Write-Warning "ログCSVが見つかりません: $LogDir"
        exit 1
    }
    $LogPath = $latest.FullName
}

if (-not (Test-Path -LiteralPath $LogPath)) {
    Write-Warning "ログが見つかりません: $LogPath"
    exit 1
}

$rows = @(Import-Csv -LiteralPath $LogPath | Where-Object { $_.Result -eq 'OK' })
if ($rows.Count -eq 0) {
    Write-Host '戻す対象がありません。' -ForegroundColor Green
    exit 0
}

$mode = if ($Apply) { '実行モード (-Apply)' } else { 'ドライラン（何も動かしません）' }
Write-Host ''
Write-Host "ログ   : $LogPath"
Write-Host "モード : $mode" -ForegroundColor Cyan
Write-Host ("対象   : {0} 件" -f $rows.Count)
Write-Host ''

$ok = 0; $ng = 0; $skip = 0
$touchedDirs = New-Object System.Collections.Generic.HashSet[string]

# 後入れのものから戻す（連番リネームの衝突を避けるため）
[array]::Reverse($rows)

foreach ($r in $rows) {
    if (-not (Test-Path -LiteralPath $r.Destination)) {
        $skip++
        Write-Warning ('移動先に見当たらないため skip: {0}' -f $r.Destination)
        continue
    }
    if (Test-Path -LiteralPath $r.Source) {
        $skip++
        Write-Warning ('元の場所に同名が既に存在するため skip: {0}' -f $r.Source)
        continue
    }

    if (-not $Apply) {
        '{0}  ->  {1}' -f $r.Destination, $r.Source | Write-Host
        continue
    }

    try {
        $parent = Split-Path -Path $r.Source -Parent
        if (-not (Test-Path -LiteralPath $parent)) {
            New-Item -ItemType Directory -Path $parent -Force | Out-Null
        }
        [void]$touchedDirs.Add((Split-Path -Path $r.Destination -Parent))
        Move-Item -LiteralPath $r.Destination -Destination $r.Source
        $ok++
    } catch {
        $ng++
        Write-Warning ('戻せませんでした: {0} : {1}' -f $r.Destination, $_.Exception.Message)
    }
}

if (-not $Apply) {
    Write-Host ''
    Write-Host '※ ドライランです。実際に戻すには -Apply を付けてください。' -ForegroundColor Green
    exit 0
}

if ($RemoveEmptyCategoryFolders) {
    foreach ($d in $touchedDirs) {
        if ((Test-Path -LiteralPath $d) -and
            -not (Get-ChildItem -LiteralPath $d -Force -ErrorAction SilentlyContinue)) {
            Remove-Item -LiteralPath $d -Force
            Write-Host "空フォルダを削除: $d"
        }
    }
}

Write-Host ''
Write-Host ('完了: 復元 {0} 件 / 失敗 {1} 件 / スキップ {2} 件' -f $ok, $ng, $skip) -ForegroundColor Green
