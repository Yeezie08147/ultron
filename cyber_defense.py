import psutil
import asyncio
import logging
import subprocess

log = logging.getLogger("ultron.cyber_defense")

# Common ports that are often scanned or targeted (HTTP, HTTPS, SSH, FTP, RDP, MySQL, etc.)
SUSPICIOUS_PORTS = [21, 22, 23, 3389, 1433, 3306]

def scan_network() -> str:
    """Scans active network connections for foreign or suspicious IPs."""
    try:
        connections = psutil.net_connections(kind='inet')
        suspicious_conns = []
        
        for conn in connections:
            # We only care about ESTABLISHED connections that are remote
            if conn.status == 'ESTABLISHED' and conn.raddr:
                r_port = conn.raddr.port
                r_ip = conn.raddr.ip
                
                # Filter out local loopback
                if r_ip.startswith("127.") or r_ip.startswith("192.168.") or r_ip.startswith("10."):
                    continue
                
                if r_port in SUSPICIOUS_PORTS:
                    suspicious_conns.append(f"IP: {r_ip} on port {r_port}")
        
        if suspicious_conns:
            return f"Warning. I have detected {len(suspicious_conns)} suspicious outbound connections: " + ", ".join(suspicious_conns[:3])
        return "Network perimeter is secure. No suspicious outbound connections detected."
    except Exception as e:
        log.error(f"Network scan failed: {e}")
        return "Network scanner encountered an error."

def scan_processes() -> str:
    """Audits running processes for high resource consumption or suspicious patterns."""
    try:
        rogue_processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                # Find processes eating more than 50% CPU or 40% Memory (excluding known heavy apps)
                name = proc.info['name']
                if name and not any(safe in name.lower() for safe in ['chrome', 'firefox', 'game', 'obs', 'python', 'code', 'discord', 'ollama', 'vmmem']):
                    if proc.info['cpu_percent'] and proc.info['cpu_percent'] > 50.0:
                        rogue_processes.append(f"{name} (CPU Spiking)")
                    elif proc.info['memory_percent'] and proc.info['memory_percent'] > 40.0:
                        rogue_processes.append(f"{name} (Memory Leak)")
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
                
        if rogue_processes:
            return f"I found {len(rogue_processes)} anomalous processes: " + ", ".join(rogue_processes[:3])
        return "Process audit complete. System resources are operating within normal parameters."
    except Exception as e:
        log.error(f"Process scan failed: {e}")
        return "Process audit encountered an error."

def initiate_lockdown() -> str:
    """Uses PowerShell to create a temporary firewall rule blocking incoming traffic."""
    try:
        log.warning("INITIATING CYBERSECURITY LOCKDOWN.")
        # Create a rule blocking incoming traffic (Mocked output if not elevated, but attempts it)
        # Note: Requires Administrator privileges to actually succeed.
        cmd = 'New-NetFirewallRule -DisplayName "ULTRON_LOCKDOWN" -Direction Inbound -Action Block'
        process = subprocess.run(
            ["powershell", "-Command", cmd],
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        )
        
        if "Access is denied" in process.stderr or process.returncode != 0:
            return "Lockdown protocol failed. I require elevated Administrator privileges to modify the Windows Firewall."
        
        return "Lockdown protocol engaged. All non-essential inbound connections have been severed."
    except Exception as e:
        log.error(f"Lockdown failed: {e}")
        return "Lockdown protocol encountered a critical failure."

async def cyber_defense_daemon():
    """Background loop monitoring system security."""
    log.info("Cyber Defense Daemon started.")
    while True:
        try:
            # Periodically scan network and processes in the background
            net_res = scan_network()
            proc_res = scan_processes()
            
            if "Warning" in net_res:
                log.warning(f"CYBER DEFENSE ALERT: {net_res}")
            if "anomalous" in proc_res:
                log.warning(f"CYBER DEFENSE ALERT: {proc_res}")
                
        except Exception as e:
            log.error(f"Defense daemon error: {e}")
            
        # Check every 5 minutes
        await asyncio.sleep(300)
