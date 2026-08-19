"""
doc_creator.py — ULTRON Desktop Document & Markdown Creator.

Capabilities:
- Create and open new Markdown (.md), Text (.txt), or Python (.py) files directly on Desktop
"""

import os
import re
import logging
from pathlib import Path
from typing import Dict, Any

log = logging.getLogger("ultron.doccreator")

DESKTOP_DIR = Path.home() / "Desktop"


def create_document(text: str) -> Dict[str, Any]:
    """Create a new file on Desktop and write initial text."""
    t = text.strip()
    
    # Extract filename if provided
    fn_match = re.search(r'\b([a-zA-Z0-9_\-]+\.(?:txt|md|py|json|html|css))\b', t, re.I)
    filename = fn_match.group(1) if fn_match else "new_document.txt"

    # Extract content after 'with' or 'saying'
    content_match = re.search(r'(?:with|containing|saying)\s+(.*)$', t, re.I)
    content = content_match.group(1) if content_match else f"# {filename}\nCreated by ULTRON.\n"

    target_path = DESKTOP_DIR / filename
    try:
        target_path.write_text(content, encoding="utf-8")
        # Open with default text editor
        os.system(f'notepad "{target_path.resolve()}"')
        return {
            "success": True,
            "filename": filename,
            "path": str(target_path),
            "message": f"Created {filename} on your Desktop and opened it in Notepad, sir."
        }
    except Exception as e:
        return {"success": False, "message": f"Document creation failed: {e}"}
