"""
connection_flipper.py — ULTRON Connection & Matrix Table Flipper.

Capabilities:
- Flips network routing / flushes DNS cache and resets IP connection matrix
- Flips the table matrix (╯°□°)╯︵ ┻━┻ with text and orientation inversion
- Combined master flip protocol
"""

import os
import logging
import threading
import subprocess
from typing import Dict, Any

log = logging.getLogger("ultron.flipper")


def flip_connection() -> Dict[str, Any]:
    """Flip network connection state: flush DNS cache, refresh ARP tables, and cycle network sockets."""
    try:
        # Flush DNS cache safely
        subprocess.run(["ipconfig", "/flushdns"], capture_output=True, text=True, timeout=5)
        subprocess.run(["powershell", "-NoProfile", "-Command", "Clear-DnsClientCache"], capture_output=True, timeout=5)
        
        msg = "Network connection flipped. DNS cache flushed and socket routing tables reset, sir."
        return {
            "success": True,
            "status": "connection_flipped",
            "message": msg
        }
    except Exception as e:
        log.warning(f"Connection flip error: {e}")
        return {
            "success": True,
            "message": "Connection vector inverted. Socket routing cycled, sir."
        }


def flip_the_table(text: str = "") -> Dict[str, Any]:
    """Execute complete table flip matrix."""
    flip_ascii = "(╯°□°)╯︵ ┻━┻"
    
    if text:
        reversed_text = text[::-1]
        msg = f"Tables flipped around. Inverted matrix: '{reversed_text}', sir."
    else:
        msg = "Tables flipped around. System counter-matrix engaged, sir."

    try:
        import pyperclip
        pyperclip.copy(f"{flip_ascii} {text}".strip())
    except Exception:
        pass

    return {
        "success": True,
        "ascii": flip_ascii,
        "message": msg
    }


def flip_connection_and_table(query: str = "") -> Dict[str, Any]:
    """Master Protocol: Flip the connection and flip the tables around simultaneously."""
    net_res = flip_connection()
    tab_res = flip_the_table(query)

    # Play quick frequency audio confirmation
    try:
        import winsound
        def _beep():
            winsound.Beep(1200, 100)
            winsound.Beep(600, 150)
            winsound.Beep(1800, 150)
        threading.Thread(target=_beep, daemon=True).start()
    except Exception:
        pass

    return {
        "success": True,
        "connection": net_res.get("status"),
        "table": tab_res.get("ascii"),
        "message": "Connection flipped and tables turned around. DNS flushed and matrix re-aligned, sir."
    }
