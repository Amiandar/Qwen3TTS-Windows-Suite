@echo off
setlocal
cd /d %~dp0\..
python -m pip install pyinstaller
pyinstaller --noconfirm --onefile --name Qwen3TTS-Installer installer\installer_app.py
