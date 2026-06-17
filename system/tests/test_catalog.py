"""Catalog consistency tests.

Validates that every catalog entry is self-consistent (its reference code passes
its own tests, and any buggy-first variant actually fails them) and that the
demo/watch prompts resolve to the intended catalog keys with no keyword
collisions.
"""

from __future__ import annotations

import pytest

from core.catalog import CATALOG, detect_task_key
from models.task import Task, TaskState


@pytest.mark.parametrize("key", sorted(CATALOG.keys()))
async def test_reference_code_passes_its_tests(make_agent, key):
    """Every catalog entry's reference implementation passes its own tests."""
    entry = CATALOG[key]
    agent = make_agent("test_runner")
    task = Task(prompt=key)
    state = TaskState(task=task)
    state.artifacts.update({"code": entry["code"], "test_code": entry["tests"]})
    out = await agent.process(task, state)
    assert out.is_success, f"{key}: reference code failed its tests"
    assert out.payload["pass_rate"] == 1.0


@pytest.mark.parametrize(
    "key", sorted(k for k, v in CATALOG.items() if v.get("buggy_first"))
)
async def test_buggy_variant_fails_its_tests(make_agent, key):
    """Every buggy-first variant genuinely fails the tests (so the loop fires)."""
    entry = CATALOG[key]
    agent = make_agent("test_runner")
    task = Task(prompt=key)
    state = TaskState(task=task)
    state.artifacts.update({"code": entry["buggy_code"], "test_code": entry["tests"]})
    out = await agent.process(task, state)
    assert out.is_failure, f"{key}: buggy variant unexpectedly passed"


def test_demo_and_watch_prompts_resolve():
    """Each demo/watch prompt maps to a catalog key (except the routing solver)."""
    import main

    prompts = [p for p, _ in main._DEMO_TASKS] + [p for p, _ in main._WATCH_TASKS]
    for prompt in prompts:
        key = detect_task_key(prompt)
        if "vehicle routing" in prompt.lower():
            assert key is None, "the routing solver must remain unknown (escalates)"
        else:
            assert key is not None, f"prompt did not resolve to a catalog key: {prompt!r}"
            assert key in CATALOG


def test_no_keyword_collision_on_watch_prompts():
    """Sanity: the Kadane/binary-search/sort prompts don't collide with others."""
    assert detect_task_key("Implement Kadane's maximum subarray sum") == "max_subarray"
    assert detect_task_key("Implement binary search over a sorted list") == "binary_search"
    assert detect_task_key("Sort a list of numbers (ascending)") == "sort_numbers"
    assert detect_task_key("Sum a list of numbers") == "sum_list"
