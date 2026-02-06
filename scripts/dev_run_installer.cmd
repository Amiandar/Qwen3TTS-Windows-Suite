@echo off
setlocal
cd /d %~dp0\..

call :ensure_python || exit /b 1
call %PY_CMD% -m installer.installer_app
exit /b %ERRORLEVEL%

:detect_python
set "PY_CMD="
where py >nul 2>nul && set "PY_CMD=py -3"
if not defined PY_CMD (
  where python >nul 2>nul && set "PY_CMD=python"
)
exit /b 0

:ensure_python
call :detect_python
if defined PY_CMD exit /b 0

echo [INFO] Python 3 not found. Attempting automatic install via winget...
where winget >nul 2>nul || (
  echo [ERROR] winget is not available. Install Python 3.11 manually, then rerun this script.
  exit /b 1
)

winget install --id Python.Python.3.11 -e --source winget --accept-source-agreements --accept-package-agreements || (
  echo [ERROR] Automatic Python installation failed. Install Python manually and rerun.
  exit /b 1
)

call :detect_python
if defined PY_CMD exit /b 0

if exist "%LocalAppData%\Programs\Python\Python311\python.exe" (
  set "PY_CMD=%LocalAppData%\Programs\Python\Python311\python.exe"
  exit /b 0
)

if exist "%ProgramFiles%\Python311\python.exe" (
  set "PY_CMD=%ProgramFiles%\Python311\python.exe"
  exit /b 0
)

echo [ERROR] Python appears installed but is still not detectable in this shell.
echo [ERROR] Reopen terminal and run script again, or reinstall Python with PATH/py launcher enabled.
exit /b 1
