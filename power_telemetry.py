"""
power_telemetry.py — ULTRON Battery & Power Matrix.

Capabilities:
- Real-time battery percentage, charging status, and power health telemetry
"""

import logging
from typing import Dict, Any

log = logging.getLogger("ultron.power")


def get_power_status() -> Dict[str, Any]:
    """Fetch live battery and charging status."""
    try:
        import psutil
        battery = psutil.sensors_battery()
        if battery is None:
            return {
                "success": True,
                "message": "Workstation is running on direct AC power with no battery attached, sir."
            }

        percent = int(battery.percent)
        charging = battery.power_plugged
        charging_str = "charging" if charging else "discharging on battery"

        secs_left = battery.secsleft
        if secs_left > 0 and secs_left != psutil.BATTERY_TIME_UNLIMITED:
            hours = int(secs_left // 3600)
            mins = int((secs_left % 3600) // 60)
            time_str = f" Estimated {hours} hours and {mins} minutes remaining."
        else:
            time_str = ""

        msg = f"Power status: Battery is at {percent}%, currently {charging_str}.{time_str}"
        return {
            "success": True,
            "percent": percent,
            "charging": charging,
            "message": msg
        }
    except Exception as e:
        log.warning(f"Battery check failed: {e}")
        return {"success": False, "message": "Unable to acquire power telemetry, sir."}
