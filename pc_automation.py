"""
pc_automation.py — ULTRON PC Maintenance & System Automation.

Capabilities:
- Empty Windows Recycle Bin
- Safely clean temporary junk files (%temp%)
- Lock Windows workstation
- Schedule or abort system sleep / shutdown
"""

import os
import shutil
import ctypes
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any

log = logging.getLogger("ultron.automation")


def empty_recycle_bin() -> Dict[str, Any]:
    """Empty the Windows Recycle Bin safely."""
    try:
        # PowerShell command to empty recycle bin silently
        cmd = ["powershell", "-NoProfile", "-Command", "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"]
        subprocess.run(cmd, capture_output=True, timeout=5)
        return {"success": True, "message": "Recycle bin has been purged, sir."}
    except Exception as e:
        log.error(f"Failed to empty recycle bin: {e}")
        return {"success": False, "message": f"Could not empty recycle bin: {e}"}


def clean_temp_files() -> Dict[str, Any]:
    """Safely purge junk files from %TEMP% directory."""
    temp_dir = Path(os.environ.get("TEMP", r"C:\Windows\Temp"))
    deleted_files = 0
    deleted_bytes = 0

    if not temp_dir.exists():
        return {"success": False, "message": "Temporary directory not found."}

    for item in temp_dir.glob("*"):
        try:
            if item.is_file() or item.is_symlink():
                size = item.stat().st_size
                item.unlink(missing_ok=True)
                deleted_files += 1
                deleted_bytes += size
            elif item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
                deleted_files += 1
        except Exception:
            # Skip in-use files safely
            pass

    mb = deleted_bytes / (1024 * 1024)
    log.info(f"Cleaned {deleted_files} temp items ({mb:.1f} MB)")
    return {
        "success": True,
        "files_removed": deleted_files,
        "megabytes": round(mb, 1),
        "message": f"Purged {deleted_files} temporary files freeing {mb:.1f} megabytes, sir."
    }


def lock_workstation() -> Dict[str, Any]:
    """Immediately lock the Windows desktop workstation."""
    try:
        ctypes.windll.user32.LockWorkStation()
        return {"success": True, "message": "Workstation locked, sir."}
    except Exception as e:
        log.error(f"Failed to lock workstation: {e}")
        return {"success": False, "message": "Failed to lock workstation."}


def schedule_shutdown(minutes: int = 15) -> Dict[str, Any]:
    """Schedule a system shutdown after X minutes."""
    secs = max(10, minutes * 60)
    try:
        subprocess.run(["shutdown", "/s", "/t", str(secs)], capture_output=True)
        return {"success": True, "message": f"System shutdown scheduled in {minutes} minutes, sir."}
    except Exception as e:
        return {"success": False, "message": f"Failed to schedule shutdown: {e}"}


def abort_shutdown() -> Dict[str, Any]:
    """Cancel any scheduled system shutdown."""
    try:
        subprocess.run(["shutdown", "/a"], capture_output=True)
        return {"success": True, "message": "Scheduled shutdown aborted, sir."}
    except Exception as e:
        return {"success": False, "message": f"Failed to abort shutdown: {e}"}
