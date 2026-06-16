"""Task data model and the per-task state container.

A :class:`Task` is the immutable-ish request (what to build). A
:class:`TaskState` is the mutable, serializable record of where the task is in
the pipeline, every output produced so far, retry counters, and loop counters.
All mutable state lives here so agents can remain stateless (horizontal
scaling): any worker can resume any task from its persisted ``TaskState``.
"""

from __future__ import annotations

import enum
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Optional


class TaskStatus(str, enum.Enum):
    """Lifecycle status of a whole task."""

    QUEUED = "queued"
    RUNNING = "running"
    AWAITING_RETRY = "awaiting_retry"
    ESCALATED = "escalated"          # handed to human review
    COMPLETED = "completed"
    ABORTED = "aborted"
    FROZEN = "frozen"                # critical failure; state preserved
    CHECKPOINTED = "checkpointed"    # timeout; resumable from checkpoint


@dataclass
class Spec:
    """Structured specification produced by the SpecParser agent.

    This is the contract the Coder and TestWriter build against.
    """

    function_name: str
    signature: str
    description: str
    requirements: list[str] = field(default_factory=list)
    examples: list[dict[str, Any]] = field(default_factory=list)
    # Catalog key used by the deterministic backend / for early-termination
    # heuristics. Empty for free-form tasks.
    task_key: str = ""
    trivial: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Spec":
        """Deserialize from dict, ignoring unknown keys."""
        allowed = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in d.items() if k in allowed})


@dataclass
class Task:
    """A code-generation request.

    Attributes:
        prompt: Natural-language description of the code to produce.
        language: Target language (only "python" is executed by TestRunner).
        priority: 1 (highest) .. 5 (lowest). Drives the priority queue.
        task_id: Unique id.
        created_at: Epoch seconds.
        metadata: Free-form caller metadata.
    """

    prompt: str
    language: str = "python"
    priority: int = 3
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    created_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Task":
        """Deserialize from dict, ignoring unknown keys."""
        allowed = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in d.items() if k in allowed})


@dataclass
class TaskState:
    """Mutable, serializable state for a task in flight.

    Everything the orchestrator needs to resume a task lives here, so it can be
    checkpointed to the state store and picked up by any worker.

    Attributes:
        task: The originating request.
        status: Whole-task lifecycle status.
        current_stage: Name of the agent stage about to run / running.
        artifacts: Accumulated payloads keyed by artifact name
            (e.g. "spec", "code", "tests", "test_report", "review").
        outputs: Ordered history of every AgentOutput (audit trail), as dicts.
        retry_counts: Per-agent retry counters.
        loop_counts: Per-feedback-loop iteration counters.
        routing_log: Ordered list of routing decisions (timestamp + reason).
        failure_reason: Last failure reason, fed to refinement agents.
        escalation_context: Full context bundle assembled on escalation.
        started_at / updated_at: Timing for the timeout category.
    """

    task: Task
    status: TaskStatus = TaskStatus.QUEUED
    current_stage: str = ""
    artifacts: dict[str, Any] = field(default_factory=dict)
    outputs: list[dict[str, Any]] = field(default_factory=list)
    retry_counts: dict[str, int] = field(default_factory=dict)
    loop_counts: dict[str, int] = field(default_factory=dict)
    routing_log: list[dict[str, Any]] = field(default_factory=list)
    failure_reason: str = ""
    escalation_context: dict[str, Any] = field(default_factory=dict)
    started_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    # ------------------------------------------------------------------ #
    # Mutators (all bump updated_at)
    # ------------------------------------------------------------------ #
    def touch(self) -> None:
        """Update the last-modified timestamp."""
        self.updated_at = time.time()

    def record_output(self, output_dict: dict[str, Any]) -> None:
        """Append an output to the audit trail."""
        self.outputs.append(output_dict)
        self.touch()

    def record_routing(self, decision: str, reason: str, extra: Optional[dict] = None) -> None:
        """Append a routing decision to the audit log with a timestamp."""
        entry = {
            "timestamp": time.time(),
            "stage": self.current_stage,
            "decision": decision,
            "reason": reason,
        }
        if extra:
            entry.update(extra)
        self.routing_log.append(entry)
        self.touch()

    def retry_count(self, agent_name: str) -> int:
        """Current retry count for an agent."""
        return self.retry_counts.get(agent_name, 0)

    def incr_retry(self, agent_name: str) -> int:
        """Increment and return the retry count for an agent."""
        self.retry_counts[agent_name] = self.retry_counts.get(agent_name, 0) + 1
        self.touch()
        return self.retry_counts[agent_name]

    def reset_retry(self, agent_name: str) -> None:
        """Reset an agent's retry counter (after a successful advance)."""
        self.retry_counts[agent_name] = 0
        self.touch()

    def loop_count(self, loop_name: str) -> int:
        """Current iteration count for a feedback loop."""
        return self.loop_counts.get(loop_name, 0)

    def incr_loop(self, loop_name: str) -> int:
        """Increment and return the iteration count for a feedback loop."""
        self.loop_counts[loop_name] = self.loop_counts.get(loop_name, 0) + 1
        self.touch()
        return self.loop_counts[loop_name]

    def elapsed_seconds(self) -> float:
        """Wall-clock seconds since the task started."""
        return time.time() - self.started_at

    # ------------------------------------------------------------------ #
    # Serialization
    # ------------------------------------------------------------------ #
    def to_dict(self) -> dict[str, Any]:
        """Serialize the whole state to a JSON-friendly dict."""
        d = asdict(self)
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "TaskState":
        """Reconstruct a TaskState from its serialized dict."""
        task = Task.from_dict(d["task"])
        state = cls(task=task)
        state.status = TaskStatus(d.get("status", "queued"))
        state.current_stage = d.get("current_stage", "")
        state.artifacts = d.get("artifacts", {})
        state.outputs = d.get("outputs", [])
        state.retry_counts = d.get("retry_counts", {})
        state.loop_counts = d.get("loop_counts", {})
        state.routing_log = d.get("routing_log", [])
        state.failure_reason = d.get("failure_reason", "")
        state.escalation_context = d.get("escalation_context", {})
        state.started_at = d.get("started_at", time.time())
        state.updated_at = d.get("updated_at", time.time())
        return state
