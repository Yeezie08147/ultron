@echo off
title ULTRON CLI // Autonomous Matrix
cd /d "%~dp0"

if exist ".venv_win313\Scripts\python.exe" (
    ".venv_win313\Scripts\python.exe" cli.py
) else (
    python cli.py
)

pause
