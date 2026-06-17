"""Pluggable LLM client.

Two backends implement the same async interface:

  - :class:`DeterministicLLMClient` — fully offline, reproducible. Drives the
    whole pipeline (and the test suite) with no API key by serving from the task
    catalog. It also models the test-fix loop by returning a buggy first attempt
    for catalog entries flagged ``buggy_first``.

  - :class:`AnthropicLLMClient` — calls the real Claude API. Uses
    ``claude-opus-4-8`` (generation) and ``claude-haiku-4-5`` (validation) with
    adaptive thinking, per config. Prompts are cached for token/cost savings.

Both return a typed :class:`LLMResponse` with token + cost accounting so the
optimization layer can log cost per task and per agent.
"""

from __future__ import annotations

import abc
import asyncio
import json
import os
import random
from dataclasses import dataclass, field
from typing import Any, Optional

from core.cache import TTLCache
from core.catalog import CATALOG, detect_task_key

# Public per-MTok pricing (USD), used to estimate cost for logging.
_PRICING = {
    "claude-opus-4-8": {"in": 5.0, "out": 25.0},
    "claude-haiku-4-5": {"in": 1.0, "out": 5.0},
}


@dataclass
class LLMRequest:
    """A single LLM request.

    Attributes:
        stage: Logical pipeline stage ("spec" | "code" | "tests" | "review").
        model: Concrete model id to use.
        system: System prompt.
        prompt: User prompt (rendered text; used by the real backend).
        context: Structured inputs (used by the deterministic backend so it does
            not have to parse free text — e.g. {"task_key", "code", "spec"}).
        attempt: 0-based attempt number (drives buggy-first behaviour).
        max_tokens: Output cap.
    """

    stage: str
    model: str
    system: str
    prompt: str
    context: dict[str, Any] = field(default_factory=dict)
    attempt: int = 0
    max_tokens: int = 8000


@dataclass
class LLMResponse:
    """A single LLM response with accounting."""

    text: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0


def _estimate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    """Estimate USD cost from token counts and the pricing table."""
    price = _PRICING.get(model, {"in": 0.0, "out": 0.0})
    return (tokens_in / 1_000_000) * price["in"] + (tokens_out / 1_000_000) * price["out"]


class LLMClient(abc.ABC):
    """Abstract async LLM client interface."""

    @abc.abstractmethod
    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Run a completion and return a typed response."""
        raise NotImplementedError


class TransientLLMError(Exception):
    """Raised for retryable LLM faults (timeouts, rate limits, 5xx)."""


# --------------------------------------------------------------------------- #
# Deterministic (offline) backend
# --------------------------------------------------------------------------- #
class DeterministicLLMClient(LLMClient):
    """Offline backend that serves the pipeline from the task catalog.

    Reproducible and dependency-free. Optionally injects a small simulated
    latency and a configurable transient-failure rate so the failure-handling
    paths can be exercised without a network.
    """

    def __init__(
        self,
        latency: float = 0.0,
        transient_rate: float = 0.0,
        seed: Optional[int] = None,
    ) -> None:
        """Create the deterministic client.

        Args:
            latency: Artificial per-call latency in seconds.
            transient_rate: Probability [0..1] of raising a transient error.
            seed: RNG seed for reproducible transient injection.
        """
        self._latency = latency
        self._transient_rate = transient_rate
        self._rng = random.Random(seed)

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Serve a completion from the catalog based on stage/context.

        Raises:
            TransientLLMError: Randomly, per ``transient_rate`` (retryable).
        """
        if self._latency:
            await asyncio.sleep(self._latency)
        if self._transient_rate and self._rng.random() < self._transient_rate:
            raise TransientLLMError("simulated transient LLM fault")

        text = self._dispatch(request)
        tokens_in = max(1, len(request.prompt) // 4)
        tokens_out = max(1, len(text) // 4)
        return LLMResponse(
            text=text,
            model=request.model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=0.0,  # offline backend is free
        )

    def _dispatch(self, request: LLMRequest) -> str:
        """Route to the right catalog response for the stage."""
        if request.stage == "spec":
            return self._spec(request)
        if request.stage == "code":
            return self._code(request)
        if request.stage == "tests":
            return self._tests(request)
        if request.stage == "review":
            return self._review(request)
        return json.dumps({"error": f"unknown stage {request.stage}"})

    def _spec(self, request: LLMRequest) -> str:
        """Produce a spec JSON for the prompt (catalog or a generic fallback)."""
        prompt = request.context.get("prompt", request.prompt)
        key = detect_task_key(prompt)
        if key:
            return json.dumps(CATALOG[key]["spec"])
        # Generic fallback spec for unknown tasks. Downstream code generation
        # will fail its tests and the task will escalate — demonstrating the
        # escalation path.
        return json.dumps(
            {
                "function_name": "solution",
                "signature": "def solution(*args, **kwargs)",
                "description": prompt.strip()[:200],
                "requirements": ["Implement the described behaviour"],
                "examples": [],
                "task_key": "",
                "trivial": False,
            }
        )

    def _code(self, request: LLMRequest) -> str:
        """Produce code JSON; buggy-first for catalog entries so flagged."""
        key = request.context.get("task_key", "")
        if key and key in CATALOG:
            entry = CATALOG[key]
            if entry.get("buggy_first") and request.attempt == 0 and entry["buggy_code"]:
                code = entry["buggy_code"]
            else:
                code = entry["code"]
            return json.dumps({"code": code, "language": "python"})
        # Unknown task: emit a stub that will not satisfy any meaningful test.
        return json.dumps(
            {
                "code": "def solution(*args, **kwargs):\n"
                '    """Auto-generated stub."""\n'
                "    raise NotImplementedError\n",
                "language": "python",
            }
        )

    def _tests(self, request: LLMRequest) -> str:
        """Produce a test module JSON for the task."""
        key = request.context.get("task_key", "")
        if key and key in CATALOG:
            return json.dumps({"test_code": CATALOG[key]["tests"]})
        # Unknown task: a single smoke test that imports the symbol.
        fn = request.context.get("function_name", "solution")
        return json.dumps(
            {
                "test_code": f"from solution import {fn}\n\n"
                f"def test_exists():\n    assert callable({fn})\n"
            }
        )

    def _review(self, request: LLMRequest) -> str:
        """Compute a heuristic review score from the code text.

        Score components (deterministic, explainable):
          base 0.5
          +0.2 if a docstring is present
          +0.15 if the implementation is non-trivial (not a bare stub)
          +0.15 if tests already passed (signalled via context)
        """
        code = request.context.get("code", "")
        tests_passed = bool(request.context.get("tests_passed", False))
        issues: list[str] = []

        # A stub implementation is decisively rejected regardless of a trivial
        # passing smoke test — this is what drives unknown tasks to escalate.
        if "NotImplementedError" in code or code.strip().endswith("pass"):
            return json.dumps(
                {
                    "quality_score": 0.4,
                    "issues": ["implementation appears to be a stub"],
                    "approved": False,
                }
            )

        score = 0.6
        if '"""' in code or "'''" in code:
            score += 0.2
        else:
            issues.append("missing docstring")
        if tests_passed:
            score += 0.2
        else:
            issues.append("tests not passing at review time")
        score = min(1.0, round(score, 3))
        return json.dumps(
            {"quality_score": score, "issues": issues, "approved": score >= 0.75}
        )


# --------------------------------------------------------------------------- #
# Real Anthropic backend
# --------------------------------------------------------------------------- #
class AnthropicLLMClient(LLMClient):
    """Calls the real Claude API via the ``anthropic`` SDK.

    Uses adaptive thinking and structured-JSON system instructions. Caches
    identical prompts (token/cost optimization). Maps SDK timeouts / rate-limits
    / overloads to :class:`TransientLLMError` so the failure layer can back off.
    """

    def __init__(
        self,
        cache: Optional[TTLCache] = None,
        cache_ttl: float = 600.0,
        thinking: str = "adaptive",
        request_timeout: float = 60.0,
    ) -> None:
        """Create the Anthropic-backed client.

        Args:
            cache: Optional shared prompt cache.
            cache_ttl: TTL for cached prompt responses.
            thinking: Thinking mode ("adaptive" recommended for 4.x).
            request_timeout: Per-request timeout (seconds).

        Raises:
            RuntimeError: If the ``anthropic`` package is not installed.
        """
        try:
            import anthropic  # noqa: F401
        except ImportError as exc:  # pragma: no cover - exercised only with backend
            raise RuntimeError(
                "anthropic package not installed; `pip install anthropic` or use "
                "the deterministic backend"
            ) from exc
        from anthropic import AsyncAnthropic

        self._client = AsyncAnthropic()
        self._cache = cache
        self._cache_ttl = cache_ttl
        self._thinking = thinking
        self._timeout = request_timeout

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Call Claude and return a typed response.

        Raises:
            TransientLLMError: On retryable API faults.
        """
        import anthropic

        # Prompt cache: identical (model, system, prompt) returns cached text.
        cache_key = None
        if self._cache is not None:
            cache_key = TTLCache.make_key(
                "llm", [request.model, request.system, request.prompt]
            )
            cached = self._cache.get(cache_key)
            if cached is not None:
                return LLMResponse(text=cached, model=request.model, cost_usd=0.0)

        # Instruct the model to return strict JSON (we parse it in the agents).
        system = (
            request.system
            + "\n\nRespond with a single JSON object and nothing else."
        )
        try:
            msg = await self._client.messages.create(
                model=request.model,
                max_tokens=request.max_tokens,
                thinking={"type": self._thinking},
                system=system,
                messages=[{"role": "user", "content": request.prompt}],
                timeout=self._timeout,
            )
        except (
            anthropic.RateLimitError,
            anthropic.APITimeoutError,
            anthropic.InternalServerError,
            anthropic.APIConnectionError,
        ) as exc:
            raise TransientLLMError(str(exc)) from exc

        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        tokens_in = msg.usage.input_tokens
        tokens_out = msg.usage.output_tokens
        cost = _estimate_cost(request.model, tokens_in, tokens_out)

        if self._cache is not None and cache_key is not None:
            self._cache.set(cache_key, text, self._cache_ttl)

        return LLMResponse(
            text=text,
            model=request.model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost,
        )


def build_llm_client(config: Any, cache: Optional[TTLCache] = None) -> LLMClient:
    """Factory that builds the configured LLM backend.

    Args:
        config: The :class:`~core.config.Config`.
        cache: Shared prompt cache (used by the Anthropic backend).

    Returns:
        An :class:`LLMClient` instance.
    """
    backend = config.get("llm.backend", "deterministic")
    if backend == "anthropic" and os.environ.get("ANTHROPIC_API_KEY"):
        return AnthropicLLMClient(
            cache=cache,
            cache_ttl=config.get("llm.prompt_cache_ttl_seconds", 600),
            thinking=config.get("llm.thinking", "adaptive"),
            request_timeout=config.get("llm.request_timeout_seconds", 60),
        )
    # Default / fallback: deterministic offline backend.
    return DeterministicLLMClient(
        latency=config.get("llm.simulated_latency_seconds", 0.0)
    )
