@echo off
title ULTRON 2.0 - Disable Startup Stealth Mode
cd /d "%~dp0"
.venv_win313\Scripts\python.exe startup_manager.py --disable
echo.
echo ULTRON startup entry removed.
echo.
pause
