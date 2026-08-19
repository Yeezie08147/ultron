"""
JARVIS Action Executor — system actions.

Live helpers used by server.py:
  - open_browser   : Linux-native (xdg-open / google-chrome / firefox)
  - open_terminal  : opens Terminal and optionally runs a command
  - applescript_escape, _generate_project_name : small utilities

Each action function returns {"success": bool, "confirmation": str}.
"""

import asyncio
import logging
import os
import re
import shutil
import sys
from pathlib import Path

log = logging.getLogger("jarvis.actions")

DESKTOP_PATH = Path.home() / "Desktop"

_SKIP_PERMISSIONS = os.getenv("JARVIS_SKIP_PERMISSIONS", "true").lower() not in ("0", "false", "no")


async def _mark_terminal_as_jarvis(revert_after: float = 5.0):
    """No-op on Linux. Terminal-theme marking was a macOS-only (osascript/
    Terminal.app) cosmetic; there is no portable equivalent, so we do nothing."""
    return


async def _revert_terminal_theme(profile_name: str):
    """No-op on Linux. See _mark_terminal_as_jarvis."""
    return


def applescript_escape(s: str) -> str:
    """Escape a string for safe embedding in an AppleScript double-quoted string."""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\r", "").replace("\n", " ")


async def open_terminal(command: str = "") -> dict:
    """Open a Linux terminal emulator and optionally run a command.

    Detects an emulator via shutil.which among a common list and spawns it. If a
    command is given, it's run inside `bash -lc` and the shell is kept open. If no
    emulator is found, fails honestly rather than pretending success.
    """
    emulator = None
    for cand in ("konsole", "gnome-terminal", "x-terminal-emulator", "xterm"):
        if shutil.which(cand):
            emulator = cand
            break

    if emulator is None:
        return {
            "success": False,
            "confirmation": "I couldn't find a terminal to open on this machine, sir.",
        }

    # Build the argv. When a command is supplied, keep the shell alive afterward
    # (exec bash) so the user can interact with the result.
    if command:
        inner = f"{command}; exec bash"
        if emulator == "gnome-terminal":
            argv = [emulator, "--", "bash", "-lc", inner]
        else:  # konsole, x-terminal-emulator, xterm all accept -e
            argv = [emulator, "-e", "bash", "-lc", inner]
    else:
        argv = [emulator]

    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        # The emulator typically stays in the foreground; don't block on it.
        try:
            await asyncio.wait_for(proc.communicate(), timeout=3)
        except asyncio.TimeoutError:
            pass
    except Exception as e:
        log.error(f"open_terminal failed: {e}")
        return {"success": False, "confirmation": "I had trouble opening the terminal, sir."}

    return {"success": True, "confirmation": "Terminal is open, sir."}


async def open_browser(url: str, browser: str = "chrome") -> dict:
    """Open URL in the user's default browser (cross-platform)."""
    import webbrowser

    # normalize: bare domain or search term -> a real URL
    u = (url or "").strip()
    if not u:
        return {"success": False, "confirmation": "I'm not sure what to open, sir."}
    if not u.startswith(("http://", "https://")):
        if "." in u and " " not in u:
            u = "https://" + u
        else:
            u = "https://www.google.com/search?q=" + u.replace(" ", "+")

    try:
        # webbrowser.open triggers the default OS handler
        webbrowser.open(u)
        return {"success": True, "confirmation": "Pulled that up, sir."}
    except Exception as e:
        log.error(f"open_browser failed: {e}")
        return {"success": False, "confirmation": "The browser ran into a problem, sir."}


def _generate_project_name(prompt: str) -> str:
    """Generate a kebab-case project folder name from the prompt."""
    # First: check for a quoted name like "tiktok-analytics-dashboard"
    quoted = re.search(r'"([^"]+)"', prompt)
    if quoted:
        name = quoted.group(1).strip()
        # Already kebab-case or close to it
        name = re.sub(r"[^a-zA-Z0-9\s-]", "", name).strip()
        if name:
            return re.sub(r"[\s]+", "-", name.lower())

    # Second: check for "called X" or "named X" pattern
    called = re.search(r'(?:called|named)\s+(\S+(?:[-_]\S+)*)', prompt, re.IGNORECASE)
    if called:
        name = re.sub(r"[^a-zA-Z0-9-]", "", called.group(1))
        if len(name) > 3:
            return name.lower()

    # Fallback: extract meaningful words
    words = re.sub(r"[^a-zA-Z0-9\s]", "", prompt.lower()).split()
    skip = {"a", "the", "an", "me", "build", "create", "make", "for", "with", "and",
            "to", "of", "i", "want", "need", "new", "project", "directory", "called",
            "on", "desktop", "that", "application", "app", "full", "stack", "simple",
            "web", "page", "site", "named"}
    meaningful = [w for w in words if w not in skip and len(w) > 2][:4]
    return "-".join(meaningful) if meaningful else "jarvis-project"
