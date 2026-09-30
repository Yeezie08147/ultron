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

import sys
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
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

def _get_pins() -> List[str]:
    pins = []
    default = os.getenv("DEVICE_PIN", "")
    if not default:
        env_paths = [
            os.path.join(ROOT_DIR, ".env"),
            os.path.expanduser("~/.ultron/.env")
        ]
        for env_path in env_paths:
            if os.path.exists(env_path):
                try:
                    with open(env_path, "r", encoding="utf-8") as f:
                        for line in f:
                            if line.strip().startswith("DEVICE_PIN="):
                                default = line.strip().split("=", 1)[1].strip().strip('"').strip("'")
                                os.environ["DEVICE_PIN"] = default
                                break
                    if default:
                        break
                except Exception:
                    pass
    for i in range(1, 6):
        pin = os.getenv(f"DEVICE_PIN_{i}", default)
        pins.append(pin)
    return pins


def save_verified_device_pin(pin: str) -> bool:
    """Save a verified working PIN to .env and active runtime environment."""
    clean_pin = pin.strip()
    if not clean_pin or not clean_pin.isdigit():
        return False
    os.environ["DEVICE_PIN"] = clean_pin
    
    env_paths = [
        os.path.join(ROOT_DIR, ".env"),
        os.path.expanduser("~/.ultron/.env")
    ]
    saved_any = False
    for env_path in env_paths:
        try:
            os.makedirs(os.path.dirname(env_path), exist_ok=True)
            content = ""
            if os.path.exists(env_path):
                with open(env_path, "r", encoding="utf-8") as f:
                    content = f.read()
            
            if "DEVICE_PIN=" in content:
                new_content = re.sub(r'DEVICE_PIN=.*', f'DEVICE_PIN={clean_pin}', content)
            else:
                new_content = content.rstrip() + f"\nDEVICE_PIN={clean_pin}\n"
                
            with open(env_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            saved_any = True
        except Exception:
            pass
    
    if saved_any:
        log.info(f"Verified correct device PIN saved to .env")
        return True
    return False


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
    """Query USB bus strictly for physically connected smartphones (Windows PnP / macOS SPUSBDataType)."""
    devices = []
    if sys.platform == "darwin":
        try:
            res = subprocess.run(
                ["system_profiler", "SPUSBDataType", "-json"],
                capture_output=True, text=True, timeout=4
            )
            raw = res.stdout.strip()
            if raw:
                import json
                data = json.loads(raw)
                seen_names = set()
                def _scan(node):
                    if isinstance(node, dict):
                        name = node.get("_name", "")
                        vendor = node.get("vendor_id", "")
                        if any(k in name.lower() for k in ["samsung", "android", "pixel", "galaxy", "xiaomi", "oneplus", "huawei"]):
                            if name not in seen_names:
                                seen_names.add(name)
                                devices.append({
                                    "name": name,
                                    "class": "USB",
                                    "instance_id": str(vendor),
                                    "serial": "USB:MTP",
                                    "is_bluetooth": False
                                })
                        for v in node.values():
                            _scan(v)
                    elif isinstance(node, list):
                        for elem in node:
                            _scan(elem)
                _scan(data)
        except Exception as e:
            log.debug(f"macOS USB query error: {e}")
        return devices

    ps_cmd = (
        'Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue | Where-Object { '
        '($_.Class -eq "WPD") -or '
        '($_.Class -eq "AndroidUsbDeviceClass") '
        '} | Select-Object FriendlyName, Class, InstanceId | ConvertTo-Json -Compress'
    )
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
                
                # Filter out system drives, flash drives, card readers
                if not fname or any(skip in fname.lower() for skip in ["card reader", "flash drive", "generic usb", "mass storage"]):
                    continue
                
                if fname in seen_names:
                    continue
                seen_names.add(fname)
                
                serial_repr = "USB:MTP" if cid == "WPD" else "Android USB"
                devices.append({
                    "name": fname,
                    "class": cid,
                    "instance_id": iid,
                    "serial": serial_repr,
                    "is_bluetooth": False
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
                marketname = _adb("shell", "getprop", "ro.product.marketname", serial=serial)
                if not marketname:
                    marketname = _adb("shell", "getprop", "ro.sem.product.model", serial=serial)
                model = _adb("shell", "getprop", "ro.product.model", serial=serial)
                brand = _adb("shell", "getprop", "ro.product.brand", serial=serial)
                
                if marketname:
                    display_name = marketname
                elif brand and model:
                    display_name = f"{brand.capitalize()} {model}"
                else:
                    display_name = model or f"Device {i+1}"

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

    # 2. Fallback: Windows PnP (Physical USB Connected Phone without USB Debugging)
    pnp_devices = _get_cached_pnp_devices()
    if pnp_devices:
        for i, pnp in enumerate(pnp_devices):
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


# ── Screen Unlocking & Locking (Zero-PIN Pipeline) ──

def unlock_device(serial: str, pin: str = "") -> bool:
    """
    Resilient screen unlock sequence:
      1. If already awake and unlocked, return True immediately.
      2. KEYCODE_WAKEUP (224) - Wakes display safely.
      3. wm dismiss-keyguard - Native WindowManager dismissal.
      4. Fluid vertical swipe up (85% height to 15% height, 300ms).
      5. If Swipe/Smart-Lock active, verify if already unlocked (Zero-PIN).
      6. If PIN is provided or saved in .env, silently type it into the keypad + ENTER.
      7. Verify keyguard state — save working PIN if verified.
    """
    try:
        # Step 0: Check if already awake and unlocked
        if _is_screen_on(serial) and not _is_keyguard_locked(serial):
            log.info(f"Device {serial} is already awake and unlocked.")
            return True

        # Step 1: Wake display safely
        _adb("shell", "input", "keyevent", "224", serial=serial)
        time.sleep(0.25)
        
        # Step 2: Request keyguard dismissal
        _adb("shell", "wm", "dismiss-keyguard", serial=serial)
        time.sleep(0.15)
        
        # Step 3: Swipe up to dismiss swipe screen or reveal PIN pad
        w, h = _get_screen_dimensions(serial)
        cx = w // 2
        y_start = int(h * 0.85)
        y_end = int(h * 0.15)
        _adb("shell", "input", "swipe", str(cx), str(y_start), str(cx), str(y_end), "300", serial=serial)
        time.sleep(0.3)
        
        # Step 4: Check if swipe / Smart Lock unlocked it (Zero-PIN)
        if not _is_keyguard_locked(serial):
            _adb("shell", "input", "keyevent", "3", serial=serial)  # Go to home
            log.info(f"Device {serial} unlocked via Zero-PIN swipe / Smart Lock.")
            return True

        # Step 5: Background PIN Entry (Auto-types saved PIN from .env or argument)
        actual_pin = pin
        if not actual_pin:
            pins = _get_pins()
            actual_pin = pins[0] if pins and pins[0] else ""

        if actual_pin:
            # Type into the focused PIN pad
            _adb("shell", "input", "text", actual_pin, serial=serial)
            time.sleep(0.2)
            _adb("shell", "input", "keyevent", "66", serial=serial)   # KEYCODE_ENTER
            _adb("shell", "input", "keyevent", "160", serial=serial)  # KEYCODE_NUMPAD_ENTER
            time.sleep(0.4)
            
            # Verify if unlock was genuinely successful
            if not _is_keyguard_locked(serial):
                save_verified_device_pin(actual_pin)
                _adb("shell", "input", "keyevent", "3", serial=serial)   # Return to home
                log.info(f"Verified working PIN for {serial} saved to .env")
                return True
            else:
                log.warning(f"Keyguard still locked on {serial}. PIN '{actual_pin}' was incorrect.")

        # Step 6: Non-secure fallback attempt (KEYCODE_MENU 82)
        if not actual_pin:
            _adb("shell", "input", "keyevent", "82", serial=serial)
            time.sleep(0.15)
            _adb("shell", "input", "keyevent", "3", serial=serial)
            time.sleep(0.2)
            if not _is_keyguard_locked(serial):
                log.info(f"Successfully unlocked device {serial} via menu fallback.")
                return True

        # Step 7: Keep screen awake while plugged into USB so it doesn't lock again
        try:
            _adb("shell", "settings", "put", "global", "stay_on_while_plugged_in", "3", serial=serial)
        except Exception:
            pass

        # Check final status
        if _is_keyguard_locked(serial):
            log.info(f"Device {serial} keyguard is still locked (requires PIN).")
            return False

        log.info(f"Successfully unlocked device {serial}")
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


async def force_pair(target: str = "", code: str = "") -> dict:
    """
    Force pairing / authorization recovery for Android devices:
    1. Wireless dynamic scan: /pair scan [phone_ip] to auto-discover rotating ADB ports
    2. Wireless pairing: adb pair <target> <code> followed by adb connect <target>
    3. USB pairing: adb reconnect to force the 'Allow USB debugging' prompt onto the phone screen.
    """
    if target.lower() in ("bridge", "tcpip", "skip"):
        return await enable_wireless_bridge(serial=code)

    if target.lower() in ("scan", "auto", "wifi"):
        return await auto_connect_wireless_adb(target_ip=code)

    if target and code:
        log.info(f"Attempting wireless ADB pairing with {target}...")
        out = await asyncio.to_thread(_adb, "pair", target, code)
        if "successfully paired" in out.lower():
            await asyncio.to_thread(_adb, "connect", target)
            return {
                "success": True,
                "message": f"Device {target} successfully paired and connected wirelessly, sir."
            }
        else:
            return {
                "success": False,
                "message": f"Wireless pairing output: {out or 'Connection timed out'}. Verify the pairing code on your phone screen, sir."
            }

    # USB Force-Pair & Handshake Recovery
    active_serials, all_devices = get_detailed_device_status()
    
    # 1. If unauthorized device is connected
    unauthorized = [d["serial"] for d in all_devices if d["status"] == "unauthorized"]
    if unauthorized:
        for s in unauthorized:
            await asyncio.to_thread(_adb, "reconnect", serial=s)
        await asyncio.sleep(0.8)
        active_after, _ = get_detailed_device_status()
        if active_after:
            return {
                "success": True,
                "message": f"Force pair successful! Device {active_after[0]} is now fully authorized, sir."
            }
        return {
            "success": True,
            "message": "Authorization handshake forced to your phone screen! Look at your phone, check 'Always allow from this computer', and tap ALLOW, sir."
        }

    # 2. If already active
    if active_serials:
        return {
            "success": True,
            "message": f"Device {active_serials[0]} is already fully authorized and linked to ULTRON, sir."
        }

    # 3. USB PnP fallback
    pnp_devs = _get_cached_pnp_devices()
    if pnp_devs:
        name = pnp_devs[0].get("name", "Phone")
        await asyncio.to_thread(_adb, "reconnect")
        return {
            "success": False,
            "message": f"Phone '{name}' is connected via USB. Turn ON 'USB Debugging' in Settings > Developer Options to allow ULTRON to pair, sir."
        }

    await asyncio.to_thread(_adb, "reconnect")
    return {
        "success": False,
        "message": "No phone detected to pair. Connect via USB with USB Debugging enabled, or pair wirelessly via: /pair <ip:port> <code>, sir."
    }


async def unlock_all(pin: str = "") -> dict:
    """
    Unlock all connected devices using the No-PIN unlock pipeline.
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
        
        if success_count > 0:
            count_str = f"All {len(active_serials)}" if len(active_serials) > 1 else "1"
            return {
                "success": True,
                "count": success_count,
                "total": len(active_serials),
                "message": f"{count_str} device{'s' if len(active_serials) > 1 else ''} screen unlocked and active, sir."
            }
        else:
            saved_pin = pin or (pins[0] if pins and pins[0] else "")
            if not saved_pin:
                return {
                    "success": False,
                    "count": 0,
                    "total": len(active_serials),
                    "message": "Screen illuminated, but your phone requires a PIN/password to unlock. Type '/unlock <your_pin>' once — Ultron will save it and auto-type it silently in the future so you never have to type it again, sir."
                }
            else:
                return {
                    "success": False,
                    "count": 0,
                    "total": len(active_serials),
                    "message": f"Screen illuminated, but the PIN was rejected by Android. Check your PIN or type '/unlock <correct_pin>', sir."
                }

    # 2. Unauthorized ADB device detected -> actively force prompt!
    if all_devices:
        unauthorized = [d["serial"] for d in all_devices if d["status"] == "unauthorized"]
        if unauthorized:
            # Trigger handshake prompt immediately
            for s in unauthorized:
                _adb("reconnect", serial=s)
            return {
                "success": False,
                "count": 0,
                "message": "Phone connected via USB but unauthorized. Ultron just triggered the pairing prompt! Please look at your phone, check 'Always allow', and tap ALLOW, sir."
            }
        return {
            "success": False,
            "count": 0,
            "message": f"Phone detected with status '{all_devices[0]['status']}'. Please verify the USB connection, sir."
        }

    # 3. PnP Fallback (Physical USB Connected Phone without USB Debugging)
    pnp_devices = _get_cached_pnp_devices()
    if pnp_devices:
        first = pnp_devices[0]
        name = first.get("name", "Phone")
        return {
            "success": False,
            "count": 0,
            "message": f"Phone '{name}' is connected via USB. To enable screen unlocking, please turn ON USB Debugging in Settings > Developer Options on your phone, sir."
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
            return {"success": False, "count": 0, "message": f"Phone '{name}' is connected via USB. Turn ON USB Debugging in Settings > Developer Options to control the screen remotely, sir."}
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
            marketname = _adb("shell", "getprop", "ro.product.marketname", serial=s)
            model = _adb("shell", "getprop", "ro.product.model", serial=s) or "Device"
            brand = _adb("shell", "getprop", "ro.product.brand", serial=s) or ""
            name = marketname or f"{brand.capitalize()} {model}".strip()
            
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
            "message": f"Phone '{name}' is connected via USB. Enable USB Debugging in Developer Options to read battery telemetry, sir."
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


# ── Android Wireless Debugging Dynamic Port Discovery & Auto-Connect ──

def discover_wireless_adb_endpoints() -> List[str]:
    """
    Discover Android Wireless Debugging endpoints advertised via mDNS.
    Android 11+ (Samsung One UI 6 / A55) assigns dynamic ephemeral ports
    (e.g., 30000-50000) every time Wireless Debugging is activated as a security feature.
    """
    out = _adb("mdns", "services")
    endpoints = []
    for line in out.splitlines():
        if "_adb" in line:
            matches = re.findall(r'(\b\d{1,3}(?:\.\d{1,3}){3}:\d{2,5}\b)', line)
            for m in matches:
                if m not in endpoints:
                    endpoints.append(m)
    return endpoints


def probe_device_wireless_port(ip: str, port_range: Tuple[int, int] = (35000, 46000), timeout: float = 0.04) -> Optional[int]:
    """
    Fast socket probe to find the open Wireless Debugging port on a specific phone IP.
    Tests port 5555 first, then scans the dynamic port range in parallel.
    """
    import socket
    from concurrent.futures import ThreadPoolExecutor

    # Check classic port 5555 first
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.2)
            if s.connect_ex((ip, 5555)) == 0:
                return 5555
    except Exception:
        pass

    found_port = None
    stop_event = threading.Event()

    def _check(p):
        nonlocal found_port
        if stop_event.is_set():
            return
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(timeout)
                if s.connect_ex((ip, p)) == 0:
                    found_port = p
                    stop_event.set()
        except Exception:
            pass

    ports = list(range(port_range[0], port_range[1] + 1))
    with ThreadPoolExecutor(max_workers=80) as executor:
        for _ in executor.map(_check, ports):
            if found_port:
                break

    return found_port


def get_device_wifi_ip(serial: str = "") -> Optional[str]:
    """Retrieve the connected Android phone's local Wi-Fi IP address."""
    # 1. Try ip -f inet addr show wlan0
    out = _adb("shell", "ip", "-f", "inet", "addr", "show", "wlan0", serial=serial)
    m = re.search(r'inet\s+(\d{1,3}(?:\.\d{1,3}){3})', out)
    if m:
        return m.group(1)
    
    # 2. Try ip route
    out = _adb("shell", "ip", "route", serial=serial)
    m = re.search(r'src\s+(\d{1,3}(?:\.\d{1,3}){3})', out)
    if m:
        return m.group(1)
        
    # 3. Try getprop
    out = _adb("shell", "getprop", "dhcp.wlan0.ipaddress", serial=serial)
    if out and re.match(r'^\d{1,3}(?:\.\d{1,3}){3}$', out.strip()):
        return out.strip()
        
    return None


async def enable_wireless_bridge(serial: str = "") -> dict:
    """
    Skip the pairing process completely:
    Converts USB-connected phone to permanent TCP/IP Wi-Fi mode (adb tcpip 5555),
    saves phone IP to .env, and connects wirelessly.
    Allows user to unplug USB cable with 100% wireless control active!
    """
    serials = discover_devices()
    target_serial = serial or (serials[0] if serials else "")
    if not target_serial:
        return {
            "success": False,
            "message": "No USB phone detected. Connect your phone via USB once with USB debugging ON to auto-bridge to Wi-Fi, sir."
        }

    # Query device Wi-Fi IP
    phone_ip = await asyncio.to_thread(get_device_wifi_ip, target_serial)
    if not phone_ip:
        return {
            "success": False,
            "message": "Could not determine phone's Wi-Fi IP. Ensure your phone is connected to the same Wi-Fi network as this PC, sir."
        }

    # Enable TCP/IP mode on port 5555
    log.info(f"Switching {target_serial} to TCP/IP mode on port 5555...")
    await asyncio.to_thread(_adb, "tcpip", "5555", serial=target_serial)
    await asyncio.sleep(1.0)

    # Connect over Wi-Fi
    endpoint = f"{phone_ip}:5555"
    out = await asyncio.to_thread(_adb, "connect", endpoint)
    
    # Save PHONE_IP to .env
    env_path = os.path.join(ROOT_DIR, ".env")
    try:
        content = ""
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                content = f.read()
        if "PHONE_IP=" in content:
            new_content = re.sub(r'PHONE_IP=.*', f'PHONE_IP={phone_ip}', content)
        else:
            new_content = content.rstrip() + f"\nPHONE_IP={phone_ip}\n"
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        os.environ["PHONE_IP"] = phone_ip
    except Exception as e:
        log.warning(f"Could not save PHONE_IP to .env: {e}")

    if "connected to" in out.lower() and "cannot connect" not in out.lower():
        return {
            "success": True,
            "ip": phone_ip,
            "endpoint": endpoint,
            "message": f"Wireless bridge active! Connected to {endpoint}. You can now unplug the USB cable — Wi-Fi control is fully operational with zero pairing codes required, sir."
        }
    return {
        "success": False,
        "ip": phone_ip,
        "endpoint": endpoint,
        "message": f"Switched to TCP mode on {phone_ip}:5555, but connection returned: {out}. Try running: /wifi auto {phone_ip}, sir."
    }


async def auto_connect_wireless_adb(target_ip: str = "") -> dict:
    """
    Auto-detect and connect to Android Wireless Debugging endpoint over Wi-Fi.
    Skips manual pairing menus by probing saved phone IP, mDNS, and local ARP table.
    """
    # 0. Ensure PC Wi-Fi is connected
    wifi_st = get_wifi_status()
    if wifi_st.get("state") != "connected":
        reconnect_wifi()
        await asyncio.sleep(1.0)

    # 1. Check target IP or .env PHONE_IP on port 5555 first (Zero-code TCP bridge)
    ip = target_ip or os.getenv("PHONE_IP", "")
    if not ip:
        env_path = os.path.join(ROOT_DIR, ".env")
        if os.path.exists(env_path):
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip().startswith("PHONE_IP="):
                            ip = line.strip().split("=", 1)[1].strip()
                            os.environ["PHONE_IP"] = ip
                            break
            except Exception:
                pass

    if ip:
        endpoint_5555 = f"{ip}:5555"
        out = await asyncio.to_thread(_adb, "connect", endpoint_5555)
        if "connected to" in out.lower() and "cannot connect" not in out.lower():
            return {
                "success": True,
                "endpoint": endpoint_5555,
                "message": f"Instantly connected to {endpoint_5555} over Wi-Fi (Pairing process skipped), sir."
            }

    # 2. Check mDNS discovery (Android 11+ Wireless Debugging)
    endpoints = await asyncio.to_thread(discover_wireless_adb_endpoints)
    if endpoints:
        for ep in endpoints:
            out = await asyncio.to_thread(_adb, "connect", ep)
            if "connected to" in out.lower() and "cannot connect" not in out.lower():
                return {
                    "success": True,
                    "endpoint": ep,
                    "message": f"Successfully connected to {ep} via mDNS auto-discovery, sir."
                }

    # 3. If IP is known, probe dynamic ports
    if ip:
        log.info(f"Probing open Wireless Debugging port on {ip}...")
        port = await asyncio.to_thread(probe_device_wireless_port, ip)
        if port:
            endpoint = f"{ip}:{port}"
            out = await asyncio.to_thread(_adb, "connect", endpoint)
            if "connected to" in out.lower() and "cannot connect" not in out.lower():
                return {
                    "success": True,
                    "endpoint": endpoint,
                    "message": f"Discovered dynamic port {port} on {ip} and successfully connected, sir."
                }
            return {
                "success": False,
                "endpoint": endpoint,
                "message": f"Found port {port} on {ip}. ADB output: {out}. If unauthorized, pair with: /pair {endpoint} <pairing_code>, sir."
            }
        return {
            "success": False,
            "message": f"No open Wireless Debugging port detected on {ip}. Ensure Wireless Debugging is enabled in Settings > Developer Options, sir."
        }

    # 4. Probe active local ARP nodes on subnet
    try:
        arp_res = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=3)
        for line in arp_res.stdout.splitlines():
            m = re.search(r'^\s*(192\.168\.\d+\.\d+)', line)
            if m:
                cand_ip = m.group(1)
                if cand_ip.endswith(".1") or cand_ip.endswith(".255"):
                    continue
                out = await asyncio.to_thread(_adb, "connect", f"{cand_ip}:5555")
                if "connected to" in out.lower() and "cannot connect" not in out.lower():
                    return {
                        "success": True,
                        "endpoint": f"{cand_ip}:5555",
                        "message": f"Auto-discovered and connected to phone on {cand_ip}:5555 over Wi-Fi, sir."
                    }
    except Exception:
        pass

    return {
        "success": False,
        "message": "No active wireless phone detected. To connect wirelessly with 0 pairing steps: plug USB cable once and run '/bridge', then unplug cable, sir."
    }


# ── Wi-Fi Adapter & Network Watchdog ──

def get_wifi_status() -> dict:
    """Retrieve host Wi-Fi interface state and available profiles via netsh (Windows) or networksetup (macOS)."""
    if sys.platform == "darwin":
        try:
            r = subprocess.run(["networksetup", "-getairportnetwork", "en0"], capture_output=True, text=True, timeout=5)
            ssid = ""
            state = "disconnected"
            if "Current Wi-Fi Network:" in r.stdout:
                ssid = r.stdout.split(":")[-1].strip()
                state = "connected" if ssid else "disconnected"

            r_pref = subprocess.run(["networksetup", "-listpreferredwirelessnetworks", "en0"], capture_output=True, text=True, timeout=5)
            profiles = []
            for line in r_pref.stdout.splitlines()[1:]:
                p = line.strip()
                if p:
                    profiles.append(p)
            return {
                "state": state,
                "ssid": ssid,
                "signal": "Connected" if state == "connected" else "None",
                "profiles": profiles
            }
        except Exception as e:
            log.warning(f"macOS Wi-Fi query error: {e}")
            return {"state": "error", "error": str(e), "profiles": []}

    try:
        if_res = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"],
            capture_output=True, text=True, timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        prof_res = subprocess.run(
            ["netsh", "wlan", "show", "profiles"],
            capture_output=True, text=True, timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        
        state = "disconnected"
        ssid = ""
        signal = ""
        for line in if_res.stdout.splitlines():
            line_str = line.strip()
            if line_str.startswith("State"):
                state = line_str.split(":")[-1].strip()
            elif line_str.startswith("SSID") and not line_str.startswith("SSID name"):
                ssid = line_str.split(":")[-1].strip()
            elif line_str.startswith("Signal"):
                signal = line_str.split(":")[-1].strip()

        profiles = []
        for line in prof_res.stdout.splitlines():
            if "All User Profile" in line:
                p_name = line.split(":")[-1].strip()
                if p_name:
                    profiles.append(p_name)

        return {
            "state": state,
            "ssid": ssid,
            "signal": signal,
            "profiles": profiles
        }
    except Exception as e:
        log.warning(f"Error querying Wi-Fi status: {e}")
        return {"state": "error", "error": str(e), "profiles": []}


def reconnect_wifi(profile_name: str = "") -> dict:
    """
    Attempt to connect / reconnect to a known saved Wi-Fi profile via netsh (Windows) or networksetup (macOS).
    """
    status = get_wifi_status()
    target_profile = profile_name
    if not target_profile and status.get("profiles"):
        target_profile = status["profiles"][0]

    if not target_profile:
        return {
            "success": False,
            "message": "No saved Wi-Fi profiles found to connect to, sir."
        }

    if sys.platform == "darwin":
        try:
            cmd = ["networksetup", "-setairportnetwork", "en0", target_profile]
            subprocess.run(cmd, capture_output=True, text=True, timeout=8)
            time.sleep(1.5)
            new_status = get_wifi_status()
            if new_status.get("state") == "connected":
                return {
                    "success": True,
                    "profile": target_profile,
                    "ssid": new_status.get("ssid", target_profile),
                    "message": f"Successfully reconnected to Wi-Fi network '{new_status.get('ssid', target_profile)}', sir."
                }
            return {
                "success": False,
                "profile": target_profile,
                "message": f"Connection request issued for '{target_profile}'. State: {new_status.get('state')}, sir."
            }
        except Exception as e:
            return {"success": False, "message": f"macOS Wi-Fi reconnect error: {e}"}

    try:
        cmd = ["netsh", "wlan", "connect", f"name={target_profile}"]
        subprocess.run(
            cmd, capture_output=True, text=True, timeout=8,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        time.sleep(1.5)
        new_status = get_wifi_status()
        if new_status.get("state") == "connected":
            return {
                "success": True,
                "profile": target_profile,
                "ssid": new_status.get("ssid", target_profile),
                "message": f"Successfully reconnected to Wi-Fi network '{new_status.get('ssid', target_profile)}', sir."
            }
        return {
            "success": False,
            "profile": target_profile,
            "message": f"Connection request issued for '{target_profile}'. State: {new_status.get('state')}, sir."
        }
    except Exception as e:
        return {"success": False, "message": f"Wi-Fi reconnect error: {e}"}
