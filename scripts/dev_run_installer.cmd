@echo off
setlocal
cd /d %~dp0\..
python -m installer.installer_app
