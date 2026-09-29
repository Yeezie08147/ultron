@echo off
title ULTRON 2.0
cd /d "%~dp0"

if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" desktop.py
) else if exist ".venv_win313\Scripts\pythonw.exe" (
    start "" ".venv_win313\Scripts\pythonw.exe" desktop.py
) else (
    start "" python desktop.py
)
