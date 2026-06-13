"""Task management agent — the queue, priorities and scheduling brain.

Owns all reads/writes against the ``tasks`` table and contains the heuristics
that turn natural language ("finish proposal by Friday, it's urgent") into a
structured task with an inferred priority and due date.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select, update

from core.database import AsyncSessionLocal
from core.events import event_bus
from models.task import Task, TaskStatus

logger = logging.getLogger("zero.tasks")

_URGENT_CUES = ("urgent", "asap", "immediately", "critical", "right now", "emergency")
_HIGH_CUES = ("important", "high priority", "today", "soon", "deadline")
_LOW_CUES = ("whenever", "someday", "no rush", "eventually", "low priority")

_WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}


class TaskAgent:
    def infer_priority(self, text: str) -> int:
        t = text.lower()
        if any(c in t for c in _URGENT_CUES):
            return 5
        if any(c in t for c in _HIGH_CUES):
            return 4
        if any(c in t for c in _LOW_CUES):
            return 2
        return 3

    def parse_due_date(self, text: str) -> datetime | None:
        t = text.lower()
        now = datetime.now(timezone.utc)
        if "tomorrow" in t:
            return (now + timedelta(days=1)).replace(hour=17, minute=0, second=0, microsecond=0)
        if "today" in t or "tonight" in t:
            return now.replace(hour=17, minute=0, second=0, microsecond=0)
        if "next week" in t:
            return (now + timedelta(days=7)).replace(hour=17, minute=0, second=0, microsecond=0)
        for name, idx in _WEEKDAYS.items():
            if name in t:
                delta = (idx - now.weekday()) % 7
                delta = delta or 7  # next occurrence, not today
                return (now + timedelta(days=delta)).replace(
                    hour=17, minute=0, second=0, microsecond=0
                )
        m = re.search(r"in (\d+) days?", t)
        if m:
            return now + timedelta(days=int(m.group(1)))
        return None

    async def create_task(
        self,
        title: str,
        description: str = "",
        priority: int | None = None,
        due_date: datetime | str | None = None,
        tags: list[str] | None = None,
        status: TaskStatus | str = TaskStatus.PENDING,
        agent_assigned: str | None = None,
        infer_from: str | None = None,
    ) -> dict:
        if priority is None:
            priority = self.infer_priority(infer_from or title)
        if due_date is None and infer_from:
            due_date = self.parse_due_date(infer_from)
        if isinstance(due_date, str):
            try:
                due_date = datetime.fromisoformat(due_date)
            except ValueError:
                due_date = None
        if isinstance(status, str):
            status = TaskStatus(status)

        async with AsyncSessionLocal() as session:
            task = Task(
                title=title.strip(),
                description=description,
                priority=max(1, min(5, priority)),
                due_date=due_date,
                tags=tags or [],
                status=status,
                agent_assigned=agent_assigned,
            )
            session.add(task)
            await session.commit()
            await session.refresh(task)
            data = task.to_dict()
        await event_bus.publish("task.created", data)
        return data

    async def list_tasks(self, status: str | None = None) -> list[dict]:
        async with AsyncSessionLocal() as session:
            stmt = select(Task).order_by(Task.priority.desc(), Task.created_at.desc())
            if status:
                stmt = stmt.where(Task.status == TaskStatus(status))
            rows = (await session.execute(stmt)).scalars().all()
            return [r.to_dict() for r in rows]

    async def get_task(self, task_id: int) -> dict | None:
        async with AsyncSessionLocal() as session:
            row = (
                await session.execute(select(Task).where(Task.id == task_id))
            ).scalar_one_or_none()
            return row.to_dict() if row else None

    async def update_task(self, task_id: int, **fields) -> dict | None:
        allowed = {"title", "description", "priority", "status", "due_date",
                   "tags", "subtasks", "agent_assigned", "notes"}
        clean = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if "status" in clean and isinstance(clean["status"], str):
            clean["status"] = TaskStatus(clean["status"])
        if "due_date" in clean and isinstance(clean["due_date"], str):
            try:
                clean["due_date"] = datetime.fromisoformat(clean["due_date"])
            except ValueError:
                clean.pop("due_date")
        async with AsyncSessionLocal() as session:
            await session.execute(update(Task).where(Task.id == task_id).values(**clean))
            await session.commit()
            row = (
                await session.execute(select(Task).where(Task.id == task_id))
            ).scalar_one_or_none()
            data = row.to_dict() if row else None
        if data:
            await event_bus.publish("task.updated", data)
        return data

    async def delete_task(self, task_id: int) -> bool:
        async with AsyncSessionLocal() as session:
            result = await session.execute(delete(Task).where(Task.id == task_id))
            await session.commit()
            ok = result.rowcount > 0
        if ok:
            await event_bus.publish("task.deleted", {"id": task_id})
        return ok

    async def top_tasks(self, limit: int = 5) -> list[dict]:
        async with AsyncSessionLocal() as session:
            stmt = (
                select(Task)
                .where(Task.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS]))
                .order_by(Task.priority.desc(), Task.due_date.asc().nulls_last())
                .limit(limit)
            )
            rows = (await session.execute(stmt)).scalars().all()
            return [r.to_dict() for r in rows]

    async def overdue_tasks(self) -> list[dict]:
        now = datetime.now(timezone.utc)
        async with AsyncSessionLocal() as session:
            stmt = select(Task).where(
                Task.due_date.is_not(None),
                Task.due_date < now,
                Task.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS]),
            )
            rows = (await session.execute(stmt)).scalars().all()
            return [r.to_dict() for r in rows]


task_agent = TaskAgent()
