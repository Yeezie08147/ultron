"""
reminder_engine.py — ULTRON Timers & Reminders Engine.

Capabilities:
- Asynchronous timer scheduling & management
- Natural language duration parsing (e.g. "in 5 minutes to check the oven")
- Automatic voice announcement callback upon timer expiration
"""

import re
import time
import asyncio
import logging
from typing import List, Dict, Any, Optional, Callable

log = logging.getLogger("ultron.reminders")

# Active timers: list of {"id": str, "label": str, "target_time": float, "callback": Callable}
_timers: List[Dict[str, Any]] = []
_loop_task: Optional[asyncio.Task] = None
_notification_callback: Optional[Callable] = None


def parse_duration(text: str) -> tuple[int, str]:
    """Parse duration in seconds and task label from natural language.
    
    Examples:
    'set a timer for 5 minutes' -> (300, 'timer')
    'remind me in 10 minutes to take out the trash' -> (600, 'take out the trash')
    'timer for 30 seconds' -> (30, 'timer')
    """
    t = text.lower()
    
    seconds = 0
    # Match hours
    h_match = re.search(r'(\d+)\s*(?:hours?|hrs?)', t)
    if h_match:
        seconds += int(h_match.group(1)) * 3600
        
    # Match minutes
    m_match = re.search(r'(\d+)\s*(?:minutes?|mins?)', t)
    if m_match:
        seconds += int(m_match.group(1)) * 60
        
    # Match seconds
    s_match = re.search(r'(\d+)\s*(?:seconds?|secs?)', t)
    if s_match:
        seconds += int(s_match.group(1))

    # Extract label / reason
    label = "timer"
    to_match = re.search(r'(?:to|for)\s+(.+)$', text, flags=re.IGNORECASE)
    if to_match:
        cand = to_match.group(1).strip()
        # Strip trailing time words if matched
        cand = re.sub(r'^(?:\d+\s+(?:minutes?|seconds?|hours?|mins?|secs?)\s*(?:to\s*)?)', '', cand).strip()
        if cand:
            label = cand

    if seconds == 0:
        # Default fallback if a number was given: e.g. "timer 5" -> 5 minutes
        num_match = re.search(r'\b(\d+)\b', t)
        if num_match:
            seconds = int(num_match.group(1)) * 60

    return max(5, seconds), label


def set_reminder(text: str) -> Dict[str, Any]:
    """Schedule a new timer or reminder."""
    seconds, label = parse_duration(text)
    target_time = time.time() + seconds
    timer_id = f"timer_{int(target_time)}"
    
    _timers.append({
        "id": timer_id,
        "label": label,
        "duration": seconds,
        "target_time": target_time,
        "created_at": time.time()
    })
    
    minutes = seconds // 60
    secs = seconds % 60
    time_str = f"{minutes} minutes" if minutes > 0 else f"{secs} seconds"
    if minutes > 0 and secs > 0:
        time_str = f"{minutes} minutes and {secs} seconds"
        
    log.info(f"Timer set for {time_str}: '{label}'")
    return {
        "success": True,
        "seconds": seconds,
        "label": label,
        "message": f"Timer set for {time_str} for {label}, sir."
    }


def list_timers() -> List[Dict[str, Any]]:
    """Return all currently active timers."""
    now = time.time()
    active = []
    for t in _timers:
        remaining = max(0, int(t["target_time"] - now))
        active.append({
            "id": t["id"],
            "label": t["label"],
            "remaining_seconds": remaining
        })
    return active


def set_notification_callback(cb: Callable):
    """Set the async callback for when a timer triggers."""
    global _notification_callback
    _notification_callback = cb


async def _reminder_loop():
    """Background monitor checking timer expirations every second."""
    while True:
        try:
            now = time.time()
            expired = []
            for t in list(_timers):
                if now >= t["target_time"]:
                    expired.append(t)
                    _timers.remove(t)

            for exp in expired:
                log.info(f"Timer expired: {exp['label']}")
                if _notification_callback:
                    try:
                        msg = f"Sir, your timer for {exp['label']} has elapsed."
                        if asyncio.iscoroutinefunction(_notification_callback):
                            await _notification_callback(msg)
                        else:
                            _notification_callback(msg)
                    except Exception as e:
                        log.error(f"Timer notification callback error: {e}")
        except Exception as e:
            log.error(f"Reminder loop error: {e}")

        await asyncio.sleep(1)


def start_reminder_daemon():
    """Start the background timer monitor."""
    global _loop_task
    if _loop_task is None or _loop_task.done():
        _loop_task = asyncio.create_task(_reminder_loop())
        log.info("Reminder background daemon started.")
