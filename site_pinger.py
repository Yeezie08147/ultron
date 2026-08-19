"""
site_pinger.py — ULTRON Web Matrix & Uptime Health Checker.

Capabilities:
- Fast HTTP status & latency check for any website or API
"""

import httpx
import logging
from typing import Dict, Any

log = logging.getLogger("ultron.pinger")


def check_site_status(site: str) -> Dict[str, Any]:
    """Check if a website or URL is online and responsive."""
    clean = site.lower().strip()
    clean = clean.replace("is ", "").replace(" down", "").replace(" working", "").replace(" online", "").strip()
    
    if not clean.startswith("http://") and not clean.startswith("https://"):
        if "." not in clean:
            url = f"https://{clean}.com"
        else:
            url = f"https://{clean}"
    else:
        url = clean

    try:
        with httpx.Client(verify=False, timeout=5.0, follow_redirects=True) as client:
            resp = client.get(url)
            if resp.status_code < 400:
                return {
                    "success": True,
                    "url": url,
                    "status_code": resp.status_code,
                    "message": f"{clean} is operational and responsive with status code {resp.status_code}, sir."
                }
            else:
                return {
                    "success": True,
                    "url": url,
                    "status_code": resp.status_code,
                    "message": f"{clean} returned an error status code {resp.status_code}, sir."
                }
    except Exception as e:
        return {
            "success": False,
            "url": url,
            "message": f"{clean} appears to be unreachable or down, sir."
        }
