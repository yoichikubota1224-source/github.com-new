@echo off
rem ============================================================
rem  空き容量確保ランチャー
rem  ダブルクリック → 管理者に昇格 → 見積り表示 → Y/N確認 → 削除
rem ============================================================
setlocal

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo 管理者権限が必要です。昇格ダイアログで [はい] を選んでください...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

cd /d "%~dp0"
chcp 65001 >nul

powershell -NoProfile -ExecutionPolicy Bypass -File ".\Free-Space.ps1" -Level Standard -Interactive

echo.
echo 終了するには何かキーを押してください。
pause >nul
endlocal
