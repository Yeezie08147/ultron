"""
startup_manager.py — ULTRON Windows Startup & Background Stealth Manager.

Configures ULTRON to launch silently on Windows boot:
- Writes stealth VBS wrapper into Windows Startup folder (%APPDATA%\\...\\Startup)
- ZERO taskbar presence on boot
- Full background voice recognition and desktop control active immediately
"""

import os
import sys
import logging
from pathlib import Path
from typing import Dict, Any

log = logging.getLogger("ultron.startup")

STARTUP_DIR = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
ULTRON_DIR = Path("C:/Ultron/Ultron").resolve()
VBS_STARTUP_PATH = STARTUP_DIR / "ULTRON_Ghost_Startup.vbs"


def get_startup_status() -> Dict[str, Any]:
    """Check if ULTRON is configured to launch at Windows startup."""
    is_enabled = VBS_STARTUP_PATH.exists()
    return {
        "enabled": is_enabled,
        "path": str(VBS_STARTUP_PATH),
        "message": f"ULTRON Windows Startup Stealth Mode is {'ENABLED' if is_enabled else 'DISABLED'}, sir."
    }


def enable_startup_stealth() -> Dict[str, Any]:
    """Install stealth VBS script in Windows Startup directory."""
    try:
        STARTUP_DIR.mkdir(parents=True, exist_ok=True)
        
        # Python executable path (prefer pythonw for zero console window)
        venv_pythonw = ULTRON_DIR / ".venv_win313" / "Scripts" / "pythonw.exe"
        if not venv_pythonw.exists():
            venv_pythonw = ULTRON_DIR / ".venv_win313" / "Scripts" / "python.exe"

        desktop_py = ULTRON_DIR / "desktop.py"

        # VBScript to launch pythonw completely hidden without window
        vbs_content = f'''Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "{ULTRON_DIR}"
WshShell.Run """{venv_pythonw}"" ""{desktop_py}"" --stealth", 0, False
'''
        VBS_STARTUP_PATH.write_text(vbs_content, encoding="utf-8")
        log.info(f"Installed startup stealth launcher at {VBS_STARTUP_PATH}")

        return {
            "success": True,
            "path": str(VBS_STARTUP_PATH),
            "message": "ULTRON configured to run silently on Windows startup. Taskbar icon hidden, voice daemon online, sir."
        }
    except Exception as e:
        log.error(f"Failed to enable startup: {e}")
        return {"success": False, "message": f"Failed to configure Windows startup: {e}"}


def disable_startup_stealth() -> Dict[str, Any]:
    """Remove ULTRON from Windows Startup directory."""
    try:
        if VBS_STARTUP_PATH.exists():
            VBS_STARTUP_PATH.unlink()
            return {"success": True, "message": "ULTRON removed from Windows startup, sir."}
        return {"success": True, "message": "ULTRON was not in Windows startup, sir."}
    except Exception as e:
        return {"success": False, "message": f"Failed to disable startup: {e}"}


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--disable":
        print(disable_startup_stealth()["message"])
    else:
        print(enable_startup_stealth()["message"])
