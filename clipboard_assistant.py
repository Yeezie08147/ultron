"""
clipboard_assistant.py — ULTRON Smart Clipboard & Text AI.

Capabilities:
- Read / write Windows clipboard text
- Summarize copied text
- Fix grammar, improve tone & format copied text
- Translate copied text to any target language
- Explain and debug code snippets from clipboard
"""

import re
import logging
import asyncio
from typing import Dict, Any, Optional
import httpx

try:
    import pyperclip
except ImportError:
    pyperclip = None

log = logging.getLogger("ultron.clipboard")


def get_clipboard_text() -> str:
    """Read the current text from Windows clipboard."""
    if pyperclip:
        try:
            return pyperclip.paste().strip()
        except Exception as e:
            log.warning(f"Pyperclip read error: {e}")
            
    # Windows PowerShell fallback
    try:
        import subprocess
        res = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-Clipboard"], capture_output=True, text=True, timeout=2)
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception as e:
        log.error(f"Clipboard fallback error: {e}")
        
    return ""


def set_clipboard_text(text: str) -> bool:
    """Copy text back to the Windows clipboard."""
    if pyperclip:
        try:
            pyperclip.copy(text)
            return True
        except Exception as e:
            log.warning(f"Pyperclip write error: {e}")
            
    try:
        import subprocess
        subprocess.run(["clip"], input=text, text=True, timeout=2)
        return True
    except Exception as e:
        log.error(f"Clipboard write fallback error: {e}")
        return False


async def summarize_clipboard() -> str:
    """Summarize the text currently copied on clipboard."""
    text = get_clipboard_text()
    if not text:
        return "Your clipboard is currently empty, sir."

    prompt = (
        "You are ULTRON. Provide a concise, highly informative 1-2 sentence spoken summary of the following text:\n\n"
        f"{text[:3000]}\n\n"
        "Summary:"
    )

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                "http://127.0.0.1:11434/api/generate",
                json={
                    "model": "ultron:brain",
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.3, "num_predict": 100}
                }
            )
            if resp.status_code == 200:
                summary = resp.json().get("response", "").strip()
                if summary:
                    return summary
    except Exception as e:
        log.error(f"Clipboard summarize error: {e}")

    return f"Your clipboard contains {len(text.split())} words."


async def fix_clipboard_grammar() -> str:
    """Fix grammar, spelling, and polish the text on the clipboard."""
    text = get_clipboard_text()
    if not text:
        return "Your clipboard is empty, sir."

    prompt = (
        "You are a professional editor. Rewrite the following text with perfect grammar, spelling, and professional tone. "
        "Output ONLY the corrected text with no commentary or quotes:\n\n"
        f"{text[:2500]}"
    )

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                "http://127.0.0.1:11434/api/generate",
                json={
                    "model": "ultron:brain",
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.2, "num_predict": 500}
                }
            )
            if resp.status_code == 200:
                polished = resp.json().get("response", "").strip()
                if polished:
                    set_clipboard_text(polished)
                    return "I have corrected your clipboard text and copied it back, sir."
    except Exception as e:
        log.error(f"Clipboard grammar fix error: {e}")

    return "Unable to process the clipboard text, sir."


async def translate_clipboard(target_language: str = "Spanish") -> str:
    """Translate clipboard text to target language and copy it back."""
    text = get_clipboard_text()
    if not text:
        return "Your clipboard is empty, sir."

    prompt = (
        f"Translate the following text accurately into {target_language}. "
        "Output ONLY the translation with no extra commentary:\n\n"
        f"{text[:2500]}"
    )

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                "http://127.0.0.1:11434/api/generate",
                json={
                    "model": "ultron:brain",
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.2, "num_predict": 500}
                }
            )
            if resp.status_code == 200:
                translated = resp.json().get("response", "").strip()
                if translated:
                    set_clipboard_text(translated)
                    return f"Translated to {target_language} and copied to your clipboard, sir."
    except Exception as e:
        log.error(f"Clipboard translation error: {e}")

    return f"Failed to translate clipboard to {target_language}, sir."


async def explain_clipboard_code() -> str:
    """Explain code or error stacktrace on clipboard."""
    text = get_clipboard_text()
    if not text:
        return "Your clipboard is empty, sir."

    prompt = (
        "You are ULTRON. Explain what this code does and identify any bugs in 1-2 concise sentences for voice output:\n\n"
        f"{text[:3000]}\n\n"
        "Explanation:"
    )

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                "http://127.0.0.1:11434/api/generate",
                json={
                    "model": "ultron:brain",
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.3, "num_predict": 120}
                }
            )
            if resp.status_code == 200:
                explanation = resp.json().get("response", "").strip()
                if explanation:
                    return explanation
    except Exception as e:
        log.error(f"Explain code error: {e}")

    return "I examined your clipboard code, sir."
