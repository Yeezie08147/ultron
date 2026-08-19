"""
vision_build.py — two related capabilities bolted onto the JARVIS tiered brain:

  (1) VISION  — JARVIS can SEE. A fast detector recognises "look at this" /
      "what's on my screen" style requests; we capture the KDE/Wayland screen
      with `spectacle` (free, local) to /tmp/jarvis_view.png and let the brain's
      AGENT tier READ that image (the agent's Read tool is multimodal — proven
      path) and answer in one short JARVIS sentence. General enough to point at
      an arbitrary image path or a future camera frame.

  (2) BUILD TIER — when the user wants something SUBSTANTIAL created ("make me a
      game/app/website/tool"), we run a dedicated BUILD path on the STRONGER
      Sonnet model that does a REAL build (writes complete files to ~/Desktop/
      <name>/) and then VISUALLY SELF-CORRECTS: screenshot the result headlessly
      with Chrome, have the Sonnet session LOOK at the screenshot, judge whether
      it's broken/ugly, and iterate 1-2 times. That visual loop is the point —
      it's what makes the output good instead of a weak one-shot.

Both run inference on the user's Claude subscription via the Agent SDK (no API
key, no per-call billing). Capture is free + local. The build runs in the
BACKGROUND so the conversation never blocks.
"""
import asyncio
import re
import shutil
import time
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Detectors — cheap regex gates, run before any LLM call
# ---------------------------------------------------------------------------

# "look at this", "what's on my screen", "can you see my screen", "take a look",
# "what do you see", "what am I looking at", "read my screen", etc.
_VISION_RE = re.compile(
    r"\b("
    r"what(?:'s| is| am i| can you see)?\s+(?:on\s+)?(?:my\s+)?screen|"
    r"see\s+(?:my\s+)?screen|"
    r"look\s+at\s+(?:this|that|my\s+screen|the\s+screen)|"
    r"take\s+a\s+look|"
    r"what\s+do\s+you\s+see|"
    r"what\s+am\s+i\s+looking\s+at|"
    r"read\s+(?:my|the)\s+screen|"
    r"can\s+you\s+see\s+(?:this|that|my\s+screen)|"
    r"describe\s+(?:my|the)\s+screen|"
    r"look\s+at\s+the\s+screen"
    r")\b",
    re.IGNORECASE,
)

# Substantial CREATE requests: a build verb + a project-ish noun. Deliberately
# stricter than the agent tier's broad action regex so only real "make me a
# thing" turns get the (slower, costlier) Sonnet build path.
_BUILD_VERB_RE = re.compile(
    r"\b(make|build|create|design|code\s+up|develop|whip\s+up|put\s+together|"
    r"generate|scaffold|write)\b",
    re.IGNORECASE,
)
_BUILD_NOUN_RE = re.compile(
    r"\b(game|app|application|website|web\s*site|web\s*page|webpage|page|"
    r"landing\s+page|dashboard|tool|clone|simulator|visuali[sz]er|"
    r"calculator|clock|timer|widget|animation|demo|toy|portfolio|"
    r"snake|tetris|pong|breakout|flappy|2048|minesweeper|maze|"
    r"particle|fractal|starfield)\b",
    re.IGNORECASE,
)


def looks_like_vision(text: str) -> bool:
    """True if the user is asking JARVIS to SEE the screen / an image."""
    return bool(_VISION_RE.search(text or ""))


def looks_like_build(text: str) -> bool:
    """True if the user wants something SUBSTANTIAL built (-> Sonnet build tier)."""
    t = text or ""
    return bool(_BUILD_VERB_RE.search(t) and _BUILD_NOUN_RE.search(t))


# ---------------------------------------------------------------------------
# Screen / image capture — free + local (spectacle on KDE/Wayland)
# ---------------------------------------------------------------------------
VIEW_PATH = "/tmp/jarvis_view.png"
_SPECTACLE = shutil.which("spectacle")


async def capture_screen(out_path: str = VIEW_PATH, timeout: float = 12.0) -> Optional[str]:
    """Capture the full screen to `out_path` with spectacle (background, no
    notification). Returns the path on success, or None. Free + local."""
    if not _SPECTACLE:
        return None
    try:
        # remove any stale file so we never read an old frame
        try:
            Path(out_path).unlink()
        except FileNotFoundError:
            pass
        proc = await asyncio.create_subprocess_exec(
            _SPECTACLE, "-b", "-n", "-o", out_path,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except Exception:
            pass
        return None
    except Exception:
        return None
    p = Path(out_path)
    # spectacle may add an extension; accept the exact path or a sibling.
    if p.exists() and p.stat().st_size > 0:
        return out_path
    for cand in p.parent.glob(p.stem + ".*"):
        if cand.stat().st_size > 0:
            return str(cand)
    return None


# The instruction we hand the multimodal agent tier once a frame is captured.
def vision_prompt(image_path: str, user_text: str) -> str:
    return (
        f"A screenshot of the user's screen has ALREADY been captured for you at "
        f"{image_path}. Use your Read tool on that exact path RIGHT NOW to view it "
        f"— this is pre-authorized, do NOT ask permission and do NOT try to take a "
        f"new screenshot yourself. After reading it, answer the user in ONE short "
        f"spoken JARVIS sentence — plain words, no markdown, no lists, no questions. "
        f"The user said: \"{user_text}\". "
        f"If the Read genuinely fails, say so in one short sentence."
    )


# ---------------------------------------------------------------------------
# Headless visual check — screenshot a built HTML file with Chrome
# ---------------------------------------------------------------------------
_CHROME = shutil.which("google-chrome") or shutil.which("chromium")


async def screenshot_html(html_file: str, out_path: str, timeout: float = 30.0) -> Optional[str]:
    """Render an HTML file headlessly and screenshot it (free + local Chrome).
    Returns out_path on success or None."""
    if not _CHROME:
        return None
    file_url = html_file if "://" in html_file else f"file://{html_file}"
    try:
        try:
            Path(out_path).unlink()
        except FileNotFoundError:
            pass
        proc = await asyncio.create_subprocess_exec(
            _CHROME, "--headless=new", "--hide-scrollbars",
            "--disable-gpu", f"--screenshot={out_path}",
            "--window-size=1280,800", "--virtual-time-budget=2500",
            file_url,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except Exception:
            pass
        return None
    except Exception:
        return None
    p = Path(out_path)
    return out_path if (p.exists() and p.stat().st_size > 0) else None


def _slug(text: str) -> str:
    words = re.sub(r"[^a-z0-9\s]", "", (text or "").lower()).split()
    skip = {"a", "the", "an", "me", "build", "create", "make", "for", "with",
            "and", "to", "of", "design", "develop", "generate", "write", "us",
            "some", "my", "please", "can", "you"}
    meaningful = [w for w in words if w not in skip][:4]
    return "-".join(meaningful) if meaningful else "jarvis-build"


# ---------------------------------------------------------------------------
# BUILD TIER — a dedicated Sonnet session that builds + visually self-corrects
# ---------------------------------------------------------------------------
async def _record(summary: str) -> None:
    try:
        import memory
        await asyncio.to_thread(memory.record_action, summary, "build")
    except Exception:
        pass


def _build_options(proj_dir: Optional[str] = None):
    """Sonnet, file-editing tools only, confined to the per-build project dir.

    The agent is sandboxed: cwd is the specific project directory (NOT $HOME)
    and the toolset is whitelisted to file read/write within that tree. Bash is
    DROPPED so a misheard/adversarial utterance can't run arbitrary shell across
    the home directory. Permission mode is acceptEdits (auto-accept edits), not
    bypassPermissions.
    """
    from claude_agent_sdk import ClaudeAgentOptions
    cwd = proj_dir or str(Path.home())
    system = (
        "You are JARVIS's BUILD engine running on a Linux machine. You have "
        "file tools only (Read, Write, Edit, Glob) and are confined to your "
        "project directory — write all files there. You build real, polished, "
        "COMPLETE things — not stubs, not plans. When asked for a web game/app/"
        "page, write a single self-contained standalone index.html (inline CSS "
        "+ JS, no build step, no external deps unless via CDN) that works by "
        "just opening the file. Make it look good: sensible layout, colours, "
        "spacing; the thing must actually run. You have a multimodal Read tool "
        "— when given a screenshot path, Read it and judge the visual result "
        "honestly, then fix what's broken or ugly. Keep going until it looks "
        "right. Do not ask questions; use good judgment."
    )
    return ClaudeAgentOptions(
        system_prompt=system,
        cwd=cwd,
        model="sonnet",
        permission_mode="acceptEdits",
        allowed_tools=["Write", "Edit", "Read", "Glob"],
        setting_sources=[],
        include_partial_messages=False,
    )


async def _run_turn(client, message: str) -> str:
    """Drive one query on a ClaudeSDKClient build session; return final text."""
    from claude_agent_sdk import ResultMessage, AssistantMessage, TextBlock
    await client.query(message)
    text_parts: list[str] = []
    async for msg in client.receive_response():
        if isinstance(msg, ResultMessage):
            if msg.result:
                text_parts = [msg.result]
        elif isinstance(msg, AssistantMessage) and not text_parts:
            for b in msg.content:
                if isinstance(b, TextBlock):
                    text_parts.append(b.text)
    return "".join(text_parts).strip()


async def run_build(user_text: str, on_done=None, max_fixes: int = 2) -> dict:
    """Run a real Sonnet build with a visual self-correction loop, in the
    background. Returns a result dict; if `on_done(result)` is provided it's
    awaited at the end so the caller can speak the outcome.

    result = {"ok": bool, "name": str, "path": str, "index": str|None,
              "shot": str|None, "iterations": int, "message": str}
    """
    name = _slug(user_text)
    proj = Path.home() / "Desktop" / name
    proj.mkdir(parents=True, exist_ok=True)
    index = proj / "index.html"
    shot = f"/tmp/jarvis_build_{name}.png"

    result = {"ok": False, "name": name, "path": str(proj), "index": None,
              "shot": None, "iterations": 0, "message": ""}

    client = None
    try:
        from claude_agent_sdk import ClaudeSDKClient
        client = ClaudeSDKClient(options=_build_options(str(proj)))
        await client.connect()

        # 1) Build.
        await _run_turn(client, (
            f"Build this now: {user_text}\n\n"
            f"Write the complete result as a standalone index.html at exactly this "
            f"path: {index}\n"
            f"It must be fully working when opened directly in a browser."
        ))

        if not index.exists():
            result["message"] = f"I couldn't get {name} to produce a file, sir."
            if on_done:
                await on_done(result)
            return result
        result["index"] = str(index)
        await _record(f"Built {name} at {index} (Sonnet build tier)")

        # 2) Visual self-correction loop.
        iterations = 0
        for _ in range(max(0, max_fixes)):
            png = await screenshot_html(str(index), shot)
            if not png:
                break  # can't see it -> stop iterating, ship what we have
            result["shot"] = png
            verdict = await _run_turn(client, (
                f"Read the screenshot at {png} — this is how the page you wrote at "
                f"{index} actually renders. Judge it honestly. If it is broken, "
                f"blank, cut off, or visibly ugly, FIX {index} now (edit the file) "
                f"and reply with the single word CHANGED. If it already looks good "
                f"and works, reply with the single word GOOD."
            ))
            iterations += 1
            if "CHANGED" not in verdict.upper():
                break
            await _record(f"Visually corrected {name} (iteration {iterations})")
        result["iterations"] = iterations

        # final screenshot for the record (best-effort)
        final = await screenshot_html(str(index), shot)
        if final:
            result["shot"] = final

        result["ok"] = True
        result["message"] = (
            f"Done, sir — I built {name.replace('-', ' ')} and checked it on screen"
            + (f", refining it {iterations} time{'s' if iterations != 1 else ''}." if iterations else ".")
            + f" It's on your Desktop."
        )
        if on_done:
            await on_done(result)
        return result
    except Exception as e:
        result["message"] = f"The build for {name} hit a snag, sir: {str(e)[:120]}"
        if on_done:
            try:
                await on_done(result)
            except Exception:
                pass
        return result
    finally:
        if client is not None:
            try:
                await client.disconnect()
            except Exception:
                pass
