@echo off
title ULTRON 2.0 Launcher
cd /d "%~dp0"

echo Starting ULTRON 2.0 Engine and Background Voice Daemon...
start "" ".venv_win313\Scripts\pythonw.exe" desktop.py --stealth

timeout /t 2 /nobreak >nul

echo Opening ULTRON Desktop Application Window...
if exist "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" (
    start "" "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --app=http://127.0.0.1:8340 --start-maximized
) else if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" (
    start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --app=http://127.0.0.1:8340 --start-maximized
) else (
    start http://127.0.0.1:8340
)
