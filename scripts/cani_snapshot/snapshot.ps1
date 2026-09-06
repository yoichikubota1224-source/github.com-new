<#
  Cani PC新聞Excel (allnews.xlsx) の週次スナップショット
  - 週1本だけ取得する。Last-Modified が前回と同じなら取得しない
  - SHA-256 と来歴を _manifest.tsv に追記する
  - 保存先は Google Drive 同期フォルダを想定（本リポジトリの外）

  使い方:
    powershell -ExecutionPolicy Bypass -File .\snapshot.ps1 -OutDir "<保存先>"
#>
param(
  [Parameter(Mandatory=$true)][string]$OutDir,
  [string]$Url = "http://cani.fool.jp/S/excel/allnews.xlsx"
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir -Force | Out-Null }
$manifest = Join-Path $OutDir "_manifest.tsv"
if (-not (Test-Path $manifest)) {
  "取得日時_JST`tLast-Modified_JST`tbytes`tsha256`t保存ファイル名`t備考" |
    Out-File -FilePath $manifest -Encoding UTF8
}

# 1) HEAD で来歴を確認する（取得せずに済むならしない）
$head = Invoke-WebRequest -Uri $Url -Method Head -UseBasicParsing -TimeoutSec 60
$lmRaw = $head.Headers["Last-Modified"]
$len   = [int64]$head.Headers["Content-Length"]
$lm    = [datetime]::Parse($lmRaw).ToLocalTime()
$lmTag = $lm.ToString("yyyyMMdd_HHmm")
$now   = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")

$prev = @(Get-Content $manifest -Encoding UTF8 | Select-Object -Skip 1)
if ($prev.Count -gt 0) {
  $lastLM = ($prev[-1] -split "`t")[1]
  if ($lastLM -eq $lm.ToString("yyyy-MM-dd HH:mm:ss")) {
    Write-Host "[skip] Last-Modified が前回と同一のため取得しません: $lastLM"
    exit 0
  }
}

# 2) 取得
$dest = Join-Path $OutDir ("allnews_" + $lmTag + ".xlsx")
Invoke-WebRequest -Uri $Url -OutFile $dest -UseBasicParsing -TimeoutSec 180
Start-Sleep -Seconds 1   # 礼儀

# 3) 検証と記録
$got = (Get-Item $dest).Length
$sha = (Get-FileHash -Path $dest -Algorithm SHA256).Hash.ToLower()
$note = ""
if ($got -ne $len) { $note = "[要確認] Content-Length=$len と実サイズ=$got が不一致" }

"$now`t$($lm.ToString('yyyy-MM-dd HH:mm:ss'))`t$got`t$sha`t$(Split-Path $dest -Leaf)`t$note" |
  Out-File -FilePath $manifest -Append -Encoding UTF8

Write-Host "[ok] $dest"
Write-Host "     Last-Modified(JST) : $($lm.ToString('yyyy-MM-dd HH:mm:ss'))"
Write-Host "     bytes              : $got"
Write-Host "     sha256             : $sha"
if ($note) { Write-Warning $note }
