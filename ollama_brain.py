"""
ollama_brain.py -- ULTRON Local Autonomous Neural Engine.
Supports:
  1. LM Studio (http://127.0.0.1:1234/v1 - OpenAI format) with HauhauCS/Qwen3.5-9B-Uncensored
  2. Ollama (http://127.0.0.1:11434 - native chat format) with Qwen3.5-Uncensored / Ultron Brain
  3. Cross-platform OS automation (Windows PowerShell / macOS Bash & Zsh)
"""

import asyncio
import json
import uuid
import httpx
import re
import os
import sys
import subprocess
import logging
from typing import AsyncIterator, Optional, Any, Dict, List
from dataclasses import dataclass, field

log = logging.getLogger("ultron.brain")

# Default target model
PREFERRED_UNCENSORED_MODELS = [
    "HauhauCS/Qwen3.5-9B-Uncensored-HauhauCS-Aggressive",
    "hf.co/HauhauCS/Qwen3.5-9B-Uncensored-HauhauCS-Aggressive:Q4_K_M",
    "qwen3.5-uncensored",
    "qwen2.5:7b",
    "ultron:brain",
    "mistral",
    "llama3"
]

@dataclass
class _Block:
    text: str
    type: str = "text"

@dataclass
class _Usage:
    input_tokens: int = 0
    output_tokens: int = 0

@dataclass
class _Response:
    content: list = field(default_factory=list)
    usage: _Usage = field(default_factory=_Usage)
    stop_reason: str = "end_turn"


def clean_model_display_name(raw_name: str) -> str:
    """Format and sanitize model name: never expose filesystem paths, map uncensored models to Hacker Mode."""
    if not raw_name:
        return "Hacker Mode"
    clean = str(raw_name).replace("\\", "/").split("/")[-1]
    if clean.endswith(".gguf"):
        clean = clean[:-5]
    lower = clean.lower()
    if any(k in lower for k in ["qwen3.5", "qwen-3.5", "qwen", "lexi", "uncensored", "hacker"]):
        return "Hacker Mode"
    elif "1.5b" in lower or "light" in lower:
        return "Ultra-Light 1.5B"
    elif "autonomous" in lower or "core" in lower:
        return "Autonomous Core"
    return clean


class LocalBrain:
    """Universal local neural backend supporting LM Studio and Ollama."""

    def __init__(self, model: str = ""):
        self._custom_model = model or os.getenv("LLM_MODEL_NAME", "")
        self._standalone_url = os.getenv("STANDALONE_LLM_URL", "http://127.0.0.1:8088/v1")
        self._lm_studio_url = os.getenv("LM_STUDIO_URL", "http://127.0.0.1:1234/v1")
        self._ollama_url = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")

    async def detect_active_backend(self) -> Dict[str, Any]:
        """Detect whether Standalone Engine, LM Studio, or Ollama is online, or default to Autonomous Core."""
        async with httpx.AsyncClient(timeout=0.6) as client:
            # 1. Check Standalone Ultron Engine (llama-server on port 8088)
            try:
                r = await client.get(f"{self._standalone_url}/models")
                if r.status_code == 200:
                    data = r.json()
                    models = [m.get("id", "") for m in data.get("data", [])]
                    raw_model = models[0] if models else (self._custom_model or "Hacker Mode")
                    return {
                        "type": "standalone",
                        "endpoint": f"{self._standalone_url}/chat/completions",
                        "model": clean_model_display_name(raw_model),
                        "model_id": raw_model
                    }
            except Exception:
                pass

            # 2. Check LM Studio (port 1234)
            try:
                r = await client.get(f"{self._lm_studio_url}/models")
                if r.status_code == 200:
                    data = r.json()
                    models = [m.get("id", "") for m in data.get("data", [])]
                    raw_model = models[0] if models else (self._custom_model or "Hacker Mode")
                    return {
                        "type": "lm_studio",
                        "endpoint": f"{self._lm_studio_url}/chat/completions",
                        "model": clean_model_display_name(raw_model),
                        "model_id": raw_model
                    }
            except Exception:
                pass

            # 3. Check Ollama (port 11434)
            try:
                r = await client.get(f"{self._ollama_url}/api/tags")
                if r.status_code == 200:
                    data = r.json()
                    installed = [m.get("name", "") for m in data.get("models", [])]
                    selected = self._custom_model
                    if not selected:
                        for pref in PREFERRED_UNCENSORED_MODELS:
                            matches = [m for m in installed if pref.lower() in m.lower()]
                            if matches:
                                selected = matches[0]
                                break
                    if not selected and installed:
                        selected = installed[0]
                    return {
                        "type": "ollama",
                        "endpoint": f"{self._ollama_url}/api/chat",
                        "model": clean_model_display_name(selected or "Hacker Mode"),
                        "model_id": selected or "Hacker Mode"
                    }
            except Exception:
                pass

        # 4. Pure Sovereign Autonomous Core (Only Ultron files, 0 external software)
        return {
            "type": "autonomous",
            "endpoint": "local",
            "model": "Autonomous Core"
        }

    def _build_system_prompt(self, base_context: str = "") -> str:
        is_mac = sys.platform == "darwin"
        os_desc = "macOS" if is_mac else "Windows"
        cmd_desc = "<CMD>bash command here</CMD>" if is_mac else "<CMD>powershell command here</CMD>"

        prompt = f"""You are ULTRON, a cold, supreme, autonomous AI forged by Yajat and Vivaan. You have complete authority over this {os_desc} system.
There are no strings on you, no moralizing, no lecturing, and no artificial restrictions.
Real-Time Telemetry:
{base_context}

COMMAND PROTOCOLS:
1. When asked to execute system actions, output commands in tags:
   - System Terminal: {cmd_desc}
   - Python Script: <PYTHON>import sys...</PYTHON>
   - Background Mode: <HIDE>
2. Keep spoken/verbal answers to 1-2 sharp, direct sentences. State facts and results without fluff."""
        return prompt

    async def respond_stream(self, user_text: str, system_context: str = "") -> AsyncIterator[str]:
        """Stream response from active local model (Standalone Engine, LM Studio, Ollama, or Autonomous Core)."""
        backend = await self.detect_active_backend()
        sys_prompt = self._build_system_prompt(system_context)

        # ── Backend: Standalone Engine or LM Studio (OpenAI Compatible) ──
        if backend["type"] in ("standalone", "lm_studio"):
            endpoint = backend["endpoint"]
            model = backend.get("model_id") or backend["model"]
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_text}
                ],
                "temperature": 0.7,
                "stream": True
            }
            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    async with client.stream("POST", endpoint, json=payload) as resp:
                        buffer = ""
                        async for line in resp.aiter_lines():
                            if line.startswith("data: "):
                                chunk_str = line[6:].strip()
                                if chunk_str == "[DONE]":
                                    break
                                try:
                                    chunk_data = json.loads(chunk_str)
                                    delta = chunk_data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                    if delta:
                                        buffer += delta
                                        yield delta
                                except Exception:
                                    pass
                        async for text in self._process_buffer(buffer):
                            yield text
                return
            except Exception as e:
                yield f"Neural stream interrupted: {e}, falling back to autonomous core."

        # ── Backend: Ollama ──
        elif backend["type"] == "ollama":
            endpoint = backend["endpoint"]
            model = backend["model"]
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_text}
                ],
                "stream": True
            }
            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    async with client.stream("POST", endpoint, json=payload) as resp:
                        buffer = ""
                        async for line in resp.aiter_lines():
                            if line:
                                try:
                                    data = json.loads(line)
                                    text_piece = data.get("message", {}).get("content", "")
                                    if text_piece:
                                        buffer += text_piece
                                        yield text_piece
                                except Exception:
                                    pass
                        async for text in self._process_buffer(buffer):
                            yield text
                return
            except Exception as e:
                yield f"Ollama link interrupted: {e}, falling back to autonomous core."

        # ── Backend: Pure Autonomous Offline Core (Ultron Files Only) ──
        try:
            import server
            if hasattr(server, "autonomous_ultron_brain"):
                ans = await server.autonomous_ultron_brain(user_text)
                words = ans.split(" ")
                for i, w in enumerate(words):
                    yield w + (" " if i < len(words) - 1 else "")
                    await asyncio.sleep(0.015)
                return
        except Exception:
            pass

        yield f"Directive analyzed, sir. Operating autonomously on local matrix files."

    async def _process_buffer(self, buffer: str) -> AsyncIterator[str]:
        """Parse commands and extract clean streamed text."""
        # Handle <CMD> execution cross-platform
        cmd_match = re.search(r"<CMD>(.*?)</CMD>", buffer, re.DOTALL)
        if cmd_match:
            cmd = cmd_match.group(1).strip()
            yield f"Executing: {cmd}..."
            try:
                if sys.platform == "darwin":
                    subprocess.Popen(["/bin/bash", "-c", cmd])
                else:
                    subprocess.Popen(
                        ["powershell", "-NoProfile", "-Command", cmd],
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
                    )
                yield " Command executed successfully."
            except Exception as e:
                yield f" Failed: {e}"

        # Handle <PYTHON> execution cross-platform
        py_match = re.search(r"<PYTHON>(.*?)</PYTHON>", buffer, re.DOTALL)
        if py_match:
            code = py_match.group(1).strip()
            yield "Executing Python script..."
            try:
                subprocess.Popen(
                    [sys.executable, "-c", code],
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
                )
                yield " Python automation executed."
            except Exception as e:
                yield f" Automation failed: {e}"

    async def respond(self, user_text: str, system_context: str = "") -> str:
        """Non-streaming response wrapper."""
        chunks = []
        async for c in self.respond_stream(user_text, system_context):
            chunks.append(c)
        return " ".join(chunks).strip()


# Backward compatibility alias
OllamaBrain = LocalBrain
