"""
media_control.py — ULTRON Media & Audio Control Engine.

Capabilities:
- Master system volume adjustments (0-100%, mute, unmute)
- Media playback controls (play/pause, next track, previous track)
- Direct song & music launching (YouTube, Spotify)
"""

import os
import re
import logging
import subprocess
import urllib.parse
from typing import Dict, Any, Optional

try:
    import pyautogui
except ImportError:
    pyautogui = None

log = logging.getLogger("ultron.media")


def set_volume(level: int) -> Dict[str, Any]:
    """Set system master volume to a percentage (0-100)."""
    target = max(0, min(100, level))
    
    # Method 1: PowerShell SoundVolumeView / Audio Endpoint
    try:
        # Calculate scalar between 0.0 and 1.0
        scalar = target / 100.0
        ps_script = f"""
        $w = Add-Type -MemberDefinition '[DllImport("user32.dll")] public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, uint dwExtraInfo);' -Name 'Vol' -PassThru
        """
        # Alternatively use PowerShell AudioDeviceCmdlets or direct nircmd if present, or simulate key steps
        # Simulating relative volume adjustments using Windows Volume Keys
        # 50 volume steps total in Windows (2% per step)
        if pyautogui:
            # First mute to 0 by pressing volumedown 50 times
            for _ in range(50):
                pyautogui.press('volumedown')
            # Then press volumeup target // 2 times
            steps = target // 2
            for _ in range(steps):
                pyautogui.press('volumeup')
            return {"success": True, "message": f"Volume set to {target}%."}
    except Exception as e:
        log.warning(f"Volume adjustment failed: {e}")

    return {"success": False, "message": "Could not adjust system volume."}


def volume_up(steps: int = 5) -> Dict[str, Any]:
    """Increase system volume by a step amount."""
    if pyautogui:
        for _ in range(steps):
            pyautogui.press('volumeup')
        return {"success": True, "message": "Volume increased."}
    return {"success": False, "message": "Volume key not available."}


def volume_down(steps: int = 5) -> Dict[str, Any]:
    """Decrease system volume by a step amount."""
    if pyautogui:
        for _ in range(steps):
            pyautogui.press('volumedown')
        return {"success": True, "message": "Volume decreased."}
    return {"success": False, "message": "Volume key not available."}


def toggle_mute() -> Dict[str, Any]:
    """Toggle mute / unmute for system audio."""
    if pyautogui:
        pyautogui.press('volumemute')
        return {"success": True, "message": "Audio mute toggled."}
    return {"success": False, "message": "Audio mute key not available."}


def play_pause_media() -> Dict[str, Any]:
    """Toggle media play / pause on Windows."""
    if pyautogui:
        pyautogui.press('playpause')
        return {"success": True, "message": "Media playback toggled."}
    return {"success": False, "message": "Media control not available."}


def next_track() -> Dict[str, Any]:
    """Skip to the next audio track."""
    if pyautogui:
        pyautogui.press('nexttrack')
        return {"success": True, "message": "Skipped to next track."}
    return {"success": False, "message": "Media control not available."}


def prev_track() -> Dict[str, Any]:
    """Return to the previous audio track."""
    if pyautogui:
        pyautogui.press('prevtrack')
        return {"success": True, "message": "Returning to previous track."}
    return {"success": False, "message": "Media control not available."}


def play_on_youtube(query: str) -> Dict[str, Any]:
    """Search and launch a music track / video on YouTube."""
    clean = re.sub(r'^(?:play|listen to|put on)\s+', '', query, flags=re.IGNORECASE).strip()
    encoded = urllib.parse.quote_plus(clean)
    url = f"https://www.youtube.com/results?search_query={encoded}"
    try:
        subprocess.Popen(f'start "" "{url}"', shell=True)
        return {"success": True, "message": f"Playing {clean} on YouTube, sir."}
    except Exception as e:
        log.error(f"Failed to open YouTube: {e}")
        return {"success": False, "message": f"Failed to play YouTube: {e}"}


def play_on_spotify(query: str) -> Dict[str, Any]:
    """Search and launch a music track / album on Spotify."""
    clean = re.sub(r'^(?:play|listen to|put on)\s+', '', query, flags=re.IGNORECASE).strip()
    encoded = urllib.parse.quote_plus(clean)
    try:
        # Try native Spotify URI first
        subprocess.Popen(f'start "" "spotify:search:{encoded}"', shell=True)
        return {"success": True, "message": f"Searching for {clean} on Spotify, sir."}
    except Exception:
        # Fallback to Spotify Web Player
        web_url = f"https://open.spotify.com/search/{encoded}"
        subprocess.Popen(f'start "" "{web_url}"', shell=True)
        return {"success": True, "message": f"Opening {clean} on Spotify Web, sir."}
