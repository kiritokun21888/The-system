"""Round-robin load balancer for bottleneck agents.

Agents marked as bottlenecks in config (``optimization.load_balancing``) are
instantiated multiple times; the dispatcher hands each request to the next
instance in round-robin order. The interface mirrors a single agent
(``process``) so the orchestrator is agnostic to whether an agent is balanced.
"""

from __future__ import annotations

import itertools
import threading
from typing import TYPE_CHECKING

from models.agent_output import AgentOutput
from models.task import Task, TaskState

if TYPE_CHECKING:  # avoid import cycle at runtime
    from agents.base_agent import BaseAgent


class RoundRobinDispatcher:
    """Dispatches ``process`` calls across a pool of identical agent instances."""

    def __init__(self, instances: list["BaseAgent"]) -> None:
        """Create a dispatcher over one or more agent instances.

        Args:
            instances: The agent instance pool (length >= 1).
        """
        if not instances:
            raise ValueError("RoundRobinDispatcher requires at least one instance")
        self._instances = instances
        self._cycle = itertools.cycle(range(len(instances)))
        self._lock = threading.Lock()
        # Expose the canonical name/config from the first instance.
        self.name = instances[0].name

    def _next(self) -> "BaseAgent":
        """Return the next instance in round-robin order (thread-safe)."""
        with self._lock:
            idx = next(self._cycle)
        return self._instances[idx]

    async def process(self, task: Task, state: TaskState) -> AgentOutput:
        """Dispatch a task to the next instance and tag the chosen instance id."""
        instance = self._next()
        output = await instance.process(task, state)
        output.metadata.setdefault("instance_id", id(instance) % 10000)
        return output

    @property
    def pool_size(self) -> int:
        """Number of instances in the pool."""
        return len(self._instances)
