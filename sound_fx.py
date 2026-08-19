"""
sound_fx.py — ULTRON Cyber Audio Synthesizer & Sound Effects Matrix.

Capabilities:
- Pure native Windows winsound frequency synthesizer (Zero dependencies)
- Cyber tones: 'lockdown', 'warp', 'success', 'radar', 'alert'
"""

import time
import logging
import threading
from typing import Dict, Any

log = logging.getLogger("ultron.sfx")


def _play_beeps(pattern: list):
    try:
        import winsound
        for freq, dur in pattern:
            winsound.Beep(freq, dur)
    except Exception:
        pass


def play_sound_effect(fx_name: str = "success") -> Dict[str, Any]:
    """Play synthesized cyberpunk sound effects."""
    clean = fx_name.lower().strip()

    if "lockdown" in clean or "alarm" in clean:
        pattern = [(800, 150), (1200, 150), (800, 150), (1200, 150)]
        msg = "Lockdown audio beacon emitted, sir."
    elif "warp" in clean or "scifi" in clean or "cyber" in clean:
        pattern = [(400, 60), (600, 60), (800, 60), (1000, 60), (1400, 100)]
        msg = "Cyber matrix tone emitted, sir."
    elif "radar" in clean or "sonar" in clean:
        pattern = [(1800, 80), (1200, 80), (1800, 80)]
        msg = "Radar ping emitted, sir."
    else:  # Success / Chime
        pattern = [(523, 100), (659, 100), (784, 150)]
        msg = "Affirmative chime emitted, sir."

    threading.Thread(target=_play_beeps, args=(pattern,), daemon=True).start()
    return {"success": True, "effect": clean, "message": msg}
