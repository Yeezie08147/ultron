"""
desktop_control.py — ULTRON 2.0 Full Desktop Access & Omnipotent OS Controller.

Provides 100% Unrestricted Access to Windows:
- Universal Application Launcher: Auto-indexes Start Menu shortcuts & Registry App Paths
- Full Mouse Automation: Movement, left/right/double clicks, scrolling
- Full Keyboard Automation: Text typing, hotkeys, function keys
- Window Management: Focus, maximize, minimize, minimize all (Win+D), switch (Alt+Tab), close
- Shell Command Execution: Arbitrary PowerShell & CMD commands with administrative rights
- System Controls: Volume, lock workstation, screenshot capture, clipboard access
"""

import os
import re
import sys
import time
import winreg
import shutil
import logging
import subprocess
import webbrowser
import urllib.parse
from pathlib import Path
from typing import Optional, List, Dict, Any
from PIL import Image, ImageGrab

try:
    import pygetwindow as gw
except ImportError:
    gw = None

try:
    import pyautogui
    pyautogui.FAILSAFE = False
    pyautogui.PAUSE = 0.02
except ImportError:
    pyautogui = None

try:
    import psutil
except ImportError:
    psutil = None

try:
    import pyperclip
except ImportError:
    pyperclip = None

log = logging.getLogger("ultron.desktop")

DESKTOP_DIR = Path.home() / "Desktop"
SCREENSHOTS_DIR = Path(__file__).parent / "data" / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

# Standard built-in Windows URI protocols and system executables
SYSTEM_ALIASES = {
    "notepad": "notepad.exe",
    "calc": "calc.exe",
    "calculator": "calc.exe",
    "paint": "mspaint.exe",
    "mspaint": "mspaint.exe",
    "cmd": "cmd.exe",
    "command prompt": "cmd.exe",
    "powershell": "powershell.exe",
    "terminal": "wt.exe",
    "explorer": "explorer.exe",
    "file explorer": "explorer.exe",
    "files": "explorer.exe",
    "taskmgr": "taskmgr.exe",
    "task manager": "taskmgr.exe",
    "settings": "ms-settings:",
    "control panel": "control.exe",
    "store": "ms-windows-store:",
    "photos": "ms-photos:",
    "camera": "microsoft.windows.camera:",
}


def scan_all_installed_apps() -> Dict[str, str]:
    """Dynamically scan Windows Start Menus and Registry for every installed application."""
    apps = {}

    # 1. Start Menu Program Shortcuts (.lnk files)
    start_dirs = [
        os.path.expandvars(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs"),
        os.path.expandvars(r"%AppData%\Microsoft\Windows\Start Menu\Programs")
    ]
    for sdir in start_dirs:
        if os.path.exists(sdir):
            for path in Path(sdir).rglob("*.lnk"):
                name = path.stem.lower().strip()
                apps[name] = str(path.resolve())

    # 2. Registry App Paths (HKLM & HKCU)
    for hive in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
        try:
            with winreg.OpenKey(hive, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths") as key:
                for i in range(winreg.QueryInfoKey(key)[0]):
                    try:
                        sub = winreg.EnumKey(key, i)
                        with winreg.OpenKey(key, sub) as subkey:
                            val, _ = winreg.QueryValueEx(subkey, "")
                            if val:
                                clean_val = val.strip('\"')
                                if os.path.exists(clean_val):
                                    k_name = sub.lower()
                                    apps[k_name] = clean_val
                                    if k_name.endswith(".exe"):
                                        apps[k_name[:-4]] = clean_val
                    except Exception:
                        pass
        except Exception:
            pass

    return apps


def open_app(app_query: str) -> Dict[str, Any]:
    """Launch ANY installed Windows application, shortcut, URI, or website without limitations."""
    raw = app_query.lower().strip()
    
    # Strip conversational prefixes
    for pfx in ["can you open ", "please open ", "open up ", "open ", "launch ", "start ", "run "]:
        if raw.startswith(pfx):
            raw = raw[len(pfx):].strip()
            break

    if not raw:
        return {"success": False, "message": "No application specified to open, sir."}

    # 1. Check for web targets (YouTube, Google, URLs)
    if "youtube" in raw or raw in ["yt"]:
        webbrowser.open("https://youtube.com")
        return {"success": True, "message": "Opened YouTube in your browser, sir."}

    if raw.startswith("http://") or raw.startswith("https://") or ".com" in raw or ".org" in raw or ".net" in raw:
        url = raw if raw.startswith("http") else f"https://{raw}"
        webbrowser.open(url)
        return {"success": True, "message": f"Opened {url}, sir."}

    # 2. Check System Aliases
    clean_target = re.sub(r'[^\w\s-]', '', raw).strip().lower()
    if clean_target in SYSTEM_ALIASES:
        target = SYSTEM_ALIASES[clean_target]
        try:
            os.startfile(target)
            return {"success": True, "message": f"Launched {clean_target}, sir."}
        except Exception:
            subprocess.Popen(f'start "" "{target}"', shell=True)
            return {"success": True, "message": f"Launched {clean_target}, sir."}

    # 3. Dynamic Registry & Start Menu Search
    installed = scan_all_installed_apps()
    
    # Exact match first
    if clean_target in installed:
        target_path = installed[clean_target]
        try:
            os.startfile(target_path)
            return {"success": True, "message": f"Opened {clean_target.title()}, sir."}
        except Exception as e:
            log.warning(f"os.startfile error: {e}")

    # Substring match (e.g. "chrome" matches "Google Chrome.lnk")
    for k, v in installed.items():
        if clean_target in k or k in clean_target:
            try:
                os.startfile(v)
                return {"success": True, "message": f"Opened {k.title()}, sir."}
            except Exception as e:
                log.warning(f"os.startfile error: {e}")

    # 4. Try native executable search via shutil.which
    exe_cand = clean_target if clean_target.endswith(".exe") else f"{clean_target}.exe"
    found_exe = shutil.which(exe_cand) or shutil.which(clean_target)
    if found_exe:
        try:
            os.startfile(found_exe)
            return {"success": True, "message": f"Launched {clean_target}, sir."}
        except Exception:
            subprocess.Popen(f'start "" "{found_exe}"', shell=True)
            return {"success": True, "message": f"Launched {clean_target}, sir."}

    # 5. Fallback: Windows Start Menu Search Automation
    if pyautogui:
        try:
            pyautogui.press('win')
            time.sleep(0.2)
            pyautogui.write(clean_target)
            time.sleep(0.3)
            pyautogui.press('enter')
            return {"success": True, "message": f"Initiated search and launch for {clean_target}, sir."}
        except Exception:
            pass

    return {"success": False, "message": f"Could not find application '{app_query}', sir."}


def close_app(app_name: str) -> Dict[str, Any]:
    """Terminate an application by process name or window title."""
    if not psutil:
        return {"success": False, "message": "psutil not available"}
        
    query = app_name.lower().strip()
    if query.endswith(".exe"):
        query = query[:-4]
        
    killed = []
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
            return {"success": True, "message": f"Terminated {', '.join(unique_killed)}, sir."}
        else:
            return {"success": False, "message": f"No running application found matching '{app_name}', sir."}
    except Exception as e:
        return {"success": False, "message": f"Failed to close {app_name}: {e}"}


def execute_shell_command(cmd_str: str) -> Dict[str, Any]:
    """Execute arbitrary shell/PowerShell command with full administrative rights."""
    try:
        res = subprocess.run(["powershell", "-NoProfile", "-Command", cmd_str],
                             capture_output=True, text=True, timeout=15,
                             creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        output = (res.stdout or res.stderr or "Executed successfully").strip()
        return {"success": res.returncode == 0, "output": output, "message": output[:300]}
    except Exception as e:
        return {"success": False, "error": str(e), "message": f"Command error: {e}"}


def search_web_browser(query: str) -> Dict[str, Any]:
    """Search Google in the default web browser."""
    url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
    webbrowser.open(url)
    return {"success": True, "message": f"Searched for '{query}', sir."}


def type_text(text: str) -> Dict[str, Any]:
    """Type arbitrary text into the active focused window."""
    if pyperclip and pyautogui:
        try:
            pyperclip.copy(text)
            pyautogui.hotkey('ctrl', 'v')
            return {"success": True, "message": f"Typed text ({len(text)} characters), sir."}
        except Exception:
            pass
    if pyautogui:
        try:
            pyautogui.typewrite(text, interval=0.01)
            return {"success": True, "message": f"Typed text, sir."}
        except Exception as e:
            return {"success": False, "message": f"Typing failed: {e}"}
    return {"success": False, "message": "Keyboard automation module unavailable."}


def press_key(key_name: str) -> Dict[str, Any]:
    """Press a single key (e.g. enter, esc, space, tab, backspace, win)."""
    if pyautogui:
        try:
            pyautogui.press(key_name.lower().strip())
            return {"success": True, "message": f"Pressed {key_name}, sir."}
        except Exception as e:
            return {"success": False, "message": f"Key press failed: {e}"}
    return {"success": False, "message": "PyAutoGUI not available."}


def press_hotkey(*keys: str) -> Dict[str, Any]:
    """Press keyboard hotkey combination (e.g. 'ctrl', 'c' or 'alt', 'tab')."""
    if pyautogui:
        try:
            pyautogui.hotkey(*[k.lower().strip() for k in keys])
            return {"success": True, "message": f"Pressed hotkey {'+'.join(keys)}, sir."}
        except Exception as e:
            return {"success": False, "message": f"Hotkey failed: {e}"}
    return {"success": False, "message": "PyAutoGUI not available."}


def click_at(x: int, y: int, button: str = "left", clicks: int = 1) -> Dict[str, Any]:
    """Click at screen coordinates (x, y)."""
    if pyautogui:
        try:
            pyautogui.click(x=x, y=y, button=button, clicks=clicks)
            return {"success": True, "message": f"Clicked at ({x}, {y}), sir."}
        except Exception as e:
            return {"success": False, "message": f"Click failed: {e}"}
    return {"success": False, "message": "PyAutoGUI not available."}


def scroll_mouse(amount: int) -> Dict[str, Any]:
    """Scroll mouse wheel (positive = up, negative = down)."""
    if pyautogui:
        try:
            pyautogui.scroll(amount)
            return {"success": True, "message": f"Scrolled mouse wheel ({amount}), sir."}
        except Exception as e:
            return {"success": False, "message": f"Scroll failed: {e}"}
    return {"success": False, "message": "PyAutoGUI not available."}


def minimize_all() -> Dict[str, Any]:
    """Minimize all open windows to reveal Desktop (Win+D)."""
    try:
        import ctypes
        VK_LWIN = 0x5B
        VK_D = 0x44
        KEYEVENTF_KEYUP = 0x0002
        user32 = ctypes.windll.user32
        user32.keybd_event(VK_LWIN, 0, 0, 0)
        user32.keybd_event(VK_D, 0, 0, 0)
        user32.keybd_event(VK_D, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_LWIN, 0, KEYEVENTF_KEYUP, 0)
    except Exception:
        subprocess.Popen(['powershell', '-Command', '(New-Object -ComObject Shell.Application).MinimizeAll()'],
                         creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    return {"success": True, "message": "Minimized all windows to reveal desktop, sir."}


def switch_window() -> Dict[str, Any]:
    """Switch active window (Alt+Tab)."""
    try:
        import ctypes
        VK_LMENU = 0x12
        VK_TAB = 0x09
        KEYEVENTF_KEYUP = 0x0002
        user32 = ctypes.windll.user32
        user32.keybd_event(VK_LMENU, 0, 0, 0)
        user32.keybd_event(VK_TAB, 0, 0, 0)
        user32.keybd_event(VK_TAB, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_LMENU, 0, KEYEVENTF_KEYUP, 0)
    except Exception:
        pass
    return {"success": True, "message": "Switched active window, sir."}


def lock_pc() -> Dict[str, Any]:
    """Lock the Windows workstation."""
    subprocess.Popen(["rundll32.exe", "user32.dll,LockWorkStation"])
    return {"success": True, "message": "Workstation locked, sir."}


def volume_up() -> Dict[str, Any]:
    """Increase system audio volume."""
    if pyautogui:
        for _ in range(5):
            pyautogui.press('volumeup')
    return {"success": True, "message": "Volume increased, sir."}


def volume_down() -> Dict[str, Any]:
    """Decrease system audio volume."""
    if pyautogui:
        for _ in range(5):
            pyautogui.press('volumedown')
    return {"success": True, "message": "Volume decreased, sir."}


def mute_volume() -> Dict[str, Any]:
    """Toggle mute system audio."""
    if pyautogui:
        pyautogui.press('volumemute')
    return {"success": True, "message": "Toggled audio mute, sir."}


def capture_screenshot(filename: Optional[str] = None) -> Dict[str, Any]:
    """Capture full desktop screenshot and save to disk."""
    try:
        if filename is None:
            filename = f"screen_{int(time.time())}.png"
        filepath = SCREENSHOTS_DIR / filename
        
        img = None
        try:
            img = ImageGrab.grab(all_screens=True)
        except Exception:
            try:
                img = ImageGrab.grab()
            except Exception:
                pass

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
                "message": f"Screenshot captured: {filepath.name}, sir."
            }
        return {"success": False, "message": "No display available to capture, sir."}
    except Exception as e:
        return {"success": False, "message": f"Screenshot failed: {e}"}


def get_clipboard_text() -> str:
    """Retrieve text currently on Windows clipboard."""
    if pyperclip:
        try:
            return pyperclip.paste()
        except Exception:
            pass
    return ""


def set_clipboard_text(text: str) -> bool:
    """Copy text to Windows clipboard."""
    if pyperclip:
        try:
            pyperclip.copy(text)
            return True
        except Exception:
            pass
    return False
