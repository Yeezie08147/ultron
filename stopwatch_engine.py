"""
stopwatch_engine.py — ULTRON Precision Stopwatch & Timer Matrix.

Capabilities:
- Start, check, stop, and reset stopwatch with millisecond precision
"""

import time
import logging
from typing import Dict, Any

log = logging.getLogger("ultron.stopwatch")

_start_time = None
_is_running = False


def start_stopwatch() -> Dict[str, Any]:
    global _start_time, _is_running
    _start_time = time.time()
    _is_running = True
    return {"success": True, "message": "Stopwatch started, sir."}


def check_stopwatch() -> Dict[str, Any]:
    global _start_time, _is_running
    if not _is_running or _start_time is None:
        return {"success": False, "message": "Stopwatch is not currently running, sir."}

    elapsed = time.time() - _start_time
    mins = int(elapsed // 60)
    secs = int(elapsed % 60)
    ms = int((elapsed * 100) % 100)

    if mins > 0:
        msg = f"Elapsed time: {mins} minutes, {secs}.{ms:02d} seconds, sir."
    else:
        msg = f"Elapsed time: {secs}.{ms:02d} seconds, sir."

    return {"success": True, "elapsed": elapsed, "message": msg}


def stop_stopwatch() -> Dict[str, Any]:
    global _start_time, _is_running
    if not _is_running or _start_time is None:
        return {"success": False, "message": "Stopwatch is not currently running, sir."}

    elapsed = time.time() - _start_time
    _is_running = False
    _start_time = None

    mins = int(elapsed // 60)
    secs = int(elapsed % 60)
    ms = int((elapsed * 100) % 100)

    if mins > 0:
        msg = f"Stopwatch stopped at {mins} minutes and {secs}.{ms:02d} seconds, sir."
    else:
        msg = f"Stopwatch stopped at {secs}.{ms:02d} seconds, sir."

    return {"success": True, "elapsed": elapsed, "message": msg}
