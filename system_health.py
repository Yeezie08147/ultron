import psutil
import logging
import asyncio

log = logging.getLogger("ultron.system_health")

async def get_system_report() -> str:
    """Returns a string describing CPU, RAM, and Battery health."""
    try:
        cpu = psutil.cpu_percent(interval=0.5)
        ram = psutil.virtual_memory()
        
        report = f"System Status: CPU at {cpu}%, RAM at {ram.percent}%. "
        
        if hasattr(psutil, "sensors_battery"):
            battery = psutil.sensors_battery()
            if battery:
                plugged = "plugged in" if battery.power_plugged else "on battery"
                report += f"Power is at {battery.percent}% ({plugged})."
                
        return report
    except Exception as e:
        log.error(f"Health check failed: {e}")
        return "I could not retrieve system health metrics."

async def health_monitor_daemon(ws_manager):
    """Runs in the background and alerts if battery is low or CPU is critical."""
    while True:
        try:
            if hasattr(psutil, "sensors_battery"):
                battery = psutil.sensors_battery()
                if battery and not battery.power_plugged and battery.percent < 15:
                    msg = "Warning, sir. Battery is below 15 percent. Please connect a power source."
                    log.warning("Battery critical.")
                    # If we had a direct TTS interrupt here, we'd fire it.
                    # For now we just log it.
            
            cpu = psutil.cpu_percent(interval=1)
            if cpu > 95:
                log.warning("CPU usage critical.")
                
        except Exception as e:
            pass
            
        await asyncio.sleep(60)
