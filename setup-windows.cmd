@echo off
call "%~dp0scripts\launch-windows.cmd" setup %*
exit /b %errorlevel%
