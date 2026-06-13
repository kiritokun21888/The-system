"""SQLAlchemy Task model and task-related enums."""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Enum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    DELEGATED_TO_AGENT = "delegated_to_agent"


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    priority: Mapped[int] = mapped_column(Integer, default=3)  # 1 (low) .. 5 (urgent)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus), default=TaskStatus.PENDING, index=True
    )
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
    tags: Mapped[list] = mapped_column(JSON, default=list)
    subtasks: Mapped[list] = mapped_column(JSON, default=list)  # [{title, done}]
    agent_assigned: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "priority": self.priority,
            "status": self.status.value if isinstance(self.status, TaskStatus) else self.status,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "tags": self.tags or [],
            "subtasks": self.subtasks or [],
            "agent_assigned": self.agent_assigned,
            "notes": self.notes or "",
        }
