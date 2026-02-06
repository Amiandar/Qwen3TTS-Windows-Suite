@echo off
setlocal
cd /d %~dp0\..
python -m pip install pyinstaller
pyinstaller --noconfirm --onefile --name Qwen3TTS-Studio studio\studio_app.py
