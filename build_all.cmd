@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "PAUSE_ON_ERROR=1"
set "DO_CLEAN=0"
set "SKIP_SETUP=0"
set "SKIP_APP=0"
set "SKIP_REMOVE=0"
set "PYI_DEBUG="

:parse_args
if "%~1"=="" goto :args_done
if /I "%~1"=="--clean" set "DO_CLEAN=1"
if /I "%~1"=="--skip-setup" set "SKIP_SETUP=1"
if /I "%~1"=="--skip-app" set "SKIP_APP=1"
if /I "%~1"=="--skip-remove" set "SKIP_REMOVE=1"
if /I "%~1"=="--debug" set "PYI_DEBUG=--log-level DEBUG"
shift
goto :parse_args

:args_done
call :main
set "EC=%ERRORLEVEL%"
if not "%EC%"=="0" (
  echo.
  echo [ERROR] Exit code: %EC%
  if "%PAUSE_ON_ERROR%"=="1" pause
)
exit /b %EC%

:main
cd /d "%~dp0" || exit /b 1

set "DIST_DIR=dist\Qwen3GUI"
set "SETUP_EXE=%DIST_DIR%\Qwen3GUI-Setup.exe"
set "APP_EXE=%DIST_DIR%\Qwen3GUI.exe"
set "REMOVE_EXE=%DIST_DIR%\Qwen3GUI-Remove.exe"
set "SETUP_CONTENT=%DIST_DIR%\_setup"
set "APP_CONTENT=%DIST_DIR%\_app"
set "REMOVE_CONTENT=%DIST_DIR%\_remove"

set "BUILD_PY="
py -3.11 -c "import sys;print(sys.executable)" >nul 2>nul
if "%ERRORLEVEL%"=="0" (
  set "BUILD_PY=py -3.11"
) else (
  python -c "import sys;assert sys.version_info >= (3,11)" >nul 2>nul || (
    echo [ERROR] Python 3.11+ not found. Install Python 3.11 and retry.
    exit /b 1
  )
  set "BUILD_PY=python"
)

echo [INFO] Build Python launcher: %BUILD_PY%

if not exist ".build_venv_release\Scripts\python.exe" (
  echo [INFO] Creating .build_venv_release
  %BUILD_PY% -m venv .build_venv_release || exit /b 1
)

set "VENV_PY=.build_venv_release\Scripts\python.exe"
if not exist "%VENV_PY%" (
  echo [ERROR] Build venv python missing: %VENV_PY%
  exit /b 1
)

"%VENV_PY%" -m pip install --upgrade pip || exit /b 1
"%VENV_PY%" -m pip install -r requirements_build.txt || exit /b 1

if "%DO_CLEAN%"=="1" (
  if exist "build\setup" rmdir /s /q "build\setup"
  if exist "build\app" rmdir /s /q "build\app"
  if exist "build\remove" rmdir /s /q "build\remove"
)

if not exist "%DIST_DIR%" mkdir "%DIST_DIR%"
if exist "%SETUP_EXE%" del /f /q "%SETUP_EXE%"
if exist "%APP_EXE%" del /f /q "%APP_EXE%"
if exist "%REMOVE_EXE%" del /f /q "%REMOVE_EXE%"
if exist "%SETUP_CONTENT%" rmdir /s /q "%SETUP_CONTENT%"
if exist "%APP_CONTENT%" rmdir /s /q "%APP_CONTENT%"
if exist "%REMOVE_CONTENT%" rmdir /s /q "%REMOVE_CONTENT%"

if "%SKIP_SETUP%"=="0" (
  echo [INFO] Building Setup...
  "%VENV_PY%" -m PyInstaller --noconfirm --windowed --name Qwen3GUI-Setup --workpath "build\setup" --distpath "%DIST_DIR%" --contents-directory _setup --add-data "requirements_runtime.txt;." --add-data "shared\runtime_backend.py;shared" --hidden-import PySide6 --hidden-import PySide6.QtCore --hidden-import PySide6.QtGui --hidden-import PySide6.QtWidgets %PYI_DEBUG% installer\installer_app.py || exit /b 1
  if not exist "%SETUP_EXE%" (
    echo [ERROR] Missing setup exe: %SETUP_EXE%
    exit /b 1
  )
  if not exist "%SETUP_CONTENT%" (
    echo [ERROR] Missing setup contents-dir: %SETUP_CONTENT%
    exit /b 1
  )
  if not exist "%SETUP_CONTENT%\requirements_runtime.txt" (
    echo [ERROR] Missing setup packaged requirements: %SETUP_CONTENT%\requirements_runtime.txt
    exit /b 1
  )
  if not exist "%SETUP_CONTENT%\shared\runtime_backend.py" (
    echo [ERROR] Missing setup packaged backend script: %SETUP_CONTENT%\shared\runtime_backend.py
    exit /b 1
  )
)

if "%SKIP_APP%"=="0" (
  echo [INFO] Building App...
  "%VENV_PY%" -m PyInstaller --noconfirm --windowed --name Qwen3GUI --workpath "build\app" --distpath "%DIST_DIR%" --contents-directory _app --hidden-import PySide6 --hidden-import PySide6.QtCore --hidden-import PySide6.QtGui --hidden-import PySide6.QtWidgets %PYI_DEBUG% studio\studio_app.py || exit /b 1
  if not exist "%APP_EXE%" (
    echo [ERROR] Missing app exe: %APP_EXE%
    exit /b 1
  )
  if not exist "%APP_CONTENT%" (
    echo [ERROR] Missing app contents-dir: %APP_CONTENT%
    exit /b 1
  )
)

if "%SKIP_REMOVE%"=="0" (
  echo [INFO] Building Remove...
  "%VENV_PY%" -m PyInstaller --noconfirm --windowed --name Qwen3GUI-Remove --workpath "build\remove" --distpath "%DIST_DIR%" --contents-directory _remove --hidden-import PySide6 --hidden-import PySide6.QtCore --hidden-import PySide6.QtGui --hidden-import PySide6.QtWidgets %PYI_DEBUG% uninstaller_app.py || exit /b 1
  if not exist "%REMOVE_EXE%" (
    echo [ERROR] Missing remove exe: %REMOVE_EXE%
    exit /b 1
  )
  if not exist "%REMOVE_CONTENT%" (
    echo [ERROR] Missing remove contents-dir: %REMOVE_CONTENT%
    exit /b 1
  )
)

echo [INFO] Build OK: %DIST_DIR%
exit /b 0
