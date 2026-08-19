"""
qr_generator.py — ULTRON Instant QR Code Generator.

Capabilities:
- Generates high-resolution QR code images from URLs or text
- Saves directly to Desktop/ULTRON_QR/ and opens image in default viewer
"""

import os
import urllib.parse
import logging
from pathlib import Path
from typing import Dict, Any

import httpx

log = logging.getLogger("ultron.qrcode")

QR_DIR = Path.home() / "Desktop" / "ULTRON_QR"


def generate_qr_code(content: str) -> Dict[str, Any]:
    """Generate a QR code PNG via free QR server API and open it."""
    QR_DIR.mkdir(parents=True, exist_ok=True)
    clean_text = content.strip()
    # Strip prefixes
    import re
    clean_text = re.sub(r'^(?:generate a qr code for|create qr code for|make a qr code for|qr code for|generate qr code for)\s*', '', clean_text, flags=re.I).strip()
    if not clean_text:
        clean_text = "https://github.com"

    encoded = urllib.parse.quote(clean_text)
    api_url = f"https://api.qrserver.com/v1/create-qr-code/?size=400x400&data={encoded}"

    out_file = QR_DIR / "qr_code.png"

    try:
        with httpx.Client(verify=False, timeout=8.0) as client:
            resp = client.get(api_url)
            if resp.status_code == 200:
                with open(out_file, "wb") as f:
                    f.write(resp.content)

                # Open the generated QR code image
                os.system(f'start "" "{out_file.resolve()}"')
                return {
                    "success": True,
                    "path": str(out_file),
                    "message": f"QR code generated for {clean_text[:40]} and opened on your screen, sir."
                }
    except Exception as e:
        log.warning(f"QR generation failed: {e}")

    return {
        "success": False,
        "message": f"Unable to synthesize QR code for {clean_text[:30]}, sir."
    }
