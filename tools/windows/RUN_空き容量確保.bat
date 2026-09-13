@echo off
rem ==========================================================
rem  Free-Space launcher
rem  Double-click -> elevate (optional) -> estimate -> Y/N -> delete
rem  NOTE: keep this file ASCII-only. cmd.exe reads .bat with the
rem        console OEM codepage, so non-ASCII text would be garbled.
rem ==========================================================
setlocal EnableExtensions
cd /d "%~dp0"
chcp 65001 >nul

set "PS1=%~dp0Free-Space.ps1"
if not exist "%PS1%" (
    echo [ERROR] Free-Space.ps1 was not found next to this launcher.
    echo         Keep both files in the same folder.
    echo.
    pause
    exit /b 1
)

net session >nul 2>&1
if %errorlevel% equ 0 goto run

echo.
echo Administrator rights let this tool reclaim much more space
echo   - Windows Update download cache
echo   - C:\Windows\Temp, system logs, crash dumps
echo   - component store cleanup (Deep level)
echo A UAC prompt will appear. Choose "Yes" to continue.
echo.

powershell -NoProfile -Command "try { Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-NoExit','-File','\"%PS1%\"','-Level','Standard','-Interactive' -ErrorAction Stop } catch { exit 1 }"
if %errorlevel% equ 0 exit /b 0

echo.
echo Elevation was declined. Continuing WITHOUT administrator rights.
echo Items that need admin will be listed as skipped.
echo.

:run
powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%" -Level Standard -Interactive

echo.
echo Press any key to close this window.
pause >nul
endlocal
