# ======================================================================
#   ULTRON -- Official PowerShell 1-Line Web Installer
#   Usage: irm https://raw.githubusercontent.com/Yeezie08147/ultron/main/install.ps1 | iex
# ======================================================================

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"

$e = [char]27

Write-Host "$e[38;5;208m$e[1m======================================================================$e[0m"
Write-Host "$e[38;5;208m$e[1m   ULTRON // OFFICIAL GLOBAL CLI INSTALLER // AUTONOMOUS MATRIX$e[0m"
Write-Host "$e[38;5;208m$e[1m======================================================================$e[0m"

$InstallDir = "$env:USERPROFILE\.ultron"
$BinDir = "$InstallDir\bin"
$RepoUrl = "https://github.com/Yeezie08147/ultron.git"
$ZipUrl = "https://github.com/Yeezie08147/ultron/archive/refs/heads/main.zip"

Write-Host "$e[36m[*] Target Installation Directory:$e[0m $InstallDir"

# -- Step 1: Detect or Install Python --
Write-Host "$e[36m[1/6] Checking Python runtime...$e[0m"
$PythonCmd = $null
if (Get-Command "python" -ErrorAction SilentlyContinue) {
    $PythonCmd = "python"
} elseif (Get-Command "py" -ErrorAction SilentlyContinue) {
    $PythonCmd = "py -3"
}

if (-not $PythonCmd) {
    Write-Host "$e[33m[!] Python not found in system PATH. Attempting automated installation via winget...$e[0m"
    if (Get-Command "winget" -ErrorAction SilentlyContinue) {
        Write-Host "$e[36m[*] Installing Python 3.12...$e[0m"
        winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
        if (Get-Command "python" -ErrorAction SilentlyContinue) {
            $PythonCmd = "python"
        }
    }
}

if (-not $PythonCmd) {
    Write-Host "$e[31m[ERROR] Python is required to run ULTRON. Please install Python 3.10+ from https://www.python.org/$e[0m"
    Write-Host "$e[33mEnsure you check Add Python to PATH during installation, then re-run this command.$e[0m"
    return
}

$PyVer = & $PythonCmd --version 2>&1
Write-Host "$e[32m[OK] Python detected:$e[0m $PyVer"

# -- Step 2: Download or Clone ULTRON Repository --
Write-Host "$e[36m[2/6] Fetching ULTRON repository into $InstallDir...$e[0m"
if (Test-Path $InstallDir) {
    if (Test-Path "$InstallDir\.git") {
        Write-Host "$e[36m[*] Updating existing repository...$e[0m"
        git -C $InstallDir pull origin main 2>&1 | Out-Null
    } else {
        Write-Host "$e[33m[*] Existing directory found. Refreshing files...$e[0m"
    }
} else {
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
    if (Get-Command "git" -ErrorAction SilentlyContinue) {
        Write-Host "$e[36m[*] Cloning with Git...$e[0m"
        git clone --depth 1 $RepoUrl $InstallDir
    } else {
        Write-Host "$e[36m[*] Git not detected. Downloading package zip...$e[0m"
        $TempZip = "$env:TEMP\ultron_install.zip"
        $TempExt = "$env:TEMP\ultron_extract"
        Invoke-WebRequest -Uri $ZipUrl -OutFile $TempZip -UseBasicParsing
        if (Test-Path $TempExt) { Remove-Item $TempExt -Recurse -Force }
        Expand-Archive -Path $TempZip -DestinationPath $TempExt -Force
        Copy-Item -Path "$TempExt\ultron-main\*" -Destination $InstallDir -Recurse -Force
        Remove-Item $TempZip -Force -ErrorAction SilentlyContinue
        Remove-Item $TempExt -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# -- Step 3: Setup Virtual Environment --
Write-Host "$e[36m[3/6] Configuring virtual environment (.venv)...$e[0m"
$VenvPy = "$InstallDir\.venv\Scripts\python.exe"
if (-not (Test-Path $VenvPy)) {
    & $PythonCmd -m venv "$InstallDir\.venv"
}

Write-Host "$e[36m[4/6] Installing dependencies from requirements.txt...$e[0m"
& $VenvPy -m pip install --upgrade pip setuptools wheel --quiet
if (Test-Path "$InstallDir\requirements.txt") {
    & $VenvPy -m pip install -r "$InstallDir\requirements.txt" --quiet
}

# -- Step 4: Create Global CLI Shims in bin --
Write-Host "$e[36m[5/6] Registering global ultron command in system PATH...$e[0m"
New-Item -ItemType Directory -Path $BinDir -Force | Out-Null

# 1. ultron.cmd
$CmdContent = "@echo off`r`nset PYTHONIOENCODING=utf-8`r`n`"$VenvPy`" `"$InstallDir\cli.py`" %*"
[System.IO.File]::WriteAllText("$BinDir\ultron.cmd", $CmdContent, [System.Text.Encoding]::UTF8)

# 2. ultron.ps1
$Ps1Content = "`$env:PYTHONIOENCODING = `"utf-8`"`r`n& `"$VenvPy`" `"$InstallDir\cli.py`" @args"
[System.IO.File]::WriteAllText("$BinDir\ultron.ps1", $Ps1Content, [System.Text.Encoding]::UTF8)

# 3. ultron-gui.cmd
$GuiCmdContent = "@echo off`r`n`"$InstallDir\.venv\Scripts\pythonw.exe`" `"$InstallDir\desktop.py`" %*"
[System.IO.File]::WriteAllText("$BinDir\ultron-gui.cmd", $GuiCmdContent, [System.Text.Encoding]::UTF8)

# Add bin directory to User PATH environment variable
$UserPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
if ($UserPath -notlike "*$BinDir*") {
    $NewPath = "$UserPath;$BinDir"
    [System.Environment]::SetEnvironmentVariable("Path", $NewPath, "User")
    Write-Host "$e[32m[OK] Added $BinDir to User PATH.$e[0m"
}

# Add to current process PATH immediately so it works in this console
if ($env:Path -notlike "*$BinDir*") {
    $env:Path = "$BinDir;$env:Path"
}

# -- Step 5: Create Desktop Shortcut --
Write-Host "$e[36m[6/6] Generating desktop shortcut...$e[0m"
try {
    $WshShell = New-Object -ComObject WScript.Shell
    $DesktopPath = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::Desktop)
    $Shortcut = $WshShell.CreateShortcut("$DesktopPath\ULTRON.lnk")
    $Shortcut.TargetPath = "$BinDir\ultron-gui.cmd"
    $Shortcut.WorkingDirectory = $InstallDir
    $Shortcut.Description = "ULTRON Cybernetic Intelligence"
    $Shortcut.Save()
    Write-Host "$e[32m[OK] Created Desktop shortcut: ULTRON.lnk$e[0m"
} catch {
    # Non-critical if shortcut creation fails
}

# -- Step 6: Success Banner --
Write-Host "$e[38;5;208m$e[1m======================================================================$e[0m"
Write-Host "$e[38;5;208m$e[1m  [SUCCESS] ULTRON HAS BEEN INSTALLED GLOBALLY!$e[0m"
Write-Host "$e[38;5;208m$e[1m======================================================================$e[0m"
Write-Host "  You can now use ULTRON directly from ANY terminal or directory:"
Write-Host ""
Write-Host "    ultron           - Launch the Interactive Terminal CLI"
Write-Host "    ultron /model    - Switch or configure AI neural models"
Write-Host "    ultron /devices  - Quick device matrix status query"
Write-Host ""
Write-Host "  Web HUD: Open http://localhost:8340 in your browser."
Write-Host "======================================================================"

# -- Step 7: Optional Model Configuration --
Write-Host ""
Write-Host "$e[38;5;208m$e[1m======================================================================$e[0m"
Write-Host "$e[38;5;208m$e[1m   AI NEURAL BACKEND INITIALIZATION$e[0m"
Write-Host "$e[38;5;208m$e[1m======================================================================$e[0m"
Write-Host "  Select an AI model option to configure now (or skip to choose in CLI):"
Write-Host "    [1] Hacker Mode (5.3 GB) - Supreme Uncensored Intelligence [Recommended]"
Write-Host "    [2] Ultra-Light 1.5B (1.1 GB)       - Ultra-Fast, Low RAM (<8GB)"
Write-Host "    [3] Skip / Pure Autonomous Core     - 0 MB, Instant Offline System Control"
Write-Host ""
$Choice = Read-Host "  Selection [1/2/3] (Press Enter for 1)"
$VenvPy = "$InstallDir\.venv\Scripts\python.exe"
if (-not (Test-Path $VenvPy)) {
    $VenvPy = $PythonCmd
}

if ($Choice -eq "2") {
    & $VenvPy "$InstallDir\scripts\standalone_engine.py" start light
} elseif ($Choice -eq "3") {
    & $VenvPy -c "import json, pathlib; pathlib.Path('$InstallDir/config.json').write_text(json.dumps({'model_choice': 'autonomous'}))"
    Write-Host "$e[32m[OK] Pure Autonomous Core configured (0 MB).$e[0m"
} else {
    & $VenvPy "$InstallDir\scripts\standalone_engine.py" start default
}

