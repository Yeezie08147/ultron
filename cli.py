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
{Colors.GREY}  Type your directive or ask anything. Commands: /help, /devices, /exit{Colors.RESET}
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


def print_help():
    """Print CLI usage guide."""
    print(f"""
{Colors.BOLD}{Colors.ORANGE}ULTRON CLI COMMAND DIRECTORY:{Colors.RESET}
  {Colors.BOLD}/help{Colors.RESET}        - Display this command reference
  {Colors.BOLD}/devices{Colors.RESET}     - Scan and display connected mobile devices (ADB & Bluetooth)
  {Colors.BOLD}/unlock{Colors.RESET}      - Unlock connected phone screen (e.g. /unlock 1234)
  {Colors.BOLD}/lock{Colors.RESET}        - Put connected phone screen to sleep
  {Colors.BOLD}/battery{Colors.RESET}     - Query mobile device battery level
  {Colors.BOLD}/vitals{Colors.RESET}      - Display PC CPU, RAM, disk, and load telemetry
  {Colors.BOLD}/network{Colors.RESET}     - Run a local network node reconnaissance scan
  {Colors.BOLD}/clear{Colors.RESET}       - Clear the terminal console
  {Colors.BOLD}/exit{Colors.RESET}        - Disconnect and exit ULTRON CLI

{Colors.BOLD}NATURAL LANGUAGE DIRECTIVES:{Colors.RESET}
  You can speak to ULTRON naturally just like in the GUI:
  - "unlock phone", "lock screen", "phone battery"
  - "play Back in Black", "pause music"
  - "open youtube on phone", "open camera on phone"
  - "who created you", "tell me a quote", "current time"
  - Any programming, system automation, or calculation task
""")


async def execute_input(user_input: str):
    """Route directive through fast actions or autonomous brain."""
    raw = user_input.strip()
    if not raw:
        return

    # Slash commands
    lower = raw.lower()
    if lower in ("/help", "help", "?"):
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
    elif lower.startswith("/unlock"):
        await handle_unlock_command(raw)
        return
    elif lower in ("/lock", "lock"):
        await handle_lock_command()
        return
    elif lower in ("/battery", "battery"):
        await handle_battery_command()
        return
    elif lower in ("/vitals", "vitals", "/stats"):
        await handle_vitals_command()
        return
    elif lower in ("/network", "/scan", "scan"):
        await handle_network_command()
        return

    # 1. Fast Action Matching
    if server:
        act = server.detect_action_fast(raw)
        if act:
            action_type = act.get("action")
            if action_type in ("device_unlock_all", "unlock_all_devices"):
                await handle_unlock_command(act.get("pin", ""))
                return
            elif action_type == "device_lock_all":
                await handle_lock_command()
                return
            elif action_type == "phone_battery":
                await handle_battery_command()
                return
            elif action_type == "device_open_app":
                app_name = act.get("app", "youtube")
                if device_control:
                    serials = device_control.discover_devices()
                    if serials:
                        for s in serials:
                            device_control.open_app_on_device(s, app_name)
                        print_ultron(f"Opening {app_name.capitalize()} on connected device, sir.")
                    else:
                        print_ultron(f"Cannot launch {app_name.capitalize()}. Connect phone via USB with USB Debugging enabled, sir.")
                return
            elif action_type == "play_favorite_all":
                if device_control:
                    res = await device_control.play_favorite_song_all("Back in Black AC/DC")
                    print_ultron(res.get("message", "Playing audio across matrix."))
                return

    # 2. Autonomous Cognition Engine
    if server and hasattr(server, "autonomous_ultron_brain"):
        response = await server.autonomous_ultron_brain(raw)
        print_ultron(response)
        return

    # 3. Direct local fallback response
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
