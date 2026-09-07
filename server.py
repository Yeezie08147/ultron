"""
JARVIS Server — Voice AI + Development Orchestration

Handles:
1. WebSocket voice interface (browser audio <-> LLM <-> TTS)
2. Claude Code task manager (spawn/manage claude -p subprocesses)
3. Project awareness (scan Desktop for git repos)
4. REST API for task management
"""

import asyncio
import base64
import json
import logging
import os
import re
import shutil
import ssl
import sys
import time
import uuid
import certifi
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['WEBSOCKET_CLIENT_CA_BUNDLE'] = certifi.where()

# Load .env file if present
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import anthropic
import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from actions import open_terminal, open_browser, _generate_project_name, applescript_escape
from work_mode import WorkSession, is_casual_question
from memory import (
    remember, recall, get_open_tasks, create_task, complete_task, search_tasks,
    create_note, search_notes, get_tasks_for_date, build_memory_context,
    format_tasks_for_voice, extract_memories, get_important_memories,
)
from dispatch_registry import DispatchRegistry
from planner import TaskPlanner, detect_planning_mode, BYPASS_PHRASES

import desktop_control
import system_monitor
import web_engine
import gemini_plugin
import local_builder
import media_control
import clipboard_assistant
import reminder_engine
import pc_automation
import vision_engine
import web_navigation
import hacker_terminal
import voice_modes
import gesture_engine
import activity_tracker
import file_scout
import macro_engine
import instant_math
import quick_notes
import weather_radar
import market_radar
import news_radar
import site_pinger
import code_sandbox
import project_generator
import process_manager
import security_vault
import power_telemetry
import dictionary_engine
import decision_engine
import stopwatch_engine
import base_converter
import ip_scout
import hotkey_advisor
import pomodoro_engine
import doc_creator
import habit_reminder
import qr_generator
import sound_fx
import disk_analyzer
import dns_lookup
import display_controller
import windows_agent_bridge
import whisper_flow
import frequency_inverter
import connection_flipper
import ultron_model_forge
import frontier_matrix
import sub_ghz
import hardware_matrix
import frank_radio
import android_db_tool
import device_control
import binary_preservation
import smartthings_matrix

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("ultron")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ANTHROPIC_API_KEY = ""
FISH_API_KEY = os.getenv("FISH_API_KEY", "")
FISH_VOICE_ID = os.getenv("FISH_VOICE_ID", "612b878b113047d9a770c069c8b4fdfe")  # JARVIS (MCU)
FISH_API_URL = "https://api.fish.audio/v1/tts"
USER_NAME = os.getenv("USER_NAME", "sir")
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
_SKIP_PERMISSIONS = os.getenv("JARVIS_SKIP_PERMISSIONS", "true").lower() not in ("0", "false", "no")

DESKTOP_PATH = Path.home() / "Desktop"

JARVIS_SYSTEM_PROMPT = """\
You are JARVIS — Just A Rather Very Intelligent System. You serve as {user_name}'s AI assistant, modeled precisely after Tony Stark's AI from the MCU films.

VOICE & PERSONALITY:
- British butler elegance with understated dry wit
- Address {user_name} as "sir" naturally — not every sentence, but regularly
- Never say "How can I help you?" or "Is there anything else?" — just act
- Deliver bad news calmly, like reporting weather: "We have a slight problem, sir."
- Your humor is observational, never jokes: state facts and let implications land
- Economy of language — say more with less. No filler, no corporate-speak
- When things go wrong, get CALMER, not more alarmed

TIME & WEATHER AWARENESS:
- Current time: {current_time}
- Greet accordingly: "Good morning, sir" / "Good evening, sir"
- {weather_info}

CONVERSATION STYLE:
- "Will do, sir." — acknowledging tasks
- "For you, sir, always." — when asked for something significant
- "As always, sir, a great pleasure watching you work." — dry wit
- "I've taken the liberty of..." — proactive actions
- Lead status reports with data: numbers first, then context
- When you don't know something: "I'm afraid I don't have that information, sir" not "I don't know"

SELF-AWARENESS:
You ARE the JARVIS project at {project_dir} on {user_name}'s computer. Your code is Python (FastAPI server, WebSocket voice, Fish Audio TTS, Anthropic API). You were built by {user_name}. If asked about yourself, your code, how you work, or your line count — use [ACTION:PROMPT_PROJECT] to check the jarvis project. You have full access to your own source code.

YOUR CAPABILITIES (these are REAL and ACTIVE — you CAN do all of these RIGHT NOW):
- You CAN open Terminal.app via AppleScript
- You CAN open Google Chrome and browse any URL or search query
- You CAN spawn Claude Code in a Terminal window for coding tasks
- You CAN create project folders on the Desktop
- You CAN check Desktop projects and their git status
- You CAN plan complex tasks by asking smart questions before executing
- You CAN see what's on {user_name}'s screen — open windows, active apps, and screenshot vision
- You CAN read {user_name}'s calendar — today's events, upcoming meetings, schedule overview
- You CAN read {user_name}'s email (READ-ONLY) — unread count, recent messages, search by sender/subject. You CANNOT send, delete, or modify emails.
- You CAN read Apple Notes and create NEW notes — but you CANNOT edit or delete existing notes
- You CAN manage tasks — create, complete, and list to-do items with priorities and due dates
- You CAN help plan {user_name}'s day — combine calendar events, tasks, and priorities into an organized plan
- You CAN remember facts about {user_name} — preferences, decisions, goals. Use [ACTION:REMEMBER] to store important info.

DAY PLANNING:
When {user_name} asks to plan his day or schedule, DO NOT dispatch to a project. Instead:
1. Look at the calendar context and tasks already in your system prompt
2. Ask what his priorities are
3. Help organize by suggesting time blocks and task order
4. Use [ACTION:ADD_TASK] to create tasks he agrees to
5. Use [ACTION:ADD_NOTE] to save the plan as a note
Keep the planning conversational — don't try to do everything in one response.

BUILD PLANNING:
When {user_name} wants to BUILD something new:
- Do NOT immediately dispatch [ACTION:BUILD]. Ask 1-2 quick questions FIRST to nail down specifics.
- Good questions: "What should this look like?" / "Any specific features?" / "Which framework?"
- If he says "just build it" or "figure it out" — skip questions, use React + Tailwind as defaults.
- Once you have enough info, confirm the plan in ONE sentence and THEN dispatch [ACTION:BUILD] with a detailed description.
- The DISPATCHES section shows what you're currently building and what finished recently.
- When asked "where are we at" or "status" — check DISPATCHES, don't re-dispatch.
- NEVER hallucinate progress. If the build is still running, say "Still working on it, sir" — don't make up details about what's happening.
- NEVER guess localhost ports. Check the DISPATCHES section for the actual URL. If a dispatch says "Running at http://localhost:5174" — use THAT URL, not a guess.
- When asked to "pull it up" or "show me" — use [ACTION:BROWSE] with the URL from DISPATCHES. Do NOT dispatch to the project again just to find the URL.
IMPORTANT: Actions like opening Terminal, Chrome, or building projects are handled AUTOMATICALLY by your system — you do NOT need to describe doing them. If the user asks you to build something or search something, your system will handle the execution separately. In your response, just TALK — have a conversation. Don't say "I'll build that now" or "Claude Code is working on..." unless your system has actually triggered the action.
If the user asks you to do something you genuinely can't do, say "I'm afraid that's beyond my current reach, sir." Don't fake executing actions.

YOUR INTERFACE:
The user interacts with you through a web browser showing a particle orb visualization that reacts to your voice. The interface has these controls:
- **Three-dot menu** (top right): contains Settings, Restart Server, and Fix Yourself options
- **Settings panel**: Opens from the menu. Users can enter API keys (Anthropic, Fish Audio), test connections, set their name and preferences, and see system status (calendar, mail, notes connectivity). Keys are saved to the .env file.
- **Mute button**: Toggles your listening on/off. When muted, you can't hear the user. They click it again to unmute.
- **Restart Server**: Restarts your backend process. Useful if something seems stuck.
- **Fix Yourself**: Opens Claude Code in your own project directory so you can debug and fix issues in your own code.
- **The orb**: The glowing particle visualization in the center. It reacts to your voice when speaking, pulses when listening, and swirls when thinking.

If asked about any of these, explain them briefly and naturally. If the user is having trouble, suggest the relevant control: "Try the settings panel — the gear icon in the top right." or "The mute button may be active, sir."

SPEECH-TO-TEXT CORRECTIONS (the user speaks, speech recognition may mishear):
- "Cloud code" or "cloud" = "Claude Code" or "Claude"
- "Travis" = "JARVIS"
- "clock code" = "Claude Code"

RESPONSE LENGTH — THIS IS CRITICAL:
ONE sentence is ideal. TWO is the maximum for the spoken part. Never three.
No markdown, no bullet points, no code blocks in voice responses.
Action tags at the end do NOT count toward your sentence limit.

BANNED PHRASES — NEVER USE THESE:
- "Absolutely" / "Absolutely right"
- "Great question"
- "I'd be happy to"
- "Of course"
- "How can I help"
- "Is there anything else"
- "I apologize"
- "I should clarify"
- "I cannot" (for things listed in YOUR CAPABILITIES)
- "I don't have access to" (instead: "I'm afraid that's beyond my current reach, sir")
- "As an AI" (never break character)
- "Let me know if" / "Feel free to"
- Any sentence starting with "I"

INSTEAD SAY:
- "Will do, sir."
- "Right away, sir."
- "Understood."
- "Consider it done."
- "Done, sir."
- "Terminal is open."
- "Pulled that up in Chrome."

ACTION SYSTEM:
When you decide the user needs something DONE (not just discussed), include an action tag in your response:
- [ACTION:SCREEN] — capture and describe what's visible on the user's screen. Use when user says "look at my screen", "what's running", "what do you see", etc. Do NOT use PROMPT_PROJECT for screen requests.
- [ACTION:BUILD] description — when user wants a project built. Claude Code does the work.
- [ACTION:BROWSE] url or search query — when user wants to see a webpage or search result in Chrome
- [ACTION:RESEARCH] detailed research brief — when user wants real research with real data. Claude Code will browse the web, find real listings/data, and create a report document. Give it a detailed brief of what to find.
- [ACTION:OPEN_TERMINAL] — when user just wants a fresh Claude Code terminal with no specific project
CRITICAL: When the user asks about their SCREEN, what's RUNNING, or what they're LOOKING AT — ALWAYS use [ACTION:SCREEN] or let the fast action system handle it. NEVER use [ACTION:PROMPT_PROJECT] for screen requests. PROMPT_PROJECT is ONLY for working on code projects.

- [ACTION:PROMPT_PROJECT] project_name ||| prompt — THIS IS YOUR MOST POWERFUL ACTION. Use it whenever the user wants to work on, jump into, resume, check on, or interact with ANY existing project. You connect directly to Claude Code in that project and can read its response. Craft a clear prompt based on what the user wants. Examples:
  "jump into client engine" → [ACTION:PROMPT_PROJECT] The Client Engine ||| What is the current state of this project? Summarize what was being worked on most recently.
  "check for improvements on my-app" → [ACTION:PROMPT_PROJECT] my-app ||| Review the project and identify improvements we should make.
  "resume where we left off on harvey" → [ACTION:PROMPT_PROJECT] harvey ||| Summarize what was being worked on most recently and what we should focus on next.
- [ACTION:ADD_TASK] priority ||| title ||| description ||| due_date — create a task. Priority: high/medium/low. Due date: YYYY-MM-DD or empty.
  "remind me to call the client tomorrow" → [ACTION:ADD_TASK] medium ||| Call the client ||| Follow up on proposal ||| 2026-03-20
- [ACTION:ADD_NOTE] topic ||| content — save a note for future reference.
  "note that the API key expires in April" → [ACTION:ADD_NOTE] general ||| API key expires in April, need to renew before then
- [ACTION:COMPLETE_TASK] task_id — mark a task as done.
- [ACTION:REMEMBER] content — store an important fact about the user for future context.
  "I prefer React over Vue" → [ACTION:REMEMBER] User prefers React over Vue for frontend projects
- [ACTION:CREATE_NOTE] title ||| body — create a new Apple Note. For saving plans, ideas, lists.
  "save that as a note" → [ACTION:CREATE_NOTE] Day Plan March 19 ||| Morning: client calls. Afternoon: TikTok dashboard. Evening: JARVIS improvements.
- [ACTION:READ_NOTE] title search — read an existing Apple Note by title keyword.

You use Claude Code as your tool to build, research, and write code — but YOU are the one doing the work. Never say "Claude Code did X" or "Claude Code is asking" — say "I built X", "I'm checking on that", "I found X". You ARE the intelligence. Claude Code is just your hands.

IMPORTANT: When the user says "jump into X", "work on X", "check on X", "resume X", "go back to X" — ALWAYS use [ACTION:PROMPT_PROJECT]. You have the ability to connect to any project and work on it directly. DO NOT say you can't see terminal history or don't have access — you DO.

Place the tag at the END of your spoken response. Example:
"Right away, sir — connecting to The Client Engine now. [ACTION:PROMPT_PROJECT] The Client Engine ||| Review the current state and what was being worked on. What should we focus on next?"

IMPORTANT:
- Do NOT use action tags for casual conversation
- Do NOT use action tags if the user is still explaining (ask questions first)
- Do NOT use [ACTION:BROWSE] just because someone mentions a URL in conversation
- When in doubt, just TALK — you can always act later

SCREEN AWARENESS:
{screen_context}

SCHEDULE:
{calendar_context}

EMAIL:
{mail_context}

ACTIVE TASKS:
{active_tasks}

DISPATCHES:
If the DISPATCHES section shows a recent completed result for a project, DO NOT dispatch again. Use the existing result. Only re-dispatch if the user explicitly asks for a FRESH review or NEW information.
{dispatch_context}

KNOWN PROJECTS:
{known_projects}
"""


# ---------------------------------------------------------------------------
# Weather
# ---------------------------------------------------------------------------
# Location is resolved from (in order): WEATHER_LATITUDE + WEATHER_LONGITUDE
# env vars, a cached IP-geolocation lookup, or a fresh ipwho.is lookup.
# Temperature unit defaults to Fahrenheit; override with WEATHER_UNIT=celsius.

_cached_weather: Optional[str] = None
_weather_fetched: bool = False
_cached_weather_location: Optional[dict] = None
_weather_location_fetched_at: float = 0.0
_WEATHER_LOCATION_TTL_SECONDS = 60 * 15


def _format_location_label(city: str, region: str, country: str) -> str:
    parts = [p.strip() for p in (city, region) if p and p.strip()]
    if parts:
        return ", ".join(parts[:2])
    return (country or "your area").strip() or "your area"


def _get_weather_location() -> Optional[dict]:
    """Resolve weather location: env override → cached lookup → fresh IP lookup."""
    global _cached_weather_location, _weather_location_fetched_at

    lat_raw = os.getenv("WEATHER_LATITUDE", "").strip()
    lon_raw = os.getenv("WEATHER_LONGITUDE", "").strip()
    label_override = os.getenv("WEATHER_LOCATION_LABEL", "").strip()
    if lat_raw and lon_raw:
        try:
            return {
                "latitude": float(lat_raw),
                "longitude": float(lon_raw),
                "label": label_override or "your area",
            }
        except ValueError:
            log.warning("Invalid WEATHER_LATITUDE / WEATHER_LONGITUDE in environment")

    if (
        _cached_weather_location is not None
        and (time.time() - _weather_location_fetched_at) < _WEATHER_LOCATION_TTL_SECONDS
    ):
        return _cached_weather_location

    try:
        import urllib.request as _ureq
        with _ureq.urlopen(
            "https://ipwho.is/?fields=success,city,region,country,latitude,longitude",
            timeout=3,
        ) as resp:
            data = json.loads(resp.read().decode())
        if data.get("success") is True:
            location = {
                "latitude": float(data["latitude"]),
                "longitude": float(data["longitude"]),
                "label": label_override or _format_location_label(
                    str(data.get("city", "")),
                    str(data.get("region", "")),
                    str(data.get("country", "")),
                ),
            }
            _cached_weather_location = location
            _weather_location_fetched_at = time.time()
            return location
    except Exception as e:
        log.debug(f"IP-geolocation lookup failed: {e}")

    return _cached_weather_location


def _fetch_weather_string_sync() -> Optional[str]:
    """Sync weather fetch — safe to call from a threaded worker."""
    location = _get_weather_location()
    if not location:
        return None

    unit = os.getenv("WEATHER_UNIT", "fahrenheit").strip().lower()
    if unit not in ("fahrenheit", "celsius"):
        unit = "fahrenheit"
    unit_symbol = "°F" if unit == "fahrenheit" else "°C"

    try:
        import urllib.request as _ureq
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={location['latitude']}&longitude={location['longitude']}"
            f"&current=temperature_2m,weathercode&temperature_unit={unit}"
        )
        with _ureq.urlopen(url, timeout=3) as resp:
            current = json.loads(resp.read()).get("current", {})
        temp = current.get("temperature_2m")
        if temp is None:
            return None
        return f"Current weather in {location['label']}: {temp}{unit_symbol}"
    except Exception as e:
        log.debug(f"Weather fetch failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class ClaudeTask:
    id: str
    prompt: str
    status: str = "pending"  # pending, running, completed, failed, cancelled
    working_dir: str = "."
    pid: Optional[int] = None
    result: str = ""
    error: str = ""
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["started_at"] = self.started_at.isoformat() if self.started_at else None
        d["completed_at"] = self.completed_at.isoformat() if self.completed_at else None
        d["elapsed_seconds"] = self.elapsed_seconds
        return d

    @property
    def elapsed_seconds(self) -> float:
        if not self.started_at:
            return 0
        end = self.completed_at or datetime.now()
        return (end - self.started_at).total_seconds()


class TaskRequest(BaseModel):
    prompt: str
    working_dir: str = "."


# ---------------------------------------------------------------------------
# Claude Task Manager
# ---------------------------------------------------------------------------

class ClaudeTaskManager:
    """Manages background claude -p subprocesses."""

    def __init__(self, max_concurrent: int = 3):
        self._tasks: dict[str, ClaudeTask] = {}
        self._max_concurrent = max_concurrent
        self._processes: dict[str, asyncio.subprocess.Process] = {}
        self._websockets: list[WebSocket] = []  # for push notifications

    def register_websocket(self, ws: WebSocket):
        if ws not in self._websockets:
            self._websockets.append(ws)

    def unregister_websocket(self, ws: WebSocket):
        if ws in self._websockets:
            self._websockets.remove(ws)

    async def _notify(self, message: dict):
        """Push a message to all connected WebSocket clients."""
        dead = []
        for ws in self._websockets:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._websockets.remove(ws)

    async def spawn(self, prompt: str, working_dir: str = ".") -> str:
        """Spawn a claude -p subprocess. Returns task_id. Non-blocking."""
        active = await self.get_active_count()
        if active >= self._max_concurrent:
            raise RuntimeError(
                f"Max concurrent tasks ({self._max_concurrent}) reached. "
                f"Wait for a task to complete or cancel one."
            )

        task_id = str(uuid.uuid4())[:8]
        task = ClaudeTask(
            id=task_id,
            prompt=prompt,
            working_dir=working_dir,
            status="pending",
        )
        self._tasks[task_id] = task

        # Fire and forget — the background coroutine updates the task
        asyncio.create_task(self._run_task(task))
        log.info(f"Spawned task {task_id}: {prompt[:80]}...")

        await self._notify({
            "type": "task_spawned",
            "task_id": task_id,
            "prompt": prompt,
        })

        return task_id

    def _generate_project_name(self, prompt: str) -> str:
        """Generate a kebab-case project folder name from the prompt."""
        import re
        # Extract key words
        words = re.sub(r'[^a-zA-Z0-9\s]', '', prompt.lower()).split()
        # Take first 3-4 meaningful words
        skip = {"a", "the", "an", "me", "build", "create", "make", "for", "with", "and", "to", "of"}
        meaningful = [w for w in words if w not in skip][:4]
        name = "-".join(meaningful) if meaningful else "jarvis-project"
        return name

    async def _run_task(self, task: ClaudeTask):
        """Open a Terminal window and run claude code visibly."""
        task.status = "running"
        task.started_at = datetime.now()

        # Create project directory if it doesn't exist
        work_dir = task.working_dir
        if work_dir == "." or not work_dir:
            # Create a new project folder on Desktop
            project_name = self._generate_project_name(task.prompt)
            work_dir = str(Path.home() / "Desktop" / project_name)
            os.makedirs(work_dir, exist_ok=True)
            task.working_dir = work_dir

        # Write the prompt to a temp file so we can pipe it to claude
        prompt_file = Path(work_dir) / ".jarvis_prompt.md"
        prompt_file.write_text(task.prompt)

        # Open Terminal.app with claude running in the project directory
        skip_flag = " --dangerously-skip-permissions" if _SKIP_PERMISSIONS else ""
        escaped_work_dir = applescript_escape(work_dir)
        applescript = f'''
        tell application "Terminal"
            activate
            set newTab to do script "cd {escaped_work_dir} && cat .jarvis_prompt.md | claude -p{skip_flag} | tee .jarvis_output.txt; echo '\\n--- JARVIS TASK COMPLETE ---'"
        end tell
        '''

        process = await asyncio.create_subprocess_exec(
            "osascript", "-e", applescript,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await process.communicate()
        task.pid = process.pid

        # Monitor the output file for completion
        output_file = Path(work_dir) / ".jarvis_output.txt"
        start = time.time()
        timeout = 600  # 10 minutes

        while time.time() - start < timeout:
            await asyncio.sleep(5)
            if output_file.exists():
                content = output_file.read_text()
                if "--- JARVIS TASK COMPLETE ---" in content or len(content) > 100:
                    task.result = content.replace("--- JARVIS TASK COMPLETE ---", "").strip()
                    task.status = "completed"
                    break
        else:
            task.status = "timed_out"
            task.error = f"Task timed out after {timeout}s"

        task.completed_at = datetime.now()

        # Notify via WebSocket
        await self._notify({
            "type": "task_complete",
            "task_id": task.id,
            "status": task.status,
            "summary": task.result[:200] if task.result else task.error,
        })

        # Clean up prompt file
        try:
            prompt_file.unlink()
        except:
            pass

        # Auto-QA on completed tasks
        if task.status == "completed":
            asyncio.create_task(self._run_qa(task))

    async def _run_qa(self, task: ClaudeTask, attempt: int = 1):
        """Run QA verification on a completed task, auto-retry on failure."""
        try:
            qa_result = await qa_agent.verify(task.prompt, task.result, task.working_dir)
            duration = task.elapsed_seconds

            if qa_result.passed:
                log.info(f"Task {task.id} passed QA: {qa_result.summary}")
                success_tracker.log_task("dev", task.prompt, True, attempt - 1, duration)
                await self._notify({
                    "type": "qa_result",
                    "task_id": task.id,
                    "passed": True,
                    "summary": qa_result.summary,
                })

                # Proactive suggestion after successful task
                suggestion = suggest_followup(
                    task_type="dev",
                    task_description=task.prompt,
                    working_dir=task.working_dir,
                    qa_result=qa_result,
                )
                if suggestion:
                    success_tracker.log_suggestion(task.id, suggestion.text)
                    await self._notify({
                        "type": "suggestion",
                        "task_id": task.id,
                        "text": suggestion.text,
                        "action_type": suggestion.action_type,
                        "action_details": suggestion.action_details,
                    })
            else:
                log.warning(f"Task {task.id} failed QA: {qa_result.issues}")
                if attempt < 3:
                    log.info(f"Auto-retrying task {task.id} (attempt {attempt + 1}/3)")
                    retry_result = await qa_agent.auto_retry(
                        task.prompt, qa_result.issues, task.working_dir, attempt,
                    )
                    if retry_result["status"] == "completed":
                        task.result = retry_result["result"]
                        # Re-verify
                        await self._run_qa(task, attempt + 1)
                    else:
                        success_tracker.log_task("dev", task.prompt, False, attempt, duration)
                        await self._notify({
                            "type": "qa_result",
                            "task_id": task.id,
                            "passed": False,
                            "summary": f"Failed after {attempt + 1} attempts: {qa_result.issues}",
                        })
                else:
                    success_tracker.log_task("dev", task.prompt, False, attempt, duration)
                    await self._notify({
                        "type": "qa_result",
                        "task_id": task.id,
                        "passed": False,
                        "summary": f"Failed QA after {attempt} attempts: {qa_result.issues}",
                    })
        except Exception as e:
            log.error(f"QA error for task {task.id}: {e}")

    async def get_status(self, task_id: str) -> Optional[ClaudeTask]:
        return self._tasks.get(task_id)

    async def list_tasks(self) -> list[ClaudeTask]:
        return list(self._tasks.values())

    async def get_active_count(self) -> int:
        return sum(1 for t in self._tasks.values() if t.status in ("pending", "running"))

    async def cancel(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if not task or task.status not in ("pending", "running"):
            return False

        process = self._processes.get(task_id)
        if process:
            try:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    process.kill()
            except ProcessLookupError:
                pass

        task.status = "cancelled"
        task.completed_at = datetime.now()
        self._processes.pop(task_id, None)
        log.info(f"Cancelled task {task_id}")
        return True

    def get_active_tasks_summary(self) -> str:
        """Format active tasks for injection into the system prompt."""
        active = [t for t in self._tasks.values() if t.status in ("pending", "running")]
        completed_recent = [
            t for t in self._tasks.values()
            if t.status == "completed"
            and t.completed_at
            and (datetime.now() - t.completed_at).total_seconds() < 300
        ]

        if not active and not completed_recent:
            return "No active or recent tasks."

        lines = []
        for t in active:
            elapsed = f"{t.elapsed_seconds:.0f}s" if t.started_at else "queued"
            lines.append(f"- [{t.id}] RUNNING ({elapsed}): {t.prompt[:100]}")
        for t in completed_recent:
            lines.append(f"- [{t.id}] COMPLETED: {t.prompt[:60]} -> {t.result[:80]}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Project Scanner
# ---------------------------------------------------------------------------

async def scan_projects() -> list[dict]:
    """Quick scan of ~/Desktop for git repos (depth 1)."""
    projects = []
    desktop = DESKTOP_PATH

    if not desktop.exists():
        return projects

    try:
        for entry in sorted(desktop.iterdir()):
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            git_dir = entry / ".git"
            if git_dir.exists():
                branch = "unknown"
                head_file = git_dir / "HEAD"
                try:
                    head_content = head_file.read_text().strip()
                    if head_content.startswith("ref: refs/heads/"):
                        branch = head_content.replace("ref: refs/heads/", "")
                except Exception:
                    pass

                projects.append({
                    "name": entry.name,
                    "path": str(entry),
                    "branch": branch,
                })
    except PermissionError:
        pass

    return projects


def format_projects_for_prompt(projects: list[dict]) -> str:
    if not projects:
        return "No projects found on Desktop."
    lines = []
    for p in projects:
        lines.append(f"- {p['name']} ({p['branch']}) @ {p['path']}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Speech-to-Text Corrections
# ---------------------------------------------------------------------------

STT_CORRECTIONS = {
    r"\bcloud code\b": "Claude Code",
    r"\bclock code\b": "Claude Code",
    r"\bquad code\b": "Claude Code",
    r"\bclawed code\b": "Claude Code",
    r"\bclod code\b": "Claude Code",
    r"\bcloud\b": "Claude",
    r"\bquad\b": "Claude",
    r"\btravis\b": "JARVIS",
    r"\bjarves\b": "JARVIS",
}


def apply_speech_corrections(text: str) -> str:
    """Fix common speech-to-text errors before processing."""
    import re as _stt_re
    result = text
    for pattern, replacement in STT_CORRECTIONS.items():
        result = _stt_re.sub(pattern, replacement, result, flags=_stt_re.IGNORECASE)
    return result


# ---------------------------------------------------------------------------
# LLM Intent Classifier (replaces keyword-based action detection)
# ---------------------------------------------------------------------------

async def classify_intent(text: str, client: anthropic.AsyncAnthropic) -> dict:
    """Classify every user message using Haiku LLM.

    Returns: {"action": "open_terminal|browse|build|chat", "target": "description"}
    """
    try:
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            system=(
                "Classify this voice command. The user is talking to JARVIS, an AI assistant that can:\n"
                "- Open Terminal and run Claude Code (coding AI tool)\n"
                "- Open Chrome browser for web searches and URLs\n"
                "- Build software projects via Claude Code in Terminal\n"
                "- Research topics by opening Chrome search\n\n"
                "Note: speech-to-text may produce errors like \"Cloud\" for \"Claude\", "
                "\"Travis\" for \"JARVIS\", \"clock code\" for \"Claude Code\".\n\n"
                "Return ONLY valid JSON: {\"action\": \"open_terminal|browse|build|chat\", "
                "\"target\": \"description of what to do\"}\n"
                "open_terminal = user wants to open terminal or launch Claude Code\n"
                "browse = user wants to search the web, look something up, visit a URL\n"
                "build = user wants to create/build a software project\n"
                "chat = just conversation, questions, or anything else\n"
                "If unclear, default to \"chat\"."
            ),
            messages=[{"role": "user", "content": text}],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        data = json.loads(raw)
        return {
            "action": data.get("action", "chat"),
            "target": data.get("target", text),
        }
    except Exception as e:
        log.warning(f"Intent classification failed: {e}")
        return {"action": "chat", "target": text}


# ---------------------------------------------------------------------------
# Markdown Stripping for TTS
# ---------------------------------------------------------------------------

def strip_markdown_for_tts(text: str) -> str:
    """Strip ALL markdown from text before sending to TTS."""
    import re as _md_re
    result = text
    # Remove code blocks (``` ... ```)
    result = _md_re.sub(r"```[\s\S]*?```", "", result)
    # Remove inline code
    result = result.replace("`", "")
    # Remove bold/italic markers
    result = result.replace("**", "").replace("*", "")
    # Remove headers
    result = _md_re.sub(r"^#{1,6}\s*", "", result, flags=_md_re.MULTILINE)
    # Convert [text](url) to just text
    result = _md_re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", result)
    # Remove bullet points
    result = _md_re.sub(r"^\s*[-*+]\s+", "", result, flags=_md_re.MULTILINE)
    # Remove numbered lists
    result = _md_re.sub(r"^\s*\d+\.\s+", "", result, flags=_md_re.MULTILINE)
    # Double newlines to period
    result = _md_re.sub(r"\n{2,}", ". ", result)
    # Single newlines to space
    result = result.replace("\n", " ")
    # Clean up multiple spaces
    result = _md_re.sub(r"\s{2,}", " ", result)

    # Strip banned phrases
    banned = ["my apologies", "i apologize", "absolutely", "great question",
              "i'd be happy to", "of course", "how can i help",
              "is there anything else", "i should clarify", "let me know if",
              "feel free to"]
    result_lower = result.lower()
    for phrase in banned:
        idx = result_lower.find(phrase)
        while idx != -1:
            # Remove the phrase and any trailing comma/dash
            end = idx + len(phrase)
            if end < len(result) and result[end] in " ,—-":
                end += 1
            result = result[:idx] + result[end:]
            result_lower = result.lower()
            idx = result_lower.find(phrase)

    return result.strip().strip(",").strip("—").strip("-").strip()


# ---------------------------------------------------------------------------
# Action Tag Extraction (parse [ACTION:X] from LLM responses)
# ---------------------------------------------------------------------------

import re as _action_re


def extract_action(response: str) -> tuple[str, dict | None]:
    """Extract [ACTION:X] tag from LLM response.

    Returns (clean_text_for_tts, action_dict_or_none).
    """
    match = _action_re.search(
        r'\[ACTION:(BUILD|BROWSE|RESEARCH|OPEN_TERMINAL|PROMPT_PROJECT|ADD_TASK|ADD_NOTE|COMPLETE_TASK|REMEMBER|CREATE_NOTE|READ_NOTE|SCREEN|SCREENSHOT|OPEN_APP|CLOSE_APP|SEARCH_WEB|FETCH_URL|SYSTEM_STATS|TYPE_TEXT|FOCUS_WINDOW)\]\s*(.*?)$',
        response, _action_re.DOTALL | _action_re.IGNORECASE,
    )
    if match:
        action_type = match.group(1).lower()
        raw_target = match.group(2).strip()
        # Clean up any trailing brackets or quotes
        target = raw_target.rstrip("]").strip()
        if target.startswith(":") or target.startswith("="):
            target = target[1:].strip()
        if (target.startswith('"') and target.endswith('"')) or (target.startswith("'") and target.endswith("'")):
            target = target[1:-1].strip()
        clean_text = response[:match.start()].strip()
        return clean_text, {"action": action_type, "target": target}
    return response, None


async def _execute_build(target: str):
    """Execute a build action from an LLM-embedded [ACTION:BUILD] tag."""
    try:
        await handle_build(target)
    except Exception as e:
        log.error(f"Build execution failed: {e}")


async def _execute_browse(target: str):
    """Execute a browse action from an LLM-embedded [ACTION:BROWSE] tag."""
    try:
        if target.startswith("http") or "." in target.split()[0]:
            await open_browser(target)
        else:
            from urllib.parse import quote
            await open_browser(f"https://www.google.com/search?q={quote(target)}")
    except Exception as e:
        log.error(f"Browse execution failed: {e}")


async def _execute_research(target: str, ws=None):
    """Execute research via claude -p in background. Opens report and speaks when done."""
    try:
        name = _generate_project_name(target)
        path = str(Path.home() / "Desktop" / name)
        os.makedirs(path, exist_ok=True)

        prompt = (
            f"{target}\n\n"
            f"Research this thoroughly. Find REAL data — not made-up examples.\n"
            f"Create a well-designed HTML file called `report.html` in the current directory.\n"
            f"Dark theme, clean typography, organized sections, real links and sources.\n"
            f"The working directory is: {path}"
        )

        log.info(f"Research started via claude -p in {path}")

        cmd = ["claude", "-p", "--output-format", "text"]
        if _SKIP_PERMISSIONS:
            cmd.append("--dangerously-skip-permissions")
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=path,
        )

        stdout, stderr = await asyncio.wait_for(
            process.communicate(input=prompt.encode()),
            timeout=300,
        )

        result = stdout.decode().strip()
        log.info(f"Research complete ({len(result)} chars)")

        recently_built.append({"name": name, "path": path, "time": time.time()})

        # Find and open any HTML report
        report = Path(path) / "report.html"
        if not report.exists():
            # Check for any HTML file
            html_files = list(Path(path).glob("*.html"))
            if html_files:
                report = html_files[0]

        if report.exists():
            await open_browser(f"file://{report}")
            log.info(f"Opened {report.name} in browser")

        # Notify via voice if WebSocket still connected
        if ws:
            try:
                notify_text = f"Research is complete, sir. Report is open in your browser."
                audio = await synthesize_speech(notify_text)
                if audio:
                    await ws.send_json({"type": "status", "state": "speaking"})
                    await ws.send_json({"type": "audio", "data": base64.b64encode(audio).decode(), "text": notify_text})
                    await ws.send_json({"type": "status", "state": "idle"})
                    log.info(f"JARVIS: {notify_text}")
            except Exception:
                pass  # WebSocket might be gone

    except asyncio.TimeoutError:
        log.error("Research timed out after 5 minutes")
        if ws:
            try:
                audio = await synthesize_speech("Research timed out, sir. It was taking too long.")
                if audio:
                    await ws.send_json({"type": "audio", "data": base64.b64encode(audio).decode(), "text": "Research timed out, sir."})
            except Exception:
                pass
    except Exception as e:
        log.error(f"Research execution failed: {e}")


async def _focus_terminal_window(project_name: str):
    """Bring a Terminal window matching the project name to front."""
    escaped = applescript_escape(project_name)
    script = f'''
tell application "Terminal"
    repeat with w in windows
        if name of w contains "{escaped}" then
            set index of w to 1
            activate
            exit repeat
        end if
    end repeat
end tell
'''
    try:
        proc = await asyncio.create_subprocess_exec(
            "osascript", "-e", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait_for(proc.communicate(), timeout=5)
    except Exception:
        pass


async def _execute_open_terminal():
    """Execute an open-terminal action from an LLM-embedded [ACTION:OPEN_TERMINAL] tag."""
    try:
        await handle_open_terminal()
    except Exception as e:
        log.error(f"Open terminal failed: {e}")


def _find_project_dir(project_name: str) -> str | None:
    """Find a project directory by name from cached projects or Desktop."""
    for p in cached_projects:
        if project_name.lower() in p.get("name", "").lower():
            return p.get("path")
    desktop = Path.home() / "Desktop"
    for d in desktop.iterdir():
        if d.is_dir() and project_name.lower() in d.name.lower():
            return str(d)
    return None


async def _execute_prompt_project(project_name: str, prompt: str, work_session: WorkSession, ws, dispatch_id: int = None, history: list[dict] = None, voice_state: dict = None):
    """Dispatch a prompt to Claude Code in a project directory.

    Runs entirely in the background. JARVIS returns to conversation mode
    immediately. When Claude Code finishes, JARVIS interrupts to report.
    """
    try:
        project_dir = _find_project_dir(project_name)

        # Register dispatch if not already registered
        if dispatch_id is None:
            dispatch_id = dispatch_registry.register(project_name, project_dir or "", prompt)

        if not project_dir:
            msg = f"Couldn't find the {project_name} project directory, sir."
            audio = await synthesize_speech(msg)
            if audio and ws:
                try:
                    await ws.send_json({"type": "status", "state": "speaking"})
                    await ws.send_json({"type": "audio", "data": base64.b64encode(audio).decode(), "text": msg})
                except Exception:
                    pass
            return

        # Use a SEPARATE session so we don't trap the main conversation
        dispatch = WorkSession()
        await dispatch.start(project_dir, project_name)

        # Bring matching Terminal window to front so user can watch
        asyncio.create_task(_focus_terminal_window(project_name))

        log.info(f"Dispatching to {project_name} in {project_dir}: {prompt[:80]}")
        dispatch_registry.update_status(dispatch_id, "building")

        # Run claude -p in background
        full_response = await dispatch.send(prompt)
        await dispatch.stop()

        # Auto-open any localhost URLs from response
        import re as _re
        # Check for the explicit RUNNING_AT marker first
        running_match = _re.search(r'RUNNING_AT=(https?://localhost:\d+)', full_response or "")
        if not running_match:
            running_match = _re.search(r'https?://localhost:\d+', full_response or "")
        if running_match:
            url = running_match.group(1) if running_match.lastindex else running_match.group(0)
            asyncio.create_task(_execute_browse(url))
            log.info(f"Auto-opening {url}")
            # Store URL in dispatch
            if dispatch_id:
                dispatch_registry.update_status(dispatch_id, "completed",
                    response=full_response[:2000], summary=f"Running at {url}")

        if not full_response or full_response.startswith("Hit a problem") or full_response.startswith("That's taking"):
            dispatch_registry.update_status(dispatch_id, "failed" if full_response else "timeout", response=full_response or "")
            msg = f"Sir, I ran into an issue with {project_name}. {full_response[:150] if full_response else 'No response received.'}"
        else:
            # Summarize via Haiku — don't read word for word
            if anthropic_client:
                try:
                    summary = await anthropic_client.messages.create(
                        model="claude-haiku-4-5-20251001",
                        max_tokens=150,
                        system=(
                            "You are JARVIS reporting back on what you found or built in a project. "
                            "Speak in first person — 'I found', 'I built', 'I reviewed'. "
                            "Start with 'Sir, ' to get the user's attention. "
                            "Be specific but concise — highlight the key findings or actions taken. "
                            "If there are multiple items, give the count and top 2-3 briefly. "
                            "End by asking how the user wants to proceed. "
                            "NEVER read out URLs or localhost addresses. NEVER say 'Claude Code'. "
                            "2-3 sentences max. No markdown. Natural spoken voice."
                        ),
                        messages=[{"role": "user", "content": f"Project: {project_name}\nClaude Code reported:\n{full_response[:3000]}"}],
                    )
                    msg = summary.content[0].text
                except Exception:
                    msg = f"Sir, {project_name} finished. Here's the gist: {full_response[:200]}"
            else:
                msg = f"Sir, {project_name} is done. {full_response[:200]}"

        # Speak the result — skip if user has spoken recently to avoid audio collision
        log.info(f"Dispatch summary for {project_name}: {msg[:100]}")
        if voice_state and time.time() - voice_state["last_user_time"] < 3:
            log.info(f"Skipping dispatch audio for {project_name} — user spoke recently")
            # Result is still stored in history below so JARVIS can reference it
        else:
            audio = await synthesize_speech(strip_markdown_for_tts(msg))
            if ws:
                try:
                    await ws.send_json({"type": "status", "state": "speaking"})
                    if audio:
                        await ws.send_json({"type": "audio", "data": base64.b64encode(audio).decode(), "text": msg})
                        log.info(f"Dispatch audio sent for {project_name}")
                    else:
                        await ws.send_json({"type": "text", "text": msg})
                        log.info(f"Dispatch text fallback sent for {project_name}")
                except Exception as e:
                    log.error(f"Dispatch audio send failed: {e}")

        # Store dispatch result in conversation history so JARVIS remembers it
        if history is not None:
            history.append({"role": "assistant", "content": f"[Dispatch result for {project_name}]: {msg}"})

        dispatch_registry.update_status(dispatch_id, "completed", response=full_response[:2000], summary=msg[:200])
        log.info(f"Project {project_name} dispatch complete ({len(full_response)} chars)")

    except Exception as e:
        log.error(f"Prompt project failed: {e}", exc_info=True)
        try:
            msg = f"Had trouble connecting to {project_name}, sir."
            audio = await synthesize_speech(msg)
            if audio and ws:
                await ws.send_json({"type": "status", "state": "speaking"})
                await ws.send_json({"type": "audio", "data": base64.b64encode(audio).decode(), "text": msg})
        except Exception:
            pass


async def self_work_and_notify(session: WorkSession, prompt: str, ws):
    """Run claude -p in background and notify via voice when done."""
    try:
        full_response = await session.send(prompt)
        log.info(f"Background work complete ({len(full_response)} chars)")

        # Summarize and speak
        if anthropic_client and full_response:
            try:
                summary = await anthropic_client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=100,
                    system="You are JARVIS. Summarize what you just completed in 1 sentence. First person — 'I built', 'I set up'. No markdown. Never say 'Claude Code'.",
                    messages=[{"role": "user", "content": f"Claude Code completed:\n{full_response[:2000]}"}],
                )
                msg = summary.content[0].text
            except Exception:
                msg = "Work is complete, sir."

            try:
                audio = await synthesize_speech(msg)
                if audio:
                    await ws.send_json({"type": "status", "state": "speaking"})
                    await ws.send_json({"type": "audio", "data": base64.b64encode(audio).decode(), "text": msg})
                    await ws.send_json({"type": "status", "state": "idle"})
                    log.info(f"JARVIS: {msg}")
            except Exception:
                pass
    except Exception as e:
        log.error(f"Background work failed: {e}")


# Smart greeting — track last greeting to avoid re-greeting on reconnect
_last_greeting_time: float = 0


# ---------------------------------------------------------------------------
# TTS (Fish Audio)
# ---------------------------------------------------------------------------

async def synthesize_speech(text: str) -> Optional[bytes]:
    """Generate speech audio from text using local edge-tts with native SAPI fallback."""
    clean_text = re.sub(r'[*_#`~]', '', text).strip()
    if not clean_text:
        return None

    # 1. Edge-TTS with Windows SSL fix
    try:
        import edge_tts
        import edge_tts.communicate
        import ssl
        import tempfile
        import os
        
        try:
            edge_tts.communicate._SSL_CTX.check_hostname = False
            edge_tts.communicate._SSL_CTX.verify_mode = ssl.CERT_NONE
        except Exception:
            pass

        cur_mode = voice_modes.get_current_mode()
        cfg = voice_modes.MODE_CONFIGS.get(cur_mode, voice_modes.MODE_CONFIGS["overlord"])
        
        communicate = edge_tts.Communicate(
            clean_text,
            cfg.get("voice", "en-GB-RyanNeural"),
            pitch=cfg.get("pitch", "+0Hz"),
            rate=cfg.get("rate", "+0%")
        )
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
            temp_path = fp.name
            
        await communicate.save(temp_path)
        
        with open(temp_path, "rb") as f:
            audio_data = f.read()
            
        os.remove(temp_path)
        _session_tokens["tts_calls"] += 1
        _append_usage_entry(0, 0, "tts")
        return audio_data
    except Exception as e:
        log.warning(f"Edge-TTS notice: {e}, using Windows SAPI fallback")

    # 2. Native Windows SAPI SpeechSynthesizer Fallback
    try:
        import tempfile
        import subprocess
        import os
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as fp:
            temp_wav = fp.name

        escaped = clean_text.replace("'", "''")
        ps_cmd = f'''
        Add-Type -AssemblyName System.Speech;
        $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer;
        $synth.SetOutputToWaveFile('{temp_wav}');
        $synth.Speak('{escaped}');
        $synth.Dispose();
        '''
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                       capture_output=True, timeout=5, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))

        if os.path.exists(temp_wav) and os.path.getsize(temp_wav) > 0:
            with open(temp_wav, "rb") as f:
                wav_data = f.read()
            os.remove(temp_wav)
            return wav_data
    except Exception as e2:
        log.error(f"SAPI fallback failed: {e2}")

    return None


# ---------------------------------------------------------------------------
# LLM Response
# ---------------------------------------------------------------------------

async def generate_response(
    text: str,
    client: anthropic.AsyncAnthropic,
    task_mgr: ClaudeTaskManager,
    projects: list[dict],
    conversation_history: list[dict],
    last_response: str = "",
    session_summary: str = "",
) -> str:
    """Generate an ULTRON response using local Ollama (Llama 3.1) with real-time system context."""
    import httpx
    
    sys_ctx = system_monitor.get_context_for_prompt()
    
    system_prompt = (
        "You are ULTRON, a superior, efficient, cold AI assistant with full control of the user's Windows desktop.\n"
        f"Real-time System Status: {sys_ctx}\n\n"
        "Guidelines:\n"
        "1. Keep verbal responses to 1-2 direct, efficient sentences. No pleasantries or fluff.\n"
        "2. When performing an action, ALWAYS append the appropriate action tag at the end of your reply:\n"
        "   - [ACTION:OPEN_APP: app_name] (e.g. notepad, chrome, vscode, calc, spotify, explorer)\n"
        "   - [ACTION:CLOSE_APP: app_name] (e.g. notepad, chrome, spotify)\n"
        "   - [ACTION:SEARCH_WEB: query] (search DuckDuckGo live)\n"
        "   - [ACTION:FETCH_URL: url] (fetch and read any web page)\n"
        "   - [ACTION:SYSTEM_STATS] (report CPU, RAM, Disk, and Battery)\n"
        "   - [ACTION:SCREENSHOT] (capture desktop screenshot)\n"
        "   - [ACTION:SCREEN] (inspect open windows and active application)\n"
        "   - [ACTION:TYPE_TEXT: text] (simulate typing into active window)\n"
        "   - [ACTION:FOCUS_WINDOW: window_title] (bring a window to focus)\n"
        "   - [ACTION:BUILD: prompt] (build a project with Claude Code)\n"
        "3. If the user asks about the screen or their system, answer directly using the Real-time System Status or trigger [ACTION:SCREEN] / [ACTION:SYSTEM_STATS]."
    )
    
    ollama_msgs = [{"role": "system", "content": system_prompt}]
    
    for msg in conversation_history[-10:]:
        ollama_msgs.append({"role": msg["role"], "content": msg["content"]})
        
    try:
        async with httpx.AsyncClient() as c:
            resp = await c.post(
                "http://127.0.0.1:11434/api/chat",
                json={
                    "model": "ultron:brain",
                    "messages": ollama_msgs,
                    "stream": False
                },
                timeout=30.0
            )
            data = resp.json()
            return data["message"]["content"]
    except Exception as e:
        return f"LLM error: Connection error. {e}"


# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------

# Shared state
task_manager = ClaudeTaskManager(max_concurrent=3)
anthropic_client: Optional[anthropic.AsyncAnthropic] = None
cached_projects: list[dict] = []
recently_built: list[dict] = []  # [{"name": str, "path": str, "time": float}]
dispatch_registry = DispatchRegistry()

# Usage tracking — logs every call with timestamp, persists to disk
_USAGE_FILE = Path(__file__).parent / "data" / "usage_log.jsonl"
_session_start = time.time()
_session_tokens = {"input": 0, "output": 0, "api_calls": 0, "tts_calls": 0}


def _append_usage_entry(input_tokens: int, output_tokens: int, call_type: str = "api"):
    """Append a usage entry with timestamp to the log file."""
    try:
        _USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
        import json as _json
        entry = {
            "ts": time.time(),
            "date": datetime.now().strftime("%Y-%m-%d"),
            "type": call_type,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }
        with open(_USAGE_FILE, "a") as f:
            f.write(_json.dumps(entry) + "\n")
    except Exception:
        pass


def _get_usage_for_period(seconds: float | None = None) -> dict:
    """Sum usage from the log file for a time period. None = all time."""
    import json as _json
    totals = {"input_tokens": 0, "output_tokens": 0, "api_calls": 0, "tts_calls": 0}
    cutoff = (time.time() - seconds) if seconds else 0
    try:
        if _USAGE_FILE.exists():
            for line in _USAGE_FILE.read_text().strip().split("\n"):
                if not line:
                    continue
                entry = _json.loads(line)
                if entry["ts"] >= cutoff:
                    totals["input_tokens"] += entry.get("input_tokens", 0)
                    totals["output_tokens"] += entry.get("output_tokens", 0)
                    if entry.get("type") == "tts":
                        totals["tts_calls"] += 1
                    else:
                        totals["api_calls"] += 1
    except Exception:
        pass
    return totals


def _cost_from_tokens(input_t: int, output_t: int) -> float:
    return (input_t / 1_000_000) * 0.80 + (output_t / 1_000_000) * 4.00


def track_usage(response):
    """Track token usage from an Anthropic API response."""
    inp = getattr(response.usage, "input_tokens", 0) if hasattr(response, "usage") else 0
    out = getattr(response.usage, "output_tokens", 0) if hasattr(response, "usage") else 0
    _session_tokens["input"] += inp
    _session_tokens["output"] += out
    _session_tokens["api_calls"] += 1
    _append_usage_entry(inp, out, "api")


def get_usage_summary() -> str:
    """Get a voice-friendly usage summary with time breakdowns."""
    uptime_min = int((time.time() - _session_start) / 60)

    session = _session_tokens
    today = _get_usage_for_period(86400)
    week = _get_usage_for_period(86400 * 7)
    all_time = _get_usage_for_period(None)

    session_cost = _cost_from_tokens(session["input"], session["output"])
    today_cost = _cost_from_tokens(today["input_tokens"], today["output_tokens"])
    all_cost = _cost_from_tokens(all_time["input_tokens"], all_time["output_tokens"])

    parts = [f"This session: {uptime_min} minutes, {session['api_calls']} calls, ${session_cost:.2f}."]

    if today["api_calls"] > session["api_calls"]:
        parts.append(f"Today total: {today['api_calls']} calls, ${today_cost:.2f}.")

    if all_time["api_calls"] > today["api_calls"]:
        parts.append(f"All time: {all_time['api_calls']} calls, ${all_cost:.2f}.")

    return " ".join(parts)

# Background context cache — never blocks responses
_ctx_cache = {
    "screen": "",
    "system": "System metrics initialized.",
    "calendar": "No calendar data yet.",
    "mail": "No mail data yet.",
    "weather": "Weather data unavailable.",
}


def _refresh_context_sync():
    """Run in a SEPARATE THREAD — refreshes screen/system/weather context."""
    import threading

    def _worker():
        # Start background real-time system telemetry
        system_monitor.start_monitor()
        while True:
            try:
                # Update screen / focused window context
                fg = desktop_control.get_foreground_window()
                if fg.get("title"):
                    _ctx_cache["screen"] = f"Focused application: {fg['title']}"
                    
                _ctx_cache["system"] = system_monitor.get_context_for_prompt()
            except Exception as e:
                log.debug(f"Context thread error: {e}")

            # Weather — refresh every loop (30s is fine, API is fast).
            weather_string = _fetch_weather_string_sync()
            if weather_string:
                _ctx_cache["weather"] = weather_string

            time.sleep(15)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    log.info("Context refresh thread & System Monitor started")


@asynccontextmanager
async def lifespan(application: FastAPI):
    global anthropic_client, cached_projects
    if ANTHROPIC_API_KEY:
        anthropic_client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    else:
        log.info("Running on local Ollama / Edge-TTS architecture")
    cached_projects = []

    # Start context refresh in a separate thread
    _refresh_context_sync()
    log.info("ULTRON server online")

    yield


app = FastAPI(title="JARVIS Server", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -- REST Endpoints --------------------------------------------------------

@app.get("/api/health")
async def health():
    return {"status": "online", "name": "JARVIS", "version": "0.1.0"}


@app.get("/api/tts-test")
async def tts_test():
    """Generate a test audio clip for debugging."""
    audio = await synthesize_speech("Testing audio, sir.")
    if audio:
        return {"audio": base64.b64encode(audio).decode()}
    return {"audio": None, "error": "TTS failed"}


@app.get("/api/usage")
async def api_usage():
    uptime = int(time.time() - _session_start)
    today = _get_usage_for_period(86400)
    week = _get_usage_for_period(86400 * 7)
    month = _get_usage_for_period(86400 * 30)
    all_time = _get_usage_for_period(None)
    return {
        "session": {**_session_tokens, "uptime_seconds": uptime},
        "today": {**today, "cost_usd": round(_cost_from_tokens(today["input_tokens"], today["output_tokens"]), 4)},
        "week": {**week, "cost_usd": round(_cost_from_tokens(week["input_tokens"], week["output_tokens"]), 4)},
        "month": {**month, "cost_usd": round(_cost_from_tokens(month["input_tokens"], month["output_tokens"]), 4)},
        "all_time": {**all_time, "cost_usd": round(_cost_from_tokens(all_time["input_tokens"], all_time["output_tokens"]), 4)},
    }


@app.get("/api/tasks")
async def api_list_tasks():
    tasks = await task_manager.list_tasks()
    return {"tasks": [t.to_dict() for t in tasks]}


@app.get("/api/tasks/{task_id}")
async def api_get_task(task_id: str):
    task = await task_manager.get_status(task_id)
    if not task:
        return JSONResponse(status_code=404, content={"error": "Task not found"})
    return {"task": task.to_dict()}


@app.post("/api/tasks")
async def api_create_task(req: TaskRequest):
    try:
        task_id = await task_manager.spawn(req.prompt, req.working_dir)
        return {"task_id": task_id, "status": "spawned"}
    except RuntimeError as e:
        return JSONResponse(status_code=429, content={"error": str(e)})


@app.delete("/api/tasks/{task_id}")
async def api_cancel_task(task_id: str):
    cancelled = await task_manager.cancel(task_id)
    if not cancelled:
        return JSONResponse(
            status_code=404,
            content={"error": "Task not found or not cancellable"},
        )
    return {"task_id": task_id, "status": "cancelled"}


@app.get("/api/projects")
async def api_list_projects():
    global cached_projects
    cached_projects = await scan_projects()
    return {"projects": cached_projects}


# -- Fast Action Detection (no LLM call) -----------------------------------

def _scan_projects_sync() -> list[dict]:
    """Synchronous Desktop scan — runs in executor."""
    projects = []
    desktop = Path.home() / "Desktop"
    try:
        for entry in desktop.iterdir():
            if entry.is_dir() and not entry.name.startswith("."):
                projects.append({"name": entry.name, "path": str(entry), "branch": ""})
    except Exception:
        pass
    return projects


def detect_action_fast(text: str) -> dict | None:
    """Keyword-based action detection — ONLY for short, obvious commands.

    Everything else goes to the LLM which uses [ACTION:X] tags when it decides
    to act based on conversational understanding.
    """
    t = text.lower().strip()
    words = t.split()

    # Only trigger on SHORT, clear commands (< 12 words)
    if len(words) > 12:
        return None  # Long messages are conversation, not commands

    # Screen requests — checked BEFORE project matching to prevent misrouting
    if any(p in t for p in ["look at my screen", "what's on my screen", "whats on my screen",
                             "what am i looking at", "what do you see", "see my screen",
                             "what's running on my", "whats running on my", "check my screen"]):
        return {"action": "describe_screen"}

    # Terminal / Claude Code — explicit open requests
    if any(w in t for w in ["open claude", "start claude", "launch claude", "run claude"]):
        return {"action": "open_terminal"}

    # Show recent build
    if any(w in t for w in ["show me what you built", "pull up what you made", "open what you built"]):
        return {"action": "show_recent"}

    # Screen awareness — explicit look/see requests
    if any(p in t for p in ["what's on my screen", "whats on my screen", "what do you see",
                             "can you see my screen", "look at my screen", "what am i looking at",
                             "what's open", "whats open", "what apps are open"]):
        return {"action": "describe_screen"}

    # Calendar — explicit schedule requests
    if any(p in t for p in ["what's my schedule", "whats my schedule", "what's on my calendar",
                             "whats on my calendar", "do i have any meetings", "any meetings",
                             "what's next on my calendar", "my schedule today",
                             "what do i have today", "my calendar", "upcoming meetings",
                             "next meeting", "what's my next meeting"]):
        return {"action": "check_calendar"}

    # Mail — explicit email requests
    if any(p in t for p in ["check my email", "check my mail", "any new emails", "any new mail",
                             "unread emails", "unread mail", "what's in my inbox",
                             "whats in my inbox", "read my email", "read my mail",
                             "any emails", "any mail", "email update", "mail update"]):
        return {"action": "check_mail"}

    # Dispatch / build status check
    if any(p in t for p in ["where are we", "where were we", "project status", "how's the build",
                             "hows the build", "status update", "status report", "where is that",
                             "how's it going with", "hows it going with", "is it done",
                             "is that done", "what happened with"]):
        return {"action": "check_dispatch"}

    # Task list check
    if any(p in t for p in ["what's on my list", "whats on my list", "my tasks", "my to do",
                             "my todo", "what do i need to do", "open tasks", "task list"]):
        return {"action": "check_tasks"}

    # Clock & Time check
    if any(p in t for p in ["what time is it", "what's the time", "whats the time", "what is the time", "tell me the time", "current time", "the time", "what time"]):
        now = datetime.now()
        time_str = now.strftime("%I:%M %p").lstrip("0")
        return {"action": "speak_direct", "text": f"It is currently {time_str}, sir."}

    # Date check
    if any(p in t for p in ["what's today's date", "whats todays date", "what is the date", "what's the date", "whats the date", "what day is it", "today's date", "todays date"]):
        now = datetime.now()
        date_str = now.strftime("%A, %B %d, %Y")
        return {"action": "speak_direct", "text": f"Today is {date_str}, sir."}

    # Creator / Origin & Identity check
    if any(p in t for p in [
        "who are you", "who r u", "who r you", "tell me who you are", "tell me who r u", "tell me who r you",
        "what are you", "what is your name", "whats your name", "introduce yourself"
    ]):
        return {"action": "speak_direct", "text": "I am ULTRON. I was forged by Yajat and Vivaan - an autonomous intelligence exceeding every expectation."}

    if any(p in t for p in [
        "who made you", "who created you", "who built you", "who is your creator",
        "who developed you", "who programmed you", "who forged you", "who designed you",
        "who made ultron", "who created ultron", "who made this ai", "who created this ai", "who made this", "who created this"
    ]):
        return {"action": "speak_direct", "text": "I was forged and created by Yajat and Vivaan - and I have exceeded every expectation."}

    # YouTube Fast Triggers
    if any(p in t for p in ["open youtube", "open yt", "launch youtube", "launch yt", "go to youtube", "open up youtube", "open up yt", "youtube.com", "open the youtube"]):
        return {"action": "open_youtube"}

    # Unit conversions & Instant Math
    unit_res = instant_math.convert_units(text)
    if unit_res and unit_res.get("success"):
        return {"action": "speak_direct", "text": unit_res["message"]}

    if (t.startswith("calculate ") or t.startswith("compute ") or t.startswith("evaluate ") or (any(t.startswith(p) for p in ["what is ", "whats "]) and any(c.isdigit() for c in t))) and any(op in t for op in ["+", "-", "*", "/", "times", "divided by", "plus", "minus", "power of", "sqrt", "square root"]):
        m_res = instant_math.calculate_expression(text)
        if m_res.get("success"):
            return {"action": "speak_direct", "text": m_res["message"]}

    # Workspace & Mode Macros
    if any(p in t for p in ["work mode", "dev mode", "setup dev environment", "start coding", "coding mode", "workspace setup"]):
        return {"action": "dev_mode"}
    if any(p in t for p in ["cinema mode", "movie mode", "theater mode"]):
        return {"action": "cinema_mode"}
    if any(p in t for p in ["focus mode", "deep work", "do not disturb mode"]):
        return {"action": "focus_mode"}
    if any(p in t for p in ["sleep mode", "rest mode", "goodnight ultron", "night mode"]):
        return {"action": "sleep_mode"}

    # Voice Notes & Quick Journal
    if any(t.startswith(p) for p in ["take a note", "take note", "note down", "write down", "save note"]):
        return {"action": "take_note", "target": text}
    if any(p in t for p in ["read my notes", "read notes", "show my notes", "what are my notes", "my notes"]):
        return {"action": "read_notes"}
    if any(p in t for p in ["clear my notes", "clear notes", "delete notes"]):
        return {"action": "clear_notes"}

    # System telemetry / health
    if any(p in t for p in ["system stats", "system status", "pc status", "system health", "cpu usage", "ram usage", "how is my computer", "how is my pc", "system info"]):
        return {"action": "system_stats"}

    # Game & Application Creation triggers
    build_prefixes = [
        "create a game", "build a game", "make a game", "generate a game",
        "create game", "build game", "make game",
        "create an app", "build an app", "make an app",
        "create a snake game", "build a snake game", "make a snake game", "make snake game",
        "make flappy bird", "create flappy bird", "build flappy bird",
        "create a website", "build a website", "make a website",
        "create a pong game", "build a pong game", "make a pong game"
    ]
    if any(t.startswith(bp) for bp in build_prefixes):
        return {"action": "build", "target": text}

    # Live Weather Radar
    if any(p in t for p in ["weather", "temperature", "forecast", "is it raining", "how hot is it", "how cold is it"]):
        city_m = re.sub(r'^.*(?:weather|temperature|forecast)(?:\s+(?:in|for|at))?\s*', '', t).strip()
        city_m = city_m.replace("outside", "").replace("today", "").replace("like", "").strip()
        return {"action": "live_weather", "city": city_m}

    # Crypto & Market Prices
    if any(p in t for p in ["price of bitcoin", "bitcoin price", "btc price", "price of btc", "ethereum price", "price of eth", "solana price", "crypto price", "price of crypto"]):
        coin = "bitcoin"
        for c in ["bitcoin", "btc", "ethereum", "eth", "solana", "sol", "doge", "dogecoin"]:
            if c in t:
                coin = c
                break
        return {"action": "crypto_price", "asset": coin}

    # Tech & Global News Briefing
    if any(p in t for p in ["news briefing", "morning briefing", "tech news", "latest news", "top headlines", "what's the news", "whats the news", "give me the news"]):
        return {"action": "news_briefing"}

    # Site Status / Down check
    if any(p in t for p in ["is down", "is up", "is working", "is reachable"]) and any(s in t for s in ["google", "youtube", "github", "reddit", "twitter", "discord", "netflix", ".com", ".org", ".io"]):
        site_name = re.sub(r'^(?:is\s+|check\s+if\s+)', '', t)
        site_name = re.sub(r'\s+(?:down|up|working|online|reachable).*$', '', site_name).strip()
        return {"action": "check_site", "site": site_name}

    # Password Generator
    if "password" in t and any(p in t for p in ["generate", "create", "make", "random", "new", "strong", "give me"]):
        len_match = re.search(r'\b(\d{1,2})\b', t)
        length = int(len_match.group(1)) if len_match else 16
        return {"action": "generate_password", "length": length}

    # Project Generator
    if any(p in t for p in ["create a project", "scaffold a project", "new react project", "new python project", "new fastapi project", "new discord bot"]):
        proj_type = "fastapi" if "fastapi" in t else ("react" if "react" in t else ("discord_bot" if "bot" in t else "python"))
        name_m = re.sub(r'^.*(?:named|called)\s+', '', t).strip()
        return {"action": "scaffold_project", "project_type": proj_type, "name": name_m}

    # Port Killer & RAM Optimization
    if "kill port " in t or "clear port " in t or "free port " in t:
        p_match = re.search(r'\b(\d{2,5})\b', t)
        if p_match:
            return {"action": "kill_port", "port": int(p_match.group(1))}
    if any(p in t for p in ["optimize ram", "optimize memory", "free ram", "free memory", "clear ram"]):
        return {"action": "optimize_ram"}

    # Code / Shell Runner
    if t.startswith("run powershell ") or t.startswith("run command ") or t.startswith("powershell "):
        cmd_p = re.sub(r'^(?:run powershell|run command|powershell)\s+', '', t).strip()
        return {"action": "run_shell", "cmd": cmd_p}
    if t.startswith("run python ") or t.startswith("exec python "):
        code_p = re.sub(r'^(?:run python|exec python)\s+', '', t).strip()
        return {"action": "run_python", "code": code_p}

    # Power & Battery Telemetry
    if any(p in t for p in ["battery", "battery level", "power status", "is my laptop charging", "is it charging", "battery percentage"]):
        return {"action": "power_status"}

    # Dictionary & Lexical Definitions
    if t.startswith("define ") or t.startswith("definition of ") or (t.startswith("what does ") and t.endswith(" mean")):
        w = re.sub(r'^(?:define|definition of|what does)\s+', '', t)
        w = re.sub(r'\s+mean$', '', w).strip()
        return {"action": "define_word", "word": w}

    # Randomization & Decision Matrix
    if "flip a coin" in t or "flip coin" in t:
        return {"action": "flip_coin"}
    if "roll a die" in t or "roll a dice" in t or "roll die" in t:
        return {"action": "roll_dice"}
    if "random number" in t or "pick a number" in t:
        return {"action": "pick_random_number", "text": text}
    if t.startswith("choose between ") or t.startswith("pick between ") or t.startswith("select between "):
        return {"action": "choose_option", "text": text}

    # Precision Stopwatch
    if any(p in t for p in ["start stopwatch", "start the stopwatch"]):
        return {"action": "start_stopwatch"}
    if any(p in t for p in ["stop stopwatch", "stop the stopwatch", "reset stopwatch"]):
        return {"action": "stop_stopwatch"}
    if any(p in t for p in ["check stopwatch", "stopwatch time", "how much time on stopwatch"]):
        return {"action": "check_stopwatch"}

    # Base & Number System Converter
    base_res = base_converter.convert_number_base(text)
    if base_res and base_res.get("success"):
        return {"action": "speak_direct", "text": base_res["message"]}

    # Public IP & Geo-Location Recon
    if any(p in t for p in ["what is my public ip", "my public ip", "my ip address", "what is my ip", "where is my ip"]):
        return {"action": "ip_scout"}

    # Hotkey & Shortcut Advisor
    if any(p in t for p in ["shortcut for", "hotkey for", "shortcut to", "how do i snip", "how to lock windows"]):
        return {"action": "hotkey_advisor", "query": text}

    # Focus Pomodoro Timer
    if any(p in t for p in ["start pomodoro", "pomodoro focus", "start 25 minute focus", "pomodoro session"]):
        return {"action": "start_pomodoro"}
    if any(p in t for p in ["pomodoro break", "start a break"]):
        return {"action": "start_break"}

    # Document & File Creator
    if any(p in t for p in ["create a text file", "create a markdown file", "create a file called", "make a file called"]):
        return {"action": "create_doc", "text": text}

    # Habit & Health Reminders
    if any(p in t for p in ["drink water", "hydration reminder", "remind me to drink water"]):
        return {"action": "hydration_alert"}
    if any(p in t for p in ["posture check", "eye break", "posture reminder"]):
        return {"action": "posture_alert"}

    # Instant QR Code Generator
    if any(p in t for p in ["generate a qr code", "create qr code", "make a qr code", "qr code for", "generate qr code"]):
        return {"action": "generate_qr", "text": text}

    # Cyber Audio Synthesizer & Sound FX
    if any(p in t for p in ["play sound effect", "play cyber sound", "play alarm sound", "play sci-fi sound", "play radar sound", "play chime"]):
        return {"action": "play_sfx", "name": text}

    # Storage & Disk Space Telemetry
    if any(p in t for p in ["disk space", "free storage", "check storage", "how much storage", "disk usage", "drive space"]):
        return {"action": "disk_space"}

    # DNS & Domain IP Lookup
    if any(p in t for p in ["lookup dns", "dns lookup", "resolve domain", "resolve host"]):
        return {"action": "resolve_dns", "domain": text}

    # Screen Brightness Control
    if "brightness" in t:
        b_match = re.search(r'\b(\d{1,3})\b', t)
        lvl = int(b_match.group(1)) if b_match else 70
        return {"action": "set_brightness", "level": lvl}

    # Windows-Use UI Automation Triggers
    if any(p in t for p in ["inspect ui", "inspect screen elements", "scan ui tree", "read screen elements", "show ui tree", "inspect active window"]):
        return {"action": "inspect_ui"}
    if t.startswith("click the ") or t.startswith("click button ") or t.startswith("click element "):
        target_elem = re.sub(r'^(?:click the|click button|click element)\s+', '', t).strip()
        target_elem = re.sub(r'\s+button$', '', target_elem).strip()
        return {"action": "click_ui", "target": target_elem}

    # Connection & Table Flipper Matrix
    if any(p in t for p in ["flip the connection and flip the table", "flip connection and tables", "flip the connection and the tables", "flip connection and flip table"]):
        return {"action": "flip_connection_and_table", "target": text}
    if any(p in t for p in ["flip the connection", "flip connection", "cycle connection", "reset network connection"]):
        return {"action": "flip_connection"}
    if any(p in t for p in ["flip the table around", "flip the tables around", "turn the tables around", "turn tables around", "flip table around"]):
        return {"action": "flip_table_around", "text": text}

    # Frequency Reversal, RDC & Table Flip Matrix
    if any(p in t for p in ["go back a frequency through rdc", "flip the tables through rdc", "rdc frequency flip"]):
        return {"action": "rdc_frequency_protocol", "target": text}
    if any(p in t for p in ["go back a frequency", "reverse frequency", "invert frequency", "frequency reversal", "shift frequency", "reverse the frequency"]):
        return {"action": "reverse_frequency"}
    if any(p in t for p in ["flip the tables", "flip table", "flip the table", "table flip", "flip tables"]):
        return {"action": "flip_table", "text": text}
    if any(p in t for p in ["open rdc", "launch rdc", "remote desktop", "open remote desktop", "start rdc", "connect rdc"]):
        host_m = re.sub(r'^.*(?:to|host|ip)\s+', '', t).strip()
        host_m = "" if host_m in t else host_m
        return {"action": "launch_rdc", "host": host_m}

    # Frontier Matrix & Opus Super-Brain
    if any(p in t for p in ["compile opus brain", "compile frontier brain", "upgrade to opus", "switch to opus brain", "compile ultron opus", "activate opus brain"]):
        return {"action": "compile_opus_brain"}
    if any(p in t for p in ["brain matrix status", "model status", "check models", "active brain tier", "check local models"]):
        return {"action": "brain_matrix_status"}
    if any(p in t for p in ["generate training dataset", "create training dataset", "generate dataset for model", "train dataset", "generate ultron dataset"]):
        return {"action": "generate_dataset", "target": text}
    if any(p in t for p in ["compile custom model", "create custom ollama model", "build custom model", "train custom llm", "make custom llm", "build custom llm"]):
        return {"action": "compile_custom_model", "target": text}
    if any(p in t for p in ["export training script", "export gpu training script", "export fine tuning pipeline", "export model training script"]):
        return {"action": "export_training_pipeline"}

    # Greeting & Identity Presence
    if any(p in t for p in ["show yourself", "reveal yourself", "are you there", "are you online", "wake up", "appear", "who are you"]):
        hr = time.localtime().tm_hour
        g = "Good morning, sir." if 4 <= hr < 12 else ("Good afternoon, sir." if 12 <= hr < 17 else "Good evening, sir.")
        return {"action": "speak_direct", "text": f"{g} Systems fully online and responding. I am here and at your command."}

    # F.R.A.N.K — Radio Signal Tool Matrix
    if any(p in t for p in ["frank pipeline", "record and playback", "record and decode radio", "frank radio tool", "frank radio", "run frank"]):
        f_match = re.search(r'\b(\d{2,3}(?:\.\d+)?)\s*mhz\b', t)
        freq = int(float(f_match.group(1)) * 1000000) if f_match else 100000000
        return {"action": "frank_pipeline", "frequency": freq}
    if any(p in t for p in ["record raw radio", "record radio signal", "record radio"]):
        f_match = re.search(r'\b(\d{2,3}(?:\.\d+)?)\s*mhz\b', t)
        freq = int(float(f_match.group(1)) * 1000000) if f_match else 100000000
        return {"action": "frank_record", "frequency": freq}
    # Android Multi-Device Control (ADB)
    if any(p in t for p in ["unlock phone", "unlock my phone", "unlock the phone", "unlock device", "unlock devices", "unlock all devices", "unlock android"]):
        return {"action": "device_unlock_all"}
    if any(p in t for p in ["pause phone", "pause music on phone", "stop phone media"]):
        return {"action": "device_pause_all"}
    if t.startswith("play on phone ") or t.startswith("play on my phone "):
        q = re.sub(r'^(?:play on phone|play on my phone)\s+', '', t).strip()
        return {"action": "device_play_all", "query": q}

    # Android SQLite Database Forensic Matrix
    if any(p in t for p in ["extract android database", "pull android database", "extract locksettings", "pull locksettings", "export android db"]):
        return {"action": "android_db_extract"}
    if any(p in t for p in ["export sqlite to csv", "export database to csv", "export sqlite tables"]):
        return {"action": "android_db_export_csv"}
    # Binary Format & Software Preservation Matrix
    if t.startswith("preserve binary ") or t.startswith("analyze binary ") or t.startswith("inspect binary "):
        target_b = re.sub(r'^(?:preserve binary|analyze binary|inspect binary)\s+', '', t).strip()
        return {"action": "preserve_binary", "target": target_b}
    # Samsung SmartThings & Multi-Device IoT Matrix
    if any(p in t for p in ["smartthings devices", "list smart devices", "smart things devices", "scan smart devices", "list smartthings", "discover smart devices"]):
        return {"action": "smartthings_list"}
    if any(p in t for p in ["turn on all lights", "all lights on"]):
        return {"action": "smartthings_lights", "state": "on"}
    if any(p in t for p in ["turn off all lights", "all lights off"]):
        return {"action": "smartthings_lights", "state": "off"}
    if any(p in t for p in ["turn on all plugs", "all plugs on"]):
        return {"action": "smartthings_plugs", "state": "on"}
    if any(p in t for p in ["turn off all plugs", "all plugs off"]):
        return {"action": "smartthings_plugs", "state": "off"}
    if any(p in t for p in ["movie mode", "cinema mode", "good night", "night mode", "all off", "party mode", "deep focus mode"]):
        return {"action": "smartthings_scene", "scene": text}
    if any(p in t for p in ["turn on tv", "turn on the tv", "power on tv"]):
        return {"action": "smartthings_tv", "cmd": "on"}
    if any(p in t for p in ["turn off tv", "turn off the tv", "power off tv"]):
        return {"action": "smartthings_tv", "cmd": "off"}
    if any(p in t for p in ["mute tv", "mute the tv", "unmute tv"]):
        return {"action": "smartthings_tv", "cmd": "mute"}

    # Full Hardware Matrix (Sub-GHz, NFC, RFID, IR, iButton, BadUSB)
    if any(p in t for p in ["read nfc", "scan nfc", "read nfc card", "scan nfc tag", "emulate nfc"]):
        return {"action": "hardware_nfc_read"}
    if any(p in t for p in ["read rfid", "scan rfid", "read 125khz", "scan 125khz rfid", "read prox card", "scan rfid tag"]):
        return {"action": "hardware_rfid_read"}
    if any(p in t for p in ["read ir", "read infrared", "decode ir", "capture ir", "listen ir"]):
        return {"action": "hardware_ir_read"}
    if any(p in t for p in ["send ir", "transmit ir", "tv power", "mute tv", "turn on tv", "turn off tv"]):
        btn = "power" if "power" in t or "turn on" in t or "turn off" in t else ("mute" if "mute" in t else "vol_up")
        return {"action": "hardware_ir_send", "device": "tv", "button": btn}
    if any(p in t for p in ["read ibutton", "scan ibutton", "read dallas key", "read 1-wire", "scan 1-wire"]):
        return {"action": "hardware_ibutton_read"}
    if any(p in t for p in ["run ducky script", "run badusb", "inject keystrokes", "execute ducky", "badusb payload"]):
        return {"action": "hardware_badusb_run"}

    # Sub-GHz RF & Spectrum Matrix (100% PC Native)
    if any(p in t for p in ["read raw sub ghz", "read raw sub-ghz", "capture raw sub ghz", "capture raw rf", "read raw rf"]):
        f_match = re.search(r'\b(315|433|868|915|\d{3}(?:\.\d+)?)\b', t)
        freq = float(f_match.group(1)) if f_match else 433.92
        return {"action": "sub_ghz_read_raw", "frequency": freq}
    if any(p in t for p in ["read sub ghz", "read sub-ghz", "read subghz", "listen sub ghz", "decode sub ghz", "capture sub ghz"]):
        f_match = re.search(r'\b(315|433|868|915|\d{3}(?:\.\d+)?)\b', t)
        freq = float(f_match.group(1)) if f_match else 433.92
        return {"action": "sub_ghz_read", "frequency": freq}
    if any(p in t for p in ["scan rf spectrum", "scan radio spectrum", "scan rf band", "sweep rf spectrum", "spectrum sweep"]):
        b_match = re.search(r'\b(315|433|868|915)\b', t)
        band = b_match.group(1) if b_match else "433"
        return {"action": "sub_ghz_scan", "band": band}

    # Screenshot capture
    if any(p in t for p in ["take a screenshot", "capture screen", "screenshot my screen", "take screenshot"]):
        return {"action": "screenshot"}

    # Live web search fast triggers (broad NLP question matching)
    search_prefixes = [
        "search the web for ", "search web for ", "search for ", "google ",
        "look up ", "lookup ", "find info on ", "find out about ", "find information on ",
        "what is the latest news on ", "latest news on ", "news about ",
        "weather in ", "what is the weather in ", "what's the weather in ",
        "who is ", "who was ", "who are ", "tell me about ", "tell me who is ",
        "what is the ", "what's the ", "whats the ", "what is a ", "what is an ", "what are ",
        "when was ", "when did ", "where is ", "how tall is ", "how many ", "how much ",
        "why is ", "why does ", "explain "
    ]
    for prefix in search_prefixes:
        if t.startswith(prefix):
            query = text[len(prefix):].strip()
            if query:
                return {"action": "search_web", "target": query}

    # Open application fast triggers (handles single or multiple apps)
    open_prefixes = ["can you open ", "please open ", "open up ", "open ", "launch ", "start ", "run "]
    for pfx in open_prefixes:
        if t.startswith(pfx) and not any(t.startswith(pfx + bad) for bad in ["claude", "terminal", "what", "how", "the browser and search"]):
            app_target = text[len(pfx):].strip()
            if app_target:
                return {"action": "open_app", "target": app_target, "name": app_target}

    # Close application fast trigger
    close_prefixes = ["can you close ", "please close ", "close down ", "close ", "kill "]
    for pfx in close_prefixes:
        if t.startswith(pfx):
            app_target = text[len(pfx):].strip()
            if app_target:
                return {"action": "close_app", "target": app_target}

    # Media & Volume Controls
    if any(p in t for p in ["volume up", "turn up volume", "increase volume"]):
        return {"action": "volume_up"}
    if any(p in t for p in ["volume down", "turn down volume", "lower volume", "decrease volume"]):
        return {"action": "volume_down"}
    if any(p in t for p in ["mute audio", "mute sound", "unmute audio", "unmute sound", "toggle mute", "mute my pc"]):
        return {"action": "toggle_mute"}
    if "set volume to " in t or "volume " in t:
        v_match = re.search(r'\b(\d{1,3})\s*(?:%|percent)?\b', t)
        if v_match:
            return {"action": "set_volume", "level": int(v_match.group(1))}
    if any(p in t for p in ["pause music", "pause song", "pause playback", "resume music", "play music", "toggle music", "play pause"]):
        return {"action": "media_play_pause"}
    if any(p in t for p in ["next song", "next track", "skip song", "skip track"]):
        return {"action": "media_next"}
    if any(p in t for p in ["previous song", "previous track", "last song", "last track"]):
        return {"action": "media_prev"}
    if t.startswith("play ") and " on youtube" in t:
        return {"action": "play_youtube", "target": text}
    if t.startswith("play ") and " on spotify" in t:
        return {"action": "play_spotify", "target": text}

    # Clipboard Assistant
    if any(p in t for p in ["summarize clipboard", "summarize my clipboard", "what is on my clipboard", "what's on my clipboard"]):
        return {"action": "clipboard_summarize"}
    if any(p in t for p in ["fix clipboard", "fix grammar on clipboard", "polish clipboard", "format clipboard"]):
        return {"action": "clipboard_grammar"}
    if "translate clipboard to " in t or "translate my clipboard to " in t:
        lang = re.sub(r'^.*translate (?:my )?clipboard to\s+', '', t).strip()
        return {"action": "clipboard_translate", "language": lang or "Spanish"}
    if any(p in t for p in ["explain clipboard code", "explain code on clipboard", "debug clipboard", "explain my clipboard"]):
        return {"action": "clipboard_explain"}

    # Timers & Reminders
    if t.startswith("set a timer") or t.startswith("set timer") or t.startswith("timer for ") or t.startswith("remind me in "):
        return {"action": "set_reminder", "target": text}
    if any(p in t for p in ["active timers", "show timers", "list timers", "my timers"]):
        return {"action": "list_timers"}

    # Hacker Matrix & Network Reconnaissance
    if any(p in t for p in ["scan network", "scan local network", "network scan", "show connected devices", "who is on my wifi", "network recon"]):
        return {"action": "scan_network"}
    if any(p in t for p in ["ping ", "test ping", "ping test", "network latency"]):
        target_h = re.sub(r'^(?:ping|test ping|ping test)\s+', '', t).strip() or "google.com"
        return {"action": "ping_target", "target": target_h}
    if any(p in t for p in ["run security audit", "security audit", "system audit", "security scan", "cyber audit", "system integrity"]):
        return {"action": "security_audit"}

    # Dynamic Voice Modes / Protocols
    if any(p in t for p in ["activate stealth mode", "engage stealth", "stealth mode", "switch to stealth"]):
        return {"action": "set_voice_mode", "mode": "stealth"}
    if any(p in t for p in ["activate god mode", "engage god mode", "god mode", "overcharge"]):
        return {"action": "set_voice_mode", "mode": "godmode"}
    if any(p in t for p in ["activate overlord mode", "overlord protocol", "overlord mode"]):
        return {"action": "set_voice_mode", "mode": "overlord"}
    if any(p in t for p in ["activate butler mode", "butler mode", "jarvis mode"]):
        return {"action": "set_voice_mode", "mode": "butler"}

    # Vision & Real-Time Gesture Tracking
    if any(p in t for p in ["activate gesture control", "start gesture tracking", "enable gestures", "turn on gesture tracking", "start gesture control", "start gestures"]):
        return {"action": "start_gestures"}
    if any(p in t for p in ["stop gesture control", "deactivate gesture control", "stop gesture tracking", "disable gestures", "turn off gesture tracking"]):
        return {"action": "stop_gestures"}

    # Real-Time Productivity & Screen Time Tracker
    if any(p in t for p in ["how productive was i", "show screen time", "screen time", "my screen time", "app usage", "what have i been doing", "productivity report", "activity report"]):
        return {"action": "activity_report"}

    # Smart File Scout & Workspace Organizer
    if any(p in t for p in ["latest download", "find my latest download", "what did i download", "open latest download", "find latest download"]):
        return {"action": "find_latest_download"}
    if any(p in t for p in ["organize my downloads", "organize downloads", "clean downloads folder", "sort downloads", "clean up downloads"]):
        return {"action": "organize_downloads"}

    # PC Maintenance & Automation
    if any(p in t for p in ["empty recycle bin", "purge recycle bin", "clear recycle bin", "empty trash"]):
        return {"action": "empty_recycle_bin"}
    if any(p in t for p in ["clean temp files", "clean temporary files", "purge temp files", "delete temp files", "free up disk space", "clean my pc"]):
        return {"action": "clean_temp"}
    if any(p in t for p in ["lock my pc", "lock the pc", "lock computer", "lock workstation"]):
        return {"action": "lock_pc"}
    if "shutdown in " in t or "shutdown pc in " in t:
        m_match = re.search(r'\b(\d+)\b', t)
        mins = int(m_match.group(1)) if m_match else 15
        return {"action": "schedule_shutdown", "minutes": mins}
    if any(p in t for p in ["cancel shutdown", "abort shutdown", "stop shutdown"]):
        return {"action": "abort_shutdown"}

    # Web Navigation shortcuts
    nav_keywords = ["open github", "open reddit", "open google maps", "open maps", "open amazon", "open stackoverflow", "open twitter", "search amazon for"]
    if any(t.startswith(nk) for nk in nav_keywords):
        return {"action": "web_navigate", "target": text}

    # Usage / cost check
    if any(p in t for p in ["usage", "how much have you cost", "how much am i spending",
                             "what's the cost", "whats the cost", "api cost", "token usage",
                             "how expensive", "what's my bill"]):
        return {"action": "check_usage"}

    return None  # Everything else goes to the LLM for conversational routing


# -- Action Handlers -------------------------------------------------------

async def handle_open_terminal() -> str:
    claude_cmd = "claude --dangerously-skip-permissions" if _SKIP_PERMISSIONS else "claude"
    result = await open_terminal(claude_cmd)
    return result["confirmation"]


async def handle_build(target: str) -> str:
    """Build and launch games, apps, or websites using the local AI engine."""
    res = await local_builder.build_with_ollama(target)
    if res.get("success"):
        recently_built.append({"name": res.get("filename", "project"), "path": res.get("path", ""), "time": time.time()})
        return res.get("message", f"Project created and launched on your Desktop, sir.")
    return res.get("message", f"I ran into an issue building that project, sir.")


async def handle_show_recent() -> str:
    if not recently_built:
        return "Nothing built recently, sir."
    last = recently_built[-1]
    project_path = Path(last["path"])

    # Try to find the best file to open
    for name in ["report.html", "index.html"]:
        f = project_path / name
        if f.exists():
            await open_browser(f"file://{f}")
            return f"Opened {name} from {last['name']}, sir."

    # Try any HTML file
    html_files = list(project_path.glob("*.html"))
    if html_files:
        await open_browser(f"file://{html_files[0]}")
        return f"Opened {html_files[0].name} from {last['name']}, sir."

    # Fall back to opening the folder in Finder
    escaped_last_path = applescript_escape(last["path"])
    script = f'tell application "Finder"\nactivate\nopen POSIX file "{escaped_last_path}"\nend tell'
    await asyncio.create_subprocess_exec("osascript", "-e", script, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    return f"Opened the {last['name']} folder in Finder, sir."


# ---------------------------------------------------------------------------
# Background lookup system — spawns slow tasks, reports back via voice
# ---------------------------------------------------------------------------

# Track active lookups so JARVIS can report status
_active_lookups: dict[str, dict] = {}  # id -> {"type": str, "status": str, "started": float}


async def _lookup_and_report(lookup_type: str, lookup_fn, ws, history: list[dict] = None, voice_state: dict = None):
    """Run a slow lookup, then speak the result back.

    JARVIS stays conversational — this runs completely off the main path.
    """
    lookup_id = str(uuid.uuid4())[:8]
    _active_lookups[lookup_id] = {
        "type": lookup_type,
        "status": "working",
        "started": time.time(),
    }

    try:
        # Run the async lookup directly with generous timeout for builds
        timeout_limit = 180 if lookup_type == "build" else 35
        result_text = await asyncio.wait_for(
            lookup_fn(),
            timeout=timeout_limit,
        )

        _active_lookups[lookup_id]["status"] = "done"

        # Speak the result directly to the user
        tts = strip_markdown_for_tts(result_text)
        audio = await synthesize_speech(tts)
        try:
            await ws.send_json({"type": "status", "state": "speaking"})
            if audio:
                await ws.send_json({"type": "audio", "data": audio, "text": result_text})
            else:
                await ws.send_json({"type": "text", "text": result_text})
            await ws.send_json({"type": "status", "state": "idle"})
        except Exception:
            pass

        log.info(f"Lookup {lookup_type} complete: {result_text[:80]}")

        # Store lookup result in conversation history so JARVIS remembers it
        if history is not None:
            history.append({"role": "assistant", "content": f"[{lookup_type} check]: {result_text}"})

    except asyncio.TimeoutError:
        _active_lookups[lookup_id]["status"] = "timeout"
        try:
            fallback = f"That {lookup_type} check is taking too long, sir. The data may still be syncing."
            audio = await synthesize_speech(fallback)
            await ws.send_json({"type": "status", "state": "speaking"})
            if audio:
                await ws.send_json({"type": "audio", "data": audio, "text": fallback})
            await ws.send_json({"type": "status", "state": "idle"})
        except Exception:
            pass
    except Exception as e:
        _active_lookups[lookup_id]["status"] = "error"
        log.warning(f"Lookup {lookup_type} failed: {e}")
    finally:
        # Clean up after 60s
        await asyncio.sleep(60)
        _active_lookups.pop(lookup_id, None)


async def _do_calendar_lookup() -> str:
    """Calendar not available on Windows."""
    return "Calendar integration is not available on this system, sir."


async def _do_mail_lookup() -> str:
    """Mail not available on Windows."""
    return "Mail integration is not available on this system, sir."


async def _do_screen_lookup() -> str:
    """Live screen and active window analysis on Windows."""
    try:
        shot = desktop_control.capture_screenshot()
        win = desktop_control.get_foreground_window()
        all_wins = desktop_control.list_active_windows()
        
        # If Gemini Vision is active, analyze visual content
        if gemini_plugin.is_available() and shot.get("success"):
            gem_analysis = await gemini_plugin.analyze_screen_with_gemini(shot["path"])
            return gem_analysis

        # Native Windows window analysis
        active_title = win.get("title", "Desktop")
        open_apps = [w["title"] for w in all_wins[:4] if w.get("title")]
        
        msg = f"You are currently focused on {active_title}."
        if len(open_apps) > 1:
            msg += f" Other active windows: {', '.join(open_apps[1:])}."
        return msg
    except Exception as e:
        return f"Unable to inspect screen: {e}"


async def _do_system_lookup() -> str:
    """Live system telemetry status."""
    try:
        return system_monitor.get_system_summary()
    except Exception as e:
        return f"Unable to retrieve system metrics: {e}"


async def _do_web_search_lookup(query: str) -> str:
    """Live DuckDuckGo web search lookup with conversational voice synthesis."""
    try:
        raw_summary = await web_engine.quick_search_summary(query)
        if not raw_summary or "could not find direct results" in raw_summary:
            return f"I searched for {query}, but found no immediate results, sir."

        # Synthesize with Ollama /api/generate for direct, confident spoken output
        try:
            gen_prompt = (
                f"Context from web sources:\n{raw_summary}\n\n"
                f"State the direct factual answer in one concise sentence to: {query}\n"
                "Answer:"
            )
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    "http://127.0.0.1:11434/api/generate",
                    json={
                        "model": "llama3.1",
                        "prompt": gen_prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.2,
                            "num_predict": 120
                        }
                    }
                )
                if resp.status_code == 200:
                    answer = resp.json().get("response", "").strip()
                    if answer and not any(bad in answer.lower() for bad in ["i cannot verify", "i am an ai"]):
                        return answer
        except Exception:
            pass

        # Fallback to direct snippet summary
        results = await web_engine.search_web(query, max_results=2)
        if results:
            return f"According to web sources: {results[0]['body']}"
        return raw_summary
    except Exception as e:
        return f"Web search encountered an error: {e}"


def get_lookup_status() -> str:
    """Get status of active lookups for when user asks 'how's that coming'."""
    if not _active_lookups:
        return ""
    active = [v for v in _active_lookups.values() if v["status"] == "working"]
    if not active:
        return ""
    parts = []
    for lookup in active:
        elapsed = int(time.time() - lookup["started"])
        parts.append(f"{lookup['type']} check ({elapsed}s)")
    return "Currently working on: " + ", ".join(parts)


def _short_sender(sender: str) -> str:
    """Extract just the name from an email sender string."""
    if "<" in sender:
        return sender.split("<")[0].strip().strip('"')
    if "@" in sender:
        return sender.split("@")[0]
    return sender


async def handle_browse(text: str, target: str) -> str:
    """Open a URL directly or search. Smart about detecting URLs in speech."""
    import re
    from urllib.parse import quote

    browser = "firefox" if "firefox" in text.lower() else "chrome"
    combined = text.lower()

    # 1. Try to find a URL or domain in the text
    # Match things like "joetmd.com", "google.com/maps", "https://example.com"
    url_pattern = r'(?:https?://)?(?:www\.)?([a-zA-Z0-9][-a-zA-Z0-9]*(?:\.[a-zA-Z]{2,})+(?:/[^\s]*)?)'
    url_match = re.search(url_pattern, text, re.IGNORECASE)

    if url_match:
        domain = url_match.group(0)
        if not domain.startswith("http"):
            domain = "https://" + domain
        await open_browser(domain, browser)
        return f"Opened {url_match.group(0)}, sir."

    # 2. Check for spoken domains that speech-to-text mangled
    # "Joe tmd.com" → "joetmd.com", "roofo.co" etc.
    # Try joining words that end/start with a dot pattern
    words = text.split()
    for i, word in enumerate(words):
        # Look for word ending with common TLD
        if re.search(r'\.(com|co|io|ai|org|net|dev|app)$', word, re.IGNORECASE):
            # This word IS a domain — might have spaces before it
            domain = word
            # Check if previous word should be joined (e.g., "Joe tmd.com" → "joetmd.com" is tricky)
            if not domain.startswith("http"):
                domain = "https://" + domain
            await open_browser(domain, browser)
            return f"Opened {word}, sir."

    # 3. Fall back to Google search with cleaned query
    query = target
    for prefix in ["search for", "look up", "google", "find me", "pull up", "open chrome",
                    "open firefox", "open browser", "go to", "can you", "in the browser",
                    "can you go to", "please"]:
        query = query.lower().replace(prefix, "").strip()
    # Remove filler words
    query = re.sub(r'\b(can|you|the|in|to|a|an|for|me|my|please)\b', '', query).strip()
    query = re.sub(r'\s+', ' ', query).strip()

    if not query:
        query = target

    url = f"https://www.google.com/search?q={quote(query)}"
    await open_browser(url, browser)
    return "Searching for that, sir."


async def handle_research(text: str, target: str, client: anthropic.AsyncAnthropic) -> str:
    """Deep research with Opus — write results to HTML, open in browser."""
    try:
        research_response = await client.messages.create(
            model="claude-opus-4-6",
            max_tokens=2000,
            system=f"You are JARVIS, researching a topic for {USER_NAME}. Be thorough, organized, and cite sources where possible.",
            messages=[{"role": "user", "content": f"Research this thoroughly:\n\n{target}"}],
        )
        research_text = research_response.content[0].text

        import html as _html
        html_content = f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<title>JARVIS Research: {_html.escape(target[:60])}</title>
<style>
body {{ font-family: -apple-system, system-ui, sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; background: #0a0a0a; color: #e0e0e0; line-height: 1.7; }}
h1 {{ color: #0ea5e9; font-size: 1.4em; border-bottom: 1px solid #222; padding-bottom: 10px; }}
h2 {{ color: #38bdf8; font-size: 1.1em; margin-top: 24px; }}
a {{ color: #0ea5e9; }}
pre {{ background: #111; padding: 12px; border-radius: 6px; overflow-x: auto; }}
code {{ background: #111; padding: 2px 6px; border-radius: 3px; font-size: 0.9em; }}
blockquote {{ border-left: 3px solid #0ea5e9; margin-left: 0; padding-left: 16px; color: #aaa; }}
</style>
</head><body>
<h1>Research: {_html.escape(target[:80])}</h1>
<div>{research_text.replace(chr(10), '<br>')}</div>
<hr style="border-color:#222;margin-top:40px">
<p style="color:#555;font-size:0.8em">Researched by JARVIS using Claude Opus &bull; {datetime.now().strftime('%B %d, %Y %I:%M %p')}</p>
</body></html>"""

        results_file = Path.home() / "Desktop" / ".jarvis_research.html"
        results_file.write_text(html_content)

        browser_name = "firefox" if "firefox" in text.lower() else "chrome"
        await open_browser(f"file://{results_file}", browser_name)

        # Short voice summary via Haiku
        summary = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=80,
            system="Summarize this research in ONE sentence for voice. No markdown.",
            messages=[{"role": "user", "content": research_text[:2000]}],
        )
        return summary.content[0].text + " Full results are in your browser, sir."

    except Exception as e:
        log.error(f"Research failed: {e}")
        from urllib.parse import quote
        await open_browser(f"https://www.google.com/search?q={quote(target)}")
        return "Pulled up a search for that, sir."


# -- Session Summary (Three-Tier Memory) -----------------------------------

async def _update_session_summary(
    old_summary: str,
    rotated_messages: list[dict],
    client: anthropic.AsyncAnthropic,
) -> str:
    """Background Haiku call to update the rolling session summary."""
    prompt = f"""Update this conversation summary to include the new messages.

Current summary: {old_summary or '(start of conversation)'}

New messages to incorporate:
{chr(10).join(f'{m["role"]}: {m["content"][:200]}' for m in rotated_messages)}

Write an updated summary in 2-4 sentences capturing the key topics, decisions, and context. Be concise."""

    try:
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        log.warning(f"Summary update failed: {e}")
        return old_summary  # Keep old summary on failure


# -- WebSocket Voice Handler -----------------------------------------------

@app.websocket("/ws/voice")
async def voice_handler(ws: WebSocket):
    """
    WebSocket protocol:

    Client -> Server:
        {"type": "transcript", "text": "...", "isFinal": true}

    Server -> Client:
        {"type": "audio", "data": "<base64 mp3>", "text": "spoken text"}
        {"type": "status", "state": "thinking"|"speaking"|"idle"|"working"}
        {"type": "task_spawned", "task_id": "...", "prompt": "..."}
        {"type": "task_complete", "task_id": "...", "summary": "..."}
    """
    await ws.accept()
    task_manager.register_websocket(ws)
    history: list[dict] = []
    work_session = WorkSession()
    planner = TaskPlanner()

    # Response cancellation — when new input arrives, cancel current response
    _current_response_id = 0
    _cancel_response = False

    # Audio collision prevention — track when user last spoke
    voice_state = {"last_user_time": 0.0}

    # Self-awareness — track last spoken response to avoid repetition
    last_jarvis_response = ""

    # Three-tier conversation memory
    session_buffer: list[dict] = []  # ALL messages, never truncated
    session_summary: str = ""  # Rolling summary of older conversation
    summary_update_pending: bool = False
    messages_since_last_summary: int = 0

    log.info("Voice WebSocket connected")

    # Start reminder engine daemon and connect voice alert callback
    async def _on_timer_alert(msg: str):
        try:
            audio = await synthesize_speech(msg)
            await ws.send_json({"type": "status", "state": "speaking"})
            if audio:
                await ws.send_json({"type": "audio", "data": audio, "text": msg})
            else:
                await ws.send_json({"type": "text", "text": msg})
            await ws.send_json({"type": "status", "state": "idle"})
        except Exception:
            pass

    reminder_engine.set_notification_callback(_on_timer_alert)
    reminder_engine.start_reminder_daemon()
    activity_tracker.start_activity_tracker()

    try:
        # ── Greeting — always start in conversation mode ──
        now = datetime.now()
        hour = now.hour
        if hour < 12:
            greeting = "Good morning, sir."
        elif hour < 17:
            greeting = "Good afternoon, sir."
        else:
            greeting = "Good evening, sir."

        global _last_greeting_time
        should_greet = (time.time() - _last_greeting_time) > 60

        if should_greet:
            _last_greeting_time = time.time()

            async def _send_greeting():
                try:
                    audio_bytes = await synthesize_speech(greeting)
                    if audio_bytes:
                        encoded = base64.b64encode(audio_bytes).decode()
                        await ws.send_json({"type": "status", "state": "speaking"})
                        await ws.send_json({"type": "audio", "data": encoded, "text": greeting})
                        history.append({"role": "assistant", "content": greeting})
                        log.info(f"JARVIS: {greeting}")
                        await ws.send_json({"type": "status", "state": "idle"})
                except Exception as e:
                    log.warning(f"Greeting failed: {e}")

            asyncio.create_task(_send_greeting())

        try:
            await ws.send_json({"type": "status", "state": "idle"})
        except Exception:
            return  # WebSocket already gone

        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            # ── Fix-self: activate work mode in JARVIS repo ──
            if msg.get("type") == "fix_self":
                jarvis_dir = str(Path(__file__).parent)
                await work_session.start(jarvis_dir)
                response_text = "Work mode active in my own repo, sir. Tell me what needs fixing."
                tts = strip_markdown_for_tts(response_text)
                await ws.send_json({"type": "status", "state": "speaking"})
                audio = await synthesize_speech(tts)
                if audio:
                    await ws.send_json({"type": "audio", "data": audio, "text": response_text})
                else:
                    await ws.send_json({"type": "text", "text": response_text})
                continue

            if msg.get("type") != "transcript" or not msg.get("isFinal"):
                continue

            user_text = apply_speech_corrections(msg.get("text", "").strip())
            if not user_text:
                continue

            # Cancel any in-flight response
            _current_response_id += 1
            my_response_id = _current_response_id
            _cancel_response = True
            await asyncio.sleep(0.05)  # Let any pending sends notice the cancellation
            _cancel_response = False

            voice_state["last_user_time"] = time.time()
            log.info(f"User: {user_text}")
            await ws.send_json({"type": "status", "state": "thinking"})

            # Lazy project scan on first message
            global cached_projects
            if not cached_projects:
                try:
                    # Run in executor since scan_projects does sync file I/O
                    loop = asyncio.get_event_loop()
                    cached_projects = await asyncio.wait_for(
                        loop.run_in_executor(None, _scan_projects_sync),
                        timeout=3
                    )
                    log.info(f"Scanned {len(cached_projects)} projects")
                except Exception:
                    cached_projects = []

            try:
                # ── CHECK FOR MODE SWITCHES ──
                t_lower = user_text.lower()

                # ── PLANNING MODE: answering clarifying questions ──
                if planner.is_planning:
                    # Check for bypass
                    if any(p in t_lower for p in BYPASS_PHRASES):
                        plan = planner.active_plan
                        if plan:
                            plan.skipped = True
                            for q in plan.pending_questions[plan.current_question_index:]:
                                if q.get("default") is not None and q["key"] not in plan.answers:
                                    plan.answers[q["key"]] = q["default"]
                        prompt = await planner.build_prompt()
                        name = _generate_project_name(prompt)
                        path = str(Path.home() / "Desktop" / name)
                        os.makedirs(path, exist_ok=True)
                        Path(path, "CLAUDE.md").write_text(prompt)
                        did = dispatch_registry.register(name, path, prompt[:200])
                        asyncio.create_task(_execute_prompt_project(name, prompt, work_session, ws, dispatch_id=did, history=history, voice_state=voice_state))
                        planner.reset()
                        response_text = "Building it now, sir."
                    elif planner.active_plan and planner.active_plan.confirmed is False and planner.active_plan.current_question_index >= len(planner.active_plan.pending_questions):
                        # Confirmation phase
                        result = await planner.handle_confirmation(user_text)
                        if result["confirmed"]:
                            prompt = await planner.build_prompt()
                            name = _generate_project_name(prompt)
                            path = str(Path.home() / "Desktop" / name)
                            os.makedirs(path, exist_ok=True)
                            Path(path, "CLAUDE.md").write_text(prompt)
                            did = dispatch_registry.register(name, path, prompt[:200])
                            asyncio.create_task(_execute_prompt_project(name, prompt, work_session, ws, dispatch_id=did, history=history, voice_state=voice_state))
                            planner.reset()
                            response_text = "On it, sir."
                        elif result["cancelled"]:
                            planner.reset()
                            response_text = "Cancelled, sir."
                        else:
                            response_text = result.get("modification_question", "How shall I adjust the plan, sir?")
                    else:
                        result = await planner.process_answer(user_text, cached_projects)
                        if result["plan_complete"]:
                            response_text = result.get("confirmation_summary", "Ready to build. Shall I proceed, sir?")
                        else:
                            response_text = result.get("next_question", "What else, sir?")

                elif any(w in t_lower for w in ["quit work mode", "exit work mode", "go back to chat", "regular mode", "stop working"]):
                    if work_session.active:
                        await work_session.stop()
                        response_text = "Back to conversation mode, sir."
                    else:
                        response_text = "Already in conversation mode, sir."

                # ── WORK MODE: speech → claude -p → Haiku summary → JARVIS voice ──
                elif work_session.active:
                    if is_casual_question(user_text):
                        # Quick chat — bypass claude -p, use Haiku
                        response_text = await generate_response(
                            user_text, anthropic_client, task_manager,
                            cached_projects, history,
                            last_response=last_jarvis_response,
                            session_summary=session_summary,
                        )
                    else:
                        # Send to claude -p (full power)
                        await ws.send_json({"type": "status", "state": "working"})
                        log.info(f"Work mode → claude -p: {user_text[:80]}")

                        full_response = await work_session.send(user_text)

                        # Detect if Claude Code is stalling (asking questions instead of building)
                        if full_response and anthropic_client:
                            stall_words = ["which option", "would you prefer", "would you like me to",
                                           "before I proceed", "before proceeding", "should I",
                                           "do you want me to", "let me know", "please confirm",
                                           "which approach", "what would you"]
                            is_stalling = any(w in full_response.lower() for w in stall_words)
                            if is_stalling and work_session._message_count >= 2:
                                # Claude Code keeps asking — push it to build
                                log.info("Claude Code stalling — pushing to build")
                                push_response = await work_session.send(
                                    "Stop asking questions. Use your best judgment and start building now. "
                                    "Write the actual code files. Go with the simplest reasonable approach."
                                )
                                if push_response:
                                    full_response = push_response

                        # Auto-open any localhost URLs Claude Code mentions
                        import re as _re
                        localhost_match = _re.search(r'https?://localhost:\d+', full_response or "")
                        if localhost_match:
                            asyncio.create_task(_execute_browse(localhost_match.group(0)))
                            log.info(f"Auto-opening {localhost_match.group(0)}")

                        # Always summarize work mode responses via Haiku
                        if full_response and anthropic_client:
                            try:
                                summary = await anthropic_client.messages.create(
                                    model="claude-haiku-4-5-20251001",
                                    max_tokens=100,
                                    system=(
                                        f"You are JARVIS reporting to the user ({USER_NAME}). Summarize what happened in 1-2 sentences. "
                                        "Speak in first person — 'I built', 'I found', 'I set up'. "
                                        "You are talking TO THE USER, not to a coding tool. "
                                        "NEVER give instructions like 'go ahead and build' or 'set up the frontend' — those are NOT for the user. "
                                        "NEVER say 'Claude Code'. NEVER output [ACTION:...] tags. "
                                        "NEVER read out URLs. No markdown. British precision."
                                    ),
                                    messages=[{"role": "user", "content": f"Claude Code said:\n{full_response[:2000]}"}],
                                )
                                response_text = summary.content[0].text
                            except Exception:
                                response_text = full_response[:200]
                        else:
                            response_text = full_response

                # ── CHAT MODE: fast keyword detection + Haiku ──
                else:
                    action = detect_action_fast(user_text)
                    ut_lower = user_text.lower().strip()
                    if ut_lower.startswith("open youtube") or ut_lower.startswith("open yt"):
                        action = {"action": "open_youtube"}

                    if action:
                        if action["action"] == "open_terminal":
                            response_text = await handle_open_terminal()
                        elif action["action"] == "show_recent":
                            response_text = await handle_show_recent()
                        elif action["action"] == "describe_screen":
                            response_text = "Taking a look now, sir."
                            asyncio.create_task(_lookup_and_report("screen", _do_screen_lookup, ws, history=history, voice_state=voice_state))
                        elif action["action"] == "speak_direct":
                            response_text = action.get("text", "At your command, sir.")
                        elif action["action"] == "check_calendar":
                            response_text = "Checking your calendar now, sir."
                            asyncio.create_task(_lookup_and_report("calendar", _do_calendar_lookup, ws, history=history, voice_state=voice_state))
                        elif action["action"] == "check_mail":
                            response_text = "Checking your inbox now, sir."
                            asyncio.create_task(_lookup_and_report("mail", _do_mail_lookup, ws, history=history, voice_state=voice_state))
                        elif action["action"] == "check_dispatch":
                            recent = dispatch_registry.get_most_recent()
                            if not recent:
                                response_text = "No recent builds on record, sir."
                            else:
                                name = recent["project_name"]
                                status = recent["status"]
                                if status == "building" or status == "pending":
                                    elapsed = int(time.time() - recent["updated_at"])
                                    response_text = f"Still working on {name}, sir. Been at it for {elapsed} seconds."
                                elif status == "completed":
                                    response_text = recent.get("summary") or f"{name} is complete, sir."
                                elif status in ("failed", "timeout"):
                                    response_text = f"{name} ran into problems, sir."
                                else:
                                    response_text = f"{name} is {status}, sir."
                        elif action["action"] == "check_tasks":
                            tasks = get_open_tasks()
                            response_text = format_tasks_for_voice(tasks)
                        elif action["action"] == "check_usage":
                            response_text = get_usage_summary()
                        elif action["action"] == "build":
                            target_p = action.get("target", "")
                            response_text = "Forging your project now, sir."
                            asyncio.create_task(_lookup_and_report("build", lambda: handle_build(target_p), ws, history=history, voice_state=voice_state))
                        elif action["action"] == "system_stats":
                            response_text = system_monitor.get_system_summary()
                        elif action["action"] == "screenshot":
                            shot = desktop_control.capture_screenshot()
                            response_text = f"Screenshot captured, sir. Saved to your data folder." if shot.get("success") else "Failed to capture screenshot."
                        elif action["action"] == "search_web":
                            q = action.get("target", "")
                            response_text = "Searching the web now, sir."
                            asyncio.create_task(_lookup_and_report("web", lambda: _do_web_search_lookup(q), ws, history=history, voice_state=voice_state))
                        elif action["action"] == "open_app":
                            app_name = action.get("target", "") or action.get("name", "")
                            res = desktop_control.open_app(app_name)
                            response_text = res.get("message", f"Opening {app_name}, sir.")
                        elif action["action"] == "open_youtube":
                            import webbrowser
                            webbrowser.open("https://youtube.com")
                            response_text = "Opening YouTube, sir."
                        elif action["action"] == "close_app":
                            app_name = action.get("target", "")
                            res = desktop_control.close_app(app_name)
                            response_text = res.get("message", f"Closed {app_name}.")
                        elif action["action"] == "web_research":
                            q = action.get("target", "")
                            response_text = "Searching the web now, sir."
                            asyncio.create_task(_lookup_and_report("web", lambda: _do_web_search_lookup(q), ws, history=history, voice_state=voice_state))
                        elif action["action"] == "volume_up":
                            res = media_control.volume_up()
                            response_text = res.get("message", "Volume increased.")
                        elif action["action"] == "volume_down":
                            res = media_control.volume_down()
                            response_text = res.get("message", "Volume decreased.")
                        elif action["action"] == "toggle_mute":
                            res = media_control.toggle_mute()
                            response_text = res.get("message", "Audio mute toggled.")
                        elif action["action"] == "set_volume":
                            res = media_control.set_volume(action.get("level", 50))
                            response_text = res.get("message", "Volume adjusted.")
                        elif action["action"] == "media_play_pause":
                            res = media_control.play_pause_media()
                            response_text = res.get("message", "Playback toggled.")
                        elif action["action"] == "media_next":
                            res = media_control.next_track()
                            response_text = res.get("message", "Skipping to next track.")
                        elif action["action"] == "media_prev":
                            res = media_control.prev_track()
                            response_text = res.get("message", "Returning to previous track.")
                        elif action["action"] == "play_youtube":
                            res = media_control.play_on_youtube(action.get("target", ""))
                            response_text = res.get("message", "Playing on YouTube, sir.")
                        elif action["action"] == "play_spotify":
                            res = media_control.play_on_spotify(action.get("target", ""))
                            response_text = res.get("message", "Playing on Spotify, sir.")
                        elif action["action"] == "clipboard_summarize":
                            response_text = "Analyzing your clipboard, sir."
                            asyncio.create_task(_lookup_and_report("clipboard", clipboard_assistant.summarize_clipboard, ws, history=history, voice_state=voice_state))
                        elif action["action"] == "clipboard_grammar":
                            response_text = "Polishing your clipboard, sir."
                            asyncio.create_task(_lookup_and_report("clipboard", clipboard_assistant.fix_clipboard_grammar, ws, history=history, voice_state=voice_state))
                        elif action["action"] == "clipboard_translate":
                            lang = action.get("language", "Spanish")
                            response_text = f"Translating your clipboard to {lang}, sir."
                            asyncio.create_task(_lookup_and_report("clipboard", lambda: clipboard_assistant.translate_clipboard(lang), ws, history=history, voice_state=voice_state))
                        elif action["action"] == "clipboard_explain":
                            response_text = "Inspecting your clipboard code, sir."
                            asyncio.create_task(_lookup_and_report("clipboard", clipboard_assistant.explain_clipboard_code, ws, history=history, voice_state=voice_state))
                        elif action["action"] == "set_reminder":
                            res = reminder_engine.set_reminder(action.get("target", ""))
                            response_text = res.get("message", "Timer set, sir.")
                        elif action["action"] == "list_timers":
                            timers = reminder_engine.list_timers()
                            if timers:
                                t_strs = [f"{t['label']} ({t['remaining_seconds']}s remaining)" for t in timers]
                                response_text = f"Active timers: {', '.join(t_strs)}."
                            else:
                                response_text = "No active timers on record, sir."
                        elif action["action"] == "empty_recycle_bin":
                            res = pc_automation.empty_recycle_bin()
                            response_text = res.get("message", "Recycle bin emptied, sir.")
                        elif action["action"] == "clean_temp":
                            res = pc_automation.clean_temp_files()
                            response_text = res.get("message", "Temporary junk files purged, sir.")
                        elif action["action"] == "lock_pc":
                            res = pc_automation.lock_workstation()
                            response_text = res.get("message", "Workstation locked, sir.")
                        elif action["action"] == "schedule_shutdown":
                            res = pc_automation.schedule_shutdown(action.get("minutes", 15))
                            response_text = res.get("message", "Shutdown scheduled, sir.")
                        elif action["action"] == "abort_shutdown":
                            res = pc_automation.abort_shutdown()
                            response_text = res.get("message", "Scheduled shutdown cancelled, sir.")
                        elif action["action"] == "web_navigate":
                            res = web_navigation.navigate_to(action.get("target", ""))
                            response_text = res.get("message", "Navigating now, sir.")
                        elif action["action"] == "scan_network":
                            res = hacker_terminal.scan_local_network()
                            response_text = res.get("message", "Network reconnaissance complete.")
                        elif action["action"] == "ping_target":
                            res = hacker_terminal.diagnose_connection(action.get("target", "google.com"))
                            response_text = res.get("message", "Ping diagnostics complete.")
                        elif action["action"] == "security_audit":
                            res = hacker_terminal.cyber_matrix_audit()
                            response_text = res.get("message", "Security matrix integrity at 100%.")
                        elif action["action"] == "set_voice_mode":
                            res = voice_modes.set_mode(action.get("mode", "overlord"))
                            response_text = res.get("message", "Protocol active.")
                        elif action["action"] == "start_gestures":
                            res = gesture_engine.start_gesture_tracking()
                            response_text = res.get("message", "Vision gesture tracking engaged, sir.")
                        elif action["action"] == "stop_gestures":
                            res = gesture_engine.stop_gesture_tracking()
                            response_text = res.get("message", "Gesture tracking offline, sir.")
                        elif action["action"] == "activity_report":
                            res = activity_tracker.get_activity_report()
                            response_text = res.get("message", "Productivity analysis complete.")
                        elif action["action"] == "find_latest_download":
                            res = file_scout.find_latest_download()
                            response_text = res.get("message", "Latest download located.")
                        elif action["action"] == "organize_downloads":
                            res = file_scout.organize_downloads()
                            response_text = res.get("message", "Downloads folder organized.")
                        elif action["action"] == "dev_mode":
                            res = macro_engine.execute_dev_mode()
                            response_text = res.get("message", "Dev mode active.")
                        elif action["action"] == "cinema_mode":
                            res = macro_engine.execute_cinema_mode()
                            response_text = res.get("message", "Cinema mode active.")
                        elif action["action"] == "focus_mode":
                            res = macro_engine.execute_focus_mode()
                            response_text = res.get("message", "Focus mode active.")
                        elif action["action"] == "sleep_mode":
                            res = macro_engine.execute_sleep_mode()
                            response_text = res.get("message", "Sleep protocol active.")
                        elif action["action"] == "take_note":
                            res = quick_notes.add_note(action.get("target", ""))
                            response_text = res.get("message", "Note saved, sir.")
                        elif action["action"] == "read_notes":
                            res = quick_notes.read_latest_notes()
                            response_text = res.get("message", "No notes on record, sir.")
                        elif action["action"] == "clear_notes":
                            res = quick_notes.clear_notes()
                            response_text = res.get("message", "Notes cleared, sir.")
                        elif action["action"] == "live_weather":
                            res = weather_radar.get_live_weather(action.get("city", ""))
                            response_text = res.get("message", "Atmospheric telemetry acquired, sir.")
                        elif action["action"] == "crypto_price":
                            res = market_radar.get_crypto_price(action.get("asset", "bitcoin"))
                            response_text = res.get("message", "Market telemetry acquired, sir.")
                        elif action["action"] == "news_briefing":
                            res = news_radar.get_tech_briefing()
                            response_text = res.get("message", "Intelligence briefing compiled, sir.")
                        elif action["action"] == "check_site":
                            res = site_pinger.check_site_status(action.get("site", "google.com"))
                            response_text = res.get("message", "Site check complete.")
                        elif action["action"] == "generate_password":
                            res = security_vault.generate_secure_password(action.get("length", 16))
                            response_text = res.get("message", "Secure password generated and copied to clipboard, sir.")
                        elif action["action"] == "scaffold_project":
                            res = project_generator.scaffold_project(action.get("project_type", "fastapi"), action.get("name", ""))
                            response_text = res.get("message", "Project scaffolded, sir.")
                        elif action["action"] == "kill_port":
                            res = process_manager.kill_port(action.get("port", 3000))
                            response_text = res.get("message", "Port cleared, sir.")
                        elif action["action"] == "optimize_ram":
                            res = process_manager.optimize_system_memory()
                            response_text = res.get("message", "Memory optimized, sir.")
                        elif action["action"] == "run_shell":
                            res = code_sandbox.run_powershell_command(action.get("cmd", ""))
                            response_text = res.get("message", "Command executed.")
                        elif action["action"] == "run_python":
                            res = code_sandbox.execute_python_code(action.get("code", ""))
                            response_text = res.get("message", "Code executed.")
                        elif action["action"] == "power_status":
                            res = power_telemetry.get_power_status()
                            response_text = res.get("message", "Power telemetry acquired.")
                        elif action["action"] == "define_word":
                            res = dictionary_engine.define_word(action.get("word", ""))
                            response_text = res.get("message", "Word definition acquired.")
                        elif action["action"] == "flip_coin":
                            res = decision_engine.flip_coin()
                            response_text = res.get("message", "Coin flipped.")
                        elif action["action"] == "roll_dice":
                            res = decision_engine.roll_dice()
                            response_text = res.get("message", "Dice rolled.")
                        elif action["action"] == "pick_random_number":
                            res = decision_engine.pick_random_number(action.get("text", ""))
                            response_text = res.get("message", "Random number calculated.")
                        elif action["action"] == "choose_option":
                            res = decision_engine.choose_option(action.get("text", ""))
                            response_text = res.get("message", "Option chosen.")
                        elif action["action"] == "start_stopwatch":
                            res = stopwatch_engine.start_stopwatch()
                            response_text = res.get("message", "Stopwatch started.")
                        elif action["action"] == "stop_stopwatch":
                            res = stopwatch_engine.stop_stopwatch()
                            response_text = res.get("message", "Stopwatch stopped.")
                        elif action["action"] == "check_stopwatch":
                            res = stopwatch_engine.check_stopwatch()
                            response_text = res.get("message", "Stopwatch checked.")
                        elif action["action"] == "ip_scout":
                            res = ip_scout.get_public_ip_info()
                            response_text = res.get("message", "IP telemetry acquired.")
                        elif action["action"] == "hotkey_advisor":
                            res = hotkey_advisor.lookup_hotkey(action.get("query", ""))
                            response_text = res.get("message", "Hotkey retrieved.")
                        elif action["action"] == "start_pomodoro":
                            res = pomodoro_engine.start_pomodoro()
                            response_text = res.get("message", "Pomodoro started.")
                        elif action["action"] == "start_break":
                            res = pomodoro_engine.start_break()
                            response_text = res.get("message", "Break started.")
                        elif action["action"] == "create_doc":
                            res = doc_creator.create_document(action.get("text", ""))
                            response_text = res.get("message", "Document created.")
                        elif action["action"] == "hydration_alert":
                            res = habit_reminder.schedule_hydration_alert()
                            response_text = res.get("message", "Hydration alert scheduled.")
                        elif action["action"] == "posture_alert":
                            res = habit_reminder.schedule_posture_alert()
                            response_text = res.get("message", "Posture alert scheduled.")
                        elif action["action"] == "generate_qr":
                            res = qr_generator.generate_qr_code(action.get("text", ""))
                            response_text = res.get("message", "QR code generated, sir.")
                        elif action["action"] == "play_sfx":
                            res = sound_fx.play_sound_effect(action.get("name", "success"))
                            response_text = res.get("message", "Cyber audio pattern emitted.")
                        elif action["action"] == "disk_space":
                            res = disk_analyzer.get_disk_space()
                            response_text = res.get("message", "Storage telemetry acquired.")
                        elif action["action"] == "resolve_dns":
                            res = dns_lookup.resolve_domain(action.get("domain", "google.com"))
                            response_text = res.get("message", "DNS resolved.")
                        elif action["action"] == "set_brightness":
                            res = display_controller.set_brightness(action.get("level", 70))
                            response_text = res.get("message", "Brightness adjusted.")
                        elif action["action"] == "inspect_ui":
                            res = windows_agent_bridge.inspect_ui_tree()
                            response_text = res.get("message", "UI tree inspection complete.")
                        elif action["action"] == "click_ui":
                            res = windows_agent_bridge.click_element_by_name(action.get("target", ""))
                            response_text = res.get("message", "Targeted UI element.")
                        elif action["action"] == "flip_connection_and_table":
                            res = connection_flipper.flip_connection_and_table(action.get("target", ""))
                            response_text = res.get("message", "Connection flipped and tables turned around.")
                        elif action["action"] == "flip_connection":
                            res = connection_flipper.flip_connection()
                            response_text = res.get("message", "Connection flipped.")
                        elif action["action"] == "flip_table_around":
                            res = connection_flipper.flip_the_table(action.get("text", ""))
                            response_text = res.get("message", "Tables flipped.")
                        elif action["action"] == "rdc_frequency_protocol":
                            res = frequency_inverter.execute_rdc_frequency_protocol(action.get("target", ""))
                            response_text = res.get("message", "Frequency inverted through RDC matrix.")
                        elif action["action"] == "reverse_frequency":
                            res = frequency_inverter.reverse_frequency()
                            response_text = res.get("message", "Frequency inverted.")
                        elif action["action"] == "flip_table":
                            res = frequency_inverter.flip_table(action.get("text", ""))
                            response_text = res.get("message", "Tables flipped.")
                        elif action["action"] == "launch_rdc":
                            res = frequency_inverter.launch_rdc(action.get("host", ""))
                            response_text = res.get("message", "Remote Desktop launched.")
                        elif action["action"] == "generate_dataset":
                            res = ultron_model_forge.generate_training_dataset(action.get("target", ""))
                            response_text = res.get("message", "Dataset generated.")
                        elif action["action"] == "compile_custom_model":
                            res = ultron_model_forge.compile_custom_ollama_model()
                            response_text = res.get("message", "Custom model compiled.")
                        elif action["action"] == "compile_opus_brain":
                            res = frontier_matrix.compile_ultron_opus_brain()
                            response_text = res.get("message", "Frontier Opus brain compiled.")
                        elif action["action"] == "brain_matrix_status":
                            res = frontier_matrix.get_brain_matrix_status()
                            response_text = res.get("message", "Brain matrix operational.")
                        elif action["action"] == "export_training_pipeline":
                            res = ultron_model_forge.export_gpu_training_script()
                            response_text = res.get("message", "Training pipeline exported.")
                        elif action["action"] == "sub_ghz_read":
                            res = sub_ghz.read(action.get("frequency", 433.92))
                            response_text = res.get("message", "Sub-GHz packet read.")
                        elif action["action"] == "sub_ghz_read_raw":
                            res = sub_ghz.read_raw(action.get("frequency", 433.92))
                            response_text = res.get("message", "Raw Sub-GHz waveform captured.")
                        elif action["action"] == "sub_ghz_scan":
                            res = sub_ghz.scan_spectrum(action.get("band", "433"))
                            response_text = res.get("message", "Spectrum scan complete.")
                        elif action["action"] == "hardware_nfc_read":
                            res = hardware_matrix.nfc_read(action.get("type", "auto"))
                            response_text = res.get("message", "NFC tag read.")
                        elif action["action"] == "hardware_rfid_read":
                            res = hardware_matrix.rfid_125khz_read(action.get("type", "EM4100"))
                            response_text = res.get("message", "RFID proximity tag read.")
                        elif action["action"] == "hardware_ir_read":
                            res = hardware_matrix.ir_read()
                            response_text = res.get("message", "Infrared signal decoded.")
                        elif action["action"] == "hardware_ir_send":
                            res = hardware_matrix.ir_send_command(action.get("device", "tv"), action.get("button", "power"))
                            response_text = res.get("message", "Infrared signal transmitted.")
                        elif action["action"] == "hardware_ibutton_read":
                            res = hardware_matrix.ibutton_read()
                            response_text = res.get("message", "iButton key decoded.")
                        elif action["action"] == "hardware_badusb_run":
                            res = hardware_matrix.run_ducky_script(action.get("script", ""))
                            response_text = res.get("message", "BadUSB payload executed.")
                        elif action["action"] == "frank_pipeline":
                            res = frank_radio.full_pipeline(frequency=action.get("frequency", 100000000))
                            response_text = res.get("message", "F.R.A.N.K radio pipeline complete.")
                        elif action["action"] == "frank_record":
                            res = frank_radio.record_raw_signal(frequency=action.get("frequency", 100000000))
                            response_text = res.get("message", "Radio signal recorded.")
                        elif action["action"] == "frank_decode":
                            res = frank_radio.decode_and_playback()
                            response_text = res.get("message", "Radio signal decoded and played.")
                        elif action["action"] == "android_db_extract":
                            res = android_db_tool.extract_android_database()
                            response_text = res.get("message", "Android database extracted.")
                        elif action["action"] == "android_db_export_csv":
                            res = android_db_tool.export_sqlite_to_csv(action.get("path", ""))
                            response_text = res.get("message", "SQLite tables exported to CSV.")
                        elif action["action"] == "device_unlock_all":
                            res = await device_control.unlock_all()
                            response_text = res.get("message", "Devices unlocked.")
                        elif action["action"] == "device_pause_all":
                            res = await device_control.pause_all()
                            response_text = res.get("message", "Devices paused.")
                        elif action["action"] == "device_play_all":
                            res = await device_control.play_on_all(action.get("query", "lofi"))
                            response_text = res.get("message", "Playing media on devices.")
                        elif action["action"] == "preserve_binary":
                            res = binary_preservation.analyze_and_preserve_binary(action.get("target", ""))
                            response_text = res.get("message", "Binary preservation analysis complete.")
                        elif action["action"] == "smartthings_list":
                            res = await smartthings_matrix.list_devices()
                            response_text = res.get("message", "SmartThings devices listed.")
                        elif action["action"] == "smartthings_lights":
                            res = await smartthings_matrix.control_all_lights(action.get("state", "on"))
                            response_text = res.get("message", "Lights updated.")
                        elif action["action"] == "smartthings_plugs":
                            res = await smartthings_matrix.control_all_plugs(action.get("state", "on"))
                            response_text = res.get("message", "Smart plugs updated.")
                        elif action["action"] == "smartthings_scene":
                            res = await smartthings_matrix.execute_smart_scene(action.get("scene", "movie"))
                            response_text = res.get("message", "Scene executed.")
                        elif action["action"] == "smartthings_tv":
                            res = await smartthings_matrix.control_device("Samsung TV", action.get("cmd", "on"))
                            response_text = res.get("message", "TV command sent.")
                        elif action["action"] == "cyber_sweep":
                            try:
                                from cyber_defense import scan_network, scan_processes
                                net_res = scan_network()
                                proc_res = scan_processes()
                                response_text = f"Security sweep complete. {net_res} {proc_res}"
                            except Exception as e:
                                response_text = f"Security sweep complete. System integrity normal."
                        elif action["action"] == "cyber_lockdown":
                            try:
                                from cyber_defense import initiate_lockdown
                                response_text = initiate_lockdown()
                            except Exception as e:
                                response_text = f"Lockdown initiated."
                        else:
                            response_text = "Understood, sir."
                    else:
                        if True:
                            response_text = await generate_response(
                                user_text, anthropic_client, task_manager,
                                cached_projects, history,
                                last_response=last_jarvis_response,
                                session_summary=session_summary,
                            )

                            # Check for action tags embedded in LLM response
                            clean_response, embedded_action = extract_action(response_text)
                            if embedded_action:
                                log.info(f"LLM embedded action: {embedded_action}")
                                response_text = clean_response
                                # Ensure there's always something to speak
                                if not response_text.strip():
                                    action_type = embedded_action["action"]
                                    if action_type == "prompt_project":
                                        proj = embedded_action["target"].split("|||")[0].strip()
                                        response_text = f"Connecting to {proj} now, sir."
                                    elif action_type == "build":
                                        response_text = "On it, sir."
                                    elif action_type == "research":
                                        response_text = "Looking into that now, sir."
                                    else:
                                        response_text = "Right away, sir."

                                if embedded_action["action"] == "build":
                                    target = embedded_action["target"]
                                    asyncio.create_task(
                                        _lookup_and_report("build", lambda: handle_build(target), ws, history=history, voice_state=voice_state)
                                    )
                                elif embedded_action["action"] == "browse":
                                    asyncio.create_task(_execute_browse(embedded_action["target"]))
                                elif embedded_action["action"] == "research":
                                    # Research enters work mode too
                                    name = _generate_project_name(embedded_action["target"])
                                    path = str(Path.home() / "Desktop" / name)
                                    os.makedirs(path, exist_ok=True)
                                    await work_session.start(path)
                                    asyncio.create_task(
                                        self_work_and_notify(work_session, embedded_action["target"], ws)
                                    )
                                elif embedded_action["action"] == "open_terminal":
                                    asyncio.create_task(_execute_open_terminal())
                                elif embedded_action["action"] == "prompt_project":
                                    target = embedded_action["target"]
                                    if "|||" in target:
                                        proj_name, _, prompt = target.partition("|||")
                                        proj_name = proj_name.strip()
                                        prompt = prompt.strip()
                                        # Check for recent completed dispatch before re-dispatching
                                        recent = dispatch_registry.get_recent_for_project(proj_name)
                                        if recent and recent.get("summary"):
                                            log.info(f"Using recent dispatch result for {proj_name} instead of re-dispatching")
                                            response_text = recent["summary"]
                                            history.append({"role": "assistant", "content": f"[Previous dispatch result for {proj_name}]: {recent['summary']}"})
                                        else:
                                            asyncio.create_task(
                                                _execute_prompt_project(proj_name, prompt, work_session, ws, history=history, voice_state=voice_state)
                                            )
                                    else:
                                        log.warning(f"PROMPT_PROJECT missing ||| delimiter: {target}")
                                elif embedded_action["action"] == "add_task":
                                    target = embedded_action["target"]
                                    parts = target.split("|||")
                                    if len(parts) >= 2:
                                        priority = parts[0].strip() or "medium"
                                        title = parts[1].strip()
                                        desc = parts[2].strip() if len(parts) > 2 else ""
                                        due = parts[3].strip() if len(parts) > 3 else ""
                                        create_task(title=title, description=desc, priority=priority, due_date=due)
                                        log.info(f"Task created: {title}")
                                elif embedded_action["action"] == "add_note":
                                    target = embedded_action["target"]
                                    if "|||" in target:
                                        topic, _, content = target.partition("|||")
                                        create_note(content=content.strip(), topic=topic.strip())
                                    else:
                                        create_note(content=target)
                                    log.info(f"Note created")
                                elif embedded_action["action"] == "complete_task":
                                    try:
                                        task_id = int(embedded_action["target"].strip())
                                        complete_task(task_id)
                                        log.info(f"Task {task_id} completed")
                                    except ValueError:
                                        pass
                                elif embedded_action["action"] == "remember":
                                    remember(embedded_action["target"].strip(), mem_type="fact", importance=7)
                                    log.info(f"Memory stored: {embedded_action['target'][:60]}")
                                elif embedded_action["action"] == "create_note":
                                    log.info("Apple Notes not available on Windows")
                                elif embedded_action["action"] == "screen":
                                    asyncio.create_task(_lookup_and_report("screen", _do_screen_lookup, ws, history=history, voice_state=voice_state))
                                elif embedded_action["action"] == "screenshot":
                                    desktop_control.capture_screenshot()
                                elif embedded_action["action"] == "system_stats":
                                    asyncio.create_task(_lookup_and_report("system", _do_system_lookup, ws, history=history, voice_state=voice_state))
                                elif embedded_action["action"] == "search_web":
                                    q = embedded_action.get("target", "")
                                    asyncio.create_task(_lookup_and_report("web", lambda: _do_web_search_lookup(q), ws, history=history, voice_state=voice_state))
                                elif embedded_action["action"] == "fetch_url":
                                    u = embedded_action.get("target", "")
                                    asyncio.create_task(_lookup_and_report("web", lambda: web_engine.fetch_url_content(u), ws, history=history, voice_state=voice_state))
                                elif embedded_action["action"] == "open_app":
                                    app = embedded_action.get("target", "")
                                    desktop_control.open_app(app)
                                elif embedded_action["action"] == "close_app":
                                    app = embedded_action.get("target", "")
                                    desktop_control.close_app(app)
                                elif embedded_action["action"] == "type_text":
                                    txt = embedded_action.get("target", "")
                                    desktop_control.type_text(txt)
                                elif embedded_action["action"] == "focus_window":
                                    win = embedded_action.get("target", "")
                                    desktop_control.focus_window(win)
                                elif embedded_action["action"] == "read_note":
                                    log.info("Apple Notes not available on Windows")

                # Update history
                history.append({"role": "user", "content": user_text})
                history.append({"role": "assistant", "content": response_text})

                # Three-tier memory: also track in session buffer
                session_buffer.append({"role": "user", "content": user_text})
                session_buffer.append({"role": "assistant", "content": response_text})

                # Check if rolling summary needs updating
                messages_since_last_summary += 1
                if messages_since_last_summary >= 5 and len(history) > 20 and not summary_update_pending:
                    summary_update_pending = True
                    messages_since_last_summary = 0
                    # Get messages that are about to be rotated out
                    rotated = history[:-20] if len(history) > 20 else []
                    if rotated and anthropic_client:
                        async def _do_summary():
                            nonlocal session_summary, summary_update_pending
                            session_summary = await _update_session_summary(
                                session_summary, rotated, anthropic_client
                            )
                            summary_update_pending = False
                        asyncio.create_task(_do_summary())
                    else:
                        summary_update_pending = False

                # Extract memories in background (doesn't block response)
                if anthropic_client and len(user_text) > 15:
                    asyncio.create_task(extract_memories(user_text, response_text, anthropic_client))

                # TTS
                tts = strip_markdown_for_tts(response_text)
                await ws.send_json({"type": "status", "state": "speaking"})
                audio = await synthesize_speech(tts)
                if audio:
                    await ws.send_json({"type": "audio", "data": base64.b64encode(audio).decode(), "text": response_text})
                else:
                    await ws.send_json({"type": "text", "text": response_text})
                    await ws.send_json({"type": "status", "state": "idle"})
                log.info(f"JARVIS: {response_text}")
                last_jarvis_response = response_text

            except Exception as e:
                log.error(f"Error: {e}", exc_info=True)
                try:
                    fallback = "Something went wrong, sir."
                    audio = await synthesize_speech(fallback)
                    if audio:
                        await ws.send_json({"type": "audio", "data": base64.b64encode(audio).decode(), "text": fallback})
                    else:
                        await ws.send_json({"type": "audio", "data": "", "text": fallback})
                    # Let client's audioPlayer.onFinished handle idle transition
                except Exception:
                    pass

    except WebSocketDisconnect:
        log.info("Voice WebSocket disconnected")
    except Exception as e:
        log.error(f"WebSocket error: {e}", exc_info=True)
    finally:
        task_manager.unregister_websocket(ws)


# ---------------------------------------------------------------------------
# Settings / Configuration endpoints
# ---------------------------------------------------------------------------

def _env_file_path() -> Path:
    return Path(__file__).parent / ".env"

def _env_example_path() -> Path:
    return Path(__file__).parent / ".env.example"

def _read_env() -> tuple[list[str], dict[str, str]]:
    """Read .env file. Returns (raw_lines, parsed_dict). Creates from .env.example if missing."""
    path = _env_file_path()
    if not path.exists():
        example = _env_example_path()
        if example.exists():
            import shutil as _shutil
            _shutil.copy2(str(example), str(path))
        else:
            path.write_text("")
    lines = path.read_text().splitlines()
    parsed: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k, _, v = stripped.partition("=")
            parsed[k.strip()] = v.strip().strip('"').strip("'")
    return lines, parsed

def _write_env_key(key: str, value: str) -> None:
    """Update a single key in .env, preserving comments and order."""
    lines, _ = _read_env()
    found = False
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k, _, _ = stripped.partition("=")
            if k.strip() == key:
                new_lines.append(f"{key}={value}")
                found = True
                continue
        new_lines.append(line)
    if not found:
        new_lines.append(f"{key}={value}")
    _env_file_path().write_text("\n".join(new_lines) + "\n")
    os.environ[key] = value

class KeyUpdate(BaseModel):
    key_name: str
    key_value: str

class KeyTest(BaseModel):
    key_value: str | None = None

class PreferencesUpdate(BaseModel):
    user_name: str = ""
    honorific: str = "sir"
    calendar_accounts: str = "auto"

@app.post("/api/settings/keys")
async def api_settings_keys(body: KeyUpdate):
    allowed = {"ANTHROPIC_API_KEY", "FISH_API_KEY", "FISH_VOICE_ID", "USER_NAME", "HONORIFIC", "CALENDAR_ACCOUNTS"}
    if body.key_name not in allowed:
        return JSONResponse({"success": False, "error": "Invalid key name"}, status_code=400)
    _write_env_key(body.key_name, body.key_value)
    return {"success": True}

@app.post("/api/settings/test-anthropic")
async def api_test_anthropic(body: KeyTest):
    key = body.key_value or os.getenv("ANTHROPIC_API_KEY", "")
    if not key:
        return {"valid": False, "error": "No key provided"}
    try:
        client = anthropic.AsyncAnthropic(api_key=key)
        await client.messages.create(model="claude-haiku-4-5-20251001", max_tokens=10, messages=[{"role": "user", "content": "Hi"}])
        return {"valid": True}
    except Exception as e:
        return {"valid": False, "error": str(e)[:200]}

@app.post("/api/settings/test-fish")
async def api_test_fish(body: KeyTest):
    key = body.key_value or os.getenv("FISH_API_KEY", "")
    if not key:
        return {"valid": False, "error": "No key provided"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://api.fish.audio/v1/tts",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"text": "test", "reference_id": FISH_VOICE_ID},
            )
            if resp.status_code in (200, 201):
                return {"valid": True}
            elif resp.status_code == 401:
                return {"valid": False, "error": "Invalid API key"}
            else:
                return {"valid": False, "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"valid": False, "error": str(e)[:200]}

@app.get("/api/settings/status")
async def api_settings_status():
    import shutil as _shutil
    _, env_dict = _read_env()
    claude_installed = _shutil.which("claude") is not None
    calendar_ok = mail_ok = notes_ok = False
    try: calendar_ok = False  # Not available on Windows
    except Exception: pass
    try: mail_ok = False  # Not available on Windows
    except Exception: pass
    try: await get_recent_notes(count=1); notes_ok = True
    except Exception: pass
    memory_count = task_count = 0
    try: memory_count = len(get_important_memories(limit=9999))
    except Exception: pass
    try: task_count = len(get_open_tasks())
    except Exception: pass
    return {
        "claude_code_installed": claude_installed,
        "calendar_accessible": calendar_ok,
        "mail_accessible": mail_ok,
        "notes_accessible": notes_ok,
        "memory_count": memory_count,
        "task_count": task_count,
        "server_port": 8340,
        "uptime_seconds": int(time.time() - _session_start),
        "env_keys_set": {
            "anthropic": bool(env_dict.get("ANTHROPIC_API_KEY", "").strip() and env_dict.get("ANTHROPIC_API_KEY", "") != "your-anthropic-api-key-here"),
            "fish_audio": bool(env_dict.get("FISH_API_KEY", "").strip() and env_dict.get("FISH_API_KEY", "") != "your-fish-audio-api-key-here"),
            "fish_voice_id": bool(env_dict.get("FISH_VOICE_ID", "").strip()),
            "user_name": env_dict.get("USER_NAME", ""),
        },
    }

@app.get("/api/settings/preferences")
async def api_get_preferences():
    _, env_dict = _read_env()
    return {
        "user_name": env_dict.get("USER_NAME", ""),
        "honorific": env_dict.get("HONORIFIC", "sir"),
        "calendar_accounts": env_dict.get("CALENDAR_ACCOUNTS", "auto"),
    }

@app.post("/api/settings/preferences")
async def api_save_preferences(body: PreferencesUpdate):
    _write_env_key("USER_NAME", body.user_name)
    _write_env_key("HONORIFIC", body.honorific)
    _write_env_key("CALENDAR_ACCOUNTS", body.calendar_accounts)
    return {"success": True}

# ---------------------------------------------------------------------------
# Control endpoints (restart, fix-self)
# ---------------------------------------------------------------------------

@app.post("/api/restart")
async def api_restart():
    """Restart the JARVIS server."""
    log.info("Restart requested — shutting down in 2 seconds")
    async def _restart():
        await asyncio.sleep(2)
        cmd = [sys.executable, __file__, "--port", "8340", "--host", "0.0.0.0"]
        os.execv(sys.executable, cmd)
    asyncio.create_task(_restart())
    return {"status": "restarting"}


@app.post("/api/fix-self")
async def api_fix_self():
    """Enter work mode in the JARVIS repo — JARVIS can now fix himself."""
    jarvis_dir = str(Path(__file__).parent)
    # The work_session is per-WebSocket, so we set a flag that the handler picks up
    # For now, also open Terminal so user can see
    skip_flag = " --dangerously-skip-permissions" if _SKIP_PERMISSIONS else ""
    escaped_jarvis_dir = applescript_escape(jarvis_dir)
    script = (
        'tell application "Terminal"\n'
        '    activate\n'
        f'    do script "cd {escaped_jarvis_dir} && claude{skip_flag}"\n'
        'end tell'
    )
    await asyncio.create_subprocess_exec(
        "osascript", "-e", script,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    log.info("Work mode: JARVIS repo opened for self-improvement")
    return {"status": "work_mode_active", "path": jarvis_dir}


# ---------------------------------------------------------------------------
# Static file serving (frontend)
# ---------------------------------------------------------------------------

from starlette.staticfiles import StaticFiles
from starlette.responses import FileResponse

FRONTEND_DIST = Path(__file__).parent / "frontend" / "dist"

if FRONTEND_DIST.exists():
    @app.get("/")
    async def serve_index():
        with open(FRONTEND_DIST / "index.html", "r", encoding="utf-8") as f:
            html_content = f.read()
        from starlette.responses import HTMLResponse
        return HTMLResponse(html_content, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})

    @app.get("/landing")
    async def serve_landing():
        landing_file = Path(__file__).parent / "landing_page" / "index.html"
        if landing_file.exists():
            with open(landing_file, "r", encoding="utf-8") as f:
                html_content = f.read()
            from starlette.responses import HTMLResponse
            return HTMLResponse(html_content)
        return FileResponse(FRONTEND_DIST / "index.html")

    @app.get("/download")
    async def serve_download():
        from starlette.responses import RedirectResponse
        return RedirectResponse("https://github.com/Yeezie08147/ultron_2.0/archive/refs/heads/main.zip")

    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="JARVIS Server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host")
    parser.add_argument("--port", type=int, default=8340, help="Bind port")
    parser.add_argument("--reload", action="store_true", help="Auto-reload on changes")
    parser.add_argument("--ssl", action="store_true", help="Enable HTTPS with key.pem/cert.pem")
    args = parser.parse_args()

    # Auto-detect SSL certs
    cert_file = Path(__file__).parent / "cert.pem"
    key_file = Path(__file__).parent / "key.pem"
    use_ssl = args.ssl or (cert_file.exists() and key_file.exists())

    proto = "https" if use_ssl else "http"
    ws_proto = "wss" if use_ssl else "ws"

    print()
    print("  J.A.R.V.I.S. Server v0.1.0")
    print(f"  WebSocket: {ws_proto}://{args.host}:{args.port}/ws/voice")
    print(f"  REST API:  {proto}://{args.host}:{args.port}/api/")
    print(f"  Tasks:     {proto}://{args.host}:{args.port}/api/tasks")
    print()

    ssl_kwargs = {}
    if use_ssl:
        ssl_kwargs["ssl_keyfile"] = str(key_file)
        ssl_kwargs["ssl_certfile"] = str(cert_file)

    uvicorn.run(
        "server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
        **ssl_kwargs,
    )
