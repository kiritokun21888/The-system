"""In-process event bus used to fan out real-time updates to connected clients.

Agents and services publish typed events here; the WebSocket layer subscribes
and forwards everything to the frontend. Decoupling publishers from the
transport keeps agents free of any knowledge about sockets.
"""
from __future__ import annotations

import asyncio
import logging
from collections import deque
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("zero.events")


class EventBus:
    """A simple async pub/sub hub with a bounded replay buffer."""

    def __init__(self, history_size: int = 200) -> None:
        self._subscribers: set[asyncio.Queue] = set()
        self._history: deque[dict] = deque(maxlen=history_size)
        self._lock = asyncio.Lock()

    async def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=256)
        async with self._lock:
            self._subscribers.add(queue)
        return queue

    async def unsubscribe(self, queue: asyncio.Queue) -> None:
        async with self._lock:
            self._subscribers.discard(queue)

    def recent(self, limit: int = 50) -> list[dict]:
        return list(self._history)[-limit:]

    async def publish(self, event_type: str, payload: dict[str, Any] | None = None) -> None:
        event = {
            "type": event_type,
            "payload": payload or {},
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        self._history.append(event)
        async with self._lock:
            subscribers = list(self._subscribers)
        for queue in subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("Dropping event for slow subscriber: %s", event_type)

    def publish_threadsafe(self, loop: asyncio.AbstractEventLoop, event_type: str,
                           payload: dict[str, Any] | None = None) -> None:
        """Publish from a non-async context (e.g. a worker thread)."""
        asyncio.run_coroutine_threadsafe(self.publish(event_type, payload), loop)


# Shared singleton used across the whole backend.
event_bus = EventBus()
