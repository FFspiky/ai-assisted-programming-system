@echo off
setlocal
"%SystemRoot%\System32\chcp.com" 65001 >nul
cd /d "%~dp0.."
if errorlevel 1 exit /b 1
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHONDONTWRITEBYTECODE=1"
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0bootstrap-windows.ps1" %*
set "result=%errorlevel%"
if not "%CODELAB_NO_PAUSE%"=="1" pause
exit /b %result%
