"""Unified failure-handling layer.

Classifies every failure into one of five categories and provides the recovery
primitives the orchestrator routes to:

  TRANSIENT — timeout / rate limit / temporary unavailability.
              Action: exponential backoff retry (configurable schedule).
  DATA      — malformed input, missing fields, type mismatch.
              Action: route to data repair (spec reparse).
  LOGIC     — agent produced output that failed a quality/test check.
              Action: route to refinement agent with failure context.
  CRITICAL  — agent crashed / unrecoverable / data corruption.
              Action: freeze task state, alert human, preserve full context.
  TIMEOUT   — task exceeded maximum allowed duration.
              Action: checkpoint current state, resume/restart from checkpoint.

For every failure the layer logs (agent, type, input, error, timestamp),
preserves the complete task state, notifies via configured channels, attempts
automatic recovery, and escalates with a full context bundle if recovery fails.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Any, Optional

from core.config import Config
from core.llm_client import TransientLLMError
from core.logger import get_logger, log_event
from models.agent_output import FailureCategory


class CriticalAgentError(Exception):
    """Raised for unrecoverable agent failures (crashes, corruption)."""


class DataValidationError(Exception):
    """Raised when an agent receives malformed/insufficient input data."""


class FailureHandler:
    """Classifies failures, runs backoff, alerts, and preserves context."""

    def __init__(self, config: Config) -> None:
        """Create the handler from config.

        Args:
            config: The system configuration.
        """
        self._config = config
        self._logger = get_logger(
            "failure",
            level=config.get("logging.level", "INFO"),
            fmt=config.get("logging.format", "json"),
            file=config.get("logging.file"),
            console=config.get("logging.console", True),
        )
        self._backoff_base = config.get("failure_handling.transient.backoff_base_seconds", 1)
        self._backoff_factor = config.get("failure_handling.transient.backoff_factor", 2)
        self._max_attempts = config.get("failure_handling.transient.max_attempts", 4)
        self._channels = config.get("failure_handling.alerting.channels", ["log"])
        self._webhook = config.get("failure_handling.alerting.webhook_url", "")
        self._email = config.get("failure_handling.alerting.email_to", "")
        self._bundle_dir = config.get(
            "failure_handling.context_bundle_dir", "./failure_bundles"
        )
        os.makedirs(self._bundle_dir, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Classification
    # ------------------------------------------------------------------ #
    @staticmethod
    def classify(exc: BaseException) -> FailureCategory:
        """Map a raised exception to a failure category.

        Args:
            exc: The exception instance.

        Returns:
            The :class:`FailureCategory`.
        """
        if isinstance(exc, TransientLLMError):
            return FailureCategory.TRANSIENT
        if isinstance(exc, asyncio.TimeoutError):
            return FailureCategory.TIMEOUT
        if isinstance(exc, DataValidationError):
            return FailureCategory.DATA
        if isinstance(exc, CriticalAgentError):
            return FailureCategory.CRITICAL
        # Default unknown exceptions to CRITICAL — never fail silently.
        return FailureCategory.CRITICAL

    # ------------------------------------------------------------------ #
    # Backoff
    # ------------------------------------------------------------------ #
    def backoff_delay(self, attempt: int) -> float:
        """Compute the exponential backoff delay for a 0-based attempt.

        Sequence with base=1, factor=2: 1s, 2s, 4s, 8s, ...

        Args:
            attempt: 0-based attempt index.

        Returns:
            Delay in seconds.
        """
        return float(self._backoff_base) * (float(self._backoff_factor) ** attempt)

    async def retry_transient(self, coro_factory: Any, *, context: dict[str, Any]) -> Any:
        """Run an async operation with exponential-backoff retry on transient faults.

        Args:
            coro_factory: A zero-arg callable returning a fresh awaitable each try.
            context: Logging context (agent, task_id, ...).

        Returns:
            The operation result on success.

        Raises:
            The last exception if all attempts are exhausted, or any
            non-transient exception immediately.
        """
        last_exc: Optional[BaseException] = None
        for attempt in range(self._max_attempts):
            try:
                return await coro_factory()
            except Exception as exc:  # noqa: BLE001 - we re-raise below
                if self.classify(exc) != FailureCategory.TRANSIENT:
                    raise
                last_exc = exc
                delay = self.backoff_delay(attempt)
                log_event(
                    self._logger,
                    "warning",
                    "transient failure; backing off",
                    attempt=attempt + 1,
                    max_attempts=self._max_attempts,
                    delay_seconds=delay,
                    error=str(exc),
                    **context,
                )
                await asyncio.sleep(delay)
        # Exhausted: re-raise the last transient as such.
        assert last_exc is not None
        raise last_exc

    # ------------------------------------------------------------------ #
    # Logging / alerting / preservation
    # ------------------------------------------------------------------ #
    def log_failure(
        self,
        agent_name: str,
        category: FailureCategory,
        error: str,
        task_id: str,
        input_summary: Any = None,
    ) -> None:
        """Log a failure with the mandated fields.

        Logs: agent name, failure type, input that caused it, error message,
        timestamp (the logger adds the timestamp).
        """
        log_event(
            self._logger,
            "error",
            "agent failure",
            agent=agent_name,
            category=category.value,
            error=error,
            task_id=task_id,
            input=input_summary,
        )

    def alert(self, subject: str, body: dict[str, Any]) -> None:
        """Dispatch an alert over the configured channels.

        Channels: "log" (always safe), "webhook", "email". Webhook/email are
        best-effort and never raise into the caller.
        """
        if "log" in self._channels:
            log_event(self._logger, "error", "ALERT: " + subject, **body)
        if "webhook" in self._channels and self._webhook:
            self._post_webhook(subject, body)
        if "email" in self._channels and self._email:
            log_event(
                self._logger,
                "info",
                "email alert queued",
                to=self._email,
                subject=subject,
            )

    def _post_webhook(self, subject: str, body: dict[str, Any]) -> None:
        """Best-effort webhook POST (never raises)."""
        try:
            import urllib.request

            payload = json.dumps({"subject": subject, "body": body}, default=str).encode()
            req = urllib.request.Request(
                self._webhook, data=payload, headers={"Content-Type": "application/json"}
            )
            urllib.request.urlopen(req, timeout=5)  # noqa: S310 - configured URL
        except Exception as exc:  # noqa: BLE001
            log_event(self._logger, "warning", "webhook alert failed", error=str(exc))

    def preserve_context(self, task_id: str, bundle: dict[str, Any]) -> str:
        """Write a full context bundle to disk for human review.

        Args:
            task_id: The task id.
            bundle: The complete context (state, outputs, error, trace).

        Returns:
            The path the bundle was written to.
        """
        path = os.path.join(self._bundle_dir, f"{task_id}-{int(time.time())}.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(bundle, fh, indent=2, default=str)
        log_event(self._logger, "info", "context bundle preserved", path=path, task_id=task_id)
        return path
