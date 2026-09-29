@echo off
setlocal enabledelayedexpansion
title ULTRON - System Installation Matrix
color 06

echo ======================================================================
echo   ██╗   ██╗██╗  ████████╗██████╗  ██████╗ ███╗   ██╗
echo   ██║   ██║██║  ╚══██╔══╝██╔══██╗██╔═══██╗████╗  ██║
echo   ██║   ██║██║     ██║   ██████╔╝██║   ██║██╔██╗ ██║
echo   ██║   ██║██║     ██║   ██╔══██╗██║   ██║██║╚██╗██║
echo   ╚██████╔╝███████╗██║   ██║  ██║╚██████╔╝██║ ╚████║
echo    ╚═════╝ ╚══════╝╚═╝   ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝
echo        AUTOMATED CROSS-SYSTEM INSTALLATION MATRIX
echo ======================================================================
echo.

cd /d "%~dp0"

:: ── Step 1: Detect or Install Python ──
echo [1/5] Checking Python environment...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    py -3 --version >nul 2>&1
    if %errorlevel% neq 0 (
        echo [!] Python is not installed or not in your PATH.
        echo [*] Attempting automated Python 3.12 installation via Windows Package Manager (winget)...
        winget --version >nul 2>&1
        if %errorlevel% equ 0 (
            echo [*] Installing Python 3.12...
            winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements
            echo [*] Python installation completed. Please restart this installer or open a new terminal.
            pause
            exit /b 0
        ) else (
            echo [!] winget not found. Please install Python 3.10+ from https://www.python.org/downloads/
            echo [!] IMPORTANT: Make sure to check "Add Python to PATH" during installation.
            pause
            exit /b 1
        )
    ) else (
        set "PY_CMD=py -3"
    )
) else (
    set "PY_CMD=python"
)

for /f "tokens=*" %%i in ('%PY_CMD% --version') do set "PY_VER=%%i"
echo [*] Detected: %PY_VER%

:: ── Step 2: Create Python Virtual Environment ──
echo.
echo [2/5] Setting up local Python Virtual Environment (.venv)...
if not exist ".venv\Scripts\python.exe" (
    echo [*] Creating virtual environment in .venv...
    %PY_CMD% -m venv .venv
    if %errorlevel% neq 0 (
        echo [!] Failed to create .venv. Falling back to global Python...
        set "VENV_PYTHON=%PY_CMD%"
    ) else (
        set "VENV_PYTHON=.venv\Scripts\python.exe"
    )
) else (
    echo [*] Existing virtual environment found.
    set "VENV_PYTHON=.venv\Scripts\python.exe"
)

:: ── Step 3: Upgrade pip and install requirements ──
echo.
echo [3/5] Installing and updating dependencies...
"%VENV_PYTHON%" -m pip install --upgrade pip setuptools wheel
if exist "requirements.txt" (
    echo [*] Installing core requirements from requirements.txt...
    "%VENV_PYTHON%" -m pip install -r requirements.txt
) else (
    echo [!] requirements.txt not found. Installing essential packages...
    "%VENV_PYTHON%" -m pip install fastapi uvicorn[standard] websockets pydantic httpx requests python-dotenv psutil pywebview pystray Pillow pyautogui pyttsx3 edge-tts SpeechRecognition rich
)

:: ── Step 4: Verify Android Debug Bridge (ADB) ──
echo.
echo [4/5] Checking Android Debug Bridge (ADB) for phone control...
adb version >nul 2>&1
if %errorlevel% neq 0 (
    echo [*] ADB not detected in system PATH.
    echo [*] ADB is optional, but needed if you wish to control/unlock Android phones.
    choice /c YN /m "Would you like to install Google Platform Tools (ADB) automatically via winget?"
    if !errorlevel! equ 1 (
        winget install Google.PlatformTools --accept-package-agreements --accept-source-agreements
        echo [*] ADB installed. It will be available on next session.
    ) else (
        echo [*] Skipping ADB installation. Phone controls will run via Bluetooth PnP fallback.
    )
) else (
    echo [*] ADB detected and operational.
)

:: ── Step 5: Check Frontend Assets ──
echo.
echo [5/5] Verifying user interface bundles...
if not exist "frontend\dist\index.html" (
    echo [*] Pre-built frontend bundle missing. Checking for Node.js...
    node --version >nul 2>&1
    if %errorlevel% equ 0 (
        echo [*] Building frontend with npm...
        cd frontend
        call npm install
        call npm run build
        cd ..
    ) else (
        echo [!] Node.js not detected. You can install Node.js LTS or use the CLI mode directly.
    )
) else (
    echo [*] Pre-built UI bundle verified.
)

:: ── Create Launchers ──
echo.
echo [*] Generating 1-click launchers...

:: 1. Launch_ULTRON.bat
(
echo @echo off
echo title ULTRON // Autonomous Cybernetic Intelligence
echo cd /d "%%~dp0"
echo if exist ".venv\Scripts\pythonw.exe" (
echo     start "" ".venv\Scripts\pythonw.exe" desktop.py
echo ) else if exist ".venv_win313\Scripts\pythonw.exe" (
echo     start "" ".venv_win313\Scripts\pythonw.exe" desktop.py
echo ) else (
echo     start "" python desktop.py
echo )
) > "Launch_ULTRON.bat"

:: 2. Launch_CLI.bat
(
echo @echo off
echo title ULTRON CLI // Autonomous Matrix
echo cd /d "%%~dp0"
echo if exist ".venv\Scripts\python.exe" (
echo     ".venv\Scripts\python.exe" cli.py
echo ) else if exist ".venv_win313\Scripts\python.exe" (
echo     ".venv_win313\Scripts\python.exe" cli.py
echo ) else (
echo     python cli.py
echo )
echo pause
) > "Launch_CLI.bat"

:: 3. Optional Desktop Shortcut Creator via PowerShell
powershell -NoProfile -Command ^
  "$ws = New-Object -ComObject WScript.Shell; $d = [Environment]::GetFolderPath('Desktop'); $s = $ws.CreateShortcut(\"$d\ULTRON.lnk\"); $s.TargetPath = \"$PSScriptRoot\Launch_ULTRON.bat\"; $s.WorkingDirectory = \"$PSScriptRoot\"; $s.Save()" >nul 2>&1

echo.
echo ======================================================================
echo   [SUCCESS] ULTRON INSTALLATION COMPLETE!
echo ======================================================================
echo.
echo   To launch ULTRON:
echo     1. Desktop GUI : Double-click "Launch_ULTRON.bat" or the Desktop shortcut
echo     2. Terminal CLI: Double-click "Launch_CLI.bat"
echo     3. Browser HUD : Open http://localhost:8340 after starting
echo.
echo   First-time startup:
echo     - On first launch, create your Master Passcode to unlock ULTRON.
echo     - To link your phone: plug in via USB with USB Debugging enabled,
echo       or connect via Bluetooth.
echo.
pause
