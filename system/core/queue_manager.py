"""Message-queue / priority-queue implementation.

Agents communicate via queues, not direct calls, so the topology can scale out.
Locally this is built on :class:`asyncio.PriorityQueue`; the interface
(``put`` / ``get`` / ``depth``) is intentionally minimal so it can be swapped
for Redis Queue or RabbitMQ in a distributed deployment.

Tasks carry a priority 1 (highest) .. 5 (lowest). High-priority tasks are
dequeued first, preempting lower-priority work at the queue boundary.
"""

from __future__ import annotations

import asyncio
import itertools
from dataclasses import dataclass, field
from typing import Any


@dataclass(order=True)
class _PrioritizedItem:
    """Wrapper that orders by (priority, sequence) for stable FIFO-within-priority."""

    priority: int
    sequence: int
    item: Any = field(compare=False)


class PriorityQueueManager:
    """An async priority queue for tasks/messages.

    Lower priority number == higher urgency. Ties break by insertion order
    (FIFO), so same-priority tasks are fair.
    """

    def __init__(self, levels: int = 5) -> None:
        """Create the queue.

        Args:
            levels: Number of priority levels (1..levels).
        """
        self._queue: asyncio.PriorityQueue[_PrioritizedItem] = asyncio.PriorityQueue()
        self._counter = itertools.count()
        self._levels = levels

    async def put(self, item: Any, priority: int = 3) -> None:
        """Enqueue ``item`` at ``priority`` (clamped to 1..levels).

        Args:
            item: The payload (typically a task id or message).
            priority: 1 (highest) .. levels (lowest).
        """
        priority = max(1, min(self._levels, priority))
        await self._queue.put(
            _PrioritizedItem(priority=priority, sequence=next(self._counter), item=item)
        )

    async def get(self) -> Any:
        """Dequeue and return the highest-priority item (awaits if empty)."""
        wrapped = await self._queue.get()
        return wrapped.item

    def task_done(self) -> None:
        """Mark the most recently dequeued item as processed."""
        self._queue.task_done()

    async def join(self) -> None:
        """Block until every enqueued item has been marked done."""
        await self._queue.join()

    def depth(self) -> int:
        """Current number of queued items."""
        return self._queue.qsize()

    def empty(self) -> bool:
        """True if the queue is empty."""
        return self._queue.empty()
