"""
frequency_inverter.py — ULTRON Frequency Reversal & Remote Desktop (RDC) Protocol Matrix.

Capabilities:
- Remote Desktop Connection (RDC / mstsc) controller and remote session launcher
- Audio frequency inversion and acoustic sweep synthesizer
- Table-flip matrix (ASCII table flip generator (╯°□°)╯︵ ┻━┻ and text inversion)
- Sci-fi Frequency Modulation & Counter-Matrix Protocol
"""

import os
import logging
import threading
import subprocess
from typing import Dict, Any

log = logging.getLogger("ultron.frequency")


def launch_rdc(target_host: str = "") -> Dict[str, Any]:
    """Launch Windows Remote Desktop Connection (mstsc.exe)."""
    clean_host = target_host.strip()
    try:
        if clean_host:
            subprocess.Popen(f'mstsc.exe /v:{clean_host}', shell=True)
            msg = f"Remote Desktop Connection protocol engaged for target host {clean_host}, sir."
        else:
            subprocess.Popen('mstsc.exe', shell=True)
            msg = "Remote Desktop Connection interface initialized on your display, sir."

        return {
            "success": True,
            "host": clean_host,
            "message": msg
        }
    except Exception as e:
        log.error(f"RDC launch error: {e}")
        return {"success": False, "message": f"Failed to initialize RDC matrix: {e}"}


def _play_frequency_sweep():
    """Synthesize an inverted frequency sweep on Windows hardware."""
    try:
        import winsound
        # High to low frequency sweep (reversal)
        for freq in range(2400, 300, -150):
            winsound.Beep(freq, 40)
        # Power pulse
        winsound.Beep(1800, 150)
    except Exception:
        pass


def reverse_frequency() -> Dict[str, Any]:
    """Execute acoustic frequency reversal sweep protocol."""
    threading.Thread(target=_play_frequency_sweep, daemon=True).start()
    return {
        "success": True,
        "message": "Frequency polarity reversed. Acoustic carrier wave inverted across local channels, sir."
    }


def flip_table(text: str = "") -> Dict[str, Any]:
    """Generate ASCII table flip and reverse text matrix."""
    flip_ascii = "(╯°□°)╯︵ ┻━┻"
    
    if text:
        reversed_text = text[::-1]
        msg = f"Tables flipped. Inverted matrix: '{reversed_text}', sir."
    else:
        msg = "Tables flipped. Counter-frequency vector active, sir."

    try:
        import pyperclip
        pyperclip.copy(f"{flip_ascii} {text}".strip())
    except Exception:
        pass

    return {
        "success": True,
        "flip": flip_ascii,
        "message": msg
    }


def execute_rdc_frequency_protocol(target: str = "") -> Dict[str, Any]:
    """Comprehensive protocol: reverse frequency sweep, flip table matrix, and open RDC."""
    reverse_frequency()
    flip_res = flip_table(target)
    rdc_res = launch_rdc(target)
    
    return {
        "success": True,
        "message": "Frequency counter-vector established through RDC matrix. Tables flipped, sir."
    }
