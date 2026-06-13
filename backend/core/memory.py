"""Persistent memory subsystem for ZERO.

Stores durable facts/preferences and a rolling conversation log in SQLite,
and uses Claude to distil key facts out of recent conversation so ZERO can
recall them in future sessions.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import delete, desc, or_, select, update

from core.database import AsyncSessionLocal
from models.context import ContextMemory, ConversationTurn, MemoryType

logger = logging.getLogger("zero.memory")


class MemoryStore:
    """CRUD + retrieval helpers over the memory and conversation tables."""

    async def add_memory(
        self,
        content: str,
        mem_type: MemoryType | str = MemoryType.FACT,
        source: str = "conversation",
        tags: list[str] | None = None,
        importance: float = 0.5,
    ) -> dict:
        if isinstance(mem_type, str):
            mem_type = MemoryType(mem_type)
        async with AsyncSessionLocal() as session:
            mem = ContextMemory(
                content=content.strip(),
                type=mem_type,
                source=source,
                tags=tags or [],
                importance_score=max(0.0, min(1.0, importance)),
            )
            session.add(mem)
            await session.commit()
            await session.refresh(mem)
            return mem.to_dict()

    async def list_memories(self, limit: int = 100, mem_type: str | None = None) -> list[dict]:
        async with AsyncSessionLocal() as session:
            stmt = select(ContextMemory).order_by(
                desc(ContextMemory.importance_score), desc(ContextMemory.timestamp)
            )
            if mem_type:
                stmt = stmt.where(ContextMemory.type == MemoryType(mem_type))
            stmt = stmt.limit(limit)
            rows = (await session.execute(stmt)).scalars().all()
            return [r.to_dict() for r in rows]

    async def search_memories(self, query: str, limit: int = 10) -> list[dict]:
        like = f"%{query.lower()}%"
        async with AsyncSessionLocal() as session:
            stmt = (
                select(ContextMemory)
                .where(or_(ContextMemory.content.ilike(like)))
                .order_by(desc(ContextMemory.importance_score))
                .limit(limit)
            )
            rows = (await session.execute(stmt)).scalars().all()
            return [r.to_dict() for r in rows]

    async def update_memory(self, memory_id: int, **fields) -> dict | None:
        allowed = {"content", "tags", "importance_score", "type"}
        clean = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if "type" in clean and isinstance(clean["type"], str):
            clean["type"] = MemoryType(clean["type"])
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(ContextMemory).where(ContextMemory.id == memory_id).values(**clean)
            )
            await session.commit()
            row = (
                await session.execute(
                    select(ContextMemory).where(ContextMemory.id == memory_id)
                )
            ).scalar_one_or_none()
            return row.to_dict() if row else None

    async def delete_memory(self, memory_id: int) -> bool:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                delete(ContextMemory).where(ContextMemory.id == memory_id)
            )
            await session.commit()
            return result.rowcount > 0

    # --- Conversation log ---

    async def log_turn(self, role: str, content: str) -> None:
        async with AsyncSessionLocal() as session:
            session.add(ConversationTurn(role=role, content=content))
            await session.commit()

    async def recent_turns(self, limit: int = 20) -> list[dict]:
        async with AsyncSessionLocal() as session:
            stmt = (
                select(ConversationTurn)
                .order_by(desc(ConversationTurn.timestamp))
                .limit(limit)
            )
            rows = (await session.execute(stmt)).scalars().all()
            return [r.to_dict() for r in reversed(rows)]

    async def turns_since(self, since: datetime) -> list[dict]:
        async with AsyncSessionLocal() as session:
            stmt = (
                select(ConversationTurn)
                .where(ConversationTurn.timestamp >= since)
                .order_by(ConversationTurn.timestamp)
            )
            rows = (await session.execute(stmt)).scalars().all()
            return [r.to_dict() for r in rows]

    # --- System-prompt context ---

    async def build_context_block(self, limit: int = 25) -> str:
        """Render the most important memories into a system-prompt fragment."""
        memories = await self.list_memories(limit=limit)
        if not memories:
            return "No long-term memories about the user yet."
        lines = []
        for m in memories:
            tag = f" [{', '.join(m['tags'])}]" if m["tags"] else ""
            lines.append(f"- ({m['type']}) {m['content']}{tag}")
        return "\n".join(lines)

    async def extract_and_store(self, brain, conversation_text: str) -> list[dict]:
        """Use Claude to pull durable facts out of a conversation snippet."""
        if not brain or not brain.enabled:
            return []
        prompt = (
            "Extract durable, long-term facts or preferences about the user from "
            "the following conversation. Ignore transient chit-chat. Respond with "
            "a JSON array of objects with keys: content, type (one of fact, "
            "preference, task_context), importance (0-1). If nothing is worth "
            "remembering, return [].\n\nConversation:\n" + conversation_text
        )
        try:
            raw = await brain.complete_text(prompt, max_tokens=600)
            raw = raw.strip()
            start, end = raw.find("["), raw.rfind("]")
            if start == -1 or end == -1:
                return []
            items = json.loads(raw[start : end + 1])
        except Exception as exc:  # noqa: BLE001
            logger.warning("Memory extraction failed: %s", exc)
            return []

        stored = []
        for item in items:
            if not isinstance(item, dict) or not item.get("content"):
                continue
            stored.append(
                await self.add_memory(
                    content=item["content"],
                    mem_type=item.get("type", "fact"),
                    source="auto-extracted",
                    importance=float(item.get("importance", 0.5)),
                )
            )
        return stored


memory_store = MemoryStore()
