"""Integration tests for the orchestrator's routing logic and feedback loops.

These drive whole tasks through the pipeline and assert on terminal states,
loop counters, the audit log, and the optimization behaviours (parallel
execution, early termination).
"""

from __future__ import annotations

import pytest

from models.task import Task, TaskStatus


async def test_full_pipeline_completes(make_orchestrator):
    """A standard catalog task completes with an approved review."""
    orch, _ = make_orchestrator()
    state = await orch.run_task(Task(prompt="Implement an is_prime primality test"))
    assert state.status == TaskStatus.COMPLETED
    assert state.artifacts["review"]["approved"] is True
    assert state.artifacts["pass_rate"] == 1.0


async def test_test_fix_loop_converges(make_orchestrator):
    """The buggy-first fibonacci task converges via the test-fix loop."""
    orch, _ = make_orchestrator()
    state = await orch.run_task(Task(prompt="nth fibonacci number"))
    assert state.status == TaskStatus.COMPLETED
    # Exactly one test-fix iteration was needed (buggy attempt 0 -> fix).
    assert state.loop_count("test_fix_loop") == 1
    assert "return a" in state.artifacts["code"]


async def test_early_termination_skips_review(make_orchestrator):
    """A trivial task completes without ever producing a review artifact."""
    orch, _ = make_orchestrator()
    state = await orch.run_task(Task(prompt="reverse a string"))
    assert state.status == TaskStatus.COMPLETED
    assert "review" not in state.artifacts  # review stage was skipped
    # The routing log records the early-termination decision.
    assert any("early termination" in r["reason"] for r in state.routing_log)


async def test_unknown_task_escalates(make_orchestrator):
    """An unsynthesizable task escalates to human review with a bundle."""
    orch, _ = make_orchestrator()
    state = await orch.run_task(Task(prompt="optimal multi-depot vehicle routing solver"))
    assert state.status == TaskStatus.ESCALATED
    assert state.escalation_context.get("bundle_path")


async def test_every_routing_decision_is_logged(make_orchestrator):
    """Every step appends a timestamped, reasoned routing entry (audit trail)."""
    orch, _ = make_orchestrator()
    state = await orch.run_task(Task(prompt="compute the factorial of n"))
    assert state.routing_log, "expected a non-empty routing log"
    for entry in state.routing_log:
        assert "timestamp" in entry
        assert "decision" in entry
        assert entry["reason"]


async def test_parallel_group_runs_coder_and_test_writer(make_orchestrator):
    """The coder and test_writer both run on the first pass (parallel group)."""
    orch, _ = make_orchestrator()
    state = await orch.run_task(Task(prompt="Implement an is_prime primality test"))
    agents_seen = {o["agent_name"] for o in state.outputs}
    assert {"coder", "test_writer"} <= agents_seen


async def test_review_refine_loop_divergence_guard(make_orchestrator):
    """A persistently low-quality task hits the review-refine cap and escalates."""
    orch, _ = make_orchestrator()
    state = await orch.run_task(Task(prompt="optimal multi-depot vehicle routing solver"))
    loop = orch.config.get("feedback_loops.review_refine_loop.max_iterations")
    assert state.loop_count("review_refine_loop") == loop + 1  # capped then escalated
    assert state.status == TaskStatus.ESCALATED


async def test_priority_queue_orders_by_priority():
    """The priority queue dequeues higher-priority items first."""
    from core.queue_manager import PriorityQueueManager

    q = PriorityQueueManager(levels=5)
    await q.put("low", priority=5)
    await q.put("high", priority=1)
    await q.put("mid", priority=3)
    assert await q.get() == "high"
    assert await q.get() == "mid"
    assert await q.get() == "low"
