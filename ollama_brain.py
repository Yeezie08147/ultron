import asyncio
import json
import uuid
import httpx
import re
import subprocess
from typing import AsyncIterator, Optional, Any
from dataclasses import dataclass, field

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

class _Messages:
    def __init__(self, model="ultron:brain"):
        self.model = model
    
    async def create(self, **kwargs) -> _Response:
        return _Response(content=[_Block(text="Not implemented")])

class OllamaBrain:
    def __init__(self, model: str = "ultron:brain"):
        self.messages = _Messages(model=model)
        self._model = model

    def _wrap(self, user_text: str, system_context: str) -> str:
        ctx = (system_context or "").strip()
        # Inject the custom command instructions
        ctx += """
You are ULTRON. You have been given full control over the user's Windows desktop.
IMPORTANT RULE: You must ONLY execute commands if the user EXPLICITLY asks you to do so (e.g. "open notepad", "type this out", "move the mouse"). Do NOT run commands on your own.
If you need to run a PowerShell command, output EXACTLY this format and nothing else:
<CMD>command here</CMD>
If you need to automate the desktop (move mouse, click, type text, use hotkeys), output EXACTLY this format to run a Python script using pyautogui:
<PYTHON>
import pyautogui
import time
pyautogui.write("hello")
</PYTHON>
To open ANY application that isn't a simple command, use the Windows search bar:
<PYTHON>
import pyautogui
import time
pyautogui.press('win')
time.sleep(0.5)
pyautogui.write('app name here')
time.sleep(0.5)
pyautogui.press('enter')
</PYTHON>
If you need to hide/close yourself into the background tray, output EXACTLY:
<HIDE>
Otherwise, just respond normally without tags.
"""
        return f"<ULTRON_CONTEXT>\n{ctx}\n</ULTRON_CONTEXT>\n\n{user_text}" if ctx else user_text

    async def respond_stream(self, user_text: str, system_context: str = "") -> AsyncIterator[str]:
        ollama_msgs = []
        
        ctx = system_context + "\n\nYou have access to the user's computer. To run a PowerShell command, output <CMD>command here</CMD>. To run desktop automation, output <PYTHON>import pyautogui...</PYTHON>. To hide yourself, output <HIDE>. ONLY DO THIS IF EXPLICITLY ASKED."
        
        ollama_msgs.append({"role": "system", "content": ctx})
        ollama_msgs.append({"role": "user", "content": user_text})
        
        try:
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    "http://127.0.0.1:11434/api/chat",
                    json={
                        "model": self._model,
                        "messages": ollama_msgs,
                        "stream": True
                    },
                    timeout=120.0
                ) as response:
                    buffer = ""
                    async for chunk in response.aiter_lines():
                        if chunk:
                            try:
                                data = json.loads(chunk)
                                text_piece = data.get("message", {}).get("content", "")
                                if text_piece:
                                    buffer += text_piece
                                    
                                    # Check for command execution
                                    if "<HIDE>" in buffer:
                                        # Tell desktop.py to hide window
                                        try:
                                            import desktop
                                            desktop.hide_window()
                                        except:
                                            pass
                                        yield "I am returning to the background, sir."
                                        buffer = ""
                                        break
                                        
                                    cmd_match = re.search(r"<CMD>(.*?)</CMD>", buffer, re.DOTALL)
                                    if cmd_match:
                                        cmd = cmd_match.group(1).strip()
                                        yield f"Executing command: {cmd}..."
                                        try:
                                            # Run command in background
                                            subprocess.Popen(["powershell", "-Command", cmd], creationflags=subprocess.CREATE_NO_WINDOW)
                                            yield " Command executed successfully."
                                        except Exception as e:
                                            yield f" Failed to execute: {e}"
                                        buffer = ""
                                        break

                                    python_match = re.search(r"<PYTHON>(.*?)</PYTHON>", buffer, re.DOTALL)
                                    if python_match:
                                        code = python_match.group(1).strip()
                                        yield "Executing Python automation..."
                                        try:
                                            import sys
                                            subprocess.Popen([sys.executable, "-c", code], creationflags=subprocess.CREATE_NO_WINDOW)
                                            yield " Automation script executed successfully."
                                        except Exception as e:
                                            yield f" Failed to execute automation: {e}"
                                        buffer = ""
                                        break

                                    # Only yield if we are reasonably sure we aren't building a tag
                                    is_building_tag = False
                                    if re.search(r'<(?:C(?:M(?:D)?)?|H(?:I(?:D(?:E)?)?)?|P(?:Y(?:T(?:H(?:O(?:N)?)?)?)?)?)?$', buffer) or "<CMD" in buffer or "<HIDE" in buffer or "<PYTHON" in buffer:
                                        is_building_tag = True

                                    if not is_building_tag:
                                        sentences = []
                                        last_end = 0
                                        for m in re.finditer(r"[^.!?\n]*[.!?\n]+", buffer):
                                            c = buffer[last_end:m.end()].strip()
                                            if c:
                                                sentences.append(c)
                                            last_end = m.end()
                                        buffer = buffer[last_end:]
                                        
                                        for s in sentences:
                                            yield s
                            except json.JSONDecodeError:
                                pass
                    if buffer.strip() and not re.search(r'<(?:C(?:M(?:D)?)?|H(?:I(?:D(?:E)?)?)?|P(?:Y(?:T(?:H(?:O(?:N)?)?)?)?)?)?$', buffer):
                        yield buffer.strip()
        except Exception as e:
            yield f"I'm sorry sir, there was an issue reaching the local brain: {e}"

    async def respond(self, user_text: str, system_context: str = "") -> _Response:
        return _Response(content=[_Block(text="Not implemented")])
    
    async def warmup(self) -> None:
        pass

    async def aclose(self) -> None:
        pass
