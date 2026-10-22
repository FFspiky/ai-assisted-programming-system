@echo off
setlocal
"%SystemRoot%\System32\chcp.com" 65001 >nul
cd /d "%~dp0.."
if errorlevel 1 exit /b 1
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHONDONTWRITEBYTECODE=1"
if exist ".venv\Scripts\python.exe" goto virtualenv
"%SystemRoot%\System32\where.exe" py >nul 2>nul
if not errorlevel 1 goto launcher
"%SystemRoot%\System32\where.exe" python >nul 2>nul
if not errorlevel 1 goto python
echo Python 3.11+ was not found. Install Python, then run this script again.
set "result=1"
goto done
:virtualenv
".venv\Scripts\python.exe" -B "scripts\quickstart.py" %*
set "result=%errorlevel%"
goto done
:launcher
py -3 -B "scripts\quickstart.py" %*
set "result=%errorlevel%"
goto done
:python
python -B "scripts\quickstart.py" %*
set "result=%errorlevel%"
:done
if not "%CODELAB_NO_PAUSE%"=="1" pause
exit /b %result%
