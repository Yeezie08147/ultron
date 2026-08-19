"""
file_scout.py — ULTRON Smart File Scout & Workspace Organizer.

Capabilities:
- Find recently modified files, latest downloads, and PDFs
- Intelligent folder cleanup: sorts messy Downloads into structured subfolders (Images, Docs, Code, Installers)
"""

import os
import shutil
import logging
from pathlib import Path
from typing import Dict, Any, List

log = logging.getLogger("ultron.filescout")

DOWNLOADS_DIR = Path.home() / "Downloads"
DESKTOP_DIR = Path.home() / "Desktop"
DOCUMENTS_DIR = Path.home() / "Documents"

FILE_CATEGORIES = {
    "Images": [".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp"],
    "Documents": [".pdf", ".docx", ".doc", ".txt", ".xlsx", ".pptx", ".csv"],
    "Code": [".py", ".ts", ".js", ".html", ".css", ".json", ".cpp", ".rs"],
    "Installers": [".exe", ".msi", ".dmg", ".pkg", ".iso"],
    "Archives": [".zip", ".tar", ".gz", ".7z", ".rar"]
}


def find_latest_download() -> Dict[str, Any]:
    """Find the most recently modified file in Downloads folder."""
    if not DOWNLOADS_DIR.exists():
        return {"success": False, "message": "Downloads folder not found."}

    files = [f for f in DOWNLOADS_DIR.glob("*") if f.is_file() and not f.name.startswith(".")]
    if not files:
        return {"success": False, "message": "No files found in Downloads."}

    latest = max(files, key=lambda f: f.stat().st_mtime)
    
    # Try opening folder in file explorer and highlighting file
    try:
        os.system(f'explorer /select,"{latest.resolve()}"')
    except Exception:
        pass

    return {
        "success": True,
        "filename": latest.name,
        "path": str(latest),
        "message": f"Your latest download is {latest.name}, sir. I have opened it in Explorer."
    }


def organize_downloads() -> Dict[str, Any]:
    """Sort files in Downloads folder into categorized subdirectories."""
    if not DOWNLOADS_DIR.exists():
        return {"success": False, "message": "Downloads folder not found."}

    moved_count = 0
    
    for item in DOWNLOADS_DIR.glob("*"):
        if item.is_file() and not item.name.startswith("."):
            ext = item.suffix.lower()
            
            # Determine category
            target_category = "Other"
            for cat, extensions in FILE_CATEGORIES.items():
                if ext in extensions:
                    target_category = cat
                    break
                    
            target_dir = DOWNLOADS_DIR / target_category
            target_dir.mkdir(exist_ok=True)
            
            try:
                dest = target_dir / item.name
                # Avoid collision
                if not dest.exists():
                    shutil.move(str(item), str(dest))
                    moved_count += 1
            except Exception as e:
                log.warning(f"Could not move {item.name}: {e}")

    return {
        "success": True,
        "moved": moved_count,
        "message": f"Downloads folder organized. Sorted {moved_count} files into structured archives, sir."
    }
