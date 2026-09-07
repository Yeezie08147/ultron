@echo off
title ULTRON 2.0 - Enable Startup Stealth Mode
cd /d "%~dp0"
.venv_win313\Scripts\python.exe startup_manager.py
echo.
echo ULTRON will now launch automatically on Windows boot in background stealth mode.
echo Voice commands ("Ultron ...") and global hotkey Ctrl+Alt+U are active.
echo.
pause
