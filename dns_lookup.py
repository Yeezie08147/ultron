"""
dns_lookup.py — ULTRON DNS & Hostname Resolution Matrix.

Capabilities:
- Resolve any domain name to IPv4/IPv6 addresses
"""

import socket
import logging
from typing import Dict, Any

log = logging.getLogger("ultron.dns")


def resolve_domain(domain: str) -> Dict[str, Any]:
    """Resolve domain name to IP addresses."""
    clean = domain.lower().strip().replace("http://", "").replace("https://", "").split("/")[0].strip()
    import re
    clean = re.sub(r'^(?:lookup dns for|dns lookup for|resolve domain|resolve)\s+', '', clean).strip()

    try:
        ips = socket.gethostbyname_ex(clean)[2]
        ip_str = ", ".join(ips[:3])
        msg = f"DNS resolution for {clean}: Host maps to IP {ip_str}, sir."
        return {
            "success": True,
            "domain": clean,
            "ips": ips,
            "message": msg
        }
    except Exception as e:
        return {"success": False, "message": f"Could not resolve DNS records for {clean}, sir."}
