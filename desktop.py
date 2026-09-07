"""
desktop.py — ULTRON 2.0 Autonomous Desktop & Stealth Background Manager.

Capabilities:
- Supports --stealth mode: Zero taskbar presence, runs silently in background on Windows boot
- Continuous voice daemon: Speaks & controls full desktop via voice commands ("Ultron ...")
- Global Hotkey: Ctrl+Alt+U toggles the HUD interface instantly
- System Tray: Complete control over visibility, voice listening, and settings
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

# ---------------------------------------------------------------------------
# Stealth Mode: Hide Windows Console Window completely
# ---------------------------------------------------------------------------
if sys.platform == "win313" or sys.platform == "win32":
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
import stealth_voice_daemon

is_stealth_mode = "--stealth" in sys.argv or "--ghost" in sys.argv or "--background" in sys.argv
ultron_window = None
tray_icon = None


def run_server():
    """Run ULTRON FastAPI/WebSocket backend."""
    uvicorn.run(app, host="127.0.0.1", port=8340, log_level="error")


def show_window():
    """Reveal ULTRON HUD and ensure immediate foreground responsiveness."""
    global ultron_window
    if ultron_window:
        try:
            ultron_window.show()
            ultron_window.restore()
            ultron_window.is_hidden = False
            if sys.platform == "win32":
                try:
                    # Find and focus window by title
                    hwnd = ctypes.windll.user32.FindWindowW(None, "ULTRON")
                    if hwnd:
                        ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                        ctypes.windll.user32.SetForegroundWindow(hwnd)
                except Exception:
                    pass
        except Exception:
            pass


def hide_window():
    """Hide ULTRON HUD completely from screen and taskbar."""
    global ultron_window
    if ultron_window:
        try:
            ultron_window.hide()
            ultron_window.is_hidden = True
        except Exception:
            pass


def toggle_window(icon=None, item=None):
    """Toggle HUD visibility."""
    global ultron_window
    if ultron_window:
        if getattr(ultron_window, 'is_hidden', False):
            show_window()
        else:
            hide_window()


def on_toggle_voice_mute(icon=None, item=None):
    """Toggle microphone mute."""
    is_muted = stealth_voice_daemon.toggle_mute_listening()
    if icon:
        icon.notify(f"ULTRON Voice Listening: {'MUTED' if is_muted else 'ACTIVE'}")


def on_quit(icon=None, item=None):
    """Cleanly exit ULTRON."""
    stealth_voice_daemon.stop_stealth_daemon()
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

    tray_icon = pystray.Icon("ULTRON", img, "ULTRON 2.0 (Stealth Voice Active)")
    tray_icon.menu = pystray.Menu(
        pystray.MenuItem("Toggle ULTRON HUD (Ctrl+Alt+U)", toggle_window, default=True),
        pystray.MenuItem("Show HUD", show_window),
        pystray.MenuItem("Hide (Stealth Mode)", hide_window),
        pystray.MenuItem("Mute Voice Listening", on_toggle_voice_mute),
        pystray.MenuItem("Quit ULTRON", on_quit)
    )
    tray_icon.run()


def setup_global_hotkey():
    """Register Ctrl+Alt+U hotkey to toggle HUD."""
    try:
        user32 = ctypes.windll.user32
        MOD_ALT = 0x0001
        MOD_CONTROL = 0x0002
        VK_U = 0x55
        HOTKEY_ID = 101

        if not user32.RegisterHotKey(None, HOTKEY_ID, MOD_CONTROL | MOD_ALT, VK_U):
            return

        msg = ctypes.wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            if msg.message == 0x0312 and msg.wParam == HOTKEY_ID:
                toggle_window()
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
    except Exception:
        pass


def hud_callback(show: bool):
    """Callback for stealth voice daemon to show/hide HUD."""
    if show:
        show_window()
    else:
        hide_window()


if __name__ == '__main__':
    # 1. Start backend server
    threading.Thread(target=run_server, daemon=True).start()

    # 2. Start system tray
    threading.Thread(target=setup_tray, daemon=True).start()

    # 3. Start Global Hotkey Listener (Ctrl+Alt+U)
    threading.Thread(target=setup_global_hotkey, daemon=True).start()

    # 4. Connect Stealth Voice Daemon
    stealth_voice_daemon.set_hud_callback(hud_callback)
    stealth_voice_daemon.start_stealth_daemon()

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
            hidden=is_stealth_mode,
            background_color='#000000'
        )
        ultron_window.is_hidden = is_stealth_mode
        webview.start(private_mode=False)
