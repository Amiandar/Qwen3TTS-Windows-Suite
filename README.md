# Qwen3TTS Windows Suite

## RU — Что это за проект
Qwen3TTS Windows Suite — это набор из двух Windows-приложений для не‑технического пользователя:
1. **Qwen3TTS-Installer.exe** — графический установщик/ремонт окружения.
2. **Qwen3TTS-Studio.exe** — графическая студия для озвучки книг (`.fb2`, `.txt`) в MP3-файлы `001.mp3`, `002.mp3`, ...

## RU — Зачем он нужен
- Установка без ручной CLI-настройки.
- Управляемые кэши/временные файлы в выбранных пользователем папках.
- Надёжная схема «книга → чанки MP3» с логами и прогрессом.

## RU — Ключевые возможности
- Preflight Python 3.11+ с установкой Python per-user в выбранную папку (без глобального PATH).
- Самодостаточное окружение через **micromamba** в `InstallRoot\envs\qwen3-tts`.
- Перенаправление `TEMP/TMP`, Hugging Face, Torch, pip, XDG cache в выбранный Cache/Temp Root.
- Определение железа (CPU/RAM/GPU/VRAM), рекомендации GPU/CPU fallback.
- Загрузка моделей Qwen3‑TTS через `huggingface_hub.snapshot_download(..., resume_download=True)`.
- Studio GUI с параметрами генерации, прогрессом, логами, Start/Stop, сохранением настроек.
- Строгое правило output: в папку результата пишутся только `NNN.mp3`; временные файлы в соседнюю `.tmp` папку.

## RU — Системные требования
- Windows 10/11 x64.
- Рекомендуется 20+ GB свободного места (зависит от числа моделей).
- Для 0.6B: желательно GPU 6+ GB VRAM (или CPU fallback).
- Для 1.7B: желательно GPU 10–12+ GB VRAM.
- Без NVIDIA приложение работает в CPU-режиме.

## RU — Установка (для пользователя)
1. Запустите `Qwen3TTS-Installer.exe`.
2. На экране Python preflight:
   - если Python 3.11+ найден — используйте его,
   - иначе установите Python в выбранную папку (`InstallRoot\python` по умолчанию).
3. Укажите:
   - `Install Root`
   - `Cache Root`
   - `Temp Root`
4. Нажмите Install и дождитесь завершения.
5. На экране Models скачайте нужные модели или пропустите.

## RU — Быстрый старт Studio
1. Запустите `Qwen3TTS-Studio.exe`.
2. Выберите установленную модель.
3. Укажите `Book file` (`.fb2`/`.txt`) и, для Base-режима, `Reference audio (WAV)`/`Reference text`.
4. Укажите `Output folder`.
5. Нажмите Start; отслеживайте прогресс и логи.
6. Результат: только `001.mp3`, `002.mp3`, ... в выбранной папке; временная `*.tmp` папка удаляется после успеха.

## RU — Где лежат логи
- Installer: `InstallRoot\logs\installer_YYYYMMDD_HHMMSS.log`
- Studio: `InstallRoot\logs\studio_YYYYMMDD_HHMMSS.log`

## RU — Сборка из исходников
```bat
scripts\build_installer.cmd
scripts\build_studio.cmd
```

Скрипты сборки создают изолированные окружения `.build_venv_installer` и `.build_venv_studio`, ставят зависимости из `requirements_build_*.txt` и запускают PyInstaller через python из этих venv.

Разделение зависимостей:
- `requirements_build_installer.txt` и `requirements_build_studio.txt` — только зависимости для сборки GUI exe.
- `requirements_runtime.txt` — inference/ML зависимости (qwen-tts/torch/onnxruntime и т.д.), их ставит только Installer в runtime-окружение внутри выбранного Install Root.
- Studio.exe — GUI-оболочка: запускает backend через runtime python из install-root, сама не тянет ML-стек при сборке.

Поведение артефактов:
- `build\` — временные файлы PyInstaller (можно удалять).
- `dist\` — готовая сборка для запуска.
- Для onedir-сборки запускайте exe **из папки** `dist\Qwen3TTS-Installer\` или `dist\Qwen3TTS-Studio\`; не выносите exe отдельно.
- `build_installer.cmd` добавляет `requirements_runtime.txt` и `shared\runtime_backend.py` в пакет (`--add-data`), чтобы Installer.exe корректно находил runtime-зависимости и backend-скрипт в packaged режиме.

## RU — Dev запуск
```bat
scripts\dev_run_installer.cmd
scripts\dev_run_studio.cmd
```
- Проверка ресурсов: `python -m installer.tools.print_paths`
- Smoke удаления: `python -m installer.tools.uninstall_smoke`

## RU — Uninstall
- Режим удаления: `python -m installer.installer_app --uninstall --dry-run`
- По умолчанию используется манифест `InstallRoot\install_manifest.json` (можно указать `--manifest <path>`).

## RU — Troubleshooting
- Ошибки скачивания моделей: проверьте сеть/прокси, повторите загрузку (resume включён).
- CUDA не поднялась: переключитесь на CPU (`Device=cpu`).
- Не найден ffmpeg: повторите repair через Installer Components.
- Нехватка VRAM: используйте 0.6B или CPU.
- Ошибки прав: выберите Install/Cache/Temp в доступных папках пользователя.

---

## EN — What this project is
Qwen3TTS Windows Suite is a pair of Windows apps for non-technical users:
1. **Qwen3TTS-Installer.exe** — GUI installer/repair tool.
2. **Qwen3TTS-Studio.exe** — GUI studio to convert books (`.fb2`, `.txt`) into MP3 chunks `001.mp3`, `002.mp3`, ...

## EN — Why it exists
- One-time setup without manual CLI workflows.
- Stable user-controlled cache/temp locations.
- Reliable “book → MP3 chunks” pipeline with progress and logs.

## EN — Key features
- Python 3.11+ preflight with optional per-user Python bootstrap in a selected folder (no global PATH changes).
- Self-contained runtime via **micromamba** in `InstallRoot\envs\qwen3-tts`.
- Redirects `TEMP/TMP`, Hugging Face, Torch, pip, and XDG caches to selected Cache/Temp roots.
- Hardware detection (CPU/RAM/GPU/VRAM) and GPU/CPU fallback recommendations.
- Qwen3‑TTS model downloads via `huggingface_hub.snapshot_download(..., resume_download=True)`.
- Studio GUI with generation parameters, progress/logs, Start/Stop, and settings persistence.
- Strict output rule: only `NNN.mp3` files in the output folder; temp work uses sibling `.tmp` folder.

## EN — System requirements
- Windows 10/11 x64.
- Recommended 20+ GB of free disk space (depends on model count).
- For 0.6B: recommended GPU with 6+ GB VRAM (or CPU fallback).
- For 1.7B: recommended GPU with 10–12+ GB VRAM.
- Without NVIDIA, CPU mode is supported.

## EN — Installation (end user)
1. Run `Qwen3TTS-Installer.exe`.
2. On Python preflight:
   - use detected Python 3.11+ if available,
   - otherwise install Python into selected folder (default `InstallRoot\python`).
3. Select:
   - `Install Root`
   - `Cache Root`
   - `Temp Root`
4. Click Install and wait for completion.
5. On Models screen, download required models (or skip).

## EN — Studio quick start
1. Run `Qwen3TTS-Studio.exe`.
2. Select an installed model.
3. Select `Book file` (`.fb2`/`.txt`) and, for Base mode, `Reference audio (WAV)`/`Reference text`.
4. Select `Output folder`.
5. Click Start and monitor progress/logs.
6. Result: only `001.mp3`, `002.mp3`, ... in output folder; sibling `*.tmp` folder is cleaned after success.

## EN — Logs location
- Installer: `InstallRoot\logs\installer_YYYYMMDD_HHMMSS.log`
- Studio: `InstallRoot\logs\studio_YYYYMMDD_HHMMSS.log`

## EN — Build from source
```bat
scripts\build_installer.cmd
scripts\build_studio.cmd
```

Build scripts create isolated venvs `.build_venv_installer` and `.build_venv_studio`, install dependencies from `requirements_build_*.txt`, and run PyInstaller using each venv Python.

Dependency split:
- `requirements_build_installer.txt` and `requirements_build_studio.txt` contain GUI/build-only dependencies.
- `requirements_runtime.txt` contains inference/ML dependencies (qwen-tts/torch/onnxruntime etc.) and is installed only by Installer into the selected Install Root runtime environment.
- Studio.exe is a GUI shell: it launches backend inference through runtime Python from install-root and does not pull ML stack during Studio build.

Artifact behavior:
- `build\` — temporary PyInstaller files (safe to delete).
- `dist\` — final runnable output.
- For onedir builds, run exe **from inside** `dist\Qwen3TTS-Installer\` or `dist\Qwen3TTS-Studio\`; do not move the exe out alone.
- `build_installer.cmd` bundles `requirements_runtime.txt` into `_internal` and `shared\runtime_backend.py` into `_internal\shared` via `--add-data` so Installer.exe can resolve runtime requirements and backend script in packaged mode.

## EN — Dev run
```bat
scripts\dev_run_installer.cmd
scripts\dev_run_studio.cmd
```
- Resource check: `python -m installer.tools.print_paths`
- Uninstall smoke: `python -m installer.tools.uninstall_smoke`

## EN — Uninstall
- Uninstall mode: `python -m installer.installer_app --uninstall --dry-run`
- Default manifest: `InstallRoot\install_manifest.json` (override with `--manifest <path>`).

## EN — Troubleshooting
- Model download failures: check network/proxy and retry (resume is enabled).
- CUDA issues: switch to CPU (`Device=cpu`).
- Missing ffmpeg: run Installer repair/components again.
- Low VRAM: use 0.6B models or CPU mode.
- Permission errors: choose user-writable Install/Cache/Temp folders.
