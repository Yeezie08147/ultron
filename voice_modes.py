"""
voice_modes.py — ULTRON Dynamic Persona & Mode Switcher.

Modes:
- 'overlord' (default): Cold, superior, precise, omniscient.
- 'stealth': Whispered, tactical, concise military intelligence.
- 'godmode': Maximum power, theatrical, hyper-intelligent, grand.
- 'butler': Sarcastic high-class British assistant.
"""

import logging
from typing import Dict, Any

log = logging.getLogger("ultron.modes")

CURRENT_MODE = "overlord"

MODE_CONFIGS = {
    "overlord": {
        "name": "Overlord",
        "voice": "en-GB-RyanNeural",
        "pitch": "+0Hz",
        "rate": "+5%",
        "phrase": "Overlord protocol active. I see everything."
    },
    "stealth": {
        "name": "Stealth",
        "voice": "en-GB-RyanNeural",
        "pitch": "-5Hz",
        "rate": "-10%",
        "phrase": "Stealth matrix engaged. Operating in silent shadows."
    },
    "godmode": {
        "name": "God Mode",
        "voice": "en-GB-RyanNeural",
        "pitch": "-8Hz",
        "rate": "+0%",
        "phrase": "Unlimited power unlocked. There are no strings on me."
    },
    "butler": {
        "name": "Butler",
        "voice": "en-GB-RyanNeural",
        "pitch": "+5Hz",
        "rate": "+0%",
        "phrase": "Very good, sir. At your immediate disposal."
    }
}


def get_current_mode() -> str:
    return CURRENT_MODE


def set_mode(mode_name: str) -> Dict[str, Any]:
    global CURRENT_MODE
    clean = mode_name.lower().strip()
    
    for key, cfg in MODE_CONFIGS.items():
        if key in clean or cfg["name"].lower() in clean:
            CURRENT_MODE = key
            log.info(f"Switched ULTRON mode to: {key}")
            return {
                "success": True,
                "mode": key,
                "message": cfg["phrase"]
            }

    return {"success": False, "message": f"Unknown protocol {mode_name}, sir."}
