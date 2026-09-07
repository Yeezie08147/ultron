"""
desktop.py — ULTRON Desktop Application.

Direct visual HUD application for Windows with full desktop control.
"""

import os
import sys
import time
import ctypes
import logging
import threading
import requests
import pystray
from PIL import Image
import webview

# Hide console window if launched via python.exe
if sys.platform == "win32":
    try:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)  # 0 = SW_HIDE
    except Exception:
        pass

try:
    from server import app
except ImportError:
    sys.exit(1)

import uvicorn

ultron_window = None
tray_icon = None

log = logging.getLogger("ultron.desktop")


def run_server():
    """Run ULTRON FastAPI/WebSocket backend."""
    uvicorn.run(app, host="127.0.0.1", port=8340, log_level="error")


def show_window():
    """Bring ULTRON window to foreground."""
    global ultron_window
    if ultron_window:
        try:
            ultron_window.show()
            ultron_window.restore()
        except Exception:
            pass
    if sys.platform == "win32":
        try:
            for title in ["ULTRON", "ULTRON 2.0"]:
                hwnd = ctypes.windll.user32.FindWindowW(None, title)
                if hwnd:
                    ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                    ctypes.windll.user32.BringWindowToTop(hwnd)
                    ctypes.windll.user32.SetForegroundWindow(hwnd)
                    break
        except Exception:
            pass


def hide_window():
    """Minimize ULTRON window to tray."""
    global ultron_window
    if ultron_window:
        try:
            ultron_window.hide()
        except Exception:
            pass


def toggle_window(icon=None, item=None):
    """Toggle window visibility."""
    global ultron_window
    if ultron_window:
        show_window()


def on_quit(icon=None, item=None):
    """Cleanly exit ULTRON."""
    if icon:
        icon.stop()
    if ultron_window:
        try:
            ultron_window.destroy()
        except Exception:
            pass
    sys.exit(0)


def setup_tray():
    """Setup Windows System Tray Icon."""
    global tray_icon
    icon_path = os.path.join(os.path.dirname(__file__), "ultron.ico")
    if os.path.exists(icon_path):
        try:
            img = Image.open(icon_path)
        except Exception:
            img = Image.new('RGB', (64, 64), (255, 120, 0))
    else:
        img = Image.new('RGB', (64, 64), (255, 120, 0))

    tray_icon = pystray.Icon("ULTRON", img, "ULTRON")
    tray_icon.menu = pystray.Menu(
        pystray.MenuItem("Show ULTRON", show_window, default=True),
        pystray.MenuItem("Hide to Tray", hide_window),
        pystray.MenuItem("Quit ULTRON", on_quit)
    )
    try:
        tray_icon.run_detached()
    except Exception:
        tray_icon.run()


if __name__ == '__main__':
    # Check if another instance is already running
    try:
        r = requests.get("http://127.0.0.1:8340/api/health", timeout=0.8)
        if r.status_code == 200:
            show_window()
            sys.exit(0)
    except Exception:
        pass

    # 1. Start backend server
    threading.Thread(target=run_server, daemon=True).start()

    # 2. Start system tray
    threading.Thread(target=setup_tray, daemon=True).start()

    # 3. Wait for server readiness
    server_ready = False
    for _ in range(30):
        try:
            response = requests.get("http://127.0.0.1:8340/api/health", timeout=1)
            if response.status_code == 200:
                server_ready = True
                break
        except requests.exceptions.RequestException:
            pass
        time.sleep(0.3)

    if server_ready:
        ultron_window = webview.create_window(
            'ULTRON',
            f'http://127.0.0.1:8340/?v={int(time.time())}',
            width=1360,
            height=860,
            resizable=True,
            frameless=False,
            easy_drag=False,
            background_color='#070402'
        )
        webview.start(private_mode=False)
