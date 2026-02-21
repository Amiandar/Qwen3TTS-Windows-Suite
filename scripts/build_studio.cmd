@echo off
setlocal
call "%~dp0build_all.cmd" --skip-setup --skip-remove %*
exit /b %ERRORLEVEL%
