"""Abstract base class every agent inherits from.

The base class gives all agents a uniform, production-grade ``process`` wrapper
that handles: caching (identical inputs -> cached output), per-agent timeout,
transient-fault backoff, metrics emission, cost accounting, and turning any
raised exception into a classified :class:`AgentOutput` failure (no silent
failures). Concrete agents implement only ``_run`` and ``cache_input``.

Standard interface (per spec): ``async def process(self, task, state) -> AgentOutput``.
``state`` is included alongside ``task`` because feedback-loop agents must read
accumulated artifacts (spec, prior code, failure context) to refine output.
"""

from __future__ import annotations

import abc
import asyncio
import time
from typing import Any, Optional

from core.cache import TTLCache
from core.config import Config
from core.failure_handler import FailureHandler
from core.llm_client import LLMClient, LLMRequest, LLMResponse
from core.metrics import MetricsRegistry
from models.agent_output import AgentOutput, FailureCategory, OutputStatus
from models.task import Task, TaskState


class BaseAgent(abc.ABC):
    """Common lifecycle for all agents."""

    def __init__(
        self,
        name: str,
        config: Config,
        llm: LLMClient,
        cache: TTLCache,
        metrics: MetricsRegistry,
        failure_handler: FailureHandler,
    ) -> None:
        """Wire an agent to shared infrastructure.

        Args:
            name: Registered agent name (matches a key under ``agents:`` in config).
            config: System config.
            llm: Shared LLM client.
            cache: Shared TTL cache.
            metrics: Shared metrics registry.
            failure_handler: Shared failure handler.
        """
        self.name = name
        self.config = config
        self.llm = llm
        self.cache = cache
        self.metrics = metrics
        self.failure_handler = failure_handler

        agent_cfg = config.agent_config(name)
        self.quality_threshold: float = agent_cfg.get(
            "quality_threshold", config.get("router.default_quality_threshold", 0.75)
        )
        self.max_retries: int = agent_cfg.get(
            "max_retries", config.get("router.max_retries", 3)
        )
        self.timeout_seconds: float = agent_cfg.get("timeout_seconds", 60)
        self.cache_ttl: float = agent_cfg.get("cache_ttl_seconds", 0)
        self.model_role: str = agent_cfg.get("model_role", "none")

    # ------------------------------------------------------------------ #
    # Model selection
    # ------------------------------------------------------------------ #
    def model(self) -> str:
        """Resolve the concrete model id for this agent's role.

        Validation-role agents use the cheaper model; generation-role agents use
        the full model (token/cost optimization).
        """
        if self.model_role == "generation":
            return self.config.get("llm.generation_model", "claude-opus-4-8")
        if self.model_role == "validation":
            return self.config.get("llm.validation_model", "claude-haiku-4-5")
        return "none"

    # ------------------------------------------------------------------ #
    # LLM helper (with transient backoff + accounting)
    # ------------------------------------------------------------------ #
    async def llm_complete(
        self, stage: str, system: str, prompt: str, context: dict[str, Any], attempt: int = 0
    ) -> LLMResponse:
        """Run an LLM completion with transient-fault backoff.

        Args:
            stage: Pipeline stage tag.
            system: System prompt.
            prompt: User prompt.
            context: Structured context for the deterministic backend.
            attempt: 0-based attempt number.

        Returns:
            The :class:`LLMResponse`.
        """
        request = LLMRequest(
            stage=stage,
            model=self.model(),
            system=system,
            prompt=prompt,
            context=context,
            attempt=attempt,
            max_tokens=self.config.get("llm.max_tokens", 8000),
        )
        return await self.failure_handler.retry_transient(
            lambda: self.llm.complete(request),
            context={"agent": self.name, "task_id": context.get("task_id", "")},
        )

    # ------------------------------------------------------------------ #
    # Methods concrete agents override
    # ------------------------------------------------------------------ #
    @abc.abstractmethod
    async def _run(self, task: Task, state: TaskState) -> AgentOutput:
        """Core agent logic. Must return an :class:`AgentOutput`.

        May raise; the ``process`` wrapper classifies and records any exception.
        """
        raise NotImplementedError

    def cache_input(self, task: Task, state: TaskState) -> Optional[Any]:
        """Return a JSON-serializable structure identifying this invocation.

        If it returns ``None``, the invocation is not cached. Agents whose output
        depends on the loop iteration (e.g. the Coder, which must change on
        retry) include the attempt counter so refinements are never short-
        circuited by the cache.
        """
        return None

    # ------------------------------------------------------------------ #
    # The uniform wrapper
    # ------------------------------------------------------------------ #
    async def process(self, task: Task, state: TaskState) -> AgentOutput:
        """Run the agent with caching, timeout, metrics, and failure capture.

        Args:
            task: The originating request.
            state: The mutable task state (accumulated artifacts, counters).

        Returns:
            An :class:`AgentOutput` — SUCCESS, FAILURE (classified), or a cached
            success. Never raises.
        """
        start = time.time()

        # 1. Cache lookup.
        key: Optional[str] = None
        cache_payload = self.cache_input(task, state)
        if self.cache_ttl > 0 and cache_payload is not None:
            key = TTLCache.make_key(self.name, cache_payload)
            cached = self.cache.get(key)
            if cached is not None:
                out = AgentOutput(**{**cached, "cache_hit": True})
                # Re-hydrate enums (dataclass stored their values).
                out.status = OutputStatus(cached["status"])
                out.failure_category = FailureCategory(cached["failure_category"])
                self.metrics.record_invocation(
                    self.name, latency=0.0, success=out.is_success, cache_hit=True
                )
                return out

        # 2. Run with a hard per-agent timeout.
        try:
            output = await asyncio.wait_for(
                self._run(task, state), timeout=self.timeout_seconds
            )
        except Exception as exc:  # noqa: BLE001 - converted to a classified output
            category = self.failure_handler.classify(exc)
            self.failure_handler.log_failure(
                agent_name=self.name,
                category=category,
                error=repr(exc),
                task_id=task.task_id,
                input_summary=cache_payload,
            )
            output = AgentOutput.failure(
                agent_name=self.name,
                task_id=task.task_id,
                category=category,
                reason=repr(exc),
            )

        # 3. Stamp latency + metrics.
        output.latency_seconds = time.time() - start
        self.metrics.record_invocation(
            self.name,
            latency=output.latency_seconds,
            success=output.is_success,
            cost=output.cost_usd,
            tokens_in=output.tokens_in,
            tokens_out=output.tokens_out,
            cache_hit=False,
        )

        # 4. Store successful outputs in cache.
        if key is not None and output.is_success:
            self.cache.set(key, output.to_dict(), self.cache_ttl)

        return output
