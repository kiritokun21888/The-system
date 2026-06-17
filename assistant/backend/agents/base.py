"""Base class for all agents.

Provides a uniform status surface (name, status, last/next action) that the
dashboard's agent panel renders, plus a helper to broadcast status changes.
"""

from __future__ import annotations

import time
from typing import Any, Optional

from ..events import bus


class Agent:
    """Common state + lifecycle for an agent."""

    name: str = "agent"

    def __init__(self) -> None:
        self.status: str = "idle"
        self.last_action: str = ""
        self.next_action: str = ""
        self.last_ts: float = 0.0
        self.enabled: bool = True
        self.log: list[dict[str, Any]] = []

    def set_status(self, status: str, last_action: Optional[str] = None,
                   next_action: Optional[str] = None) -> None:
        """Update status fields and append to the agent's own log."""
        self.status = status
        if last_action is not None:
            self.last_action = last_action
            self.last_ts = time.time()
            self.log.insert(0, {"ts": time.strftime("%H:%M:%S"), "msg": last_action})
            self.log = self.log[:50]
        if next_action is not None:
            self.next_action = next_action

    def snapshot(self) -> dict[str, Any]:
        """Serialize the agent's status for the UI."""
        return {
            "name": self.name,
            "status": self.status,
            "last_action": self.last_action,
            "next_action": self.next_action,
            "last_ts": self.last_ts,
            "enabled": self.enabled,
            "log": self.log[:20],
        }

    async def emit(self) -> None:
        """Broadcast this agent's current status to the UI."""
        await bus.broadcast("agent_status", self.snapshot())

    async def start(self) -> None:
        """Override in autonomous agents to run their background loop."""
        return None
