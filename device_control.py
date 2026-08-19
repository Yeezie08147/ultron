"""
device_control.py — ULTRON Multi-Device Control via ADB.

Controls Android devices connected via USB:
  - Discover connected devices
  - Unlock screens (wake + swipe + PIN)
  - Play media (YouTube search)
  - Pause/stop media
  - Volume control
"""

import asyncio
import subprocess
import logging
import os
from typing import Optional

log = logging.getLogger("jarvis.devices")

# Device PINs from .env (DEVICE_PIN_1, DEVICE_PIN_2, etc.)
# Or a single default PIN: DEVICE_PIN
def _get_pins() -> list[str]:
    pins = []
    default = os.getenv("DEVICE_PIN", "")
    for i in range(1, 6):
        pin = os.getenv(f"DEVICE_PIN_{i}", default)
        pins.append(pin)
    return pins

def _adb(*args, serial: str = "") -> str:
    """Run an ADB command synchronously and return stdout."""
    cmd = ["adb"]
    if serial:
        cmd.extend(["-s", serial])
    cmd.extend(args)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        return result.stdout.strip()
    except FileNotFoundError:
        log.error("ADB not found. Install via: winget install Google.PlatformTools")
        return ""
    except subprocess.TimeoutExpired:
        log.error(f"ADB command timed out: {cmd}")
        return ""
    except Exception as e:
        log.error(f"ADB error: {e}")
        return ""

def discover_devices() -> list[str]:
    """Return list of connected device serial numbers."""
    output = _adb("devices")
    devices = []
    for line in output.splitlines()[1:]:  # skip header
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            devices.append(parts[0])
    log.info(f"Found {len(devices)} connected device(s): {devices}")
    return devices

def _is_screen_on(serial: str) -> bool:
    """Check if device screen is on."""
    output = _adb("shell", "dumpsys", "power", serial=serial)
    return "mHoldingDisplaySuspendBlocker=true" in output

def unlock_device(serial: str, pin: str = "") -> bool:
    """Unlock a single device: wake screen, swipe up, enter PIN."""
    try:
        # Wake screen
        _adb("shell", "input", "keyevent", "26", serial=serial)  # POWER button
        import time; time.sleep(0.5)
        # Swipe up to dismiss lock screen
        _adb("shell", "input", "swipe", "500", "1500", "500", "500", serial=serial)
        import time; time.sleep(0.5)
        # Enter PIN if provided
        if pin:
            _adb("shell", "input", "text", pin, serial=serial)
            import time; time.sleep(0.3)
            _adb("shell", "input", "keyevent", "66", serial=serial)  # ENTER
        log.info(f"Unlocked device {serial}")
        return True
    except Exception as e:
        log.error(f"Failed to unlock {serial}: {e}")
        return False

async def unlock_all() -> dict:
    """Unlock all connected devices simultaneously."""
    devices = discover_devices()
    if not devices:
        return {"success": False, "count": 0, "message": "No devices connected."}
    
    pins = _get_pins()
    
    async def _unlock(i, serial):
        pin = pins[i] if i < len(pins) else ""
        return await asyncio.to_thread(unlock_device, serial, pin)
    
    results = await asyncio.gather(*[_unlock(i, s) for i, s in enumerate(devices)])
    success_count = sum(1 for r in results if r)
    return {
        "success": success_count > 0,
        "count": success_count,
        "total": len(devices),
        "message": f"Unlocked {success_count} of {len(devices)} devices."
    }

def play_media_on_device(serial: str, query: str) -> bool:
    """Open YouTube and search for a song on a specific device."""
    try:
        from urllib.parse import quote
        url = f"https://www.youtube.com/results?search_query={quote(query)}"
        _adb("shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", url, serial=serial)
        import time; time.sleep(1)
        # Tap first result area (approximate coordinates for most phones)
        _adb("shell", "input", "tap", "540", "600", serial=serial)
        log.info(f"Playing '{query}' on {serial}")
        return True
    except Exception as e:
        log.error(f"Failed to play media on {serial}: {e}")
        return False

async def play_on_all(query: str) -> dict:
    """Play media on all connected devices simultaneously."""
    devices = discover_devices()
    if not devices:
        return {"success": False, "count": 0, "message": "No devices connected."}
    
    results = await asyncio.gather(*[
        asyncio.to_thread(play_media_on_device, s, query) for s in devices
    ])
    success_count = sum(1 for r in results if r)
    return {
        "success": success_count > 0,
        "count": success_count,
        "total": len(devices),
        "message": f"Playing on {success_count} of {len(devices)} devices."
    }

def pause_device(serial: str) -> bool:
    """Send media pause command to a device."""
    try:
        _adb("shell", "input", "keyevent", "85", serial=serial)  # MEDIA_PLAY_PAUSE
        return True
    except Exception as e:
        log.error(f"Failed to pause {serial}: {e}")
        return False

async def pause_all() -> dict:
    """Pause media on all connected devices."""
    devices = discover_devices()
    if not devices:
        return {"success": False, "count": 0, "message": "No devices connected."}
    
    results = await asyncio.gather(*[
        asyncio.to_thread(pause_device, s) for s in devices
    ])
    success_count = sum(1 for r in results if r)
    return {
        "success": success_count > 0,
        "count": success_count,
        "message": f"Paused {success_count} of {len(devices)} devices."
    }

def set_volume(serial: str, level: int) -> bool:
    """Set media volume (0-15) on a device."""
    try:
        _adb("shell", "media", "volume", "--set", str(level), "--stream", "3", serial=serial)
        return True
    except Exception as e:
        log.error(f"Failed to set volume on {serial}: {e}")
        return False

async def volume_all(level: int) -> dict:
    """Set volume on all devices."""
    devices = discover_devices()
    if not devices:
        return {"success": False, "count": 0, "message": "No devices connected."}
    
    results = await asyncio.gather(*[
        asyncio.to_thread(set_volume, s, level) for s in devices
    ])
    success_count = sum(1 for r in results if r)
    return {"success": success_count > 0, "count": success_count}
