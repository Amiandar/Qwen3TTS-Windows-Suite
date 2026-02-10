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
cd /d "%~dp0.." || exit /b 1

set "DIST_DIR=dist\Qwen3GUI"
set "STAGE_DIR=dist\_stage"
set "SETUP_STAGE=%STAGE_DIR%\Qwen3GUI-Setup"
set "APP_STAGE=%STAGE_DIR%\Qwen3GUI"
set "REMOVE_STAGE=%STAGE_DIR%\Qwen3GUI-Remove"

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
  if exist "build\Qwen3GUI-Setup" rmdir /s /q "build\Qwen3GUI-Setup"
  if exist "build\Qwen3GUI" rmdir /s /q "build\Qwen3GUI"
  if exist "build\Qwen3GUI-Remove" rmdir /s /q "build\Qwen3GUI-Remove"
)

if exist "%DIST_DIR%" rmdir /s /q "%DIST_DIR%"
if exist "%STAGE_DIR%" rmdir /s /q "%STAGE_DIR%"
mkdir "%DIST_DIR%" || exit /b 1
mkdir "%STAGE_DIR%" || exit /b 1

if "%SKIP_SETUP%"=="0" (
  echo [INFO] Building Setup into stage...
  "%VENV_PY%" -m PyInstaller --noconfirm --windowed --name Qwen3GUI-Setup --workpath "build\setup" --distpath "%STAGE_DIR%" --contents-directory _setup --add-data "requirements_runtime.txt;." --add-data "shared\runtime_backend.py;shared" --hidden-import PySide6 --hidden-import PySide6.QtCore --hidden-import PySide6.QtGui --hidden-import PySide6.QtWidgets --hidden-import huggingface_hub --collect-submodules huggingface_hub %PYI_DEBUG% installer\installer_app.py || exit /b 1
  call :flatten "Qwen3GUI-Setup" "%SETUP_EXE%" "%SETUP_CONTENT%" "%SETUP_STAGE%" "_setup" || exit /b 1
  if not exist "%SETUP_CONTENT%\requirements_runtime.txt" (
    echo [ERROR] Missing setup packaged requirements: %SETUP_CONTENT%\requirements_runtime.txt
    exit /b 1
  )
  if not exist "%SETUP_CONTENT%\shared\runtime_backend.py" (
    echo [ERROR] Missing setup packaged backend script: %SETUP_CONTENT%\shared\runtime_backend.py
    exit /b 1
  )
  echo [INFO] Setup smoke imports...
  "%SETUP_EXE%" --smoke-imports
  if not "%ERRORLEVEL%"=="0" (
    echo [ERROR] Setup smoke imports failed
    exit /b 1
  )
)

if "%SKIP_APP%"=="0" (
  echo [INFO] Building App into stage...
  "%VENV_PY%" -m PyInstaller --noconfirm --windowed --name Qwen3GUI --workpath "build\app" --distpath "%STAGE_DIR%" --contents-directory _app --hidden-import PySide6 --hidden-import PySide6.QtCore --hidden-import PySide6.QtGui --hidden-import PySide6.QtWidgets %PYI_DEBUG% studio\studio_app.py || exit /b 1
  call :flatten "Qwen3GUI" "%APP_EXE%" "%APP_CONTENT%" "%APP_STAGE%" "_app" || exit /b 1
)

if "%SKIP_REMOVE%"=="0" (
  echo [INFO] Building Remove into stage...
  "%VENV_PY%" -m PyInstaller --noconfirm --windowed --name Qwen3GUI-Remove --workpath "build\remove" --distpath "%STAGE_DIR%" --contents-directory _remove --hidden-import PySide6 --hidden-import PySide6.QtCore --hidden-import PySide6.QtGui --hidden-import PySide6.QtWidgets %PYI_DEBUG% uninstaller_app.py || exit /b 1
  call :flatten "Qwen3GUI-Remove" "%REMOVE_EXE%" "%REMOVE_CONTENT%" "%REMOVE_STAGE%" "_remove" || exit /b 1
)

if exist "%STAGE_DIR%" rmdir /s /q "%STAGE_DIR%"

call :smoke "%SETUP_EXE%" "%SETUP_CONTENT%" "%SKIP_SETUP%" || exit /b 1
call :smoke "%APP_EXE%" "%APP_CONTENT%" "%SKIP_APP%" || exit /b 1
call :smoke "%REMOVE_EXE%" "%REMOVE_CONTENT%" "%SKIP_REMOVE%" || exit /b 1

if exist "%DIST_DIR%\Qwen3GUI-Setup" (
  echo [ERROR] Unexpected unflattened dir: %DIST_DIR%\Qwen3GUI-Setup
  exit /b 1
)
if exist "%DIST_DIR%\Qwen3GUI" (
  echo [ERROR] Unexpected unflattened dir: %DIST_DIR%\Qwen3GUI
  exit /b 1
)
if exist "%DIST_DIR%\Qwen3GUI-Remove" (
  echo [ERROR] Unexpected unflattened dir: %DIST_DIR%\Qwen3GUI-Remove
  exit /b 1
)

for /f %%I in ('dir /b /a-d "%DIST_DIR%" ^| findstr /v /i "Qwen3GUI-Setup.exe Qwen3GUI.exe Qwen3GUI-Remove.exe"') do (
  echo [WARN] Unexpected file in %DIST_DIR%: %%I
)

echo [INFO] Build OK: %DIST_DIR%
exit /b 0

:flatten
set "APP_NAME=%~1"
set "FINAL_EXE=%~2"
set "FINAL_CONTENT=%~3"
set "APP_STAGE_DIR=%~4"
set "CONTENT_DIR_NAME=%~5"

set "STAGE_EXE=%APP_STAGE_DIR%\%APP_NAME%.exe"
set "STAGE_CONTENT=%APP_STAGE_DIR%\%CONTENT_DIR_NAME%"

if not exist "%APP_STAGE_DIR%" (
  echo [ERROR] Missing stage app dir: %APP_STAGE_DIR%
  exit /b 1
)
if not exist "%STAGE_EXE%" (
  echo [ERROR] Missing stage exe: %STAGE_EXE%
  exit /b 1
)
if not exist "%STAGE_CONTENT%" (
  echo [ERROR] Missing stage contents dir: %STAGE_CONTENT%
  exit /b 1
)

move /y "%STAGE_EXE%" "%FINAL_EXE%" >nul || exit /b 1
if exist "%FINAL_CONTENT%" rmdir /s /q "%FINAL_CONTENT%"
move /y "%STAGE_CONTENT%" "%FINAL_CONTENT%" >nul || exit /b 1

for /f %%F in ('dir /b /a-d "%APP_STAGE_DIR%"') do (
  if /i not "%%F"=="%APP_NAME%.exe" (
    move /y "%APP_STAGE_DIR%\%%F" "%FINAL_CONTENT%\%%F" >nul
  )
)
for /f %%D in ('dir /b /ad "%APP_STAGE_DIR%"') do (
  if /i not "%%D"=="%CONTENT_DIR_NAME%" (
    move /y "%APP_STAGE_DIR%\%%D" "%FINAL_CONTENT%\%%D" >nul
  )
)
if exist "%APP_STAGE_DIR%" rmdir /s /q "%APP_STAGE_DIR%"
exit /b 0

:smoke
set "SMOKE_EXE=%~1"
set "SMOKE_CONTENT=%~2"
set "SMOKE_SKIP=%~3"
if "%SMOKE_SKIP%"=="1" exit /b 0
if not exist "%SMOKE_EXE%" (
  echo [ERROR] Missing exe: %SMOKE_EXE%
  exit /b 1
)
if not exist "%SMOKE_CONTENT%" (
  echo [ERROR] Missing contents-dir: %SMOKE_CONTENT%
  exit /b 1
)
for /f %%N in ('dir /b "%SMOKE_CONTENT%" ^| find /c /v ""') do set "COUNT=%%N"
if "%COUNT%"=="0" (
  echo [ERROR] Empty contents-dir: %SMOKE_CONTENT%
  exit /b 1
)
exit /b 0
