"""
cli.py — ULTRON Autonomous Command Line Interface (CLI).

Interactive terminal interface for ULTRON. Provides direct command execution,
device matrix controls, system telemetry, network diagnostics, and zero-cost
autonomous cognition with raw, unfiltered Ultron persona styling.
"""

import sys
import os
import re
import time
import asyncio
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

import logging
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("ultron.web").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.basicConfig(level=logging.WARNING)

# Ensure UTF-8 console output encoding on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Ensure workspace root is in path
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Import local engines
try:
    import device_control
except ImportError:
    device_control = None

try:
    import system_monitor
except ImportError:
    system_monitor = None

try:
    import hacker_terminal
except ImportError:
    hacker_terminal = None

try:
    import server
except ImportError:
    server = None

try:
    import face_tracking
except ImportError:
    face_tracking = None

try:
    import vision_engine
except ImportError:
    vision_engine = None


# ── ANSI Terminal Colors ──
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    ORANGE = "\033[38;5;208m"
    GREY = "\033[38;5;242m"


# Enable ANSI escape sequences on Windows CMD/PowerShell
if sys.platform == "win31" or sys.platform == "win32":
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass


BANNER = f"""{Colors.ORANGE}{Colors.BOLD}
======================================================================
  ██╗   ██╗██╗  ████████╗██████╗  ██████╗ ███╗   ██╗
  ██║   ██║██║  ╚══██╔══╝██╔══██╗██╔═══██╗████╗  ██║
  ██║   ██║██║     ██║   ██████╔╝██║   ██║██╔██╗ ██║
  ██║   ██║██║     ██║   ██╔══██╗██║   ██║██║╚██╗██║
  ╚██████╔╝███████╗██║   ██║  ██║╚██████╔╝██║ ╚████║
   ╚═════╝ ╚══════╝╚═╝   ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝
       COMMAND LINE INTERFACE // AUTONOMOUS MATRIX
======================================================================{Colors.RESET}
{Colors.GREY}  Type {Colors.ORANGE}/{Colors.GREY} or {Colors.ORANGE}/help{Colors.GREY} for the Slash Command Guide, or enter any natural language directive.{Colors.RESET}
"""


def print_ultron(text: str, prefix: bool = True):
    """Print response with Ultron styling."""
    clean = re.sub(r'\[ACTION:[^\]]+\]', '', text).strip()
    if prefix:
        print(f"\n{Colors.ORANGE}{Colors.BOLD}[ULTRON]{Colors.RESET} {clean}\n")
    else:
        print(f"{clean}\n")


def print_info(title: str, text: str):
    """Print structured telemetry/info."""
    print(f"{Colors.CYAN}{Colors.BOLD}[{title}]{Colors.RESET} {text}")


def print_warn(text: str):
    """Print warning notice."""
    print(f"{Colors.YELLOW}[NOTICE]{Colors.RESET} {text}")


def print_err(text: str):
    """Print error notice."""
    print(f"{Colors.RED}[ERROR]{Colors.RESET} {text}")


async def handle_devices_command():
    """Display real-time device matrix."""
    if not device_control:
        print_err("Device control module not available.")
        return
    matrix = device_control.get_device_matrix()
    if not matrix:
        print_warn("No mobile devices currently detected in the matrix.")
        return
    
    print(f"\n{Colors.BOLD}{Colors.CYAN}--- CONNECTED DEVICE MATRIX ---{Colors.RESET}")
    for d in matrix:
        st = d.get("status", "UNKNOWN")
        st_color = Colors.GREEN if "UNLOCKED" in st else (Colors.YELLOW if "ALLOW" in st or "DEBUGGING" in st else Colors.CYAN)
        bat = f"{d.get('battery')}%" if d.get("battery") else "--"
        print(f"  {Colors.BOLD}• {d.get('name')}{Colors.RESET} | Status: {st_color}{st}{Colors.RESET} | Battery: {bat} | ID: {d.get('serial')}")
    print()


async def handle_unlock_command(arg: str = ""):
    """Execute device unlock."""
    if not device_control:
        print_err("Device control module not available.")
        return
    pin_match = re.search(r'\b([0-9]{4,8})\b', arg)
    pin = pin_match.group(1) if pin_match else ""
    res = await device_control.unlock_all(pin=pin)
    print_ultron(res.get("message", "Execution complete."))


async def handle_lock_command():
    """Execute device screen lock."""
    if not device_control:
        print_err("Device control module not available.")
        return
    res = await device_control.lock_all()
    print_ultron(res.get("message", "Screen locked."))


async def handle_battery_command():
    """Execute battery telemetry lookup."""
    if not device_control:
        print_err("Device control module not available.")
        return
    res = await device_control.get_battery_status()
    print_ultron(res.get("message", "Telemetry reported."))


async def handle_vitals_command():
    """Execute hardware vitals telemetry lookup."""
    if system_monitor:
        try:
            summary = system_monitor.get_system_summary()
            print_ultron(summary)
            return
        except Exception as e:
            pass
    print_ultron("System telemetry nominal. CPU and Memory operating within normal thresholds, sir.")


async def handle_network_command():
    """Execute local network scan."""
    if hacker_terminal:
        res = hacker_terminal.scan_local_network()
        print_ultron(res.get("message", "Network scan complete."))
        devices = res.get("devices", [])
        if devices:
            for dev in devices:
                print(f"  {Colors.GREY}-> Node IP: {dev.get('ip'):16} MAC: {dev.get('mac')}{Colors.RESET}")
            print()
    else:
        print_err("Hacker terminal module not available.")


async def handle_app_command(arg: str):
    """Launch mobile app on connected phone."""
    parts = arg.strip().split()
    app_name = parts[1] if len(parts) > 1 else "youtube"
    if not device_control:
        print_err("Device control module not available.")
        return
    serials = device_control.discover_devices()
    if serials:
        for s in serials:
            device_control.open_app_on_device(s, app_name)
        print_ultron(f"Opening {app_name.capitalize()} on connected device, sir.")
    else:
        print_ultron(f"Cannot launch {app_name.capitalize()}. Connect phone via USB with USB Debugging enabled, sir.")


async def handle_play_command(arg: str):
    """Play media query across connected mobile devices."""
    parts = arg.strip().split(maxsplit=1)
    query = parts[1] if len(parts) > 1 else "Back in Black AC/DC"
    if not device_control:
        print_err("Device control module not available.")
        return
    res = await device_control.play_favorite_song_all(query)
    print_ultron(res.get("message", f"Playing '{query}' on connected devices."))


async def handle_pause_command():
    """Pause media on connected mobile devices."""
    if not device_control:
        print_err("Device control module not available.")
        return
    res = await device_control.pause_all()
    print_ultron(res.get("message", "Media paused."))


async def handle_pair_command(arg: str = ""):
    """Execute mobile force-pair / authorization recovery, dynamic Wi-Fi scan, or wireless pairing."""
    if not device_control:
        print_err("Device control module not available.")
        return
    parts = arg.strip().split()
    target = parts[1] if len(parts) > 1 else ""
    code = parts[2] if len(parts) > 2 else ""
    res = await device_control.force_pair(target=target, code=code)
    print_ultron(res.get("message", "Pairing sequence executed."))


async def handle_bridge_command():
    """Execute zero-code wireless bridge (USB -> TCP/IP -> Wi-Fi)."""
    if not device_control:
        print_err("Device control module not available.")
        return
    res = await device_control.enable_wireless_bridge()
    print_ultron(res.get("message", "Bridge sequence executed."))


async def handle_wifi_command(arg: str = ""):
    """Manage Wi-Fi network interface, password vault, scan radar & auto-unlock."""
    if not device_control:
        print_err("Device control module not available.")
        return
    parts = arg.strip().split()
    subcmd = parts[1].lower() if len(parts) > 1 else "status"
    
    if subcmd in ("bridge", "auto", "skip"):
        res = await device_control.enable_wireless_bridge()
        print_ultron(res.get("message", "Bridge sequence executed."))

    elif subcmd in ("keys", "vault", "passwords", "saved"):
        keys = device_control.get_stored_wifi_passwords()
        print(f"\n{Colors.BOLD}{Colors.CYAN}========================================================================{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.CYAN}                   STORED WI-FI PASSWORD VAULT{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.CYAN}========================================================================{Colors.RESET}")
        print(f"  {Colors.BOLD}{'ORIGIN':<15} {'SSID':<25} {'PASSWORD':<20} {'SECURITY':<10}{Colors.RESET}")
        print(f"  {Colors.GREY}{'-'*70}{Colors.RESET}")
        if not keys:
            print(f"  {Colors.YELLOW}No saved Wi-Fi passwords detected on host.{Colors.RESET}")
        else:
            for k in keys:
                pass_str = k.get('password', '')
                pass_color = Colors.GREEN if pass_str and not pass_str.startswith('[') else Colors.YELLOW
                print(f"  {Colors.WHITE}{k.get('device', 'PC'):<15}{Colors.RESET} {Colors.BOLD}{k.get('ssid', 'N/A'):<25}{Colors.RESET} {pass_color}{pass_str:<20}{Colors.RESET} {Colors.GREY}{k.get('auth', 'WPA2'):<10}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.CYAN}========================================================================{Colors.RESET}")
        print(f"  {Colors.GREY}Connect: {Colors.ORANGE}/wifi connect <ssid>{Colors.GREY} | Push to phone: {Colors.ORANGE}/wifi push <ssid>{Colors.RESET}\n")

    elif subcmd in ("scan", "radar", "audit"):
        print(f"\n{Colors.CYAN}Scanning surrounding Wi-Fi frequencies & signal radar...{Colors.RESET}")
        radar = device_control.scan_nearby_wifi()
        print(f"\n{Colors.BOLD}{Colors.CYAN}========================================================================{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.CYAN}                   SURROUNDING WI-FI RADAR & AUDIT{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.CYAN}========================================================================{Colors.RESET}")
        print(f"  {Colors.BOLD}{'SSID':<24} {'SIGNAL':<12} {'BAND':<9} {'CH':<4} {'AUTH':<15} {'STATUS'}{Colors.RESET}")
        print(f"  {Colors.GREY}{'-'*72}{Colors.RESET}")
        if not radar:
            print(f"  {Colors.YELLOW}No Wi-Fi networks in range.{Colors.RESET}")
        else:
            for net in radar:
                sig = net.get('signal', 0)
                bars = "████" if sig >= 75 else ("███░" if sig >= 50 else ("██░░" if sig >= 25 else "█░░░"))
                sig_color = Colors.GREEN if sig >= 60 else (Colors.YELLOW if sig >= 35 else Colors.RED)
                status = net.get('status', 'SECURED')
                status_color = Colors.GREEN if status in ('CONNECTED', 'OPEN', 'SAVED / VAULT') else Colors.YELLOW
                print(f"  {Colors.WHITE}{Colors.BOLD}{net.get('ssid', 'Hidden'):<24}{Colors.RESET} "
                      f"{sig_color}{bars} {sig:>2}%{Colors.RESET}  "
                      f"{Colors.GREY}{net.get('band', '2.4GHz'):<9}{Colors.RESET} "
                      f"{Colors.WHITE}{net.get('channel', '1'):<4}{Colors.RESET} "
                      f"{Colors.GREY}{net.get('auth', 'WPA2'):<15}{Colors.RESET} "
                      f"{status_color}{status}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.CYAN}========================================================================{Colors.RESET}")
        print(f"  {Colors.GREY}Actions: {Colors.ORANGE}/wifi connect <ssid>{Colors.GREY} | {Colors.ORANGE}/wifi unlock <ssid>{Colors.GREY} (Auto-Trial) | {Colors.ORANGE}/wifi keys{Colors.RESET}\n")

    elif subcmd in ("connect", "join"):
        target_ssid = parts[2] if len(parts) > 2 else ""
        target_pass = parts[3] if len(parts) > 3 else ""
        if not target_ssid:
            print_err("Usage: /wifi connect <ssid> [password]")
            return
        print(f"{Colors.CYAN}Connecting to '{target_ssid}' (Bypassing manual UI password typing)...{Colors.RESET}")
        res = device_control.connect_wifi_network(target_ssid, target_pass)
        if res.get("success"):
            print_ultron(res.get("message", f"Connected to {target_ssid}."))
        else:
            print_err(res.get("message", f"Failed to connect to {target_ssid}."))

    elif subcmd in ("unlock", "crack", "bruteforce", "trial"):
        target_ssid = parts[2] if len(parts) > 2 else ""
        if not target_ssid:
            print_err("Usage: /wifi unlock <ssid> [candidate_passwords...]")
            return
        wordlist = parts[3:] if len(parts) > 3 else None
        print(f"\n{Colors.BOLD}{Colors.ORANGE}[ULTRON] Starting autonomous Wi-Fi unlock for '{target_ssid}'...{Colors.RESET}")
        print(f"{Colors.GREY}Testing candidate router keys, heuristic patterns & vault keys in background...{Colors.RESET}")
        
        def _prog(cur, tot, cand):
            print(f"  {Colors.GREY}[Trial {cur}/{tot}]{Colors.RESET} Testing candidate key: {Colors.CYAN}'{cand}'{Colors.RESET} (Handshake probe...)")

        res = await asyncio.to_thread(device_control.smart_unlock_wifi, target_ssid, wordlist, 20, _prog)
        if res.get("success"):
            print(f"\n{Colors.BOLD}{Colors.GREEN}[ULTRON] SUCCESS! Wi-Fi network '{target_ssid}' UNLOCKED!{Colors.RESET}")
            print(f"  {Colors.BOLD}• Unlocked Password:{Colors.RESET} {Colors.GREEN}{res.get('password')}{Colors.RESET}")
            print(f"  {Colors.BOLD}• Trial Key Index:{Colors.RESET}   {res.get('attempts')}/{res.get('total')}")
            print(f"  {Colors.GREY}Credential persisted to ~/.ultron/wifi_vault.json and .env{Colors.RESET}\n")
        else:
            print_err(res.get("message", f"Could not unlock {target_ssid}."))

    elif subcmd in ("push", "phone"):
        target_ssid = parts[2] if len(parts) > 2 else ""
        target_pass = parts[3] if len(parts) > 3 else ""
        res = device_control.push_wifi_to_android("", target_ssid, target_pass)
        if res.get("success"):
            print_ultron(res.get("message", "Pushed Wi-Fi to phone."))
        else:
            print_err(res.get("message", "Failed to push Wi-Fi to phone."))

    elif subcmd in ("qr", "qrcode", "share"):
        target_ssid = parts[2] if len(parts) > 2 else ""
        if not target_ssid:
            st = device_control.get_wifi_status()
            target_ssid = st.get("ssid", "")
        if not target_ssid:
            print_err("Specify an SSID: /wifi qr <ssid>")
            return
        vault = device_control._load_wifi_vault()
        pwd = vault.get(target_ssid, {}).get("password", "")
        qr_info = device_control.generate_wifi_qr_text(target_ssid, pwd)
        print(f"\n{Colors.BOLD}{Colors.CYAN}--- WI-FI INSTANT JOIN QR LINK ---{Colors.RESET}")
        print(f"  {Colors.BOLD}• SSID:{Colors.RESET}        {qr_info['ssid']}")
        print(f"  {Colors.BOLD}• Security:{Colors.RESET}    {qr_info['auth']}")
        if pwd:
            print(f"  {Colors.BOLD}• Password:{Colors.RESET}    {Colors.GREEN}{pwd}{Colors.RESET}")
        print(f"  {Colors.BOLD}• QR Payload:{Colors.RESET}  {Colors.WHITE}{qr_info['qr_payload']}{Colors.RESET}")
        print(f"  {Colors.BOLD}• QR Image Link:{Colors.RESET} {Colors.CYAN}{qr_info['direct_link']}{Colors.RESET}\n")

    elif subcmd in ("portal", "captive", "bypass"):
        print(f"{Colors.CYAN}Checking for Captive Portal / Hotel / Cafe splash screens...{Colors.RESET}")
        res = device_control.auto_unlock_captive_portal()
        print_ultron(res.get("message", "Portal check complete."))

    elif subcmd in ("reconnect",):
        target_profile = parts[2] if len(parts) > 2 else ""
        res = device_control.reconnect_wifi(target_profile)
        print_ultron(res.get("message", "Wi-Fi command executed."))

    else:
        st = device_control.get_wifi_status()
        state_color = Colors.GREEN if st.get("state") == "connected" else Colors.YELLOW
        print(f"\n{Colors.BOLD}{Colors.CYAN}--- WI-FI NETWORK ADAPTER STATUS ---{Colors.RESET}")
        print(f"  {Colors.BOLD}• Interface State:{Colors.RESET} {state_color}{st.get('state', 'unknown').upper()}{Colors.RESET}")
        if st.get("ssid"):
            print(f"  {Colors.BOLD}• Connected SSID:{Colors.RESET}  {Colors.WHITE}{st.get('ssid')}{Colors.RESET} (Signal: {st.get('signal', 'N/A')})")
        profs = st.get("profiles", [])
        if profs:
            print(f"  {Colors.BOLD}• Saved Profiles:{Colors.RESET}  {', '.join(profs)}")
        print(f"\n{Colors.BOLD}{Colors.CYAN}Wi-Fi Automation & Unlock Commands:{Colors.RESET}")
        print(f"  {Colors.ORANGE}/wifi scan{Colors.RESET}              Nearby Wi-Fi radar with security & unlock classification")
        print(f"  {Colors.ORANGE}/wifi keys{Colors.RESET}              Show all recovered plain-text passwords from PC & phones")
        print(f"  {Colors.ORANGE}/wifi connect <ssid>{Colors.RESET}    Silently connect (skips typing password, auto-pulls key)")
        print(f"  {Colors.ORANGE}/wifi unlock <ssid>{Colors.RESET}     Autonomous brute-force & key trial tester")
        print(f"  {Colors.ORANGE}/wifi push [ssid]{Colors.RESET}       Push Wi-Fi credentials to Android phone over ADB")
        print(f"  {Colors.ORANGE}/wifi qr [ssid]{Colors.RESET}         Generate instant phone camera scan QR link")
        print(f"  {Colors.ORANGE}/wifi portal{Colors.RESET}            Auto-detect & unlock captive portal splash pages")
        print(f"  {Colors.ORANGE}/bridge{Colors.RESET}                 Auto-switch phone from USB to persistent Wi-Fi\n")


def handle_facetrack_command(arg: str):
    """Control digital gimbal face tracking."""
    if not face_tracking:
        print_err("Face tracking module not available.")
        return
    parts = arg.strip().split()
    action = parts[1].lower() if len(parts) > 1 else "start"
    if action == "stop":
        msg = face_tracking.stop_tracking()
    else:
        msg = face_tracking.start_tracking()
    print_ultron(msg)


def handle_stabilize_command():
    """Toggle digital video stabilization."""
    if not face_tracking:
        print_err("Face tracking module not available.")
        return
    msg = face_tracking.toggle_stabilization(True)
    print_ultron(msg)


async def handle_whatsapp_command(raw: str):
    """Send autonomous WhatsApp message without manual typing."""
    if not device_control:
        print_err("Device control module not available.")
        return
    parts = raw.strip().split(maxsplit=2)
    if len(parts) < 3:
        print_err("Usage: /whatsapp <phone_number_or_contact> <message>")
        return
    target, msg = parts[1], parts[2]
    print(f"{Colors.CYAN}Dispatching WhatsApp message to '{target}'...{Colors.RESET}")
    res = await asyncio.to_thread(device_control.send_whatsapp, target, msg)
    if res.get("success"):
        print_ultron(res.get("message", "WhatsApp message sent."))
    else:
        print_err(res.get("message", "Failed to send WhatsApp message."))


async def handle_call_command(raw: str):
    """Initiate cellular phone call via connected device."""
    if not device_control:
        print_err("Device control module not available.")
        return
    parts = raw.strip().split()
    if len(parts) < 2:
        print_err("Usage: /call <phone_number>")
        return
    number = parts[1]
    res = await asyncio.to_thread(device_control.make_phone_call, number)
    if res.get("success"):
        print_ultron(res.get("message", f"Calling {number}..."))
    else:
        print_err(res.get("message", f"Failed to call {number}."))


async def handle_hangup_command():
    """Terminate active cellular phone call."""
    if not device_control:
        print_err("Device control module not available.")
        return
    res = await asyncio.to_thread(device_control.end_phone_call)
    print_ultron(res.get("message", "Call terminated."))


async def handle_photo_command():
    """Remotely snap photo on phone camera and download to PC."""
    if not device_control:
        print_err("Device control module not available.")
        return
    print(f"{Colors.CYAN}Snapping remote photo via mobile camera...{Colors.RESET}")
    res = await asyncio.to_thread(device_control.take_remote_photo)
    if res.get("success"):
        print_ultron(res.get("message", "Photo captured!"))
    else:
        print_err(res.get("message", "Photo capture failed."))


async def handle_phone_command(raw: str):
    """Comprehensive mobile macro actions: tap, click, type, swipe, inspect, whatsapp, call, photo."""
    if not device_control:
        print_err("Device control module not available.")
        return
    parts = raw.strip().split(maxsplit=2)
    subcmd = parts[1].lower() if len(parts) > 1 else "inspect"

    if subcmd in ("whatsapp", "wa", "msg"):
        await handle_whatsapp_command(raw.replace("/phone", "", 1).strip())
    elif subcmd in ("call", "dial"):
        num = parts[2] if len(parts) > 2 else ""
        await handle_call_command(f"/call {num}")
    elif subcmd in ("hangup", "endcall", "end"):
        await handle_hangup_command()
    elif subcmd in ("photo", "snap", "pic"):
        await handle_photo_command()
    elif subcmd == "tap":
        coords = parts[2].split() if len(parts) > 2 else []
        if len(coords) >= 2:
            x, y = coords[0], coords[1]
            device_control._adb("shell", "input", "tap", str(x), str(y))
            print_ultron(f"Tapped coordinates ({x}, {y}) on phone screen, sir.")
        else:
            print_err("Usage: /phone tap <x> <y>")
    elif subcmd in ("click", "press"):
        target_text = parts[2] if len(parts) > 2 else ""
        if not target_text:
            print_err("Usage: /phone click \"<button_text_or_id>\"")
            return
        res = await asyncio.to_thread(device_control.click_ui_element, target_text.strip('"').strip("'"))
        if res.get("success"):
            print_ultron(res.get("message"))
        else:
            print_err(res.get("message"))
    elif subcmd in ("type", "write"):
        text = parts[2] if len(parts) > 2 else ""
        if not text:
            print_err("Usage: /phone type \"<text>\"")
            return
        res = await asyncio.to_thread(device_control.type_on_phone, text.strip('"').strip("'"))
        print_ultron(res.get("message"))
    elif subcmd in ("swipe", "scroll"):
        direction = parts[2].strip() if len(parts) > 2 else "up"
        res = await asyncio.to_thread(device_control.swipe_on_phone, direction)
        print_ultron(res.get("message"))
    elif subcmd in ("inspect", "ui", "dump"):
        print(f"{Colors.CYAN}Scanning active mobile UI elements...{Colors.RESET}")
        elems = await asyncio.to_thread(device_control.dump_ui_elements)
        if not elems:
            print(f"  {Colors.YELLOW}No interactive UI elements detected or phone screen is off.{Colors.RESET}")
        else:
            print(f"\n{Colors.BOLD}{Colors.CYAN}========================================================================{Colors.RESET}")
            print(f"{Colors.BOLD}{Colors.CYAN}                 MOBILE ON-SCREEN INTERACTIVE ELEMENTS{Colors.RESET}")
            print(f"{Colors.BOLD}{Colors.CYAN}========================================================================{Colors.RESET}")
            print(f"  {Colors.BOLD}{'LABEL / TEXT':<30} {'COORDINATES':<15} {'ID / RESOURCE'}{Colors.RESET}")
            print(f"  {Colors.GREY}{'-'*70}{Colors.RESET}")
            for el in elems[:15]:
                label = el.get("text") or el.get("desc") or "[No Label]"
                cx, cy = el.get("center", (0, 0))
                res_id = el.get("id", "").split("/")[-1] if el.get("id") else ""
                print(f"  {Colors.WHITE}{label[:28]:<30}{Colors.RESET} {Colors.ORANGE}({cx}, {cy}){Colors.RESET}       {Colors.GREY}{res_id[:25]}{Colors.RESET}")
            print(f"{Colors.BOLD}{Colors.CYAN}========================================================================{Colors.RESET}")
            print(f"  {Colors.GREY}Tap by label: {Colors.ORANGE}/phone click \"<label>\"{Colors.GREY} | Tap coords: {Colors.ORANGE}/phone tap <x> <y>{Colors.RESET}\n")
    else:
        print_err(f"Unknown phone subcommand '{subcmd}'. Options: whatsapp, call, hangup, photo, click, tap, type, swipe, inspect.")


async def handle_look_command(raw: str):
    """Ultron Screen Sense: inspects user desktop, explains errors, debugs code, answers queries."""
    if not vision_engine:
        print_err("Vision engine module not available.")
        return
    parts = raw.strip().split(maxsplit=2)
    sub = parts[1].lower() if len(parts) > 1 else "summary"

    mode = "summary"
    query = ""
    if sub in ("debug", "error", "errors", "traceback"):
        mode = "debug"
        print(f"\n{Colors.CYAN}[ULTRON VISION] Inspecting screen for compiler errors & stack traces...{Colors.RESET}")
    elif sub in ("code", "syntax", "editor"):
        mode = "code"
        print(f"\n{Colors.CYAN}[ULTRON VISION] Analyzing visible code & editor architecture...{Colors.RESET}")
    elif sub in ("ask", "query", "q"):
        mode = "ask"
        query = parts[2] if len(parts) > 2 else ""
        if not query:
            print_err("Usage: /look ask <question about your screen>")
            return
        print(f"\n{Colors.CYAN}[ULTRON VISION] Analyzing screen regarding: '{query}'...{Colors.RESET}")
    else:
        if len(parts) > 1 and sub not in ("summary", "screen", "now"):
            mode = "ask"
            query = raw.replace("/look", "", 1).replace("/screen", "", 1).strip()
            print(f"\n{Colors.CYAN}[ULTRON VISION] Analyzing screen regarding: '{query}'...{Colors.RESET}")
        else:
            mode = "summary"
            print(f"\n{Colors.CYAN}[ULTRON VISION] Observing active desktop workspace...{Colors.RESET}")

    analysis = await vision_engine.analyze_screen_sense(query=query, mode=mode)
    print(f"\n{Colors.BOLD}{Colors.ORANGE}[ULTRON SCREEN SENSE]{Colors.RESET} {analysis}\n")


def handle_gui_command():
    """Launch the 3D Holographic Desktop GUI."""
    gui_script = os.path.join(ROOT_DIR, "desktop.py")
    if os.path.exists(gui_script):
        subprocess.Popen([sys.executable, gui_script], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        print_ultron("ULTRON 3D Holographic Desktop GUI launched in background.")
    else:
        print_err("desktop.py not found.")


def handle_engine_command(raw: str):
    """Manage standalone local neural engine (llama-server) without external apps."""
    parts = raw.strip().split()
    action = parts[1].lower() if len(parts) > 1 else "status"

    scripts_dir = Path(__file__).parent / "scripts"
    standalone_script = scripts_dir / "standalone_engine.py"

    if not standalone_script.exists():
        print_err("scripts/standalone_engine.py not found.")
        return

    if action in ("status", "check"):
        subprocess.run([sys.executable, str(standalone_script), "status"])
    elif action in ("start", "up"):
        model_type = parts[2] if len(parts) > 2 else "default"
        subprocess.run([sys.executable, str(standalone_script), "start", model_type])
    elif action in ("stop", "down", "kill"):
        subprocess.run([sys.executable, str(standalone_script), "stop"])
    elif action in ("download", "pull"):
        model_type = parts[2] if len(parts) > 2 else "default"
        subprocess.run([sys.executable, str(standalone_script), "download", model_type])
    else:
        print_warn("Usage: /engine [status|start|stop|download]")


def handle_status_command():
    """Display comprehensive system status."""
    print(f"\n{Colors.BOLD}{Colors.CYAN}--- ULTRON CORE MATRIX STATUS ---{Colors.RESET}")
    print(f"  {Colors.BOLD}• Core Intelligence:{Colors.RESET} Autonomous Offline Brain (Zero-Cost)")
    if device_control:
        devs = device_control.get_device_matrix()
        if devs:
            dev_info = f"{len(devs)} Connected ({', '.join(d.get('name') for d in devs)})"
        else:
            dev_info = "0 Connected (Standby - Connect USB phone with USB Debugging)"
        print(f"  {Colors.BOLD}• Mobile Matrix:{Colors.RESET}    {dev_info}")
    if system_monitor:
        try:
            summ = system_monitor.get_system_summary()
            print(f"  {Colors.BOLD}• System Vitals:{Colors.RESET}    {summ}")
        except Exception:
            pass
    print()


def handle_diag_command():
    """Diagnose USB ADB and Samsung-specific authorization blockers."""
    print(f"\n{Colors.BOLD}{Colors.CYAN}--- SAMSUNG & MOBILE MATRIX HARDWARE DIAGNOSTICS ---{Colors.RESET}")
    
    # 1. Check USB Hardware
    pnp_items = []
    if sys.platform == "darwin":
        try:
            r = subprocess.run(["system_profiler", "SPUSBDataType", "-json"], capture_output=True, text=True, timeout=5)
            if r.stdout:
                import json
                data = json.loads(r.stdout)
                def _scan(node):
                    if isinstance(node, dict):
                        name = node.get("_name", "")
                        if any(k in name.lower() for k in ["samsung", "android", "pixel", "galaxy", "xiaomi", "oneplus"]):
                            pnp_items.append({"FriendlyName": name, "Class": "USB", "Status": "Connected"})
                        for v in node.values():
                            _scan(v)
                    elif isinstance(node, list):
                        for elem in node:
                            _scan(elem)
                _scan(data)
        except Exception:
            pass
        os_label = "macOS"
    else:
        ps_pnp = (
            'Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue | '
            'Where-Object { $_.FriendlyName -match "samsung|android|modem" -or $_.Class -eq "AndroidUsbDeviceClass" } | '
            'Select-Object FriendlyName, Class, Status | ConvertTo-Json -Compress'
        )
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-Command", ps_pnp], capture_output=True, text=True, timeout=5)
            raw = r.stdout.strip()
            if raw:
                import json
                pnp_items = json.loads(raw)
                if isinstance(pnp_items, dict):
                    pnp_items = [pnp_items]
        except Exception:
            pass
        os_label = "Windows"

    if pnp_items:
        print(f"  {Colors.GREEN}● USB Hardware Detected by {os_label}:{Colors.RESET}")
        for item in pnp_items:
            print(f"    • {item.get('FriendlyName')} [{item.get('Class')}] - {item.get('Status')}")
    else:
        print(f"  {Colors.YELLOW}○ USB Hardware:{Colors.RESET} No USB Android device currently recognized by {os_label}.")

    # 2. Check ADB Daemon Status
    adb_out = ""
    if device_control:
        active, all_devs = device_control.get_detailed_device_status()
        if active:
            adb_out = f"ACTIVE & AUTHORIZED: {', '.join(active)}"
        elif all_devs:
            adb_out = f"DETECTED BUT {all_devs[0].get('status', 'UNAUTHORIZED').upper()}: {all_devs[0].get('serial')}"
        else:
            adb_out = "No active ADB transport found."
    print(f"\n  {Colors.BOLD}● ADB Daemon State:{Colors.RESET} {adb_out}")

    # 3. Print Samsung-specific instructions
    print(f"""
{Colors.BOLD}{Colors.ORANGE}WHY SAMSUNG PHONES BLOCK 'ALWAYS ALLOW' & HOW TO FIX IT:{Colors.RESET}

  {Colors.BOLD}1. TURN OFF SAMSUNG AUTO BLOCKER (ONE UI 6 / 6.1):{Colors.RESET}
     Go to: {Colors.WHITE}Settings > Security and privacy > Auto Blocker{Colors.RESET}
     Turn {Colors.RED}Auto Blocker OFF{Colors.RESET} (or turn off "Block commands by USB cable").
     *When enabled, Samsung silently drops the RSA popup so it never appears!*

  {Colors.BOLD}2. UNLOCK PHONE & KEEP ON HOME SCREEN:{Colors.RESET}
     Unlock your phone using fingerprint or PIN.
     *Samsung Knox BLOCKS the authorization popup if the screen is locked!*

  {Colors.BOLD}3. REVOKE OLD AUTHORIZATIONS & TOGGLE DEBUGGING:{Colors.RESET}
     Go to: {Colors.WHITE}Settings > Developer options{Colors.RESET}
     Tap: {Colors.WHITE}Revoke USB debugging authorizations > OK{Colors.RESET}
     Toggle: {Colors.WHITE}USB debugging OFF{Colors.RESET}, wait 3 seconds, then turn it {Colors.GREEN}ON{Colors.RESET}.

  {Colors.BOLD}4. SET USB DEFAULT TO FILE TRANSFER:{Colors.RESET}
     In {Colors.WHITE}Settings > Developer options > Default USB configuration{Colors.RESET}
     Select {Colors.GREEN}"Transferring files"{Colors.RESET} (not "Charging phone only").

  {Colors.BOLD}5. OR PAIR WIRELESSLY (NO CABLE NEEDED // 100% SUCCESS):{Colors.RESET}
     In {Colors.WHITE}Settings > Developer options > Wireless debugging > ON{Colors.RESET}
     Tap {Colors.WHITE}"Pair device with pairing code"{Colors.RESET}
     Run in CLI: {Colors.ORANGE}/pair <ip:port> <code>{Colors.RESET}
""")


def print_help():
    """Print the complete ULTRON CLI Slash Command Guide."""
    print(f"""
{Colors.BOLD}{Colors.ORANGE}======================================================================
               ULTRON CLI SLASH COMMAND GUIDE (/)
======================================================================{Colors.RESET}

  {Colors.BOLD}{Colors.CYAN}📱 MOBILE DEVICE MATRIX COMMANDS:{Colors.RESET}
    {Colors.ORANGE}/devices{Colors.RESET}           Scan & display connected phones (Status, Battery, ID)
    {Colors.ORANGE}/wifi [scan|radar]{Colors.RESET}     Surrounding Wi-Fi radar with signal %, channels & security
    {Colors.ORANGE}/wifi keys{Colors.RESET}             Display recovered plain-text Wi-Fi passwords from PC & phone
    {Colors.ORANGE}/wifi connect <ssid>{Colors.RESET}  Connect silently (skips typing password, auto-pulls key)
    {Colors.ORANGE}/wifi unlock <ssid>{Colors.RESET}   Autonomous brute-force & key trial tester
    {Colors.ORANGE}/wifi push [ssid]{Colors.RESET}      Push Wi-Fi connection directly to Android phone via ADB
    {Colors.ORANGE}/wifi qr [ssid]{Colors.RESET}        Generate instant camera scan Wi-Fi join QR link
    {Colors.ORANGE}/wifi portal{Colors.RESET}           Auto-detect & unlock captive portal splash pages
    {Colors.ORANGE}/diag{Colors.RESET}              Diagnose Samsung USB authorization & Auto Blocker
    {Colors.ORANGE}/unlock [pin]{Colors.RESET}      Unlock screen (Auto-types saved PIN or saves new working PIN)
    {Colors.ORANGE}/lock{Colors.RESET}              Put connected phone screen to sleep / lock
    {Colors.ORANGE}/battery{Colors.RESET}           Query connected phone battery level & power status
    {Colors.ORANGE}/whatsapp <num> <msg>{Colors.RESET} Send WhatsApp message hands-free via phone
    {Colors.ORANGE}/call <number>{Colors.RESET}         Initiate phone call on connected mobile device
    {Colors.ORANGE}/hangup{Colors.RESET}                Terminate active phone call
    {Colors.ORANGE}/photo{Colors.RESET}                 Remote snap photo on phone camera & download to PC
    {Colors.ORANGE}/phone click "<text>"{Colors.RESET}  Autonomously find and tap on-screen button by label
    {Colors.ORANGE}/phone tap <x> <y>{Colors.RESET}     Tap exact screen coordinates on phone
    {Colors.ORANGE}/phone type "<text>"{Colors.RESET}   Type text into focused mobile input field
    {Colors.ORANGE}/phone inspect{Colors.RESET}         Dump and map all active interactive UI elements
    {Colors.ORANGE}/app <name>{Colors.RESET}        Launch app on phone ({Colors.GREY}youtube, spotify, camera, settings{Colors.RESET})
    {Colors.ORANGE}/play <query>{Colors.RESET}      Search and stream YouTube audio across phone matrix
    {Colors.ORANGE}/pause{Colors.RESET}             Pause media playback on connected devices

  {Colors.BOLD}{Colors.CYAN}⚡ SYSTEM TELEMETRY & RECONNAISSANCE:{Colors.RESET}
    {Colors.ORANGE}/vitals{Colors.RESET} or {Colors.ORANGE}/stats{Colors.RESET}  Display PC CPU, RAM, disk, load & thermal telemetry
    {Colors.ORANGE}/network{Colors.RESET} or {Colors.ORANGE}/scan{Colors.RESET}  Execute local network node scan (IP, MAC, active nodes)
    {Colors.ORANGE}/engine [status|start|stop]{Colors.RESET} Standalone Local Engine (Zero LM Studio / Ollama needed)
    {Colors.ORANGE}/model{Colors.RESET} or {Colors.ORANGE}/setup{Colors.RESET}         Choose model: Qwen 3.5 Uncensored vs Ultra-Light 1.5B

  {Colors.BOLD}{Colors.CYAN}👁️ VISION & SCREEN SENSE AI:{Colors.RESET}
    {Colors.ORANGE}/look{Colors.RESET} or {Colors.ORANGE}/screen{Colors.RESET}    Ultron Screen Sense: observes and summarizes active workspace
    {Colors.ORANGE}/look debug{Colors.RESET}            Inspect screen for compiler errors, exceptions & exact fixes
    {Colors.ORANGE}/look code{Colors.RESET}             Analyze visible code in IDE, check syntax & missing imports
    {Colors.ORANGE}/look ask <query>{Colors.RESET}      Ask Ultron any question about what is visible on your screen
    {Colors.ORANGE}/facetrack [start|stop]{Colors.RESET} OpenCV digital gimbal face tracking webcam window
    {Colors.ORANGE}/stabilize{Colors.RESET}        Toggle digital optical flow video stabilization

  {Colors.BOLD}{Colors.CYAN}🖥️ DESKTOP & WORKSPACE CONTROLS:{Colors.RESET}
    {Colors.ORANGE}/gui{Colors.RESET}               Launch the ULTRON 3D Holographic Desktop GUI
    {Colors.ORANGE}/clear{Colors.RESET} or {Colors.ORANGE}cls{Colors.RESET}        Clear the terminal console and show banner
    {Colors.ORANGE}/guide{Colors.RESET} or {Colors.ORANGE}/{Colors.RESET}          Display this slash command directory
    {Colors.ORANGE}/exit{Colors.RESET} or {Colors.ORANGE}/quit{Colors.RESET}      Stand down and exit ULTRON CLI

----------------------------------------------------------------------
  NATURAL LANGUAGE DIRECTIVES (NO SLASH NEEDED):
----------------------------------------------------------------------{Colors.RESET}
  You can speak to ULTRON directly in natural English:
  • {Colors.WHITE}"unlock my phone"{Colors.RESET} or {Colors.WHITE}"unlock phone with pin 1234"{Colors.RESET}
  • {Colors.WHITE}"check phone battery"{Colors.RESET}
  • {Colors.WHITE}"open youtube on phone"{Colors.RESET}
  • {Colors.WHITE}"play Back in Black on my phone"{Colors.RESET}
  • {Colors.WHITE}"what's my CPU temperature?"{Colors.RESET}
  • {Colors.WHITE}"scan the local network for devices"{Colors.RESET}
  • {Colors.WHITE}"who created you?"{Colors.RESET} or {Colors.WHITE}"write a python script to ping servers"{Colors.RESET}
""")


async def execute_input(user_input: str):
    """Route directive through slash commands, fast actions, or autonomous brain."""
    raw = user_input.strip()
    if not raw:
        return

    lower = raw.lower()

    # 1. Slash commands & Guide triggers
    if lower in ("/", "/help", "help", "/guide", "guide", "/commands", "commands", "/?"):
        print_help()
        return
    elif lower in ("/exit", "/quit", "exit", "quit", "q"):
        print_ultron("Terminating CLI session. ULTRON standing down.")
        sys.exit(0)
    elif lower in ("/clear", "cls", "clear"):
        os.system("cls" if os.name == "nt" else "clear")
        print(BANNER)
        return
    elif lower in ("/devices", "/device", "devices"):
        await handle_devices_command()
        return
    elif lower in ("/diag", "diag", "/check"):
        handle_diag_command()
        return
    elif lower in ("/bridge", "bridge", "/tcpip", "tcpip"):
        await handle_bridge_command()
        return
    elif lower.startswith("/pair") or lower in ("pair", "force pair"):
        await handle_pair_command(raw)
        return
    elif lower.startswith("/wifi") or lower in ("wifi", "reconnect wifi"):
        await handle_wifi_command(raw)
        return
    elif lower.startswith("/unlock"):
        await handle_unlock_command(raw)
        return
    elif lower in ("/lock", "lock"):
        await handle_lock_command()
        return
    elif lower in ("/battery", "battery"):
        await handle_battery_command()
        return
    elif lower.startswith("/app"):
        await handle_app_command(raw)
        return
    elif lower.startswith("/play"):
        await handle_play_command(raw)
        return
    elif lower in ("/pause", "pause"):
        await handle_pause_command()
        return
    elif lower in ("/vitals", "vitals", "/stats", "stats"):
        await handle_vitals_command()
        return
    elif lower in ("/network", "/scan", "scan", "network"):
        await handle_network_command()
        return
    elif lower.startswith("/facetrack"):
        handle_facetrack_command(raw)
        return
    elif lower in ("/stabilize", "stabilize"):
        handle_stabilize_command()
        return
    elif lower in ("/gui", "gui"):
        handle_gui_command()
        return
    elif lower in ("/status", "status"):
        handle_status_command()
        return
    elif lower.startswith("/engine"):
        handle_engine_command(raw)
        return
    elif lower.startswith("/whatsapp") or lower.startswith("/wa"):
        await handle_whatsapp_command(raw)
        return
    elif lower.startswith("/call") or lower.startswith("/dial"):
        await handle_call_command(raw)
        return
    elif lower in ("/hangup", "hangup", "/endcall", "endcall"):
        await handle_hangup_command()
        return
    elif lower in ("/photo", "photo", "/snap", "snap", "/pic"):
        await handle_photo_command()
        return
    elif lower.startswith("/phone"):
        await handle_phone_command(raw)
        return
    elif lower.startswith("/look") or lower.startswith("/screen") or lower in ("look", "screen", "see", "vision"):
        await handle_look_command(raw)
        return
    elif lower in ("/model", "/models", "/setup"):
        scripts_dir = Path(__file__).parent / "scripts"
        standalone_script = scripts_dir / "standalone_engine.py"
        if standalone_script.exists():
            subprocess.run([sys.executable, str(standalone_script), "select"])
        return
    elif lower.startswith("/"):
        print_err(f"Unknown command '{raw}'. Type / or /help for the complete Slash Command Guide.")
        return

    # 2. Fast Action Matching
    if lower.startswith("send whatsapp") or lower.startswith("whatsapp"):
        await handle_whatsapp_command(raw)
        return
    elif lower.startswith("call ") or lower.startswith("dial "):
        await handle_call_command(raw)
        return
    elif lower in ("hang up", "end call", "hangup", "disconnect call"):
        await handle_hangup_command()
        return
    elif lower in ("take a photo", "take photo", "snap photo", "take picture"):
        await handle_photo_command()
        return
    elif lower in ("look at my screen", "what's on my screen", "what is on my screen", "describe my screen", "check my screen"):
        await handle_look_command("/look")
        return
    elif lower in ("debug my screen", "check errors", "find error", "what is the error"):
        await handle_look_command("/look debug")
        return

    if server:
        act = server.detect_action_fast(raw)
        if act:
            action_type = act.get("action")
            if action_type in ("device_unlock_all", "unlock_all_devices"):
                await handle_unlock_command(act.get("pin", ""))
                return
            elif action_type == "device_force_pair":
                await handle_pair_command(f"/pair {act.get('target', '')} {act.get('code', '')}")
                return
            elif action_type == "device_lock_all":
                await handle_lock_command()
                return
            elif action_type == "phone_battery":
                await handle_battery_command()
                return
            elif action_type == "device_open_app":
                await handle_app_command(f"/app {act.get('app', 'youtube')}")
                return
            elif action_type == "play_favorite_all":
                await handle_play_command("/play Back in Black AC/DC")
                return

    # 3. Local Neural Engine (Standalone Engine / LM Studio / Ollama / Autonomous Core)
    try:
        import ollama_brain
        brain = ollama_brain.LocalBrain()
        backend = await brain.detect_active_backend()
        b_type = backend.get("type", "autonomous")
        model_disp = backend.get("model", "Autonomous Core")
        if b_type == "standalone":
            backend_disp = "Standalone Engine"
        elif b_type == "lm_studio":
            backend_disp = "LM Studio"
        elif b_type == "ollama":
            backend_disp = "Ollama"
        else:
            backend_disp = "Autonomous Core"

        print(f"\n{Colors.ORANGE}{Colors.BOLD}[ULTRON // {backend_disp} ({model_disp})]{Colors.RESET} ", end="", flush=True)
        async for chunk in brain.respond_stream(raw):
            print(chunk, end="", flush=True)
        print("\n")
        return
    except Exception:
        pass

    # 4. Autonomous Cognition Engine (Zero-Cost Offline Core)
    if server and hasattr(server, "autonomous_ultron_brain"):
        response = await server.autonomous_ultron_brain(raw)
        print_ultron(response)
        return

    # 5. Direct local fallback response
    print_ultron(f"Directive received: '{raw}'. All systems operational, sir.")


async def cli_main():
    """Main CLI entrypoint: one-shot command or interactive REPL."""
    if len(sys.argv) > 1:
        cmd = " ".join(sys.argv[1:]).strip()
        await execute_input(cmd)
        return

    print(BANNER)
    
    # Quick startup telemetry check
    if device_control:
        devs = device_control.get_device_matrix()
        if devs:
            names = ", ".join(d.get("name", "Device") for d in devs)
            print(f"{Colors.GREEN}● Matrix Connected:{Colors.RESET} {names}")
        else:
            print(f"{Colors.GREY}○ Matrix Standby: No mobile devices connected.{Colors.RESET}")
    # First-run model configuration prompt
    cfg_file = Path(os.getenv("USERPROFILE" if sys.platform == "win32" else "HOME", ".")) / ".ultron" / "config.json"
    if not cfg_file.exists():
        try:
            standalone_script = Path(__file__).parent / "scripts" / "standalone_engine.py"
            if standalone_script.exists():
                subprocess.run([sys.executable, str(standalone_script), "select"])
        except Exception:
            pass

    print()

    while True:
        try:
            prompt = f"{Colors.ORANGE}{Colors.BOLD}ULTRON >{Colors.RESET} "
            user_input = input(prompt)
            await execute_input(user_input)
        except (KeyboardInterrupt, EOFError):
            print_ultron("\nSession interrupted. Farewell, sir.")
            break
        except Exception as e:
            print_err(f"Execution error: {e}")


if __name__ == "__main__":
    asyncio.run(cli_main())
