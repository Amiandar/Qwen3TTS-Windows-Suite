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
cd /d "%~dp0.." || exit /b 1

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

if not exist ".build_venv_installer\Scripts\python.exe" (
  echo [INFO] Creating .build_venv_installer
  %BUILD_PY% -m venv .build_venv_installer || exit /b 1
)

set "VENV_PY=.build_venv_installer\Scripts\python.exe"
if not exist "%VENV_PY%" (
  echo [ERROR] Build venv python missing: %VENV_PY%
  exit /b 1
)

"%VENV_PY%" -m pip install --upgrade pip || exit /b 1
"%VENV_PY%" -m pip install -r requirements_build_installer.txt || exit /b 1

if exist "build\Qwen3TTS-Installer" rmdir /s /q "build\Qwen3TTS-Installer"
if exist "dist\Qwen3TTS-Installer" rmdir /s /q "dist\Qwen3TTS-Installer"
if exist Qwen3TTS-Installer.spec del /f /q Qwen3TTS-Installer.spec

"%VENV_PY%" -m PyInstaller --noconfirm --windowed --name Qwen3TTS-Installer --workpath "build\Qwen3TTS-Installer" --distpath "dist" --hidden-import PySide6 --hidden-import PySide6.QtCore --hidden-import PySide6.QtGui --hidden-import PySide6.QtWidgets installer\installer_app.py || exit /b 1

echo [INFO] Build complete: dist\Qwen3TTS-Installer\Qwen3TTS-Installer.exe
exit /b 0
