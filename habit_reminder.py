"""
habit_reminder.py — ULTRON Physical Wellbeing & Hydration Matrix.

Capabilities:
- Schedule health reminders (Hydration, Posture check, 20-20-20 Eye break)
"""

import logging
from typing import Dict, Any

import reminder_engine

log = logging.getLogger("ultron.habits")


def schedule_hydration_alert(minutes: int = 30) -> Dict[str, Any]:
    """Set a hydration voice reminder."""
    reminder_engine.set_reminder(f"timer for {minutes} minutes for Hydration check. Drink a glass of water to optimize your bio-metrics")
    return {
        "success": True,
        "message": f"Hydration protocol active. I will remind you in {minutes} minutes, sir."
    }


def schedule_posture_alert(minutes: int = 45) -> Dict[str, Any]:
    """Set a posture and eye break reminder."""
    reminder_engine.set_reminder(f"timer for {minutes} minutes for Posture check and 20 second eye rest")
    return {
        "success": True,
        "message": f"Posture and eye rest protocol set for {minutes} minutes, sir."
    }
