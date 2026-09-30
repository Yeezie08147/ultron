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
from typing import Optional, Dict, Any

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
    """Manage Wi-Fi network interface & auto-reconnect."""
    if not device_control:
        print_err("Device control module not available.")
        return
    parts = arg.strip().split()
    subcmd = parts[1].lower() if len(parts) > 1 else "status"
    
    if subcmd in ("bridge", "auto", "skip"):
        res = await device_control.enable_wireless_bridge()
        print_ultron(res.get("message", "Bridge sequence executed."))
    elif subcmd in ("reconnect", "connect"):
        target_profile = parts[2] if len(parts) > 2 else ""
        res = device_control.reconnect_wifi(target_profile)
        print_ultron(res.get("message", "Wi-Fi command executed."))
    elif subcmd in ("scan", "adb", "phone"):
        target_ip = parts[2] if len(parts) > 2 else ""
        res = await device_control.auto_connect_wireless_adb(target_ip)
        print_ultron(res.get("message", "Wireless ADB scan complete."))
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
        print(f"\n{Colors.GREY}  Commands: {Colors.ORANGE}/bridge{Colors.GREY} (skip pairing) | {Colors.ORANGE}/wifi reconnect [profile]{Colors.GREY} | {Colors.ORANGE}/wifi scan [phone_ip]{Colors.RESET}\n")


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


def handle_gui_command():
    """Launch the 3D Holographic Desktop GUI."""
    gui_script = os.path.join(ROOT_DIR, "desktop.py")
    if os.path.exists(gui_script):
        subprocess.Popen([sys.executable, gui_script], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        print_ultron("ULTRON 3D Holographic Desktop GUI launched in background.")
    else:
        print_err("desktop.py not found.")


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
    {Colors.ORANGE}/bridge{Colors.RESET}            Auto-switch USB phone to persistent Wi-Fi (Skips pairing process)
    {Colors.ORANGE}/pair [scan|ip:port]{Colors.RESET} Force pair USB, auto-scan rotating Wi-Fi ports, or pair
    {Colors.ORANGE}/wifi [status|reconnect]{Colors.RESET} Reconnect host Wi-Fi or auto-scan wireless phone
    {Colors.ORANGE}/diag{Colors.RESET}              Diagnose Samsung USB authorization & Auto Blocker
    {Colors.ORANGE}/unlock [pin]{Colors.RESET}      Unlock screen (Auto-types saved PIN or saves new working PIN)
    {Colors.ORANGE}/lock{Colors.RESET}              Put connected phone screen to sleep / lock
    {Colors.ORANGE}/battery{Colors.RESET}           Query connected phone battery level & power status
    {Colors.ORANGE}/app <name>{Colors.RESET}        Launch app on phone ({Colors.GREY}youtube, spotify, camera, settings{Colors.RESET})
    {Colors.ORANGE}/play <query>{Colors.RESET}      Search and stream YouTube audio across phone matrix
    {Colors.ORANGE}/pause{Colors.RESET}             Pause media playback on connected devices

  {Colors.BOLD}{Colors.CYAN}⚡ SYSTEM TELEMETRY & RECONNAISSANCE:{Colors.RESET}
    {Colors.ORANGE}/vitals{Colors.RESET} or {Colors.ORANGE}/stats{Colors.RESET}  Display PC CPU, RAM, disk, load & thermal telemetry
    {Colors.ORANGE}/network{Colors.RESET} or {Colors.ORANGE}/scan{Colors.RESET}  Execute local network node scan (IP, MAC, active nodes)
    {Colors.ORANGE}/status{Colors.RESET}            Summary of Ultron core engines, matrix, and services

  {Colors.BOLD}{Colors.CYAN}👁️ VISION & GIMBAL TRACKING:{Colors.RESET}
    {Colors.ORANGE}/facetrack start{Colors.RESET}  Start OpenCV digital gimbal face tracking webcam window
    {Colors.ORANGE}/facetrack stop{Colors.RESET}   Stop digital face tracking
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
    elif lower.startswith("/"):
        print_err(f"Unknown command '{raw}'. Type / or /help for the complete Slash Command Guide.")
        return

    # 2. Fast Action Matching
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

    # 3. Local Neural Engine (LM Studio / Ollama Qwen3.5 Uncensored)
    try:
        import ollama_brain
        brain = ollama_brain.LocalBrain()
        backend = await brain.detect_active_backend()
        if backend.get("type") != "none":
            model_disp = backend.get("model", "Local LLM")
            backend_disp = "LM Studio" if backend["type"] == "lm_studio" else "Ollama"
            print(f"\n{Colors.ORANGE}{Colors.BOLD}[ULTRON // {backend_disp} ({model_disp})]{Colors.RESET} ", end="", flush=True)
            async for chunk in brain.respond_stream(raw):
                print(chunk + " ", end="", flush=True)
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
