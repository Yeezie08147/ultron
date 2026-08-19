"""
ip_scout.py — ULTRON Public IP & Geo-Location Recon Matrix.

Capabilities:
- Real-time Public IPv4/IPv6, ISP, City, and Country telemetry via free ip-api
"""

import httpx
import logging
from typing import Dict, Any

log = logging.getLogger("ultron.ipscout")


def get_public_ip_info() -> Dict[str, Any]:
    """Fetch public IP, City, Region, and ISP."""
    url = "http://ip-api.com/json/"
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                ip = data.get("query", "Unknown")
                city = data.get("city", "Unknown")
                country = data.get("country", "Unknown")
                isp = data.get("isp", "Unknown")

                msg = f"Network telemetry: Public IP is {ip}, located in {city}, {country}. Internet Service Provider: {isp}."
                return {
                    "success": True,
                    "ip": ip,
                    "city": city,
                    "country": country,
                    "isp": isp,
                    "message": msg
                }
    except Exception as e:
        log.warning(f"IP scout failed: {e}")

    return {
        "success": False,
        "message": "Unable to acquire public IP telemetry, sir."
    }
