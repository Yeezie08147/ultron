"""
system_monitor.py — ULTRON Real-Time System & Workspace Monitoring.

Tracks:
- Hardware Telemetry (CPU, RAM, Disk, Battery, Network)
- Focused Application & Window history
- System Health Alerts (High CPU, Low Memory, Battery Low)
- Real-time summaries for voice and AI context injection
"""

import time
import logging
import threading
from typing import Dict, Any, List, Optional

try:
    import psutil
except ImportError:
    psutil = None

from desktop_control import get_foreground_window

log = logging.getLogger("ultron.monitor")

# Global real-time state snapshot
_system_snapshot: Dict[str, Any] = {
    "cpu_percent": 0.0,
    "ram_percent": 0.0,
    "ram_used_gb": 0.0,
    "ram_total_gb": 0.0,
    "disk_percent": 0.0,
    "battery_percent": None,
    "battery_plugged": None,
    "active_window": "Unknown",
    "top_processes": [],
    "updated_at": 0.0,
}

_monitor_thread: Optional[threading.Thread] = None
_monitor_running = False


def update_system_metrics() -> Dict[str, Any]:
    """Poll the OS for the latest telemetry metrics."""
    global _system_snapshot
    if not psutil:
        return _system_snapshot

    try:
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        battery = psutil.sensors_battery()
        bat_pct = round(battery.percent, 1) if battery else None
        bat_plugged = battery.power_plugged if battery else None

        active_win = get_foreground_window()
        active_title = active_win.get("title", "Unknown")

        # Top 3 CPU-consuming processes
        procs = []
        for p in sorted(psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']),
                        key=lambda x: x.info.get('cpu_percent') or 0,
                        reverse=True)[:3]:
            name = p.info.get('name', 'unknown')
            cpu_p = p.info.get('cpu_percent') or 0
            if cpu_p > 0.1:
                procs.append(f"{name} ({cpu_p:.1f}%)")

        _system_snapshot = {
            "cpu_percent": cpu,
            "ram_percent": mem.percent,
            "ram_used_gb": round(mem.used / (1024**3), 1),
            "ram_total_gb": round(mem.total / (1024**3), 1),
            "disk_percent": disk.percent,
            "battery_percent": bat_pct,
            "battery_plugged": bat_plugged,
            "active_window": active_title,
            "top_processes": procs,
            "updated_at": time.time(),
        }
    except Exception as e:
        log.debug(f"Error updating system metrics: {e}")

    return _system_snapshot


def get_system_summary() -> str:
    """Produce a concise, voice-friendly system status report."""
    metrics = update_system_metrics()
    parts = [
        f"CPU load is at {metrics['cpu_percent']:.0f} percent.",
        f"RAM usage is at {metrics['ram_percent']:.0f} percent ({metrics['ram_used_gb']} of {metrics['ram_total_gb']} GB used).",
        f"Primary disk is {metrics['disk_percent']:.0f} percent full."
    ]
    if metrics["battery_percent"] is not None:
        plugged_str = "plugged in" if metrics["battery_plugged"] else "on battery"
        parts.append(f"Battery is at {metrics['battery_percent']:.0f} percent ({plugged_str}).")
    if metrics["active_window"] and metrics["active_window"] != "Unknown":
        parts.append(f"Currently focused on: {metrics['active_window'][:50]}.")
    if metrics["top_processes"]:
        parts.append(f"Top active processes: {', '.join(metrics['top_processes'])}.")

    return " ".join(parts)


def get_context_for_prompt() -> str:
    """Format system metrics concisely for LLM prompt injection."""
    m = _system_snapshot
    if m["updated_at"] == 0:
        m = update_system_metrics()
    bat_str = f", Battery: {m['battery_percent']}%" if m['battery_percent'] is not None else ""
    return f"Active Window: {m['active_window']} | CPU: {m['cpu_percent']}% | RAM: {m['ram_percent']}% ({m['ram_used_gb']}/{m['ram_total_gb']}GB){bat_str}"


def _monitor_loop(poll_interval: float = 5.0):
    """Background monitoring loop updating global snapshot."""
    global _monitor_running
    log.info("ULTRON Real-time System Monitor loop started")
    while _monitor_running:
        try:
            update_system_metrics()
        except Exception as e:
            log.error(f"System monitor loop error: {e}")
        time.sleep(poll_interval)


def start_monitor():
    """Start the background telemetry monitor daemon."""
    global _monitor_thread, _monitor_running
    if _monitor_running:
        return
    _monitor_running = True
    _monitor_thread = threading.Thread(target=_monitor_loop, daemon=True)
    _monitor_thread.start()


def stop_monitor():
    """Stop the background telemetry monitor."""
    global _monitor_running
    _monitor_running = False
