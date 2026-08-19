"""
desktop_control.py — ULTRON Windows Full Desktop Access & Control.

Provides comprehensive Windows OS interaction:
- High-speed screenshot capture & image analysis
- Active window inspection and window focus/minimizing
- Application launching and process termination
- Keyboard typing, hotkeys, and mouse automation
- Desktop file & folder explorer actions
"""

import os
import sys
import time
import shutil
import logging
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any
from PIL import Image, ImageGrab

try:
    import pygetwindow as gw
except ImportError:
    gw = None

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.05
except ImportError:
    pyautogui = None

try:
    import psutil
except ImportError:
    psutil = None

log = logging.getLogger("ultron.desktop")

DESKTOP_DIR = Path.home() / "Desktop"
SCREENSHOTS_DIR = Path(__file__).parent / "data" / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

# Common Windows application aliases to executables / launch commands
APP_ALIASES = {
    # Text & Office
    "notepad": "notepad.exe",
    "word": "winword.exe",
    "ms word": "winword.exe",
    "microsoft word": "winword.exe",
    "wordpad": "write.exe",
    "excel": "excel.exe",
    "ms excel": "excel.exe",
    "microsoft excel": "excel.exe",
    "powerpoint": "powerpnt.exe",
    "ppt": "powerpnt.exe",
    "ms powerpoint": "powerpnt.exe",
    "microsoft powerpoint": "powerpnt.exe",
    "outlook": "outlook.exe",
    "onenote": "onenote.exe",
    
    # Graphics & Media
    "paint": "mspaint.exe",
    "ms paint": "mspaint.exe",
    "mspaint": "mspaint.exe",
    "microsoft paint": "mspaint.exe",
    "spotify": "spotify.exe",
    "vlc": "vlc.exe",
    "photos": "start ms-photos:",
    "camera": "start microsoft.windows.camera:",
    
    # Browsers
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "firefox": "firefox.exe",
    "edge": "msedge.exe",
    "msedge": "msedge.exe",
    "microsoft edge": "msedge.exe",
    "brave": "brave.exe",
    
    # Development & System
    "terminal": "wt.exe",
    "windows terminal": "wt.exe",
    "cmd": "cmd.exe",
    "command prompt": "cmd.exe",
    "powershell": "powershell.exe",
    "explorer": "explorer.exe",
    "file explorer": "explorer.exe",
    "files": "explorer.exe",
    "vscode": "code.cmd",
    "vs code": "code.cmd",
    "code": "code.cmd",
    "visual studio code": "code.cmd",
    "taskmgr": "taskmgr.exe",
    "task manager": "taskmgr.exe",
    "calc": "calc.exe",
    "calculator": "calc.exe",
    "settings": "start ms-settings:",
    "control panel": "control.exe",
    "store": "start ms-windows-store:",
    "discord": "discord.exe",
    "telegram": "telegram.exe",
    "steam": "steam.exe",
}

# Standard installation paths for Office and other Windows software
KNOWN_EXE_PATHS = [
    r"C:\Program Files\Microsoft Office\root\Office16",
    r"C:\Program Files (x86)\Microsoft Office\root\Office16",
    r"C:\Program Files\Microsoft Office\Office16",
    r"C:\Program Files (x86)\Microsoft Office\Office16",
    r"C:\Program Files\Microsoft Office\Office15",
    r"C:\Program Files (x86)\Microsoft Office\Office15",
    r"C:\Program Files\Microsoft Office\Office14",
    r"C:\Program Files (x86)\Microsoft Office\Office14",
    os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WindowsApps"),
    os.path.expandvars(r"%LOCALAPPDATA%\Programs"),
]


def capture_screenshot(filename: Optional[str] = None) -> Dict[str, Any]:
    """Capture a full desktop screenshot and save to disk."""
    try:
        if filename is None:
            filename = f"screen_{int(time.time())}.png"
        filepath = SCREENSHOTS_DIR / filename
        
        img = None
        # Attempt 1: Standard ImageGrab
        try:
            img = ImageGrab.grab()
        except Exception:
            pass

        # Attempt 2: ImageGrab with all_screens
        if img is None:
            try:
                img = ImageGrab.grab(all_screens=True)
            except Exception:
                pass

        # Attempt 3: PyAutoGUI screenshot
        if img is None and pyautogui:
            try:
                img = pyautogui.screenshot()
            except Exception:
                pass
                
        if img:
            img.save(str(filepath), "PNG")
            return {
                "success": True,
                "path": str(filepath),
                "width": img.width,
                "height": img.height,
                "message": f"Screenshot captured: {filepath.name}"
            }
        else:
            return {"success": False, "error": "No display available to capture", "message": "Screenshot failed"}
    except Exception as e:
        log.error(f"Failed to capture screenshot: {e}")
        return {"success": False, "error": str(e), "message": f"Screenshot failed: {e}"}


def get_foreground_window() -> Dict[str, Any]:
    """Get details of the currently focused window on Windows."""
    try:
        if gw:
            active = gw.getActiveWindow()
            if active and active.title.strip():
                return {
                    "title": active.title.strip(),
                    "left": active.left,
                    "top": active.top,
                    "width": active.width,
                    "height": active.height,
                    "is_maximized": active.isMaximized,
                    "is_active": True
                }
    except Exception as e:
        log.debug(f"get_foreground_window error: {e}")

    # Fallback using PowerShell if pygetwindow fails
    try:
        ps_cmd = '(Get-Process | Where-Object {$_.MainWindowHandle -ne 0 -and $_.MainWindowTitle -ne ""} | Select-Object -First 1 ProcessName, MainWindowTitle) | ConvertTo-Json'
        res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, timeout=2)
        if res.returncode == 0 and res.stdout.strip():
            import json
            data = json.loads(res.stdout)
            return {
                "title": data.get("MainWindowTitle", "Unknown"),
                "process": data.get("ProcessName", ""),
                "is_active": True
            }
    except Exception:
        pass

    return {"title": "Desktop / Unknown", "is_active": False}


def list_active_windows() -> List[Dict[str, Any]]:
    """List all open visible application windows."""
    windows = []
    try:
        if gw:
            for w in gw.getAllWindows():
                if w.title and w.title.strip() and w.visible and w.width > 50 and w.height > 50:
                    windows.append({
                        "title": w.title.strip(),
                        "left": w.left,
                        "top": w.top,
                        "width": w.width,
                        "height": w.height,
                        "is_active": w.isActive
                    })
    except Exception as e:
        log.debug(f"list_active_windows error: {e}")
        
    if not windows:
        # PowerShell fallback
        try:
            ps_cmd = 'Get-Process | Where-Object {$_.MainWindowHandle -ne 0 -and $_.MainWindowTitle -ne ""} | Select-Object ProcessName, MainWindowTitle | ConvertTo-Json'
            res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, timeout=3)
            if res.returncode == 0 and res.stdout.strip():
                import json
                data = json.loads(res.stdout)
                if isinstance(data, dict):
                    data = [data]
                for item in data:
                    windows.append({
                        "title": item.get("MainWindowTitle", ""),
                        "process": item.get("ProcessName", ""),
                        "is_active": False
                    })
        except Exception:
            pass
            
    return windows


def focus_window(title_keyword: str) -> Dict[str, Any]:
    """Bring a window matching a keyword to the foreground."""
    keyword = title_keyword.lower().strip()
    try:
        if gw:
            matches = gw.getWindowsWithTitle(title_keyword)
            if not matches:
                # Fuzzy search
                all_wins = gw.getAllWindows()
                matches = [w for w in all_wins if keyword in w.title.lower()]
            if matches:
                win = matches[0]
                if win.isMinimized:
                    win.restore()
                win.activate()
                return {"success": True, "message": f"Focused window: {win.title}"}
    except Exception as e:
        log.error(f"Failed to focus window: {e}")

    return {"success": False, "message": f"Could not find an open window matching '{title_keyword}'"}


def open_app(app_name: str) -> Dict[str, Any]:
    """Launch one or multiple Windows applications by alias, executable, URI, or Start search."""
    import re
    raw_name = app_name.lower().strip()
    
    # Remove conversational prefixes
    for pfx in ["can you open ", "please open ", "open up ", "open ", "launch ", "start ", "run "]:
        if raw_name.startswith(pfx):
            raw_name = raw_name[len(pfx):].strip()
            break

    # Split multiple applications requested (separated by 'and', '&', or ',')
    raw_list = [a.strip() for a in re.split(r'\s+and\s+|\s*,\s*|\s*&\s*', raw_name) if a.strip()]
    if not raw_list:
        raw_list = [raw_name]

    opened_messages = []
    
    for raw_item in raw_list:
        # Strip all punctuation, dots, quotes from speech recognition (e.g. "ms. paint." -> "ms paint")
        single_app = re.sub(r'[^\w\s-]', '', raw_item).strip().lower()
        single_app = re.sub(r'\s+', ' ', single_app)
        if not single_app:
            continue

        target = APP_ALIASES.get(single_app, single_app)
        log.info(f"Launching app '{single_app}' -> target: '{target}'")

        # 1. Direct URI launch (e.g. start ms-settings: or start ms-paint:)
        if target.startswith("start "):
            try:
                subprocess.Popen(target, shell=True)
                opened_messages.append(single_app)
                continue
            except Exception as e:
                log.warning(f"URI launch failed: {e}")

        # Check for YouTube or web addresses
        if single_app in ["youtube", "yt", "open youtube", "open yt"] or "youtube" in single_app:
            import webbrowser
            webbrowser.open("https://youtube.com")
            opened_messages.append("YouTube")
            continue

        if target.startswith("http://") or target.startswith("https://"):
            import webbrowser
            webbrowser.open(target)
            opened_messages.append(single_app)
            continue

        # 2. Check for Paint specifically
        if single_app in ["paint", "ms paint", "mspaint", "microsoft paint"]:
            try:
                subprocess.Popen('start "" "mspaint.exe"', shell=True)
                opened_messages.append("MS Paint")
                continue
            except Exception:
                try:
                    subprocess.Popen('start ms-paint:', shell=True)
                    opened_messages.append("MS Paint")
                    continue
                except Exception:
                    pass

        # 3. Check for Word specifically
        if single_app in ["word", "ms word", "microsoft word"]:
            word_launched = False
            for cand in ["winword.exe", r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE", r"C:\Program Files (x86)\Microsoft Office\root\Office16\WINWORD.EXE"]:
                if shutil.which(cand) or os.path.exists(cand):
                    subprocess.Popen(f'start "" "{cand}"', shell=True)
                    opened_messages.append("Microsoft Word")
                    word_launched = True
                    break
            if not word_launched:
                # Fallback to WordPad or Start Search
                subprocess.Popen('start "" "write.exe"', shell=True)
                opened_messages.append("Wordpad")
            continue

        # 4. Check if target executable is in PATH or KNOWN_EXE_PATHS
        exe_name = target if target.endswith(".exe") or target.endswith(".cmd") else f"{target}.exe"
        exe_path = shutil.which(exe_name) or shutil.which(target)
        
        if not exe_path:
            for folder in KNOWN_EXE_PATHS:
                candidate = os.path.join(folder, exe_name)
                if os.path.exists(candidate):
                    exe_path = candidate
                    break

        if exe_path:
            try:
                subprocess.Popen(f'start "" "{exe_path}"', shell=True)
                opened_messages.append(single_app)
                continue
            except Exception as e:
                log.warning(f"Direct exe launch failed: {e}")

        # 5. Try standard Windows 'start <target>'
        try:
            subprocess.Popen(f'start "" "{target}"', shell=True)
            opened_messages.append(single_app)
            continue
        except Exception:
            pass

        # 6. Fallback: Windows Start Menu search automation
        if pyautogui:
            try:
                pyautogui.press('win')
                time.sleep(0.3)
                pyautogui.write(single_app)
                time.sleep(0.4)
                pyautogui.press('enter')
                opened_messages.append(single_app)
            except Exception as e:
                log.error(f"Start Menu automation failed: {e}")

    if opened_messages:
        return {"success": True, "message": f"Opened {', '.join(opened_messages)}."}
    return {"success": False, "message": f"Could not find or open {app_name}."}


def close_app(app_name: str) -> Dict[str, Any]:
    """Terminate an application by process name or window title."""
    if not psutil:
        return {"success": False, "message": "psutil not installed"}
        
    query = app_name.lower().strip()
    killed = []
    
    # Remove .exe if given
    if query.endswith(".exe"):
        query = query[:-4]
        
    try:
        for proc in psutil.process_iter(['pid', 'name']):
            p_name = proc.info.get('name', '').lower()
            if query in p_name:
                try:
                    proc.kill()
                    killed.append(proc.info.get('name'))
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
                    
        if killed:
            unique_killed = list(set(killed))
            return {"success": True, "message": f"Closed {', '.join(unique_killed)}."}
        else:
            return {"success": False, "message": f"No running application found matching '{app_name}'."}
    except Exception as e:
        return {"success": False, "error": str(e), "message": f"Error closing {app_name}: {e}"}


def type_text(text: str, interval: float = 0.02) -> Dict[str, Any]:
    """Simulate keyboard typing on the active window."""
    if not pyautogui:
        return {"success": False, "message": "pyautogui not available"}
    try:
        # Use clipboard for complex unicode characters or fast typing
        import pyperclip
        pyperclip.copy(text)
        pyautogui.hotkey('ctrl', 'v')
        return {"success": True, "message": f"Typed text ({len(text)} characters)."}
    except Exception as e:
        # Fallback to direct typewrite
        try:
            pyautogui.typewrite(text, interval=interval)
            return {"success": True, "message": f"Typed text directly."}
        except Exception as e2:
            return {"success": False, "error": str(e2), "message": f"Typing failed: {e2}"}


def press_hotkey(*keys: str) -> Dict[str, Any]:
    """Press a combination of keys (e.g. 'ctrl', 'c' or 'alt', 'tab')."""
    if not pyautogui:
        return {"success": False, "message": "pyautogui not available"}
    try:
        pyautogui.hotkey(*keys)
        return {"success": True, "message": f"Pressed hotkey: {'+'.join(keys)}"}
    except Exception as e:
        return {"success": False, "error": str(e), "message": f"Hotkey failed: {e}"}


def click_at(x: int, y: int, clicks: int = 1) -> Dict[str, Any]:
    """Click at screen coordinates (x, y)."""
    if not pyautogui:
        return {"success": False, "message": "pyautogui not available"}
    try:
        pyautogui.click(x=x, y=y, clicks=clicks)
        return {"success": True, "message": f"Clicked at ({x}, {y})"}
    except Exception as e:
        return {"success": False, "error": str(e), "message": f"Click failed: {e}"}


def open_folder(folder_path: str = "") -> Dict[str, Any]:
    """Open a folder in Windows Explorer."""
    path = folder_path.strip() or str(DESKTOP_DIR)
    resolved = Path(path).resolve()
    if resolved.exists():
        try:
            os.startfile(str(resolved))
            return {"success": True, "message": f"Opened folder {resolved.name}."}
        except Exception as e:
            return {"success": False, "error": str(e), "message": f"Failed to open folder: {e}"}
    return {"success": False, "message": f"Path '{folder_path}' does not exist."}


def list_desktop_files() -> List[Dict[str, Any]]:
    """List files and folders currently on the user's Desktop."""
    items = []
    try:
        if DESKTOP_DIR.exists():
            for entry in DESKTOP_DIR.iterdir():
                if not entry.name.startswith("."):
                    items.append({
                        "name": entry.name,
                        "is_dir": entry.is_dir(),
                        "size": entry.stat().st_size if entry.is_file() else 0,
                        "modified": entry.stat().st_mtime
                    })
    except Exception as e:
        log.error(f"Error listing desktop: {e}")
    return items
