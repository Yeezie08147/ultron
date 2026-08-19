"""
JARVIS Memory & Planning — persistent context, tasks, notes, and smart routing.

Three systems:
1. Memory — facts, preferences, project context JARVIS learns from conversations
2. Tasks — to-do items with priority, due dates, project association
3. Notes — freeform context tied to projects, people, or topics

Everything stored in SQLite. Relevant memories injected into every LLM call
so JARVIS gets smarter over time.
"""

import json
import logging
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path

log = logging.getLogger("jarvis.memory")

DB_PATH = Path(__file__).parent / "data" / "jarvis.db"


def _get_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = _get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,          -- 'fact', 'preference', 'project', 'person', 'decision'
            content TEXT NOT NULL,
            source TEXT DEFAULT '',      -- what conversation/context it came from
            importance INTEGER DEFAULT 5, -- 1-10, higher = more important
            created_at REAL NOT NULL,
            last_accessed REAL,
            access_count INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            priority TEXT DEFAULT 'medium', -- 'high', 'medium', 'low'
            status TEXT DEFAULT 'open',     -- 'open', 'in_progress', 'done', 'cancelled'
            due_date TEXT,                  -- ISO date string
            due_time TEXT,                  -- HH:MM
            project TEXT DEFAULT '',
            tags TEXT DEFAULT '[]',         -- JSON array
            notes TEXT DEFAULT '',
            created_at REAL NOT NULL,
            completed_at REAL
        );

        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT DEFAULT '',
            content TEXT NOT NULL,
            topic TEXT DEFAULT '',       -- project name, person, or topic
            tags TEXT DEFAULT '[]',      -- JSON array
            created_at REAL NOT NULL,
            updated_at REAL
        );

        -- Durable conversation log: every turn (user text + JARVIS reply), so
        -- the dialogue survives a server restart instead of dying with the
        -- per-connection in-memory `history` list.
        CREATE TABLE IF NOT EXISTS conversation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,          -- 'user' or 'assistant'
            content TEXT NOT NULL,
            created_at REAL NOT NULL
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
            content, type, source,
            content='memories', content_rowid='id'
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS task_fts USING fts5(
            title, description, project, notes,
            content='tasks', content_rowid='id'
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS note_fts USING fts5(
            title, content, topic,
            content='notes', content_rowid='id'
        );
    """)
    conn.close()
    log.info("Memory database initialized")


# ---------------------------------------------------------------------------
# Memories — facts JARVIS learns
# ---------------------------------------------------------------------------

def remember(content: str, mem_type: str = "fact", source: str = "", importance: int = 5) -> int:
    """Store a memory. Returns the memory ID."""
    try:
        conn = _get_db()
        cur = conn.execute(
            "INSERT INTO memories (type, content, source, importance, created_at) VALUES (?, ?, ?, ?, ?)",
            (mem_type, content, source, importance, time.time())
        )
        mem_id = cur.lastrowid
        # Update FTS
        conn.execute(
            "INSERT INTO memory_fts (rowid, content, type, source) VALUES (?, ?, ?, ?)",
            (mem_id, content, mem_type, source)
        )
        conn.commit()
        conn.close()
        log.info(f"Stored memory [{mem_type}]: {content[:60]}")
        return mem_id
    except Exception as e:
        log.warning(f"remember failed (DB write): {e}")
        return None


def _sanitize_fts_query(query: str) -> str:
    """Clean a query string for FTS5 — remove special characters that break it."""
    # Remove apostrophes, quotes, and FTS operators
    cleaned = query.replace("'", "").replace('"', "").replace("*", "").replace("-", " ")
    # Take meaningful words only
    words = [w for w in cleaned.split() if len(w) > 2]
    if not words:
        return ""
    # Join with OR for broader matching
    return " OR ".join(words[:5])


def recall(query: str, limit: int = 5) -> list[dict]:
    """Search memories by relevance. Returns most relevant matches."""
    fts_query = _sanitize_fts_query(query)
    if not fts_query:
        return []
    conn = _get_db()
    try:
        results = conn.execute("""
            SELECT m.id, m.type, m.content, m.importance, m.created_at, m.access_count
            FROM memory_fts f
            JOIN memories m ON f.rowid = m.id
            WHERE memory_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """, (fts_query, limit)).fetchall()
    except Exception:
        results = []

    # Update access counts — read-hot path; a lock here must never break recall,
    # which must still return its SELECT results even if the bump fails.
    try:
        for r in results:
            conn.execute(
                "UPDATE memories SET last_accessed = ?, access_count = access_count + 1 WHERE id = ?",
                (time.time(), r["id"])
            )
        conn.commit()
    except Exception as e:
        log.warning(f"recall access-count bump failed: {e}")
    conn.close()
    return [dict(r) for r in results]


def get_recent_memories(limit: int = 10) -> list[dict]:
    """Get most recent memories."""
    conn = _get_db()
    results = conn.execute(
        "SELECT * FROM memories ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in results]


def get_important_memories(limit: int = 10) -> list[dict]:
    """Get highest importance memories."""
    conn = _get_db()
    results = conn.execute(
        "SELECT * FROM memories ORDER BY importance DESC, access_count DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in results]


# ---------------------------------------------------------------------------
# Actions — durable record of things the AGENT tier actually DID
# ---------------------------------------------------------------------------
# These are stored as ordinary memories with type='action' so they ride the
# existing FTS5 recall machinery for free. Recording one is how JARVIS keeps a
# durable record of "I built/created/deleted X" across both brain tiers AND
# across server restarts — fixing the "built a game then forgot it" bug.

def record_action(description: str, source: str = "agent") -> int:
    """Store a concise durable record of an action the agent performed, e.g.
    'Created Pacman game at /home/utsav/pacman/index.html'. Deduped against the
    most recent few actions so a repeated tool call doesn't spam the log."""
    description = (description or "").strip()
    if not description:
        return 0
    try:
        # Cheap dedup: skip if an identical action was just recorded.
        for a in get_recent_actions(limit=3):
            if a["content"].strip() == description:
                return a["id"]
    except Exception as e:
        log.warning(f"record_action dedup lookup failed: {e}")
    return remember(description, mem_type="action", source=source, importance=8)


def get_recent_actions(limit: int = 10) -> list[dict]:
    """Most recent recorded actions (newest first)."""
    conn = _get_db()
    results = conn.execute(
        "SELECT * FROM memories WHERE type = 'action' ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in results]


# ---------------------------------------------------------------------------
# Conversation — durable turn log so dialogue survives a restart
# ---------------------------------------------------------------------------

def log_turn(role: str, content: str) -> None:
    """Append one conversation turn (user or assistant) to the durable log."""
    content = (content or "").strip()
    if not content:
        return
    try:
        conn = _get_db()
        conn.execute(
            "INSERT INTO conversation (role, content, created_at) VALUES (?, ?, ?)",
            (role, content, time.time()),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        log.warning(f"log_turn failed (DB write): {e}")
        return


def get_recent_conversation(limit: int = 20) -> list[dict]:
    """Load the most recent conversation turns in chronological order. Used on a
    new WebSocket connection to seed `history` so JARVIS still has context after
    a server restart."""
    conn = _get_db()
    rows = conn.execute(
        "SELECT role, content FROM conversation ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    rows = list(reversed([dict(r) for r in rows]))
    return rows


def format_recent_conversation(limit: int = 8) -> str:
    """A short transcript of the latest turns for the shared context block."""
    turns = get_recent_conversation(limit=limit)
    if not turns:
        return ""
    lines = []
    for t in turns:
        who = "User" if t["role"] == "user" else "JARVIS"
        lines.append(f"  {who}: {t['content'][:200]}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

def create_task(title: str, description: str = "", priority: str = "medium",
                due_date: str = "", due_time: str = "", project: str = "",
                tags: list[str] = None) -> int:
    """Create a task. Returns task ID."""
    try:
        conn = _get_db()
        cur = conn.execute(
            """INSERT INTO tasks (title, description, priority, due_date, due_time,
               project, tags, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (title, description, priority, due_date, due_time,
             project, json.dumps(tags or []), time.time())
        )
        task_id = cur.lastrowid
        conn.execute(
            "INSERT INTO task_fts (rowid, title, description, project, notes) VALUES (?, ?, ?, ?, ?)",
            (task_id, title, description, project, "")
        )
        conn.commit()
        conn.close()
        log.info(f"Created task [{priority}]: {title}")
        return task_id
    except Exception as e:
        log.warning(f"create_task failed (DB write): {e}")
        return None


def get_open_tasks(project: str = None) -> list[dict]:
    """Get all open/in-progress tasks, optionally filtered by project."""
    conn = _get_db()
    if project:
        results = conn.execute(
            "SELECT * FROM tasks WHERE status IN ('open','in_progress') AND project LIKE ? ORDER BY "
            "CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, due_date",
            (f"%{project}%",)
        ).fetchall()
    else:
        results = conn.execute(
            "SELECT * FROM tasks WHERE status IN ('open','in_progress') ORDER BY "
            "CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, due_date"
        ).fetchall()
    conn.close()
    return [dict(r) for r in results]


def get_tasks_for_date(date_str: str) -> list[dict]:
    """Get tasks due on a specific date (YYYY-MM-DD)."""
    conn = _get_db()
    results = conn.execute(
        "SELECT * FROM tasks WHERE due_date = ? AND status != 'cancelled' ORDER BY "
        "CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, due_time",
        (date_str,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in results]


def complete_task(task_id: int):
    """Mark a task as done."""
    try:
        conn = _get_db()
        conn.execute(
            "UPDATE tasks SET status = 'done', completed_at = ? WHERE id = ?",
            (time.time(), task_id)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        log.warning(f"complete_task failed (DB write): {e}")
        return


def search_tasks(query: str, limit: int = 10) -> list[dict]:
    """Search tasks by text."""
    fts_query = _sanitize_fts_query(query)
    if not fts_query:
        return []
    conn = _get_db()
    try:
        results = conn.execute("""
            SELECT t.* FROM task_fts f
            JOIN tasks t ON f.rowid = t.id
            WHERE task_fts MATCH ?
            ORDER BY rank LIMIT ?
        """, (fts_query, limit)).fetchall()
    except Exception:
        results = []
    conn.close()
    return [dict(r) for r in results]


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------

def create_note(content: str, title: str = "", topic: str = "", tags: list[str] = None) -> int:
    """Create a note. Returns note ID."""
    try:
        conn = _get_db()
        now = time.time()
        cur = conn.execute(
            "INSERT INTO notes (title, content, topic, tags, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (title, content, topic, json.dumps(tags or []), now, now)
        )
        note_id = cur.lastrowid
        conn.execute(
            "INSERT INTO note_fts (rowid, title, content, topic) VALUES (?, ?, ?, ?)",
            (note_id, title, content, topic)
        )
        conn.commit()
        conn.close()
        log.info(f"Created note: {title or content[:40]}")
        return note_id
    except Exception as e:
        log.warning(f"create_note failed (DB write): {e}")
        return None


def search_notes(query: str, limit: int = 10) -> list[dict]:
    """Search notes by text."""
    fts_query = _sanitize_fts_query(query)
    if not fts_query:
        return []
    conn = _get_db()
    try:
        results = conn.execute("""
            SELECT n.* FROM note_fts f
            JOIN notes n ON f.rowid = n.id
            WHERE note_fts MATCH ?
            ORDER BY rank LIMIT ?
        """, (fts_query, limit)).fetchall()
    except Exception:
        results = []
    conn.close()
    return [dict(r) for r in results]


def get_notes_by_topic(topic: str) -> list[dict]:
    """Get all notes for a topic/project."""
    conn = _get_db()
    results = conn.execute(
        "SELECT * FROM notes WHERE topic LIKE ? ORDER BY updated_at DESC",
        (f"%{topic}%",)
    ).fetchall()
    conn.close()
    return [dict(r) for r in results]


# ---------------------------------------------------------------------------
# Context Builder — smart context for LLM calls
# ---------------------------------------------------------------------------

def build_memory_context(user_message: str) -> str:
    """Build relevant context from memories, tasks, and notes for the LLM.

    Searches for relevant memories based on what the user is talking about.
    Fast — runs FTS queries, no heavy computation.
    """
    parts = []
    relevant = []

    # Always include: open high-priority tasks
    high_tasks = [t for t in get_open_tasks() if t["priority"] == "high"]
    if high_tasks:
        task_lines = [f"  - [{t['priority']}] {t['title']}" +
                      (f" (due {t['due_date']})" if t["due_date"] else "")
                      for t in high_tasks[:5]]
        parts.append("HIGH PRIORITY TASKS:\n" + "\n".join(task_lines))

    # Search memories relevant to what user is saying
    if len(user_message) > 5:
        relevant = recall(user_message, limit=3)
        if relevant:
            mem_lines = [f"  - [{m['type']}] {m['content']}" for m in relevant]
            parts.append("RELEVANT MEMORIES:\n" + "\n".join(mem_lines))

    # Recent important memories (always available)
    important = get_important_memories(limit=3)
    if important:
        imp_lines = [f"  - {m['content']}" for m in important
                     if not any(m["content"] == r["content"] for r in relevant)]
        if imp_lines:
            parts.append("KEY FACTS:\n" + "\n".join(imp_lines[:3]))

    # Recorded ACTIONS — what JARVIS has actually DONE (files created, projects
    # built, things deleted). This is what lets "delete the game you made"
    # resolve to a concrete path. Always surfaced so BOTH brain tiers see them.
    actions = get_recent_actions(limit=4)   # trimmed 8→4: lighter per-turn prompt = faster TTFT; 4 still covers "the thing you just did"
    if actions:
        act_lines = [f"  - {a['content']}" for a in actions]
        parts.append(
            "ACTIONS YOU HAVE TAKEN (durable record across restarts — refer to "
            "these when the user mentions something you did, e.g. a file/project "
            "you built):\n" + "\n".join(act_lines)
        )

    # Recent conversation so far (durable across restarts). Both tiers get this,
    # so the chat tier knows what the agent tier did and vice-versa.
    convo = format_recent_conversation(limit=4)   # trimmed 6→4: fewer input tokens per turn; recent 4 keeps short-exchange continuity
    if convo:
        parts.append("RECENT CONVERSATION:\n" + convo)

    return "\n\n".join(parts) if parts else ""


def format_tasks_for_voice(tasks: list[dict]) -> str:
    """Format tasks for voice response."""
    if not tasks:
        return "No tasks on the list, sir."
    count = len(tasks)
    high = [t for t in tasks if t["priority"] == "high"]
    if count == 1:
        t = tasks[0]
        return f"One task: {t['title']}." + (f" Due {t['due_date']}." if t["due_date"] else "")
    result = f"You have {count} open tasks."
    if high:
        result += f" {len(high)} are high priority."
    top = tasks[:3]
    for t in top:
        result += f" {t['title']}."
    if count > 3:
        result += f" And {count - 3} more."
    return result


def format_plan_for_voice(tasks: list[dict], events: list[dict]) -> str:
    """Format a day plan combining tasks and calendar events."""
    if not tasks and not events:
        return "Your day looks clear, sir. No events or tasks scheduled."

    parts = []
    if events:
        parts.append(f"{len(events)} events on the calendar")
    if tasks:
        high = [t for t in tasks if t["priority"] == "high"]
        parts.append(f"{len(tasks)} tasks" + (f", {len(high)} high priority" if high else ""))

    result = f"For tomorrow: {', '.join(parts)}. "

    # List events first
    if events:
        for e in events[:3]:
            result += f"{e.get('start', '')} {e['title']}. "

    # Then high priority tasks
    if tasks:
        for t in [t for t in tasks if t["priority"] == "high"][:2]:
            result += f"Priority: {t['title']}. "

    result += "Shall I adjust anything?"
    return result


# ---------------------------------------------------------------------------
# Memory extraction — learn from conversations
# ---------------------------------------------------------------------------

async def extract_memories(user_text: str, jarvis_response: str, anthropic_client) -> list[str]:
    """After a conversation turn, extract any facts worth remembering.

    Uses Haiku to decide if anything in the exchange is worth storing.
    Returns list of memories stored.
    """
    if not anthropic_client or len(user_text) < 15:
        return []

    try:
        response = await anthropic_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            system=(
                "Extract facts worth remembering from this conversation. "
                "Only extract CONCRETE facts: preferences, decisions, names, dates, plans, goals. "
                "NOT opinions, greetings, or casual chat. "
                "Return JSON array of objects: [{\"type\": \"fact|preference|project|person|decision\", \"content\": \"...\", \"importance\": 1-10}] "
                "Return [] if nothing worth remembering. Be very selective."
            ),
            messages=[{"role": "user", "content": f"User: {user_text}\nJARVIS: {jarvis_response}"}],
        )

        text = response.content[0].text.strip()
        # Parse JSON
        if text.startswith("["):
            items = json.loads(text)
            stored = []
            for item in items:
                if isinstance(item, dict) and "content" in item:
                    remember(
                        content=item["content"],
                        mem_type=item.get("type", "fact"),
                        source=user_text[:50],
                        importance=item.get("importance", 5),
                    )
                    stored.append(item["content"])
            return stored
    except Exception as e:
        log.debug(f"Memory extraction failed: {e}")

    return []


# Initialize on import
init_db()
