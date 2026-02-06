@echo off
setlocal
cd /d %~dp0\..

where py >nul 2>nul && (py -3 -m studio.studio_app & exit /b %ERRORLEVEL%)
python -m studio.studio_app
