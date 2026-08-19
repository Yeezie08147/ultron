"""
activity_tracker.py — ULTRON Real-Time Activity & Screen Time Telemetry.

Capabilities:
- Real-time background daemon tracking active foreground windows
- App usage statistics (minutes spent in VS Code, Chrome, Terminal, etc.)
- Productivity analysis & daily work breakdown
"""

import time
import logging
import threading
from collections import defaultdict
from typing import Dict, Any, List

import desktop_control

log = logging.getLogger("ultron.tracker")

_app_durations: Dict[str, float] = defaultdict(float)
_last_check_time = time.time()
_last_app = "Desktop"
_tracker_active = False
_tracker_thread = None


def _clean_app_title(title: str) -> str:
    t = title.lower()
    if "visual studio code" in t or "vscode" in t or ".ts" in t or ".py" in t:
        return "VS Code"
    elif "chrome" in t:
        return "Google Chrome"
    elif "edge" in t:
        return "Microsoft Edge"
    elif "powershell" in t or "terminal" in t or "cmd" in t:
        return "Terminal"
    elif "spotify" in t:
        return "Spotify"
    elif "discord" in t:
        return "Discord"
    elif "paint" in t:
        return "Paint"
    elif "word" in t:
        return "Word"
    elif not title.strip():
        return "Desktop"
    return title[:20].strip()


def _tracking_loop():
    global _last_check_time, _last_app, _tracker_active
    _last_check_time = time.time()
    
    while _tracker_active:
        time.sleep(2)
        now = time.time()
        elapsed = now - _last_check_time
        _last_check_time = now
        
        try:
            win = desktop_control.get_foreground_window()
            raw_title = win.get("title", "") if win else ""
            app = _clean_app_title(raw_title)
            _app_durations[app] += elapsed
        except Exception:
            pass


def start_activity_tracker():
    global _tracker_active, _tracker_thread
    if not _tracker_active:
        _tracker_active = True
        _tracker_thread = threading.Thread(target=_tracking_loop, daemon=True)
        _tracker_thread.start()
        log.info("Activity Telemetry Tracker started.")


def get_activity_report() -> Dict[str, Any]:
    """Generate a spoken summary of screen time and top applications."""
    if not _app_durations:
        return {
            "success": True,
            "message": "Activity telemetry is currently calibrating, sir. Check back in a few minutes."
        }

    sorted_apps = sorted(_app_durations.items(), key=lambda x: x[1], reverse=True)
    total_seconds = sum(_app_durations.values())
    total_mins = int(total_seconds // 60)
    
    top_entries = []
    for app, secs in sorted_apps[:3]:
        mins = int(secs // 60)
        top_entries.append(f"{app}: {mins} mins" if mins > 0 else f"{app}: {int(secs)}s")

    breakdown_str = ", ".join(top_entries)
    msg = f"Screen telemetry: {total_mins} total minutes recorded. Top allocations: {breakdown_str}."
    
    return {
        "success": True,
        "total_minutes": total_mins,
        "top_apps": top_entries,
        "message": msg
    }
