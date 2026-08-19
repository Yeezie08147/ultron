"""
display_controller.py — ULTRON Display & Screen Brightness Matrix.

Capabilities:
- Adjust screen brightness via Windows WmiMonitorBrightnessMethods / PowerShell
"""

import re
import logging
import subprocess
from typing import Dict, Any

log = logging.getLogger("ultron.display")


def set_brightness(level: int = 70) -> Dict[str, Any]:
    """Set monitor brightness percentage (0-100)."""
    target_lvl = max(0, min(100, level))
    try:
        cmd = f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1, {target_lvl})"
        subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, timeout=4)
        return {
            "success": True,
            "level": target_lvl,
            "message": f"Display brightness adjusted to {target_lvl} percent, sir."
        }
    except Exception as e:
        log.warning(f"Brightness adjust failed: {e}")
        return {"success": False, "message": f"Brightness adjustment not supported on this monitor, sir."}
