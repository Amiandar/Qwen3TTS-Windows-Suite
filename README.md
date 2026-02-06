# Qwen3TTS Windows Suite

Self-contained Windows suite with:
- **Qwen3TTS-Installer.exe**: guided install, hardware detection, env repair, model download.
- **Qwen3TTS-Studio.exe**: audiobook generation from `.fb2`/`.txt` into `001.mp3`, `002.mp3`, ...

## Repository structure

```text
qwen3tts-windows-suite/
  README.md
  installer/
    installer_app.py
    installer_core.py
    ui/
  studio/
    studio_app.py
    studio_core.py
    ui/
  shared/
    env_paths.py
    hf_models.py
    text_fb2.py
    chunking.py
    audio_encode.py
    settings_store.py
    hw_detect.py
  scripts/
    dev_run_installer.cmd
    dev_run_studio.cmd
    build_installer.cmd
    build_studio.cmd
```

## Key behavior implemented

- Installer path screen: Install/Cache/Temp roots.
- All critical env vars redirected: `TEMP`, `TMP`, `HF_HOME`, `HF_HUB_CACHE`, `HUGGINGFACE_HUB_CACHE`, `TRANSFORMERS_CACHE`, `TORCH_HOME`, `PIP_CACHE_DIR`, `XDG_CACHE_HOME`.
- Hardware detection for CPU/RAM/GPU/VRAM and GPU recommendation warning.
- Micromamba-based environment creation under `InstallRoot\envs\qwen3-tts`.
- Model list from Hugging Face with official fallback list.
- Download via `huggingface_hub.snapshot_download(..., resume_download=True)`.
- Studio model selection + family-specific generation APIs:
  - Base: `generate_voice_clone`
  - CustomVoice: `generate_custom_voice`
  - VoiceDesign: `generate_voice_design`
- FB2 extraction + sentence-aware chunking.
- Strict output behavior: final folder contains only numbered MP3 files; intermediate files in sibling `.tmp` folder.
- Logs written only in `InstallRoot\logs`.
- Settings persisted in `InstallRoot\studio_settings.json`.

## Prerequisites (for development)

- Python 3.11+
- Windows 10/11

Install dev dependencies:

```bat
py -3 -m pip install PySide6 huggingface_hub soundfile psutil
```

## Run in development

```bat
scripts\dev_run_installer.cmd
scripts\dev_run_studio.cmd
```

## Build standalone executables

```bat
scripts\build_installer.cmd
scripts\build_studio.cmd
```

Artifacts are produced in `dist\` as:
- `Qwen3TTS-Installer.exe`
- `Qwen3TTS-Studio.exe`

## Notes

- Installer does not delete user-selected folders.
- Re-running installer is supported for repair and additional model downloads.
- Studio keeps UI responsive by running generation in worker thread.
