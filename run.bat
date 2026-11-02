@echo off
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1
start "" "%~dp0.venv\Scripts\pythonw.exe" main.py
