@echo off
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1
".venv\Scripts\python.exe" main.py > launch.log 2>&1

