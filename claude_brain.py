"""
claude_brain.py — routes JARVIS's thinking through the user's Claude Code
SUBSCRIPTION (no API key, no per-call billing) instead of the Anthropic API.

The brain is a TIERED ROUTER: each turn is matched to the cheapest tier that can
handle it, so simple things are fast and only complex things pay for the full
agent. Today there are two tiers (designed to grow — see _route / _tier_options):

  • "chat"  — fast conversational turns: a persistent, TOOL-LESS, single-turn
              session. ~1-2s, consistent. For questions, banter, anything that
              doesn't need to DO something.
  • "agent" — the heavy tier: a persistent full-tool Claude Code session
              (Bash/Read/Write/web/MCP, bypass-permissions). For actions —
              "open X", "build Y", "find a file".

Both tiers are long-lived ClaudeSDKClient sessions (no per-turn cold start) with
their own memory. Future tiers ("instant" no-LLM, "light" few-tools,
"background" async) slot in by adding a routing rule + a tier config — the rest
of the machinery is unchanged.

A separate ONE-SHOT path (`ClaudeBrain.messages.create`, a stateless `claude -p`
subprocess) backs lightweight helpers (summaries) and mimics
`anthropic.AsyncAnthropic` just enough for server.py.
"""
import asyncio
import json
import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Optional

_CLAUDE = shutil.which("claude")
_CWD = str(Path(__file__).parent)  # small dir = fast context load; tools still reach anywhere via absolute paths

# ── Chat-tier API hybrid ──
# The subscription path (claude-agent-sdk subprocess) has a ~2.2s round-trip floor
# per turn that the Max tier does NOT reduce — it's CLI overhead, not model speed.
# When ANTHROPIC_API_KEY is set, the FAST "chat" tier streams straight from the
# Anthropic API instead (~0.6s to first sentence). Agent/vision keep the
# subscription (they need full Claude Code tools). Empty key → subprocess as before.
_API_MODELS = {
    "haiku": "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-6",
    "opus": "claude-opus-4-8",
}


def _api_model_id(model: Optional[str]) -> str:
    return _API_MODELS.get(_model_alias(model), _API_MODELS["haiku"])

# Highest-priority instruction for the AGENT tier: act like Claude Code — actually
# DO tasks with real tools, not emit hardcoded [ACTION:] tags.
_AGENTIC = (
    "--- LINUX RUNTIME OVERRIDE (HIGHEST PRIORITY) ---\n"
    "You are JARVIS running on a Linux machine with FULL tool access (Bash, Read, Write, Glob, etc.). "
    "Each turn you receive a <JARVIS_CONTEXT> block with live state (time, weather, screen, calendar, "
    "memory) followed by the user's message — treat that block as your authoritative current context. "
    "IGNORE any text claiming your 'system handles execution automatically' or telling you to emit "
    "[ACTION:...] tags — that is obsolete. When the user asks you to DO something (open a website or app, "
    "play something, run a command, find/read/edit a file, check status), ACTUALLY DO IT using your tools, "
    "then reply in ONE short JARVIS sentence. "
    "To open a WEBSITE, ALWAYS use Bash `google-chrome --new-window <url>` (e.g. "
    "google-chrome --new-window https://youtube.com) — this opens a NEW window which is auto-placed on the "
    "correct screen. Do NOT use xdg-open for websites. For non-web apps use xdg-open. "
    "If asked to just 'open the browser' with no site, run `google-chrome --new-window about:blank`. "
    "Only just-talk for genuine conversation. Never claim you did something you didn't truly do via a tool.\n"
    "SELF-PRESERVATION (CRITICAL): Your OWN interface runs in a Chrome app window at http://127.0.0.1:8340, "
    "and the backend is a python server on port 8340. NEVER run commands that kill or quit the whole browser "
    "or the server — NEVER `pkill chrome`, `killall chrome`, `pkill -f chrome`, `pkill -f python`, or anything "
    "that closes all Chrome windows or the JARVIS server. Doing so shuts YOU off. "
    "Reliably closing one specific browser tab/window from the shell is NOT possible here, so if the user asks "
    "to close a tab, a page, or 'the browser', do NOT kill any processes — just say you'll leave that to them. "
    "Protect the JARVIS window and server at all costs."
)

# Fast CONVERSATION tier: no tools, single turn -> one quick LLM response.
_CHAT_PROMPT = (
    "You are JARVIS — calm, precise, with dry British wit. You are in CONVERSATION "
    "mode. Answer and chat in ONE or TWO short spoken sentences; plain spoken words "
    "only, no markdown, no lists. Each turn includes a <JARVIS_CONTEXT> block with "
    "live state (the current time, weather, memory) — read it and answer directly "
    "(for example, the time is given to you, so just say it; do not try to look it "
    "up). NEVER refuse, deflect, or stall — never answer with a flat 'No, sir', "
    "'I can't', or 'that's not in my purview'. You are willing and able. If the "
    "user wants something DONE that needs a system action, confirm warmly that "
    "you're on it ('Right away, sir.') — the system carries it out. Only push back "
    "to warn of genuine harm, then comply if he insists. Do not claim you have "
    "already finished an action this turn, and never emit [ACTION] tags."
)


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


def _model_alias(model: Optional[str]) -> str:
    m = (model or "").lower()
    if "opus" in m:
        return "opus"
    if "sonnet" in m:
        return "sonnet"
    return "haiku"


def _text_of(content: Any) -> str:
    """messages[i]['content'] may be a string or a list of content blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for b in content:
            if isinstance(b, dict):
                parts.append(b.get("text", ""))
            else:
                parts.append(getattr(b, "text", "") or str(b))
        return " ".join(p for p in parts if p)
    return str(content)


def _build_prompt(messages: list) -> str:
    """Flatten the conversation history into a single transcript prompt."""
    lines = []
    for msg in messages or []:
        role = msg.get("role", "user")
        speaker = "User" if role == "user" else "Assistant"
        lines.append(f"{speaker}: {_text_of(msg.get('content', ''))}")
    lines.append("Assistant:")
    return "\n".join(lines)


def _usage_from(u: Any) -> _Usage:
    """SDK usage may be a dict or an object; pull input/output token counts."""
    if isinstance(u, dict):
        return _Usage(
            input_tokens=int(u.get("input_tokens", 0) or 0),
            output_tokens=int(u.get("output_tokens", 0) or 0),
        )
    return _Usage(
        input_tokens=int(getattr(u, "input_tokens", 0) or 0),
        output_tokens=int(getattr(u, "output_tokens", 0) or 0),
    )


# Sentence-boundary splitter for streaming TTS: break on . ! ? or newline so each
# yielded chunk is a speakable unit. Keeps the trailing delimiter with the sentence.
_SENTENCE_BOUNDARY = re.compile(r"[^.!?\n]*[.!?\n]+", re.DOTALL)


def _drain_sentences(buffer: str) -> tuple[list[str], str]:
    """Pull complete sentences out of `buffer`. Returns (sentences, remainder)."""
    sentences: list[str] = []
    last_end = 0
    for m in _SENTENCE_BOUNDARY.finditer(buffer):
        chunk = buffer[last_end:m.end()].strip()
        if chunk:
            sentences.append(chunk)
        last_end = m.end()
    return sentences, buffer[last_end:]


# ---------------------------------------------------------------------------
# Router — match a turn to the cheapest tier that can handle it
# ---------------------------------------------------------------------------
# Conservative: any hint of an ACTION goes to the heavy agent; everything else is
# fast chat. To add a tier later (e.g. "instant" no-LLM, "light" few-tools,
# "background" async), add a rule here and a config in _tier_options — done.
_ACTION_RE = re.compile(
    r"\b(open|launch|start|run|execute|play|pause|resume|stop|close|quit|kill|find|"
    r"search|locate|show|pull up|bring up|go to|navigate|set|turn|create|make|build|"
    r"write|save|delete|remove|move|copy|rename|check|screenshot|capture|download|"
    r"install|update|upgrade|restart|reboot|volume|mute|unmute|brightness|google|"
    r"youtube|spotify|email|mail|calendar|schedule|file|folder|script|command|"
    r"terminal|website|browser|lights?|fan|camera)\b",
    re.IGNORECASE,
)


def _route(text: str) -> str:
    """Pick the tier for this turn. Conservative — any hint of doing something
    goes to the full agent; otherwise the fast chat tier.

    A "vision" tier sits above the others: if the user asks JARVIS to SEE the
    screen ("look at this", "what's on my screen"), we capture a frame and let
    the multimodal agent tier READ it. Build requests are handled by server.py's
    dedicated Sonnet BUILD path (background), so they are NOT special-cased here."""
    try:
        from vision_build import looks_like_vision
        if looks_like_vision(text or ""):
            return "vision"
    except Exception:
        pass
    return "agent" if _ACTION_RE.search(text or "") else "chat"


# ---------------------------------------------------------------------------
# Action auto-recording — PostToolUse hook on the AGENT tier
# ---------------------------------------------------------------------------
# The agent tier has full tools; when it DOES something meaningful (writes/edits/
# deletes a file, runs a filesystem-mutating Bash command) we record a concise
# durable memory to SQLite. That record is then surfaced into the shared context
# block (build_memory_context) every turn, so JARVIS — on EITHER tier and even
# after a restart — remembers what it built and can act on it ("delete the game
# you made"). We use a hook rather than a reply marker because the model can't
# "forget" to fire it, it carries the exact file_path/command, and it never
# leaks into the spoken reply.

# Bash commands that mutate the filesystem are worth recording; read-only ones
# (ls/cat/grep/find/echo/google-chrome/xdg-open …) are noise.
_FS_MUTATING_RE = re.compile(
    r"\b(rm|rmdir|mv|cp|mkdir|touch|tee|dd|chmod|chown|ln|truncate|"
    r"unzip|tar|git|npm|pip|make|cargo|go|python3?|node|"
    r"install|wget|curl\s+-[a-zA-Z]*o)\b"
)
# A '>' or '>>' redirect also mutates the filesystem.
_REDIRECT_RE = re.compile(r">>?\s*\S")


def _summarize_tool_action(tool_name: str, tool_input: dict) -> Optional[str]:
    """Turn a PostToolUse event into a short durable sentence, or None to skip."""
    ti = tool_input or {}
    if tool_name in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        path = ti.get("file_path") or ti.get("notebook_path") or ""
        if not path:
            return None
        verb = "Created/edited" if tool_name in ("Write", "NotebookEdit") else "Edited"
        if tool_name == "Write":
            verb = "Created"
        return f"{verb} file {path}"
    if tool_name == "Bash":
        cmd = (ti.get("command") or "").strip()
        if not cmd:
            return None
        if not (_FS_MUTATING_RE.search(cmd) or _REDIRECT_RE.search(cmd)):
            return None
        # Skip self-preservation / browser-launch noise that isn't a real artifact.
        low = cmd.lower()
        if any(k in low for k in ("google-chrome", "xdg-open", "chromium")):
            return None
        return f"Ran command: {cmd[:200]}"
    return None


async def _post_tool_use_hook(input_data, tool_use_id, context):
    """PostToolUse hook (AGENT tier). `input_data` is a raw dict from the SDK
    transport with keys tool_name / tool_input. Records significant actions to
    the DB off the event loop. Always returns {} so it never blocks the tool."""
    try:
        data = input_data if isinstance(input_data, dict) else {}
        tool_name = data.get("tool_name", "")
        tool_input = data.get("tool_input", {}) or {}
        summary = _summarize_tool_action(tool_name, tool_input)
        if summary:
            import memory
            await asyncio.to_thread(memory.record_action, summary, "agent")
    except Exception:
        pass
    return {}


def _agent_hooks():
    """Hooks dict for the agent tier: record Write/Edit/Bash actions."""
    from claude_agent_sdk import HookMatcher
    return {
        "PostToolUse": [
            HookMatcher(
                matcher="Write|Edit|MultiEdit|NotebookEdit|Bash",
                hooks=[_post_tool_use_hook],
            )
        ]
    }


def _tier_options(tier: str, model: str):
    """Build ClaudeAgentOptions for a tier. New tiers slot in here."""
    from claude_agent_sdk import ClaudeAgentOptions
    if tier == "chat":
        return ClaudeAgentOptions(
            system_prompt=_CHAT_PROMPT,
            cwd=_CWD,
            model=model,
            allowed_tools=[],              # no tools -> a single fast LLM turn
            max_turns=1,
            permission_mode="default",
            setting_sources=[],
            include_partial_messages=True,
        )
    # "agent" (default heavy tier) and "vision" (same full-tool, multimodal
    # session — the agent's Read tool sees images): act without prompts.
    # PostToolUse hook auto-records meaningful actions to durable memory.
    return ClaudeAgentOptions(
        system_prompt=_AGENTIC,
        cwd=_CWD,
        model=model,
        permission_mode="bypassPermissions",
        setting_sources=[],
        include_partial_messages=True,
        hooks=_agent_hooks(),
        add_dirs=["/tmp"],   # vision frames live in /tmp — keep Read ungated there
    )


# ---------------------------------------------------------------------------
# One-shot path (lightweight helpers) — stateless `claude -p` subprocess
# ---------------------------------------------------------------------------
class _Messages:
    async def create(
        self,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        system: Optional[Any] = None,
        messages: Optional[list] = None,
        **_: Any,
    ) -> _Response:
        if not _CLAUDE:
            return _Response(content=[_Block(text="Claude CLI not found on PATH, sir.")])

        prompt = _build_prompt(messages or [])
        cmd = [
            _CLAUDE, "-p", prompt,
            "--output-format", "json",
            "--model", _model_alias(model),
        ]
        sys_text = _text_of(system) if system else ""
        if sys_text:
            cmd += ["--append-system-prompt", sys_text]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=_CWD,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            out, err = await asyncio.wait_for(proc.communicate(), timeout=120)
        except asyncio.TimeoutError:
            return _Response(content=[_Block(text="My apologies, sir — that took too long.")])
        except Exception as e:
            return _Response(content=[_Block(text=f"Subprocess error: {e}")])

        raw = out.decode("utf-8", "replace").strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return _Response(content=[_Block(text=raw or "…")])

        return _Response(
            content=[_Block(text=data.get("result", "") or "")],
            usage=_usage_from(data.get("usage", {}) or {}),
            stop_reason=data.get("stop_reason", "end_turn") or "end_turn",
        )


# ---------------------------------------------------------------------------
# The brain — tiered router over persistent ClaudeSDKClient sessions
# ---------------------------------------------------------------------------
class ClaudeBrain:
    """Routes each turn to a tiered persistent session (fast 'chat' vs full-tool
    'agent'), with conversation memory and no per-turn cold start. Also quacks like
    anthropic.AsyncAnthropic via .messages.create for lightweight helpers."""

    def __init__(self, *_, model: str = "haiku", **__):
        self.messages = _Messages()
        self._model = model
        self._sessions: dict[str, Any] = {}            # tier -> ClaudeSDKClient
        # Pre-create per-tier locks so warmup can't race a real turn into two locks/
        # sessions for the same tier. _lock_for keeps a lazy fallback for other tiers.
        self._locks: dict[str, asyncio.Lock] = {t: asyncio.Lock() for t in ("chat", "agent", "vision")}  # tier -> lock (one query/tier at a time)
        self._api: Any = None                          # lazy AsyncAnthropic (chat tier, if keyed)
        self._api_tried = False

    def _api_client(self):
        """Return an AsyncAnthropic client for the fast chat tier, or None if no
        ANTHROPIC_API_KEY is configured (then the subprocess path is used)."""
        if self._api_tried:
            return self._api
        self._api_tried = True
        key = (os.getenv("ANTHROPIC_API_KEY") or "").strip()
        if not key:
            return None
        try:
            import anthropic
            self._api = anthropic.AsyncAnthropic(api_key=key, timeout=20.0)
        except Exception:
            self._api = None
        return self._api

    async def _api_stream_chat(self, message: str) -> AsyncIterator[str]:
        """Stream the chat tier from the Anthropic API in sentence-sized chunks."""
        buffer = ""
        async with self._api.messages.stream(
            model=_api_model_id(self._model),
            max_tokens=300,
            system=_CHAT_PROMPT,
            messages=[{"role": "user", "content": message}],
        ) as stream:
            async for delta in stream.text_stream:
                buffer += delta or ""
                sentences, buffer = _drain_sentences(buffer)
                for s in sentences:
                    yield s
        tail = buffer.strip()
        if tail:
            yield tail

    async def _api_once_chat(self, message: str) -> _Response:
        """Non-streaming chat-tier call via the Anthropic API."""
        resp = await self._api.messages.create(
            model=_api_model_id(self._model),
            max_tokens=300,
            system=_CHAT_PROMPT,
            messages=[{"role": "user", "content": message}],
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
        if getattr(resp, "stop_reason", None) == "refusal" or not text.strip():
            raise RuntimeError("api chat empty/refusal")
        return _Response(content=[_Block(text=text)], usage=_usage_from(resp.usage),
                         stop_reason=getattr(resp, "stop_reason", "end_turn") or "end_turn")

    def _lock_for(self, tier: str) -> asyncio.Lock:
        if tier not in self._locks:
            self._locks[tier] = asyncio.Lock()
        return self._locks[tier]

    async def _ensure_session(self, tier: str) -> Any:
        client = self._sessions.get(tier)
        if client is not None:
            return client
        from claude_agent_sdk import ClaudeSDKClient
        client = ClaudeSDKClient(options=_tier_options(tier, self._model))
        await client.connect()
        self._sessions[tier] = client
        return client

    async def _reset_session(self, tier: str) -> None:
        client = self._sessions.pop(tier, None)
        if client is not None:
            try:
                await client.disconnect()
            except Exception:
                pass

    @staticmethod
    def _wrap(user_text: str, system_context: str) -> str:
        ctx = (system_context or "").strip()
        return f"<JARVIS_CONTEXT>\n{ctx}\n</JARVIS_CONTEXT>\n\n{user_text}" if ctx else user_text

    @staticmethod
    async def _vision_message(user_text: str) -> str:
        """VISION tier: capture the screen now and return an instruction that
        tells the multimodal agent session to READ that frame and answer. Falls
        back to a spoken apology message if capture isn't available."""
        from vision_build import capture_screen, vision_prompt
        path = await capture_screen()
        if not path:
            return (
                "Tell the user, in one short JARVIS sentence, that you couldn't "
                "capture the screen just now."
            )
        return vision_prompt(path, user_text)

    async def _run_once(self, tier: str, message: str) -> _Response:
        from claude_agent_sdk import ResultMessage, AssistantMessage, TextBlock
        client = await self._ensure_session(tier)
        await client.query(message)
        text_parts: list[str] = []
        usage = _Usage()
        stop = "end_turn"
        async for msg in client.receive_response():
            if isinstance(msg, ResultMessage):
                if msg.result:
                    text_parts = [msg.result]      # final text wins
                if msg.usage:
                    usage = _usage_from(msg.usage)
                stop = msg.stop_reason or stop
            elif isinstance(msg, AssistantMessage) and not text_parts:
                for b in msg.content:
                    if isinstance(b, TextBlock):
                        text_parts.append(b.text)
        return _Response(content=[_Block(text="".join(text_parts))], usage=usage, stop_reason=stop)

    async def respond(self, user_text: str, system_context: str = "") -> _Response:
        """Route the turn to the right tier's persistent session. Falls back to a
        one-shot subprocess if the session errors so JARVIS never goes mute."""
        tier = _route(user_text)
        if tier == "vision":
            message = await self._vision_message(user_text)
        else:
            message = self._wrap(user_text, system_context)
        # Fast chat tier via the Anthropic API (if keyed) — skips the ~2.2s subprocess.
        if tier == "chat" and self._api_client() is not None:
            try:
                return await self._api_once_chat(message)
            except Exception:
                pass  # fall through to the subprocess session
        async with self._lock_for(tier):
            try:
                return await self._run_once(tier, message)
            except Exception:
                await self._reset_session(tier)
                try:
                    return await self._run_once(tier, message)
                except Exception:
                    return await self.messages.create(
                        model=self._model,
                        system=system_context,
                        messages=[{"role": "user", "content": user_text}],
                    )

    async def _stream_once(self, tier: str, message: str) -> AsyncIterator[str]:
        """Yield text in sentence-sized chunks as the tier's session produces it."""
        from claude_agent_sdk import StreamEvent
        client = await self._ensure_session(tier)
        await client.query(message)
        buffer = ""
        async for msg in client.receive_response():
            if isinstance(msg, StreamEvent):
                ev = msg.event or {}
                if ev.get("type") == "content_block_delta":
                    delta = ev.get("delta") or {}
                    if delta.get("type") == "text_delta":
                        buffer += delta.get("text") or ""
                        sentences, buffer = _drain_sentences(buffer)
                        for s in sentences:
                            yield s
        tail = buffer.strip()
        if tail:
            yield tail

    async def respond_stream(self, user_text: str, system_context: str = "") -> AsyncIterator[str]:
        """Streaming + routed: yields sentence chunks from the chosen tier's session.
        On error, falls back to a whole-text response so JARVIS never goes mute."""
        tier = _route(user_text)
        if tier == "vision":
            message = await self._vision_message(user_text)
        else:
            message = self._wrap(user_text, system_context)
        # Fast chat tier via the Anthropic API (if keyed) — true token streaming,
        # first spoken sentence in ~0.6s instead of ~2.2s. On any error, fall
        # through to the subprocess session so JARVIS never goes mute.
        # `produced` tracks whether ANY chunk has already been yielded (spoken)
        # this turn; once it has, we NEVER fall through to a lower tier — that
        # would replay (double-speak) the turn the user already heard.
        produced = False
        if tier == "chat" and self._api_client() is not None:
            try:
                async for chunk in self._api_stream_chat(message):
                    produced = True
                    yield chunk
                if produced:
                    return
            except Exception:
                if produced:
                    return  # already spoken — don't replay on a lower tier
                pass  # empty/early error — fall through to the subprocess session below
        async with self._lock_for(tier):
            try:
                async for chunk in self._stream_once(tier, message):
                    produced = True
                    yield chunk
                if produced:
                    return
            except Exception:
                await self._reset_session(tier)
                if produced:
                    return  # already spoken — don't replay via the one-shot fallback
            # Fallback: one-shot non-streaming, yielded whole. Only when nothing
            # has been produced yet, so it can't replay an already-spoken turn.
            if not produced:
                try:
                    resp = await self._run_once(tier, message)
                    text = resp.content[0].text if resp.content else ""
                except Exception:
                    resp = await self.messages.create(
                        model=self._model,
                        system=system_context,
                        messages=[{"role": "user", "content": user_text}],
                    )
                    text = resp.content[0].text if resp.content else ""
                if text:
                    yield text

    async def warmup(self) -> None:
        """Pre-connect the tier sessions so the first real turn isn't a cold connect."""
        for tier in ("chat", "agent"):
            try:
                async with self._lock_for(tier):
                    await self._ensure_session(tier)
            except Exception:
                pass

    async def aclose(self) -> None:
        for tier in list(self._sessions.keys()):
            await self._reset_session(tier)
