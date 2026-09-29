# ULTRON — Cross-Computer Installation & Setup Guide

This guide explains how to install, set up, and run **ULTRON** on any other Windows, macOS, or Linux computer.

---

## ⚡ Official 1-Line Global Installation (Windows PowerShell)

Open PowerShell on **any computer** and paste this single command:

```powershell
irm https://raw.githubusercontent.com/Yeezie08147/ultron/main/install.ps1 | iex
```

That's it! The script will:
1. Automatically verify and set up Python 3.
2. Clone/download ULTRON into `~/.ultron`.
3. Set up the virtual environment and install all dependencies.
4. **Register the global `ultron` command** in your system PATH.
5. Create a Desktop shortcut (`ULTRON.lnk`).

Once finished, you can run ULTRON from **any terminal or directory**:
- `ultron` (Interactive Terminal CLI)
- `ultron-gui` (Holographic Desktop GUI)
- `ultron /devices` (Quick Device Matrix Status)

---

## 🛠️ Alternative Manual Installation (Windows)

### 1. Download or Clone the Repository
On your other computer, open Command Prompt or PowerShell and clone the repository:
```cmd
git clone https://github.com/Yeezie08147/ultron.git
cd ultron
```
*(Or download the ZIP from GitHub, extract it, and open the folder).*

### 2. Run the Automated Installer
Simply double-click:
```text
install.bat
```
The installer automatically:
- Checks for **Python 3.10+** (and offers to install it via Windows Package Manager `winget` if missing).
- Creates a dedicated local virtual environment (`.venv`).
- Installs all dependencies cleanly from `requirements.txt`.
- Checks for **ADB** (Google Platform Tools for phone control) and installs it if desired.
- Generates **`Launch_ULTRON.bat`**, **`Launch_CLI.bat`**, and an optional Desktop shortcut.

### 3. Launch ULTRON
- **Desktop Holographic HUD**: Double-click **`Launch_ULTRON.bat`** (or the Desktop shortcut).
- **Terminal CLI Mode**: Double-click **`Launch_CLI.bat`** or run `python cli.py`.
- **Browser Access**: Open [http://localhost:8340](http://localhost:8340) in Chrome, Edge, or Brave.

---

## 🍏 Quick Start (macOS / Linux)

Open Terminal in the project directory:
```bash
chmod +x install.sh
./install.sh
```

To launch:
```bash
./launch_ultron.sh   # Desktop GUI
./launch_cli.sh      # Terminal CLI
```

---

## 📱 Connecting Your Mobile Phone

ULTRON features a real-time **Multi-Device Matrix** with hybrid detection:

### Option A: USB Cable (Full Remote Screen Unlock & Control)
1. On your Android phone, enable **Developer Options**:
   - Go to **Settings > About Phone > Software Information**.
   - Tap **Build Number** 7 times.
2. Go to **Settings > Developer Options** and enable **USB Debugging**.
3. Plug your phone into the computer with a USB cable.
4. When prompted on the phone (*"Allow USB debugging?"*), check **"Always allow from this computer"** and tap **Allow**.
5. Your phone will immediately appear in the ULTRON HUD with battery percentage, screen lock status, and full remote control.

### Option B: Bluetooth (Wireless Telemetry Link)
1. Pair your phone to your PC via Windows Bluetooth settings.
2. ULTRON will automatically detect the phone and display **`BLUETOOTH LINKED`** in the HUD Matrix.

---

## 🔒 First-Time Security Passcode

When launching ULTRON for the first time:
1. You will be prompted to create your **Master Passcode**.
2. Enter a secure passcode (at least 3 characters).
3. Once set, your Master Passcode unlocks the cybernetic security matrix and grants full access to ULTRON's voice, desktop, and device systems.

---

## 🌐 Accessing ULTRON from Other Devices on Local Wi-Fi

You can access the ULTRON HUD and call companion from any smartphone, tablet, or laptop on the same local network:
1. Find your host PC's local IP address (e.g. `192.168.1.10` via `ipconfig` or `/network` in CLI).
2. On your phone or secondary computer, open:
   ```text
   http://192.168.1.10:8340
   ```
3. Enter your Master Passcode to unlock and interact remotely!
