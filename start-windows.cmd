@echo off
call "%~dp0scripts\launch-windows.cmd" start %*
exit /b %errorlevel%
