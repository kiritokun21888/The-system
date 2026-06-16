"""Failure-scenario tests.

Covers every failure category and the recovery primitives: classification,
exponential backoff, transient retry/exhaustion, critical freeze, timeout
checkpoint + resume, and context-bundle preservation. Every failure path in the
system is exercised here.
"""

from __future__ import annotations

import asyncio

import pytest

from core.failure_handler import (
    CriticalAgentError,
    DataValidationError,
    FailureHandler,
)
from core.llm_client import (
    DeterministicLLMClient,
    LLMClient,
    LLMRequest,
    LLMResponse,
    TransientLLMError,
)
from models.agent_output import FailureCategory
from models.task import Task, TaskStatus


# --------------------------------------------------------------------------- #
# Classification + backoff
# --------------------------------------------------------------------------- #
def test_classify_maps_every_category(config):
    """Each known exception maps to its category; unknowns -> CRITICAL."""
    assert FailureHandler.classify(TransientLLMError()) == FailureCategory.TRANSIENT
    assert FailureHandler.classify(asyncio.TimeoutError()) == FailureCategory.TIMEOUT
    assert FailureHandler.classify(DataValidationError()) == FailureCategory.DATA
    assert FailureHandler.classify(CriticalAgentError()) == FailureCategory.CRITICAL
    assert FailureHandler.classify(RuntimeError("?")) == FailureCategory.CRITICAL


def test_backoff_is_exponential(config):
    """Backoff delays follow 1, 2, 4, 8 with the default config."""
    fh = FailureHandler(config)
    assert [fh.backoff_delay(i) for i in range(4)] == [1.0, 2.0, 4.0, 8.0]


# --------------------------------------------------------------------------- #
# Transient retry / exhaustion
# --------------------------------------------------------------------------- #
async def test_retry_transient_succeeds_after_failures(make_config):
    """retry_transient retries transient faults and eventually succeeds."""
    # Zero backoff so the test is fast.
    cfg = make_config(
        **{
            "failure_handling.transient.backoff_base_seconds": 0,
            "failure_handling.transient.max_attempts": 5,
        }
    )
    fh = FailureHandler(cfg)
    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise TransientLLMError("temporary")
        return "ok"

    result = await fh.retry_transient(lambda: flaky(), context={"agent": "t"})
    assert result == "ok"
    assert calls["n"] == 3


async def test_retry_transient_reraises_non_transient(config):
    """Non-transient exceptions are raised immediately, not retried."""
    fh = FailureHandler(config)

    async def boom():
        raise DataValidationError("bad data")

    with pytest.raises(DataValidationError):
        await fh.retry_transient(lambda: boom(), context={"agent": "t"})


async def test_transient_exhaustion_becomes_failure_output(make_config, infra):
    """An agent whose LLM always faults returns a TRANSIENT failure output."""
    from agents.spec_parser import SpecParserAgent

    cfg = make_config(
        **{
            "failure_handling.transient.backoff_base_seconds": 0,
            "failure_handling.transient.max_attempts": 2,
        }
    )
    # Client that always raises a transient fault.
    client = DeterministicLLMClient(transient_rate=1.0, seed=1)
    agent = SpecParserAgent(
        "spec_parser", cfg, client, infra["cache"], infra["metrics"], infra["failure"]
    )
    # Reuse the agent's own failure handler with zero backoff.
    agent.failure_handler = FailureHandler(cfg)
    task = Task(prompt="Write an is_prime primality test")
    from models.task import TaskState

    out = await agent.process(task, TaskState(task=task))
    assert out.is_failure
    assert out.failure_category == FailureCategory.TRANSIENT


# --------------------------------------------------------------------------- #
# Critical failure -> freeze
# --------------------------------------------------------------------------- #
class _CriticalLLM(LLMClient):
    """An LLM client that crashes with a critical error."""

    async def complete(self, request: LLMRequest) -> LLMResponse:
        raise CriticalAgentError("unrecoverable")


async def test_critical_failure_freezes_task(make_orchestrator):
    """A critical agent crash freezes the task and preserves a bundle."""
    orch, _ = make_orchestrator(llm_client=_CriticalLLM())
    state = await orch.run_task(Task(prompt="Write an is_prime primality test"))
    assert state.status == TaskStatus.FROZEN
    assert state.escalation_context.get("bundle_path")


# --------------------------------------------------------------------------- #
# Timeout -> checkpoint -> resume
# --------------------------------------------------------------------------- #
async def test_global_timeout_checkpoints(make_orchestrator, make_config):
    """Exceeding the global task timeout checkpoints a resumable state."""
    cfg = make_config(**{"system.task_timeout_seconds": 0})
    orch, state_mgr = make_orchestrator(cfg=cfg)
    state = await orch.run_task(Task(prompt="Write an is_prime primality test"))
    assert state.status == TaskStatus.CHECKPOINTED
    # The state is persisted and shows up as resumable.
    assert state.task.task_id in state_mgr.resumable_ids()


async def test_checkpointed_task_can_resume(make_orchestrator, make_config):
    """A checkpointed task resumes to completion under a normal timeout."""
    # First run with a zero timeout -> checkpoint immediately.
    cfg0 = make_config(**{"system.task_timeout_seconds": 0})
    orch0, state_mgr = make_orchestrator(cfg=cfg0)
    task = Task(prompt="Implement an is_prime primality test")
    s0 = await orch0.run_task(task)
    assert s0.status == TaskStatus.CHECKPOINTED

    # Resume using the SAME state store but a generous timeout. A brand-new
    # orchestrator (fresh agents, fresh LLM client) picks up the persisted state
    # and completes — demonstrating stateless workers + resumable state.
    cfg1 = make_config(**{"system.task_timeout_seconds": 120})
    from agents.orchestrator import AgentRegistry, Orchestrator
    from core.cache import TTLCache
    from core.metrics import MetricsRegistry

    failure = orch0.failure
    registry = AgentRegistry(
        cfg1, DeterministicLLMClient(), TTLCache(), MetricsRegistry(), failure
    )
    orch1 = Orchestrator(cfg1, registry, state_mgr, failure, MetricsRegistry())
    s1 = await orch1.run_task(task, resume=True)
    assert s1.status == TaskStatus.COMPLETED


# --------------------------------------------------------------------------- #
# Data failure -> spec repair routing
# --------------------------------------------------------------------------- #
async def test_data_failure_logs_and_preserves(config):
    """The failure handler logs, alerts, and preserves a context bundle."""
    fh = FailureHandler(config)
    path = fh.preserve_context("task123", {"some": "context", "n": 1})
    import os

    assert os.path.exists(path)
    # Alerting over the "log" channel never raises.
    fh.alert("test alert", {"task_id": "task123"})


async def test_unknown_task_bundle_contains_full_trace(make_orchestrator):
    """The escalation bundle contains the routing log and outputs."""
    import json
    import os

    orch, _ = make_orchestrator()
    state = await orch.run_task(Task(prompt="optimal multi-depot vehicle routing solver"))
    path = state.escalation_context["bundle_path"]
    with open(path, "r", encoding="utf-8") as fh:
        bundle = json.load(fh)
    assert bundle["routing_log"]
    assert bundle["outputs"]
    assert bundle["reason"]
    os.remove(path)


# --------------------------------------------------------------------------- #
# State persistence
# --------------------------------------------------------------------------- #
def test_state_roundtrips_through_store():
    """TaskState survives a save/load roundtrip with all counters intact."""
    from core.state_manager import StateManager
    from models.task import TaskState

    mgr = StateManager(db_path=":memory:")
    task = Task(prompt="x")
    state = TaskState(task=task)
    state.incr_loop("test_fix_loop")
    state.incr_retry("coder")
    state.artifacts["code"] = "def f(): pass"
    mgr.save(state)

    loaded = mgr.load(task.task_id)
    assert loaded is not None
    assert loaded.loop_count("test_fix_loop") == 1
    assert loaded.retry_count("coder") == 1
    assert loaded.artifacts["code"] == "def f(): pass"
