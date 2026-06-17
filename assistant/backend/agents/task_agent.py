"""Task agent — SQLite-backed task list with auto-prioritization.

Accepts tasks via command, auto-prioritizes by keywords + due date, checks for
overdue tasks hourly, and exposes the list to the UI.
"""

from __future__ import annotations

import asyncio
import re
import time
from typing import Any, Optional

from .. import db
from ..events import bus
from .base import Agent

_URGENT = ("urgent", "asap", "immediately", "now", "critical")
_SOON = ("today", "tonight", "this morning", "this afternoon")
_LOW = ("whenever", "someday", "eventually", "no rush")


def _priority_for(text: str) -> int:
    """Infer priority 1 (highest)..5 from keywords."""
    low = text.lower()
    if any(k in low for k in _URGENT):
        return 1
    if any(k in low for k in _SOON):
        return 2
    if any(k in low for k in _LOW):
        return 5
    return 3


class TaskAgent(Agent):
    """Manages the task database."""

    name = "task"

    async def add(self, description: str, due: Optional[float] = None) -> dict[str, Any]:
        """Add a task, auto-prioritized."""
        priority = _priority_for(description)
        title = re.sub(r"\b(urgent|asap|whenever|someday)\b", "", description,
                       flags=re.I).strip() or description
        task_id = await db.add_task(title, priority=priority, due=due)
        self.set_status("active", last_action=f"Added task: {title} (P{priority})")
        await self.broadcast_tasks()
        return {"ok": True, "message": f"Added '{title}' at priority {priority}", "id": task_id}

    async def list(self) -> list[dict[str, Any]]:
        """Return current open tasks."""
        return await db.list_tasks()

    async def complete(self, task_id: int) -> dict[str, Any]:
        """Mark a task done."""
        await db.complete_task(task_id)
        self.set_status("active", last_action=f"Completed task #{task_id}")
        await self.broadcast_tasks()
        return {"ok": True, "message": f"Completed task #{task_id}"}

    async def remove(self, task_id: int) -> dict[str, Any]:
        """Delete a task."""
        await db.delete_task(task_id)
        await self.broadcast_tasks()
        return {"ok": True, "message": f"Deleted task #{task_id}"}

    async def decompose(self, description: str) -> dict[str, Any]:
        """Break a task into simple ordered subtasks (heuristic)."""
        parent_id = (await db.add_task(description, _priority_for(description)))
        steps = [s.strip() for s in re.split(r",|;| then | and ", description) if s.strip()]
        if len(steps) <= 1:
            steps = [f"Plan: {description}", f"Do: {description}", f"Review: {description}"]
        for s in steps:
            await db.add_task(s, _priority_for(description), parent_id=parent_id)
        await self.broadcast_tasks()
        return {"ok": True, "message": f"Broke into {len(steps)} subtasks"}

    async def broadcast_tasks(self) -> None:
        """Push the current task list to the UI."""
        await bus.broadcast("task_update", await db.list_tasks())

    async def start(self) -> None:
        """Hourly overdue check."""
        self.set_status("running", next_action="overdue check (hourly)")
        while True:
            try:
                overdue = await db.overdue_tasks()
                if overdue:
                    titles = ", ".join(t["title"] for t in overdue[:5])
                    await bus.notify("Overdue tasks", titles, level="warning", agent="task")
                    self.set_status("running", last_action=f"{len(overdue)} overdue",
                                    next_action="overdue check (hourly)")
                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                return
            except Exception:  # noqa: BLE001
                await asyncio.sleep(60)
