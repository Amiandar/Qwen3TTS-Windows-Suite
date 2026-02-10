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
set "DIST_ROOT=dist"
set "INSTALLER_DIR=%DIST_ROOT%\Qwen3TTS-Installer"
set "UNINSTALLER_DIR=%DIST_ROOT%\Qwen3TTS-Uninstaller"

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
if exist "build\Qwen3TTS-Uninstaller" rmdir /s /q "build\Qwen3TTS-Uninstaller"
if exist "%INSTALLER_DIR%" rmdir /s /q "%INSTALLER_DIR%"
if exist "%UNINSTALLER_DIR%" rmdir /s /q "%UNINSTALLER_DIR%"
if exist Qwen3TTS-Installer.spec del /f /q Qwen3TTS-Installer.spec
if exist Qwen3TTS-Uninstaller.spec del /f /q Qwen3TTS-Uninstaller.spec

"%VENV_PY%" -m PyInstaller --noconfirm --windowed --name Qwen3TTS-Installer --workpath "build\Qwen3TTS-Installer" --distpath "%DIST_ROOT%" --add-data "requirements_runtime.txt;." --add-data "shared\runtime_backend.py;shared" --hidden-import PySide6 --hidden-import PySide6.QtCore --hidden-import PySide6.QtGui --hidden-import PySide6.QtWidgets installer\installer_app.py || exit /b 1
"%VENV_PY%" -m PyInstaller --noconfirm --windowed --name Qwen3TTS-Uninstaller --workpath "build\Qwen3TTS-Uninstaller" --distpath "%DIST_ROOT%" --hidden-import PySide6 --hidden-import PySide6.QtCore --hidden-import PySide6.QtGui --hidden-import PySide6.QtWidgets uninstaller_app.py || exit /b 1

if not exist "%UNINSTALLER_DIR%\Qwen3TTS-Uninstaller.exe" (
  echo [ERROR] Missing Uninstaller executable: %UNINSTALLER_DIR%\Qwen3TTS-Uninstaller.exe
  exit /b 1
)
copy /y "%UNINSTALLER_DIR%\Qwen3TTS-Uninstaller.exe" "%INSTALLER_DIR%\Qwen3TTS-Uninstaller.exe" >nul || exit /b 1

if exist "%INSTALLER_DIR%\_internal\_internal\requirements_runtime.txt" (
  echo [WARN] Detected nested path: %INSTALLER_DIR%\_internal\_internal\requirements_runtime.txt
  echo [WARN] This indicates wrong add-data destination. Use --add-data "requirements_runtime.txt;."
)

if exist "%INSTALLER_DIR%\_internal\_internal\shared\runtime_backend.py" (
  echo [WARN] Detected nested backend path: %INSTALLER_DIR%\_internal\_internal\shared\runtime_backend.py
  echo [WARN] Use --add-data "shared\runtime_backend.py;shared" to avoid _internal\_internal nesting.
)

if not exist "%INSTALLER_DIR%\_internal\requirements_runtime.txt" (
  echo [WARN] Missing packaged requirements: %INSTALLER_DIR%\_internal\requirements_runtime.txt
  echo [WARN] Packaging mode: onedir
  echo [WARN] Check Installer add-data syntax, it must be: --add-data "requirements_runtime.txt;." and --add-data "shared\runtime_backend.py;shared"
  if exist "%INSTALLER_DIR%\_internal" (
    echo [WARN] Existing contents of %INSTALLER_DIR%\_internal:
    dir /b "%INSTALLER_DIR%\_internal"
  ) else (
    echo [WARN] _internal directory not found under %INSTALLER_DIR%
  )
  if exist "requirements_runtime.txt" if exist "%INSTALLER_DIR%\_internal" (
    echo [WARN] Fallback: copying requirements_runtime.txt into Installer _internal.
    copy /y "requirements_runtime.txt" "%INSTALLER_DIR%\_internal\requirements_runtime.txt" >nul || exit /b 1
  )
)


if not exist "%INSTALLER_DIR%\_internal\requirements_runtime.txt" (
  echo [ERROR] Missing packaged requirements: %INSTALLER_DIR%\_internal\requirements_runtime.txt
  exit /b 1
)

if not exist "%INSTALLER_DIR%\_internal\shared\runtime_backend.py" (
  echo [ERROR] Missing packaged backend script: %INSTALLER_DIR%\_internal\shared\runtime_backend.py
  exit /b 1
)

"%VENV_PY%" -m installer.tools.print_paths || exit /b 1

echo [INFO] Build complete: %INSTALLER_DIR%\Qwen3TTS-Installer.exe and Qwen3TTS-Uninstaller.exe
exit /b 0
