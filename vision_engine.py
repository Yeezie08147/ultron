"""
vision_engine.py — ULTRON Screen Understanding & Visual Inspection Engine.

Capabilities:
- Capture desktop screen snapshot
- Inspect active foreground window and UI hierarchy
- Explain on-screen code, error dialogs, and diagrams via local AI
"""

import time
import logging
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional
import httpx

import desktop_control

log = logging.getLogger("ultron.vision")


async def describe_current_screen() -> str:
    """Capture screen and describe the active workspace and applications."""
    try:
        shot = desktop_control.capture_screenshot()
        active_win = desktop_control.get_foreground_window()
        active_list = desktop_control.list_active_windows()
        
        win_titles = [w.get("title", "") for w in active_list[:5] if w.get("title")]
        current_focus = active_win.get("title", "Desktop") if active_win else "Desktop"

        prompt = (
            "You are ULTRON. Based on this desktop state:\n"
            f"- Currently Focused Application: {current_focus}\n"
            f"- Open Windows: {', '.join(win_titles)}\n\n"
            "Provide a concise, direct 1-2 sentence spoken status of what the user is currently working on:\n"
            "Status:"
        )

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "http://127.0.0.1:11434/api/generate",
                json={
                    "model": "llama3.1",
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.3, "num_predict": 100}
                }
            )
            if resp.status_code == 200:
                text = resp.json().get("response", "").strip()
                if text:
                    return text
    except Exception as e:
        log.error(f"Screen description error: {e}")

    return f"You are currently working in {current_focus}, sir."
