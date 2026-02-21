@echo off
setlocal
call "%~dp0build_all.cmd" --skip-app --skip-remove %*
exit /b %ERRORLEVEL%
