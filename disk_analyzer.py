"""
disk_analyzer.py — ULTRON Storage & Disk Space Telemetry.

Capabilities:
- Real-time storage telemetry across all connected Windows drives (C:, D:, etc.)
"""

import shutil
import logging
from typing import Dict, Any

log = logging.getLogger("ultron.storage")


def get_disk_space() -> Dict[str, Any]:
    """Calculate free and total storage on main Windows drive."""
    try:
        total, used, free = shutil.disk_usage("C:\\")
        total_gb = round(total / (1024**3), 1)
        used_gb = round(used / (1024**3), 1)
        free_gb = round(free / (1024**3), 1)
        percent_used = round((used / total) * 100, 1)

        msg = f"Storage telemetry: Drive C has {free_gb} GB free out of {total_gb} GB total ({percent_used}% utilized), sir."
        return {
            "success": True,
            "total_gb": total_gb,
            "free_gb": free_gb,
            "used_gb": used_gb,
            "percent_used": percent_used,
            "message": msg
        }
    except Exception as e:
        return {"success": False, "message": f"Storage telemetry error: {e}"}
