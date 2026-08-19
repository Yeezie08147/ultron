import os
import sys
import ctypes
import threading
import uvicorn
import time
import requests
import pystray
from PIL import Image, ImageDraw

# ---------------------------------------------------------------------------
# Stealth Mode: Hide Windows Console Window completely
# ---------------------------------------------------------------------------
if sys.platform == "win32":
    try:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)  # 0 = SW_HIDE
    except Exception:
        pass

try:
    from server import app
except ImportError as e:
    sys.exit(1)

import webview

ultron_window = None


def run_server():
    uvicorn.run(app, host="127.0.0.1", port=8340, log_level="error")


def toggle_window(icon=None, item=None):
    global ultron_window
    if ultron_window:
        if getattr(ultron_window, 'is_hidden', False):
            show_window()
        else:
            hide_window()


def show_window():
    global ultron_window
    if ultron_window:
        try:
            ultron_window.show()
            ultron_window.restore()
            ultron_window.is_hidden = False
        except Exception:
            pass


def hide_window():
    global ultron_window
    if ultron_window:
        try:
            ultron_window.hide()
            ultron_window.is_hidden = True
        except Exception:
            pass


def on_quit(icon=None, item=None):
    if icon:
        icon.stop()
    if ultron_window:
        ultron_window.destroy()
    sys.exit(0)


def setup_tray():
    icon_path = os.path.join(os.path.dirname(__file__), "ultron.ico")
    if os.path.exists(icon_path):
        try:
            img = Image.open(icon_path)
        except Exception:
            img = Image.new('RGB', (64, 64), (255, 120, 0))
    else:
        img = Image.new('RGB', (64, 64), (255, 120, 0))
        
    icon = pystray.Icon("ULTRON", img, "ULTRON System")
    icon.menu = pystray.Menu(
        pystray.MenuItem("Toggle ULTRON", toggle_window, default=True),
        pystray.MenuItem("Show ULTRON", show_window),
        pystray.MenuItem("Hide to Tray", hide_window),
        pystray.MenuItem("Quit", on_quit)
    )
    icon.run()


if __name__ == '__main__':
    # 1. Start backend server
    threading.Thread(target=run_server, daemon=True).start()

    # 2. Start system tray
    threading.Thread(target=setup_tray, daemon=True).start()

    # 3. Start Wake Word Listener
    try:
        from wake_word import start_wake_word_listener
        threading.Thread(target=start_wake_word_listener, args=(show_window,), daemon=True).start()
    except Exception as e:
        pass

    # 4. Start Vision Loop if present
    try:
        from vision import start_vision_loop
        threading.Thread(target=start_vision_loop, daemon=True).start()
    except Exception:
        pass

    # 5. Wait for server readiness
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
            fullscreen=True,
            frameless=True,
            easy_drag=False,
            background_color='#000000'
        )
        ultron_window.is_hidden = False
        webview.start(private_mode=False)
    else:
        pass
