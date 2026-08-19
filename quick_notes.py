"""
quick_notes.py — ULTRON Voice Notes & Quick Journal Matrix.

Capabilities:
- Instant voice note capture to Desktop/ULTRON_Notes/notes.txt
- Read back most recent voice notes
- Clear/archive voice notes
"""

import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

log = logging.getLogger("ultron.notes")

NOTES_DIR = Path.home() / "Desktop" / "ULTRON_Notes"
NOTES_FILE = NOTES_DIR / "notes.txt"


def _ensure_dir():
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    if not NOTES_FILE.exists():
        NOTES_FILE.write_text("# ULTRON Quick Voice Notes\n\n", encoding="utf-8")


def add_note(content: str) -> Dict[str, Any]:
    """Append a timestamped voice note to the user's notes."""
    _ensure_dir()
    clean = content.strip()
    
    # Strip prefixes like "take a note", "note down", etc.
    import re
    clean = re.sub(r'^(?:take a note|take note|note down|save note|write down)\s*(?:that|to|:)?\s*', '', clean, flags=re.I).strip()
    if not clean:
        clean = "Untitled reminder"

    timestamp = datetime.now().strftime("%Y-%m-%d %I:%M %p")
    entry = f"- [{timestamp}] {clean}\n"

    with open(NOTES_FILE, "a", encoding="utf-8") as f:
        f.write(entry)

    log.info(f"Saved voice note: {clean}")
    return {
        "success": True,
        "note": clean,
        "message": f"Note saved to your Desktop: {clean}, sir."
    }


def read_latest_notes(count: int = 3) -> Dict[str, Any]:
    """Read back the most recent notes."""
    _ensure_dir()
    lines = [line.strip() for line in NOTES_FILE.read_text(encoding="utf-8").splitlines() if line.startswith("- [")]
    if not lines:
        return {"success": True, "message": "You have no notes on record, sir."}

    recent = lines[-count:]
    notes_clean = []
    for r in recent:
        # Extract after timestamp
        parts = r.split("] ", 1)
        if len(parts) > 1:
            notes_clean.append(parts[1])
        else:
            notes_clean.append(r)

    summary = "; ".join(notes_clean)
    return {
        "success": True,
        "notes": notes_clean,
        "message": f"Your recent notes are: {summary}, sir."
    }


def clear_notes() -> Dict[str, Any]:
    """Clear all voice notes."""
    _ensure_dir()
    NOTES_FILE.write_text("# ULTRON Quick Voice Notes\n\n", encoding="utf-8")
    return {"success": True, "message": "All voice notes have been cleared, sir."}
