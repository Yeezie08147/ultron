"""
gemini_plugin.py — Optional Google Gemini Plugin for ULTRON.

Provides:
- Gemini 2.0 Flash / 1.5 Flash querying (zero extra SDK dependencies, direct httpx REST client)
- Screen Vision: Multimodal analysis of desktop screenshots
- Standby / Fallback handling when no GEMINI_API_KEY is configured
"""

import os
import base64
import logging
from pathlib import Path
from typing import Optional, Dict, Any
import httpx

log = logging.getLogger("ultron.gemini")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash").strip()
GEMINI_ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"


def is_available() -> bool:
    """Check if Gemini plugin is configured with an active API key."""
    return bool(GEMINI_API_KEY)


async def ask_gemini(prompt: str, system_instruction: str = "You are ULTRON, a superior AI assistant.") -> str:
    """Send a text prompt to Google Gemini."""
    if not is_available():
        return "Gemini API key is not configured in .env."

    payload = {
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ],
        "systemInstruction": {
            "parts": [{"text": system_instruction}]
        }
    }

    try:
        async with httpx.AsyncClient(timeout=20.0, verify=False) as client:
            resp = await client.post(
                f"{GEMINI_ENDPOINT}?key={GEMINI_API_KEY}",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            if resp.status_code == 200:
                data = resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                return text.strip()
            else:
                return f"Gemini API returned status {resp.status_code}: {resp.text}"
    except Exception as e:
        log.error(f"Gemini request failed: {e}")
        return f"Gemini connection error: {e}"


async def analyze_screen_with_gemini(image_path: str, prompt: str = "Describe what is currently visible on the screen.") -> str:
    """Analyze a screenshot image using Gemini Multimodal Vision."""
    if not is_available():
        return "Gemini Vision is in standby mode (no API key configured in .env)."

    path = Path(image_path)
    if not path.exists():
        return f"Screenshot file not found: {image_path}"

    try:
        image_bytes = path.read_bytes()
        b64_image = base64.b64encode(image_bytes).decode("utf-8")

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": "image/png",
                                "data": b64_image
                            }
                        }
                    ]
                }
            ],
            "systemInstruction": {
                "parts": [{"text": "You are ULTRON. Provide a concise, highly accurate analysis of what is visible on this desktop screen. Keep voice responses to 1-3 sentences."}]
            }
        }

        async with httpx.AsyncClient(timeout=25.0, verify=False) as client:
            resp = await client.post(
                f"{GEMINI_ENDPOINT}?key={GEMINI_API_KEY}",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            if resp.status_code == 200:
                data = resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                return text.strip()
            else:
                return f"Gemini Vision API error {resp.status_code}: {resp.text}"
    except Exception as e:
        log.error(f"Gemini Vision error: {e}")
        return f"Failed to analyze screen with Gemini: {e}"
