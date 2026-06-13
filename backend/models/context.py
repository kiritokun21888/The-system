"""SQLAlchemy models for ZERO's persistent memory and conversation log."""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Enum, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MemoryType(str, enum.Enum):
    FACT = "fact"
    PREFERENCE = "preference"
    TASK_CONTEXT = "task_context"
    CONVERSATION = "conversation"


class ContextMemory(Base):
    """A single durable memory ZERO holds about the user."""

    __tablename__ = "memory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type: Mapped[MemoryType] = mapped_column(
        Enum(MemoryType), default=MemoryType.FACT, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(128), default="conversation")
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )
    tags: Mapped[list] = mapped_column(JSON, default=list)
    importance_score: Mapped[float] = mapped_column(Float, default=0.5)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type.value if isinstance(self.type, MemoryType) else self.type,
            "content": self.content,
            "source": self.source,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "tags": self.tags or [],
            "importance_score": self.importance_score,
        }


class ConversationTurn(Base):
    """An individual message in the rolling conversation history."""

    __tablename__ = "conversation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role: Mapped[str] = mapped_column(String(16))  # user | assistant
    content: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }
