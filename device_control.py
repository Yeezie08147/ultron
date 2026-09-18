"""
device_control.py — ULTRON Multi-Device Control via ADB & Windows PnP.

Controls Android and mobile devices connected via USB / Wi-Fi / Bluetooth:
  - Hybrid real-time detection: ADB authorized, unauthorized, offline + Windows PnP Bluetooth/USB devices
  - Resilient screen unlock (KEYCODE_WAKEUP 224 + wm dismiss-keyguard + dynamic swipe + PIN entry)
  - Screen lock (KEYCODE_SLEEP 223)
  - Battery telemetry & diagnostics
  - Media control (YouTube search, pause, play, volume)
  - App launcher (YouTube, Camera, Settings, Spotify, etc.)
"""

import asyncio
import subprocess
import logging
import os
import re
import time
import threading
from typing import Optional, Dict, List, Tuple, Any

log = logging.getLogger("ultron.devices")

# ── Device PINs from .env (DEVICE_PIN, DEVICE_PIN_1, etc.) ──
def _get_pins() -> List[str]:
    pins = []
    default = os.getenv("DEVICE_PIN", "")
    for i in range(1, 6):
        pin = os.getenv(f"DEVICE_PIN_{i}", default)
        pins.append(pin)
    return pins


def _adb(*args, serial: str = "") -> str:
    """Run an ADB command synchronously and return stdout. Never kills the server."""
    cmd = ["adb"]
    if serial:
        cmd.extend(["-s", serial])
    cmd.extend(args)
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=8,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        return result.stdout.strip()
    except FileNotFoundError:
        log.error("ADB executable not found in PATH.")
        return ""
    except subprocess.TimeoutExpired:
        log.warning(f"ADB command timed out: {cmd}")
        return ""
    except Exception as e:
        log.error(f"ADB error: {e}")
        return ""


# ── ADB Device Discovery ──

def get_detailed_device_status() -> Tuple[List[str], List[Dict[str, str]]]:
    """
    Return active authorized devices and a list of all detected devices with status.
    Critically, never runs adb kill-server so USB handshakes remain undisturbed.
    """
    output = _adb("devices")
    
    # If ADB server wasn't running, start it cleanly without killing anything
    if not output:
        _adb("start-server")
        output = _adb("devices")

    active_serials = []
    all_devices = []
    
    for line in output.splitlines()[1:]:  # skip 'List of devices attached'
        parts = line.split()
        if len(parts) >= 2:
            serial = parts[0]
            status = parts[1]
            all_devices.append({"serial": serial, "status": status})
            if status == "device":
                active_serials.append(serial)
                
    return active_serials, all_devices


def discover_devices() -> List[str]:
    """Return list of authorized connected device serial numbers."""
    active, _ = get_detailed_device_status()
    return active


# ── Screen & Keyguard Diagnostics ──

def _get_screen_dimensions(serial: str) -> Tuple[int, int]:
    """Get screen dimensions (width, height) via wm size."""
    try:
        out = _adb("shell", "wm", "size", serial=serial)
        for line in out.splitlines():
            if "size:" in line:
                parts = line.split(":")[-1].strip().split("x")
                if len(parts) == 2:
                    return int(parts[0]), int(parts[1])
    except Exception:
        pass
    return 1080, 2400  # Default modern smartphone resolution


def _is_screen_on(serial: str) -> bool:
    """Check if device screen is on / awake."""
    try:
        output = _adb("shell", "dumpsys", "power", serial=serial)
        return (
            "mHoldingDisplaySuspendBlocker=true" in output
            or "Display Power: state=ON" in output
            or "mWakefulness=Awake" in output
        )
    except Exception:
        return False


def _is_keyguard_locked(serial: str) -> bool:
    """Check if device keyguard is actively locked."""
    try:
        win_out = _adb("shell", "dumpsys", "window", serial=serial)
        if "isStatusBarKeyguardShowing=true" in win_out or "mKeyguardShowing=true" in win_out:
            return True
        if "isStatusBarKeyguardShowing=false" in win_out or "mKeyguardShowing=false" in win_out:
            return False
        trust_out = _adb("shell", "dumpsys", "trust", serial=serial)
        if "deviceLocked=true" in trust_out:
            return True
    except Exception:
        pass
    return False


# ── Windows PnP Mobile Device Detection (Fallback) ──

_PNP_CACHE: List[Dict[str, Any]] = []
_PNP_LAST_FETCH: float = 0.0
_PNP_LOCK = threading.Lock()


def _fetch_pnp_mobile_devices() -> List[Dict[str, Any]]:
    """Query Windows PnP for connected smartphones via Bluetooth or USB MTP."""
    ps_cmd = (
        'Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue | Where-Object { '
        '($_.Class -eq "WPD") -or '
        '($_.Class -eq "AndroidUsbDeviceClass") -or '
        '($_.InstanceId -like "*0000111F*") -or '
        '($_.InstanceId -like "*0000112F*") '
        '} | Select-Object FriendlyName, Class, InstanceId | ConvertTo-Json -Compress'
    )
    devices = []
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            timeout=4,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        raw = res.stdout.strip()
        if raw:
            import json
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                parsed = [parsed]
            
            seen_names = set()
            for item in parsed:
                fname = item.get("FriendlyName", "").strip()
                cid = item.get("Class", "").strip()
                iid = item.get("InstanceId", "").strip()
                
                # Ignore generic services
                if not fname or "Phonebook Access" in fname or "Adapter" in fname:
                    continue
                
                # Clean name: remove Bluetooth suffixes
                clean_name = re.sub(r"\s*(Hands-Free HF|Avrcp Transport|A2DP SNK|Audio).*$", "", fname, flags=re.IGNORECASE).strip()
                if not clean_name or clean_name in seen_names:
                    continue
                seen_names.add(clean_name)
                
                # Extract Bluetooth MAC if present
                mac_match = re.search(r"DEV_([0-9A-Fa-f]{12})", iid)
                if not mac_match:
                    mac_match = re.search(r"&([0-9A-Fa-f]{12})_", iid)
                serial_repr = f"BT:{mac_match.group(1)}" if mac_match else ("USB:MTP" if cid == "WPD" else "Android USB")
                
                is_bt = "0000111F" in iid or "0000112F" in iid or "BTHENUM" in iid
                devices.append({
                    "name": clean_name,
                    "class": cid,
                    "instance_id": iid,
                    "serial": serial_repr,
                    "is_bluetooth": is_bt
                })
    except Exception as e:
        log.debug(f"PnP query error: {e}")
    return devices


def _get_cached_pnp_devices() -> List[Dict[str, Any]]:
    """Return cached PnP mobile devices, updating asynchronously in background."""
    global _PNP_CACHE, _PNP_LAST_FETCH
    now = time.time()
    
    # Refresh cache in background if older than 8 seconds
    if now - _PNP_LAST_FETCH > 8:
        def _worker():
            global _PNP_CACHE, _PNP_LAST_FETCH
            with _PNP_LOCK:
                _PNP_CACHE = _fetch_pnp_mobile_devices()
                _PNP_LAST_FETCH = time.time()
                
        # If never fetched, fetch once synchronously
        if _PNP_LAST_FETCH == 0.0:
            _worker()
        else:
            threading.Thread(target=_worker, daemon=True).start()
            
    return _PNP_CACHE


# ── In-Memory Media State for Active Devices ──
_DEVICE_MEDIA_STATE: Dict[str, str] = {}


# ── Device Matrix Generation ──

def get_device_matrix() -> List[Dict[str, Any]]:
    """
    Return real-time status of physically connected devices.
    Prioritizes ADB connected devices; falls back to Windows PnP (Bluetooth / USB MTP).
    """
    active_serials, all_devices = get_detailed_device_status()
    matrix = []

    # 1. ADB Detected Devices
    if all_devices:
        for i, dev in enumerate(all_devices):
            serial = dev["serial"]
            status = dev["status"]
            
            if status == "device":
                model = _adb("shell", "getprop", "ro.product.model", serial=serial)
                brand = _adb("shell", "getprop", "ro.product.brand", serial=serial)
                display_name = f"{brand.capitalize()} {model}" if (brand and model) else (model or f"Device {i+1}")

                battery = 100
                try:
                    bat_out = _adb("shell", "dumpsys", "battery", serial=serial)
                    for line in bat_out.splitlines():
                        if "level:" in line:
                            battery = int(line.split(":")[1].strip())
                            break
                except Exception:
                    battery = 100

                screen_on = _is_screen_on(serial)
                keyguard_locked = _is_keyguard_locked(serial)
                is_unlocked = screen_on and not keyguard_locked

                matrix.append({
                    "id": i + 1,
                    "name": display_name,
                    "serial": serial,
                    "status": "UNLOCKED" if is_unlocked else "LOCKED",
                    "battery": battery,
                    "media": _DEVICE_MEDIA_STATE.get(serial, "Standby"),
                    "real": True,
                    "connection": "adb"
                })
            elif status == "unauthorized":
                matrix.append({
                    "id": i + 1,
                    "name": f"Android Device ({serial[:8]})",
                    "serial": serial,
                    "status": "UNAUTHORIZED - TAP ALLOW ON PHONE",
                    "battery": 0,
                    "media": "Pending Auth",
                    "real": True,
                    "connection": "adb_unauthorized"
                })
            else:
                matrix.append({
                    "id": i + 1,
                    "name": f"Android Device ({serial[:8]})",
                    "serial": serial,
                    "status": status.upper(),
                    "battery": 0,
                    "media": "Standby",
                    "real": True,
                    "connection": "adb_offline"
                })
        return matrix

    # 2. Fallback: Windows PnP (Bluetooth & USB MTP)
    pnp_devices = _get_cached_pnp_devices()
    if pnp_devices:
        for i, pnp in enumerate(pnp_devices):
            if pnp.get("is_bluetooth"):
                matrix.append({
                    "id": i + 1,
                    "name": pnp["name"],
                    "serial": pnp["serial"],
                    "status": "BLUETOOTH LINKED",
                    "battery": 0,
                    "media": "Bluetooth Audio Linked",
                    "real": True,
                    "connection": "bluetooth"
                })
            else:
                matrix.append({
                    "id": i + 1,
                    "name": pnp["name"],
                    "serial": pnp["serial"],
                    "status": "ENABLE USB DEBUGGING",
                    "battery": 0,
                    "media": "MTP Storage Connected",
                    "real": True,
                    "connection": "usb_pnp"
                })
        return matrix

    return []


# ── Screen Unlocking & Locking ──

def unlock_device(serial: str, pin: str = "") -> bool:
    """
    Resiliently wake and unlock device screen:
      1. KEYCODE_WAKEUP (224) - wakes display without toggling off if already on
      2. wm dismiss-keyguard - native Android keyguard dismissal
      3. Dynamic screen swipe up based on actual display resolution
      4. KEYCODE_MENU (82) - triggers PIN pad on Samsung/OEM devices
      5. Enters PIN if provided or configured in .env, followed by ENTER (66 / 160)
    """
    try:
        # Step 1: Wake screen safely
        _adb("shell", "input", "keyevent", "224", serial=serial)
        time.sleep(0.2)
        
        # Step 2: Request keyguard dismissal
        _adb("shell", "wm", "dismiss-keyguard", serial=serial)
        time.sleep(0.2)
        
        # Step 3: Dynamic swipe up
        w, h = _get_screen_dimensions(serial)
        cx = w // 2
        y_start = int(h * 0.82)
        y_end = int(h * 0.25)
        _adb("shell", "input", "swipe", str(cx), str(y_start), str(cx), str(y_end), "250", serial=serial)
        time.sleep(0.3)
        
        # Step 4: Keycode MENU for keypad trigger
        _adb("shell", "input", "keyevent", "82", serial=serial)
        time.sleep(0.2)
        
        # Step 5: Enter PIN if supplied
        actual_pin = pin or os.getenv("DEVICE_PIN", "")
        if actual_pin:
            _adb("shell", "input", "text", actual_pin, serial=serial)
            time.sleep(0.2)
            _adb("shell", "input", "keyevent", "66", serial=serial)   # KEYCODE_ENTER
            _adb("shell", "input", "keyevent", "160", serial=serial)  # KEYCODE_NUMPAD_ENTER
            
        log.info(f"Successfully processed unlock sequence on device {serial}")
        return True
    except Exception as e:
        log.error(f"Failed to unlock {serial}: {e}")
        return False


def lock_device(serial: str) -> bool:
    """Put device screen to sleep / lock via KEYCODE_SLEEP (223)."""
    try:
        _adb("shell", "input", "keyevent", "223", serial=serial)
        log.info(f"Screen locked on device {serial}")
        return True
    except Exception as e:
        log.error(f"Failed to lock {serial}: {e}")
        return False


async def unlock_all(pin: str = "") -> dict:
    """
    Unlock all connected devices with comprehensive status handling and actionable feedback.
    """
    active_serials, all_devices = get_detailed_device_status()
    
    # 1. Active ADB devices connected
    if active_serials:
        pins = _get_pins()
        tasks = []
        for i, s in enumerate(active_serials):
            p = pin or (pins[i] if i < len(pins) else "")
            tasks.append(asyncio.to_thread(unlock_device, s, p))
            
        results = await asyncio.gather(*tasks, return_exceptions=True)
        success_count = sum(1 for r in results if r is True)
        count_str = f"All {len(active_serials)}" if len(active_serials) > 1 else "1"
        return {
            "success": success_count > 0,
            "count": success_count,
            "total": len(active_serials),
            "message": f"Checking. One second. {count_str} device{'s' if len(active_serials) > 1 else ''} unlocked, sir."
        }

    # 2. Unauthorized ADB device detected
    if all_devices:
        unauthorized = [d["serial"] for d in all_devices if d["status"] == "unauthorized"]
        if unauthorized:
            return {
                "success": False,
                "count": 0,
                "message": "Phone connected via USB but unauthorized. Please tap 'Always allow from this computer' and 'Allow' on your phone screen, sir."
            }
        return {
            "success": False,
            "count": 0,
            "message": f"Phone detected with status '{all_devices[0]['status']}'. Please verify the USB connection, sir."
        }

    # 3. PnP Fallback (Bluetooth or USB MTP)
    pnp_devices = _get_cached_pnp_devices()
    if pnp_devices:
        first = pnp_devices[0]
        name = first.get("name", "Phone")
        if first.get("is_bluetooth"):
            return {
                "success": False,
                "count": 0,
                "message": f"Phone '{name}' is linked via Bluetooth. To unlock the screen, connect via USB cable with USB Debugging enabled in Developer Options, sir."
            }
        return {
            "success": False,
            "count": 0,
            "message": f"Phone '{name}' is connected via USB. To enable screen unlocking, please turn ON USB Debugging in your phone's Developer Options, sir."
        }

    # 4. No device found
    return {
        "success": False,
        "count": 0,
        "message": "No mobile devices detected in the matrix. Connect your Android phone via USB with USB Debugging turned ON, sir."
    }


async def unlock_all_three(pin: str = "") -> dict:
    """Alias for unlock_all for backward compatibility with existing triggers."""
    return await unlock_all(pin=pin)


async def lock_all() -> dict:
    """Lock / sleep all connected authorized devices."""
    active_serials, all_devices = get_detailed_device_status()
    if not active_serials:
        if all_devices:
            return {"success": False, "count": 0, "message": "Phone connected but unauthorized. Tap Allow on your phone screen, sir."}
        pnp_devs = _get_cached_pnp_devices()
        if pnp_devs:
            name = pnp_devs[0].get("name", "Phone")
            return {"success": False, "count": 0, "message": f"Phone '{name}' is connected via Bluetooth only. Connect via USB with USB Debugging to lock the display remotely, sir."}
        return {"success": False, "count": 0, "message": "No mobile devices connected, sir."}

    tasks = [asyncio.to_thread(lock_device, s) for s in active_serials]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    success_count = sum(1 for r in results if r is True)
    return {
        "success": success_count > 0,
        "count": success_count,
        "message": f"Screen locked on {success_count} connected device{'s' if len(active_serials) > 1 else ''}, sir."
    }


# ── Battery Telemetry ──

async def get_battery_status() -> dict:
    """Query live battery telemetry across connected devices."""
    active_serials, all_devices = get_detailed_device_status()
    if active_serials:
        reports = []
        for s in active_serials:
            model = _adb("shell", "getprop", "ro.product.model", serial=s) or "Device"
            brand = _adb("shell", "getprop", "ro.product.brand", serial=s) or ""
            name = f"{brand.capitalize()} {model}".strip()
            
            bat_level = "Unknown"
            try:
                bat_out = _adb("shell", "dumpsys", "battery", serial=s)
                for line in bat_out.splitlines():
                    if "level:" in line:
                        bat_level = line.split(":")[1].strip() + "%"
                        break
            except Exception:
                pass
            reports.append(f"{name} is at {bat_level}")
        return {
            "success": True,
            "message": f"{', and '.join(reports)}, sir."
        }

    pnp_devs = _get_cached_pnp_devices()
    if pnp_devs:
        name = pnp_devs[0].get("name", "Phone")
        return {
            "success": True,
            "message": f"Phone '{name}' is linked via Bluetooth. Connect via USB with USB Debugging enabled to read exact battery telemetry, sir."
        }

    return {
        "success": False,
        "message": "No mobile devices currently connected, sir."
    }


# ── Media Control (YouTube & Playback) ──

def play_media_on_device(serial: str, query: str) -> bool:
    """Open YouTube and search for a song on a specific device."""
    try:
        from urllib.parse import quote
        url = f"https://www.youtube.com/results?search_query={quote(query)}"
        _adb("shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", url, serial=serial)
        time.sleep(1)
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
        return {"success": False, "count": 0, "message": "No authorized devices connected, sir."}
    
    results = await asyncio.gather(*[
        asyncio.to_thread(play_media_on_device, s, query) for s in devices
    ])
    success_count = sum(1 for r in results if r is True)
    return {
        "success": success_count > 0,
        "count": success_count,
        "total": len(devices),
        "message": f"Playing on {success_count} of {len(devices)} devices, sir."
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
        return {"success": False, "count": 0, "message": "No authorized devices connected, sir."}
    
    results = await asyncio.gather(*[
        asyncio.to_thread(pause_device, s) for s in devices
    ])
    success_count = sum(1 for r in results if r is True)
    return {
        "success": success_count > 0,
        "count": success_count,
        "message": f"Paused {success_count} of {len(devices)} devices, sir."
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
        return {"success": False, "count": 0, "message": "No devices connected, sir."}
    
    results = await asyncio.gather(*[
        asyncio.to_thread(set_volume, s, level) for s in devices
    ])
    success_count = sum(1 for r in results if r is True)
    return {"success": success_count > 0, "count": success_count}


async def play_favorite_song_all(song: str = "Back in Black AC/DC") -> dict:
    """Play favorite song across connected devices and host system."""
    real_devices = discover_devices()
    if real_devices:
        tasks = [asyncio.to_thread(play_media_on_device, s, song) for s in real_devices]
        await asyncio.gather(*tasks, return_exceptions=True)
        for s in real_devices:
            _DEVICE_MEDIA_STATE[s] = f"Playing: {song}"

    try:
        import webbrowser
        from urllib.parse import quote
        webbrowser.open(f"https://www.youtube.com/results?search_query={quote(song)}")
    except Exception:
        pass

    if not real_devices:
        return {
            "success": True,
            "message": f"Playing {song} on host audio system. No mobile devices connected."
        }
    return {
        "success": True,
        "message": f"Playing {song} across host and {len(real_devices)} connected device{'s' if len(real_devices) > 1 else ''}, sir."
    }


# ── Common App Launcher ──

APP_PACKAGE_MAP = {
    "youtube": "com.google.android.youtube",
    "spotify": "com.spotify.music",
    "whatsapp": "com.whatsapp",
    "camera": "android.media.action.STILL_IMAGE_CAMERA",
    "settings": "android.settings.SETTINGS",
    "chrome": "com.android.chrome"
}

def open_app_on_device(serial: str, app_name: str) -> bool:
    """Launch an application on Android phone via monkey or intent."""
    pkg = APP_PACKAGE_MAP.get(app_name.lower().strip(), app_name)
    try:
        if pkg.startswith("android."):
            _adb("shell", "am", "start", "-a", pkg, serial=serial)
        else:
            _adb("shell", "monkey", "-p", pkg, "-c", "android.intent.category.LAUNCHER", "1", serial=serial)
        return True
    except Exception as e:
        log.error(f"Failed to launch {app_name} on {serial}: {e}")
        return False
