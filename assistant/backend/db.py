"""SQLite database (async) for tasks, reminders, clipboard, and activity.

All persistence the agents need lives here so state survives restarts. Uses
``aiosqlite`` so it never blocks the asyncio event loop.
"""

from __future__ import annotations

import os
import time
from typing import Any, Optional

import aiosqlite

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "system.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    priority INTEGER DEFAULT 3,
    due REAL,
    done INTEGER DEFAULT 0,
    parent_id INTEGER,
    created REAL NOT NULL,
    updated REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    fire_at REAL,
    cron TEXT,
    fired INTEGER DEFAULT 0,
    created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS clipboard (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    is_url INTEGER DEFAULT 0,
    ts REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,        -- app_open, command, etc.
    name TEXT,
    ts REAL NOT NULL,
    hour INTEGER,
    weekday INTEGER
);
"""


async def init() -> None:
    """Create the database schema if it does not exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(_SCHEMA)
        await db.commit()


async def _rows(db: aiosqlite.Connection, query: str, args: tuple = ()) -> list[dict[str, Any]]:
    """Run a query and return rows as dicts."""
    db.row_factory = aiosqlite.Row
    cur = await db.execute(query, args)
    rows = await cur.fetchall()
    return [dict(r) for r in rows]


# --------------------------------------------------------------------------- #
# Tasks
# --------------------------------------------------------------------------- #
async def add_task(title: str, priority: int = 3, due: Optional[float] = None,
                   parent_id: Optional[int] = None) -> int:
    """Insert a task and return its id."""
    now = time.time()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO tasks (title, priority, due, parent_id, created, updated) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (title, priority, due, parent_id, now, now),
        )
        await db.commit()
        return cur.lastrowid or 0


async def list_tasks(include_done: bool = False) -> list[dict[str, Any]]:
    """Return tasks ordered by done, priority, due."""
    q = "SELECT * FROM tasks"
    if not include_done:
        q += " WHERE done = 0"
    q += " ORDER BY done ASC, priority ASC, COALESCE(due, 9e18) ASC, created ASC"
    async with aiosqlite.connect(DB_PATH) as db:
        return await _rows(db, q)


async def complete_task(task_id: int) -> None:
    """Mark a task complete."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE tasks SET done = 1, updated = ? WHERE id = ?",
                         (time.time(), task_id))
        await db.commit()


async def delete_task(task_id: int) -> None:
    """Delete a task."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        await db.commit()


async def overdue_tasks() -> list[dict[str, Any]]:
    """Return incomplete tasks past their due time."""
    now = time.time()
    async with aiosqlite.connect(DB_PATH) as db:
        return await _rows(
            db, "SELECT * FROM tasks WHERE done = 0 AND due IS NOT NULL AND due < ?",
            (now,),
        )


# --------------------------------------------------------------------------- #
# Reminders
# --------------------------------------------------------------------------- #
async def add_reminder(text: str, fire_at: Optional[float], cron: Optional[str]) -> int:
    """Insert a reminder; returns id."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO reminders (text, fire_at, cron, created) VALUES (?, ?, ?, ?)",
            (text, fire_at, cron, time.time()),
        )
        await db.commit()
        return cur.lastrowid or 0


async def list_reminders(include_fired: bool = False) -> list[dict[str, Any]]:
    """Return reminders."""
    q = "SELECT * FROM reminders"
    if not include_fired:
        q += " WHERE fired = 0"
    q += " ORDER BY COALESCE(fire_at, 9e18) ASC"
    async with aiosqlite.connect(DB_PATH) as db:
        return await _rows(db, q)


async def mark_reminder_fired(rem_id: int) -> None:
    """Mark a one-shot reminder as fired."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE reminders SET fired = 1 WHERE id = ?", (rem_id,))
        await db.commit()


# --------------------------------------------------------------------------- #
# Clipboard
# --------------------------------------------------------------------------- #
async def add_clip(content: str, is_url: bool) -> None:
    """Store a clipboard entry, keeping only the most recent 50."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO clipboard (content, is_url, ts) VALUES (?, ?, ?)",
                         (content, int(is_url), time.time()))
        await db.execute(
            "DELETE FROM clipboard WHERE id NOT IN "
            "(SELECT id FROM clipboard ORDER BY ts DESC LIMIT 50)"
        )
        await db.commit()


async def list_clips(limit: int = 50) -> list[dict[str, Any]]:
    """Return recent clipboard entries (newest first)."""
    async with aiosqlite.connect(DB_PATH) as db:
        return await _rows(db, "SELECT * FROM clipboard ORDER BY ts DESC LIMIT ?", (limit,))


# --------------------------------------------------------------------------- #
# Activity (routine learning)
# --------------------------------------------------------------------------- #
async def add_activity(kind: str, name: str) -> None:
    """Record a timestamped activity event for routine learning."""
    import datetime as _dt

    now = time.time()
    dt = _dt.datetime.fromtimestamp(now)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO activity (kind, name, ts, hour, weekday) VALUES (?, ?, ?, ?, ?)",
            (kind, name, now, dt.hour, dt.weekday()),
        )
        await db.commit()


async def activity_since(seconds: float) -> list[dict[str, Any]]:
    """Return activity events newer than ``seconds`` ago."""
    cutoff = time.time() - seconds
    async with aiosqlite.connect(DB_PATH) as db:
        return await _rows(db, "SELECT * FROM activity WHERE ts >= ? ORDER BY ts ASC", (cutoff,))
