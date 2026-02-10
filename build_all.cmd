@echo off
setlocal
call "%~dp0scripts\build_all.cmd" %*
exit /b %ERRORLEVEL%
