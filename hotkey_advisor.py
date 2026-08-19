"""
hotkey_advisor.py — ULTRON Windows Hotkey & Shortcut Advisor.

Capabilities:
- Instant spoken guidance for any Windows shortcut or productivity key combination
"""

import logging
from typing import Dict, Any

log = logging.getLogger("ultron.hotkey")

HOTKEYS = {
    "snip": "Press Windows + Shift + S to open the Snipping Tool.",
    "screenshot": "Press Windows + Shift + S for snip, or Windows + PrintScreen to save directly to Pictures.",
    "lock": "Press Windows + L to immediately lock your workstation.",
    "task manager": "Press Ctrl + Shift + Escape to open Task Manager directly.",
    "emoji": "Press Windows + Period ( . ) to open the emoji and symbol matrix.",
    "clipboard history": "Press Windows + V to view your clipboard history.",
    "virtual desktop": "Press Windows + Ctrl + D to create a new desktop, or Windows + Tab to view all.",
    "minimize all": "Press Windows + D or Windows + M to minimize all windows.",
    "split screen": "Press Windows + Left or Right arrow to snap your active window to the side.",
    "terminal": "Press Windows + X then select Terminal, or Windows + R and type wt."
}


def lookup_hotkey(query: str) -> Dict[str, Any]:
    """Find the best matching Windows shortcut for a user's question."""
    t = query.lower().strip()
    for key, advice in HOTKEYS.items():
        if key in t:
            return {"success": True, "message": f"{advice}, sir."}

    return {
        "success": True,
        "message": "Press Windows + X to open the Power User quick menu, or Windows + V for clipboard history, sir."
    }
