"""WebSocket event bus.

A single broadcaster every agent uses to push real-time events to the UI:
``agent_status``, ``notification``, ``stats``, ``task_update``, ``transcript``,
``response``, ``clipboard_update``, etc. Thread-safe scheduling is provided so
agents running in worker threads (voice) can broadcast onto the event loop.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Optional


class EventBus:
    """Tracks WebSocket clients and broadcasts JSON events to all of them."""

    def __init__(self) -> None:
        self._clients: set[Any] = set()
        self._lock = asyncio.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._recent: list[dict[str, Any]] = []  # last notifications for new clients

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Capture the running loop (so threads can schedule broadcasts)."""
        self._loop = loop

    async def connect(self, ws: Any) -> None:
        """Register a client and replay recent notifications."""
        await ws.accept()
        async with self._lock:
            self._clients.add(ws)
        for note in self._recent[-10:]:
            try:
                await ws.send_text(json.dumps(note))
            except Exception:
                break

    async def disconnect(self, ws: Any) -> None:
        """Remove a client."""
        async with self._lock:
            self._clients.discard(ws)

    async def broadcast(self, event_type: str, data: Any) -> None:
        """Send an event to all connected clients."""
        msg = {"type": event_type, "data": data, "ts": time.time()}
        if event_type == "notification":
            self._recent.append(msg)
            self._recent = self._recent[-30:]
        text = json.dumps(msg, default=str)
        async with self._lock:
            dead = []
            for ws in self._clients:
                try:
                    await ws.send_text(text)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self._clients.discard(ws)

    def broadcast_threadsafe(self, event_type: str, data: Any) -> None:
        """Schedule a broadcast from a non-async thread (e.g. the voice thread)."""
        if self._loop is None:
            return
        asyncio.run_coroutine_threadsafe(self.broadcast(event_type, data), self._loop)

    async def notify(self, title: str, body: str = "", level: str = "info",
                     agent: str = "system") -> None:
        """Convenience: emit a UI notification."""
        await self.broadcast("notification", {
            "title": title, "body": body, "level": level, "agent": agent,
        })

    @property
    def count(self) -> int:
        """Number of connected clients."""
        return len(self._clients)


# Global singleton used across the backend.
bus = EventBus()
