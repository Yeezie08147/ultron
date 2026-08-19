"""
vision.py — ULTRON Screen Awareness Module
"""
import io
import base64
import logging
import pyautogui
import httpx

log = logging.getLogger("ultron.vision")

async def analyze_screen(prompt: str = "Describe what is on my screen right now in a brief, concise way.") -> str:
    """Takes a screenshot and sends it to a local vision model."""
    try:
        # 1. Take a screenshot
        screenshot = pyautogui.screenshot()
        
        # 2. Convert to Base64
        buffer = io.BytesIO()
        screenshot.save(buffer, format="JPEG", quality=80)
        img_str = base64.b64encode(buffer.getvalue()).decode("utf-8")
        
        # 3. Query Ollama with LLaVA (Vision model)
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://127.0.0.1:11434/api/generate",
                json={
                    "model": "llava:8b",
                    "prompt": prompt,
                    "images": [img_str],
                    "stream": False
                },
                timeout=30.0
            )
            
            if response.status_code == 200:
                return response.json().get("response", "I could not analyze the screen.")
            else:
                log.error(f"Vision API Error: {response.text}")
                return "My visual cortex is currently offline. Ensure the 'llava' model is installed."
    except Exception as e:
        log.error(f"Failed to capture screen: {e}")
        return "I am unable to see the screen at this moment."

def start_vision_loop():
    pass

