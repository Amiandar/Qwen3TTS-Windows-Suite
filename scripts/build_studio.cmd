@echo off
setlocal
cd /d %~dp0\..

set "PY_CMD="
where py >nul 2>nul && set "PY_CMD=py -3"
if not defined PY_CMD (
  where python >nul 2>nul && set "PY_CMD=python"
)

if not defined PY_CMD (
  echo [ERROR] Python not found. Install Python 3 and/or enable the py launcher.
  exit /b 1
)

call %PY_CMD% -m pip install --upgrade pip pyinstaller || exit /b 1
call %PY_CMD% -m PyInstaller --noconfirm --onefile --name Qwen3TTS-Studio studio\studio_app.py || exit /b 1

echo [OK] Build completed: dist\Qwen3TTS-Studio.exe
