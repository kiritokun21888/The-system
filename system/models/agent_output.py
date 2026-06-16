"""Standardized output schema shared by every agent.

Every agent's ``process`` returns an :class:`AgentOutput`. The orchestrator
routes purely on the typed fields here — it never inspects agent internals.
"""

from __future__ import annotations

import enum
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Optional


class OutputStatus(str, enum.Enum):
    """Terminal status of a single agent invocation."""

    SUCCESS = "success"          # Agent produced a valid payload.
    FAILURE = "failure"          # Agent ran but failed (see failure_category).
    SKIPPED = "skipped"          # Agent was skipped (early termination).


class FailureCategory(str, enum.Enum):
    """The five failure categories handled by the failure layer.

    The orchestrator maps each category to a recovery action:
      TRANSIENT -> exponential backoff retry
      DATA      -> route to data repair / spec reparse
      LOGIC     -> route to refinement agent (coder) with context
      CRITICAL  -> freeze state, alert human, preserve bundle
      TIMEOUT   -> checkpoint state, resume/restart from checkpoint
    """

    NONE = "none"
    TRANSIENT = "transient"
    DATA = "data"
    LOGIC = "logic"
    CRITICAL = "critical"
    TIMEOUT = "timeout"


@dataclass
class AgentOutput:
    """The single, standardized return type for all agents.

    Attributes:
        agent_name: Registered name of the producing agent.
        task_id: The task this output belongs to.
        status: SUCCESS / FAILURE / SKIPPED.
        quality_score: A 0.0..1.0 quality signal the router thresholds against.
        payload: Arbitrary structured result (spec dict, code string, report...).
        failure_category: Set when status == FAILURE; drives recovery routing.
        failure_reason: Human/agent-readable explanation of the failure, fed
            back into refinement agents as context.
        latency_seconds: Wall-clock time the agent took.
        cost_usd: Estimated LLM cost for this invocation (0 for non-LLM agents).
        tokens_in / tokens_out: Token accounting for cost optimization.
        cache_hit: True if this output was served from cache.
        metadata: Free-form extra data (model used, instance id, etc.).
        output_id: Unique id for this output instance.
        created_at: Epoch seconds at creation.
    """

    agent_name: str
    task_id: str
    status: OutputStatus = OutputStatus.SUCCESS
    quality_score: float = 0.0
    payload: dict[str, Any] = field(default_factory=dict)
    failure_category: FailureCategory = FailureCategory.NONE
    failure_reason: str = ""
    latency_seconds: float = 0.0
    cost_usd: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    cache_hit: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    output_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    created_at: float = field(default_factory=time.time)

    # ------------------------------------------------------------------ #
    # Convenience constructors / predicates
    # ------------------------------------------------------------------ #
    @classmethod
    def success(
        cls,
        agent_name: str,
        task_id: str,
        payload: dict[str, Any],
        quality_score: float = 1.0,
        **kwargs: Any,
    ) -> "AgentOutput":
        """Build a SUCCESS output."""
        return cls(
            agent_name=agent_name,
            task_id=task_id,
            status=OutputStatus.SUCCESS,
            quality_score=quality_score,
            payload=payload,
            **kwargs,
        )

    @classmethod
    def failure(
        cls,
        agent_name: str,
        task_id: str,
        category: FailureCategory,
        reason: str,
        payload: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> "AgentOutput":
        """Build a FAILURE output with a category and reason."""
        return cls(
            agent_name=agent_name,
            task_id=task_id,
            status=OutputStatus.FAILURE,
            quality_score=0.0,
            payload=payload or {},
            failure_category=category,
            failure_reason=reason,
            **kwargs,
        )

    @classmethod
    def skipped(cls, agent_name: str, task_id: str, reason: str) -> "AgentOutput":
        """Build a SKIPPED output (early termination)."""
        return cls(
            agent_name=agent_name,
            task_id=task_id,
            status=OutputStatus.SKIPPED,
            quality_score=1.0,
            failure_reason=reason,
        )

    @property
    def is_success(self) -> bool:
        """True if the agent succeeded."""
        return self.status == OutputStatus.SUCCESS

    @property
    def is_failure(self) -> bool:
        """True if the agent failed."""
        return self.status == OutputStatus.FAILURE

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-friendly dict (enums become their values)."""
        d = asdict(self)
        d["status"] = self.status.value
        d["failure_category"] = self.failure_category.value
        return d
