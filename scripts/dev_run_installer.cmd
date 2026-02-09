@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "PAUSE_ON_ERROR=1"

call :main
set "EC=%ERRORLEVEL%"
if not "%EC%"=="0" (
  echo.
  echo [ERROR] Exit code: %EC%
  if "%PAUSE_ON_ERROR%"=="1" pause
)
exit /b %EC%

:main
cd /d "%~dp0.."
python -m installer.installer_app || exit /b 1
exit /b 0
