<#
.SYNOPSIS
    デスクトップ直下のファイルを種類別フォルダへ仕分けします。

.DESCRIPTION
    既定は「ドライラン（何も動かさない）」です。実際に移動するには -Apply を付けます。
    ファイルの削除は一切行いません。移動のみです。
    移動内容は CSV ログに残るため、Undo-SortDesktop.ps1 で元に戻せます。

    OneDrive でデスクトップがバックアップされている環境も自動で検出します。

.PARAMETER Path
    対象フォルダを明示指定します。省略時はデスクトップを自動検出します。

.PARAMETER Apply
    実際に移動を実行します。付けない場合は計画の表示だけ（ドライラン）。

.PARAMETER IncludeShortcuts
    .lnk / .url（ショートカット）も仕分け対象にします。既定は対象外。

.PARAMETER IncludeFolders
    デスクトップ直下のフォルダも「10_フォルダ」へ移動します。既定は対象外。

.PARAMETER OlderThanDays
    最終更新日が指定日数より古いものだけを対象にします。0（既定）は全件。

.PARAMETER LogDir
    ログCSVの出力先。既定は %USERPROFILE%\DesktopSortLogs

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\Sort-Desktop.ps1
    まず何も動かさずに計画だけ確認する（推奨・最初はこれ）

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\Sort-Desktop.ps1 -Apply
    実際に仕分けを実行する
#>
[CmdletBinding()]
param(
    [string[]]$Path,
    [switch]$Apply,
    [switch]$IncludeShortcuts,
    [switch]$IncludeFolders,
    [int]$OlderThanDays = 0,
    [string]$LogDir = (Join-Path $env:USERPROFILE 'DesktopSortLogs')
)

$ErrorActionPreference = 'Stop'
$OutputEncoding = [System.Text.Encoding]::UTF8

# ---- 種類別カテゴリ定義 -------------------------------------------------
$CategoryMap = [ordered]@{
    '01_画像'           = @('.jpg','.jpeg','.png','.gif','.bmp','.webp','.heic','.heif','.tif','.tiff','.svg','.ico')
    '02_PDF'            = @('.pdf')
    '03_Excel'          = @('.xlsx','.xls','.xlsm','.xlsb','.xltx','.ods')
    '04_CSV・テキスト'  = @('.csv','.tsv','.txt','.log','.json','.xml','.md','.yaml','.yml')
    '05_文書'           = @('.doc','.docx','.rtf','.odt','.ppt','.pptx','.pps','.ppsx','.one','.epub')
    '06_圧縮'           = @('.zip','.7z','.rar','.tar','.gz','.lzh','.cab','.iso')
    '07_インストーラ'   = @('.exe','.msi','.msix','.appx','.msu')
    '08_動画・音声'     = @('.mp4','.mov','.avi','.mkv','.wmv','.mp3','.wav','.m4a','.aac','.flac')
    '09_ショートカット' = @('.lnk','.url','.website')
}
$OtherCategory  = '99_その他'
$FolderCategory = '10_フォルダ'

# カテゴリフォルダ名の一覧（仕分け先そのものを再仕分けしないため）
$CategoryNames = @($CategoryMap.Keys) + @($OtherCategory, $FolderCategory)

# 触ってはいけないファイル名
$ProtectedNames = @('desktop.ini','thumbs.db','.ds_store')

function Get-DesktopPaths {
    $candidates = New-Object System.Collections.Generic.List[string]

    $shellDesktop = [Environment]::GetFolderPath('Desktop')
    if ($shellDesktop) { [void]$candidates.Add($shellDesktop) }
    [void]$candidates.Add((Join-Path $env:USERPROFILE 'Desktop'))

    foreach ($od in @($env:OneDrive, $env:OneDriveCommercial, $env:OneDriveConsumer)) {
        if ($od) {
            [void]$candidates.Add((Join-Path $od 'Desktop'))
            [void]$candidates.Add((Join-Path $od 'デスクトップ'))
        }
    }

    $resolved = foreach ($c in $candidates) {
        if ($c -and (Test-Path -LiteralPath $c -PathType Container)) {
            (Resolve-Path -LiteralPath $c).Path.TrimEnd('\')
        }
    }
    return @($resolved | Sort-Object -Unique)
}

function Get-Category {
    param([string]$Extension)
    $ext = $Extension.ToLowerInvariant()
    foreach ($key in $CategoryMap.Keys) {
        if ($CategoryMap[$key] -contains $ext) { return $key }
    }
    return $OtherCategory
}

function Get-UniqueDestination {
    param([string]$Directory, [string]$FileName)
    $dest = Join-Path $Directory $FileName
    if (-not (Test-Path -LiteralPath $dest)) { return $dest }

    $base = [System.IO.Path]::GetFileNameWithoutExtension($FileName)
    $ext  = [System.IO.Path]::GetExtension($FileName)
    for ($i = 1; $i -le 999; $i++) {
        $candidate = Join-Path $Directory ('{0}_{1}{2}' -f $base, $i, $ext)
        if (-not (Test-Path -LiteralPath $candidate)) { return $candidate }
    }
    throw "重複名を解決できませんでした: $FileName"
}

function Format-Size {
    param([long]$Bytes)
    if ($Bytes -ge 1GB) { return ('{0:N2} GB' -f ($Bytes / 1GB)) }
    if ($Bytes -ge 1MB) { return ('{0:N2} MB' -f ($Bytes / 1MB)) }
    if ($Bytes -ge 1KB) { return ('{0:N2} KB' -f ($Bytes / 1KB)) }
    return "$Bytes B"
}

# ---- 対象フォルダの決定 -------------------------------------------------
if ($Path) {
    $targets = @($Path | Where-Object { Test-Path -LiteralPath $_ -PathType Container } |
                 ForEach-Object { (Resolve-Path -LiteralPath $_).Path.TrimEnd('\') } |
                 Sort-Object -Unique)
} else {
    $targets = Get-DesktopPaths
}

if (-not $targets -or $targets.Count -eq 0) {
    Write-Warning 'デスクトップフォルダを検出できませんでした。-Path で明示指定してください。'
    exit 1
}

$mode = if ($Apply) { '実行モード (-Apply)' } else { 'ドライラン（何も動かしません）' }
Write-Host ''
Write-Host '============================================================' -ForegroundColor Cyan
Write-Host ' デスクトップ 種類別仕分け' -ForegroundColor Cyan
Write-Host " モード : $mode" -ForegroundColor Cyan
Write-Host '============================================================' -ForegroundColor Cyan
foreach ($t in $targets) { Write-Host " 対象 : $t" }
Write-Host ''

$cutoff = if ($OlderThanDays -gt 0) { (Get-Date).AddDays(-$OlderThanDays) } else { $null }
$plan   = New-Object System.Collections.Generic.List[object]

foreach ($root in $targets) {

    # --- ファイル ---
    $items = @(Get-ChildItem -LiteralPath $root -File -Force -ErrorAction SilentlyContinue)
    foreach ($f in $items) {
        if ($ProtectedNames -contains $f.Name.ToLowerInvariant()) { continue }
        if ($f.Attributes -band [System.IO.FileAttributes]::System)  { continue }
        if ($f.Attributes -band [System.IO.FileAttributes]::Hidden)  { continue }

        $ext = $f.Extension.ToLowerInvariant()
        if (-not $IncludeShortcuts -and ($CategoryMap['09_ショートカット'] -contains $ext)) { continue }
        if ($cutoff -and $f.LastWriteTime -ge $cutoff) { continue }

        $category = Get-Category -Extension $ext
        $plan.Add([pscustomobject]@{
            Root      = $root
            Type      = 'File'
            Name      = $f.Name
            Source    = $f.FullName
            Category  = $category
            DestDir   = (Join-Path $root $category)
            SizeBytes = [long]$f.Length
            Updated   = $f.LastWriteTime
        })
    }

    # --- フォルダ（任意） ---
    if ($IncludeFolders) {
        $dirs = @(Get-ChildItem -LiteralPath $root -Directory -Force -ErrorAction SilentlyContinue)
        foreach ($d in $dirs) {
            if ($CategoryNames -contains $d.Name) { continue }
            if ($d.Attributes -band [System.IO.FileAttributes]::System) { continue }
            if ($cutoff -and $d.LastWriteTime -ge $cutoff) { continue }

            $plan.Add([pscustomobject]@{
                Root      = $root
                Type      = 'Folder'
                Name      = $d.Name
                Source    = $d.FullName
                Category  = $FolderCategory
                DestDir   = (Join-Path $root $FolderCategory)
                SizeBytes = 0L
                Updated   = $d.LastWriteTime
            })
        }
    }
}

if ($plan.Count -eq 0) {
    Write-Host '仕分け対象はありませんでした。' -ForegroundColor Green
    exit 0
}

# ---- 計画の表示 ---------------------------------------------------------
Write-Host '--- 仕分け計画 ---' -ForegroundColor Yellow
$plan | Group-Object Category | Sort-Object Name | ForEach-Object {
    $sum = ($_.Group | Measure-Object SizeBytes -Sum).Sum
    '{0,-20} {1,5} 件  {2}' -f $_.Name, $_.Count, (Format-Size ([long]$sum))
} | Write-Host

$totalSize = ($plan | Measure-Object SizeBytes -Sum).Sum
Write-Host ''
Write-Host ('合計 {0} 件 / {1}' -f $plan.Count, (Format-Size ([long]$totalSize))) -ForegroundColor Yellow
Write-Host ''

if (-not $Apply) {
    Write-Host '※ ドライランです。ファイルは1つも動かしていません。' -ForegroundColor Green
    Write-Host '   実行する場合はもう一度 -Apply を付けて実行してください:' -ForegroundColor Green
    Write-Host '   powershell -ExecutionPolicy Bypass -File .\Sort-Desktop.ps1 -Apply' -ForegroundColor Green
    Write-Host ''
    $plan | Select-Object Category, Name, @{n='Size';e={Format-Size $_.SizeBytes}}, Updated |
        Sort-Object Category, Name | Format-Table -AutoSize
    exit 0
}

# ---- 実行 ---------------------------------------------------------------
if (-not (Test-Path -LiteralPath $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}
$stamp   = Get-Date -Format 'yyyyMMdd_HHmmss'
$logPath = Join-Path $LogDir "desktop-sort_$stamp.csv"
$log     = New-Object System.Collections.Generic.List[object]

$ok = 0; $ng = 0
foreach ($p in $plan) {
    try {
        if (-not (Test-Path -LiteralPath $p.DestDir)) {
            New-Item -ItemType Directory -Path $p.DestDir -Force | Out-Null
        }
        $dest = Get-UniqueDestination -Directory $p.DestDir -FileName $p.Name
        Move-Item -LiteralPath $p.Source -Destination $dest -Force:$false
        $ok++
        $log.Add([pscustomobject]@{
            Timestamp   = (Get-Date).ToString('s')
            Result      = 'OK'
            Type        = $p.Type
            Category    = $p.Category
            Source      = $p.Source
            Destination = $dest
            SizeBytes   = $p.SizeBytes
            Message     = ''
        })
    } catch {
        $ng++
        Write-Warning ('移動できませんでした: {0} : {1}' -f $p.Name, $_.Exception.Message)
        $log.Add([pscustomobject]@{
            Timestamp   = (Get-Date).ToString('s')
            Result      = 'NG'
            Type        = $p.Type
            Category    = $p.Category
            Source      = $p.Source
            Destination = ''
            SizeBytes   = $p.SizeBytes
            Message     = $_.Exception.Message
        })
    }
}

$log | Export-Csv -LiteralPath $logPath -NoTypeInformation -Encoding UTF8

Write-Host ''
Write-Host ('完了: 成功 {0} 件 / 失敗 {1} 件' -f $ok, $ng) -ForegroundColor Green
Write-Host ("ログ: $logPath") -ForegroundColor Green
Write-Host '元に戻す場合:' -ForegroundColor Green
Write-Host ("  powershell -ExecutionPolicy Bypass -File .\Undo-SortDesktop.ps1 -LogPath `"$logPath`" -Apply") -ForegroundColor Green
