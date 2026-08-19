"""
os_monitor.py — ULTRON Proactive Autonomous OS Monitor
"""
import psutil
import asyncio
import logging
from datetime import datetime

log = logging.getLogger("ultron.monitor")

# Keep track of when we last warned the user so we don't spam them
_last_warning_time = 0

async def monitor_system(ws_manager=None, synth_func=None):
    """
    Runs in the background, checking system vitals every 10 seconds.
    If CPU or Memory spikes dangerously high, ULTRON will autonomously speak up.
    """
    global _last_warning_time
    
    while True:
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            mem = psutil.virtual_memory()
            
            warning_msg = None
            
            if cpu_percent > 95.0:
                warning_msg = f"Sir, system CPU usage has spiked to {int(cpu_percent)} percent. Proceed with caution."
            elif mem.percent > 90.0:
                warning_msg = f"Sir, available memory is critically low at {int(100 - mem.percent)} percent."
                
            if warning_msg:
                now = datetime.now().timestamp()
                # Only warn once every 5 minutes (300 seconds)
                if now - _last_warning_time > 300:
                    log.warning(f"Proactive warning triggered: {warning_msg}")
                    _last_warning_time = now
                    
                    if synth_func and ws_manager:
                        try:
                            # Autonomously synthesize speech
                            audio = await synth_func(warning_msg)
                            if audio:
                                import base64
                                # Tell UI to switch to speaking state
                                await ws_manager.send_json({"type": "status", "state": "alert"})
                                await ws_manager.send_json({
                                    "type": "audio", 
                                    "data": base64.b64encode(audio).decode(), 
                                    "text": f"[Autonomous Alert] {warning_msg}"
                                })
                        except Exception as e:
                            log.error(f"Failed to deliver autonomous warning: {e}")
            
        except Exception as e:
            log.error(f"OS Monitor error: {e}")
            
        await asyncio.sleep(10)
