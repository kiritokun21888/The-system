"""Unit tests for every agent.

Each agent is exercised in isolation through its ``process`` wrapper: the happy
path plus every failure path it can produce (so there are no untested failure
branches).
"""

from __future__ import annotations

import pytest

from core.catalog import CATALOG
from models.agent_output import FailureCategory, OutputStatus
from models.task import Spec, Task, TaskState


def _state_with(prompt: str, **artifacts) -> tuple[Task, TaskState]:
    """Build a Task + TaskState seeded with the given artifacts."""
    task = Task(prompt=prompt)
    state = TaskState(task=task)
    state.artifacts.update(artifacts)
    return task, state


# --------------------------------------------------------------------------- #
# SpecParserAgent
# --------------------------------------------------------------------------- #
async def test_spec_parser_success(make_agent):
    """SpecParser produces a valid spec for a known catalog prompt."""
    agent = make_agent("spec_parser")
    task, state = _state_with("Write an is_prime primality test")
    out = await agent.process(task, state)
    assert out.is_success
    assert out.payload["spec"]["function_name"] == "is_prime"
    assert out.quality_score > 0.5


async def test_spec_parser_empty_prompt_is_data_failure(make_agent):
    """An empty prompt is a DATA failure (malformed input)."""
    agent = make_agent("spec_parser")
    task, state = _state_with("  ")
    out = await agent.process(task, state)
    assert out.is_failure
    assert out.failure_category == FailureCategory.DATA


async def test_spec_parser_unknown_prompt_generic_spec(make_agent):
    """An unrecognized prompt still yields a (generic) spec, not a crash."""
    agent = make_agent("spec_parser")
    task, state = _state_with("Build an optimal vehicle routing solver")
    out = await agent.process(task, state)
    assert out.is_success
    assert out.payload["spec"]["function_name"]  # non-empty fallback name


# --------------------------------------------------------------------------- #
# CoderAgent
# --------------------------------------------------------------------------- #
async def test_coder_generates_code(make_agent):
    """Coder produces non-empty code from a spec artifact."""
    agent = make_agent("coder")
    spec = CATALOG["factorial"]["spec"]
    task, state = _state_with("factorial", spec=spec)
    out = await agent.process(task, state)
    assert out.is_success
    assert "def factorial" in out.payload["code"]


async def test_coder_without_spec_is_data_failure(make_agent):
    """Coder invoked with no spec raises a DATA failure."""
    agent = make_agent("coder")
    task, state = _state_with("anything")
    out = await agent.process(task, state)
    assert out.is_failure
    assert out.failure_category == FailureCategory.DATA


async def test_coder_buggy_first_then_correct(make_agent):
    """A buggy-first catalog task yields wrong code on attempt 0, correct later."""
    agent = make_agent("coder")
    spec = CATALOG["fibonacci"]["spec"]
    task, state = _state_with("fibonacci", spec=spec)

    first = await agent.process(task, state)
    assert "return b" in first.payload["code"]  # the off-by-one bug

    # Simulate one test-fix loop iteration so attempt becomes 1.
    state.incr_loop("test_fix_loop")
    second = await agent.process(task, state)
    assert "return a" in second.payload["code"]  # corrected


# --------------------------------------------------------------------------- #
# TestWriterAgent
# --------------------------------------------------------------------------- #
async def test_test_writer_generates_tests(make_agent):
    """TestWriter emits test_* functions from a spec."""
    agent = make_agent("test_writer")
    spec = CATALOG["is_prime"]["spec"]
    task, state = _state_with("is_prime", spec=spec)
    out = await agent.process(task, state)
    assert out.is_success
    assert "def test" in out.payload["test_code"]
    assert out.payload["n_tests"] >= 1


async def test_test_writer_without_spec_is_data_failure(make_agent):
    """TestWriter with no spec raises a DATA failure."""
    agent = make_agent("test_writer")
    task, state = _state_with("anything")
    out = await agent.process(task, state)
    assert out.is_failure
    assert out.failure_category == FailureCategory.DATA


# --------------------------------------------------------------------------- #
# TestRunnerAgent (actually executes code)
# --------------------------------------------------------------------------- #
async def test_runner_passes_on_correct_code(make_agent):
    """Correct code + matching tests yields SUCCESS with pass_rate 1.0."""
    agent = make_agent("test_runner")
    entry = CATALOG["factorial"]
    task, state = _state_with(
        "factorial", code=entry["code"], test_code=entry["tests"]
    )
    out = await agent.process(task, state)
    assert out.is_success
    assert out.payload["pass_rate"] == 1.0


async def test_runner_fails_on_buggy_code_logic_category(make_agent):
    """Buggy code yields a LOGIC failure carrying the failing-test context."""
    agent = make_agent("test_runner")
    entry = CATALOG["fibonacci"]
    task, state = _state_with(
        "fibonacci", code=entry["buggy_code"], test_code=entry["tests"]
    )
    out = await agent.process(task, state)
    assert out.is_failure
    assert out.failure_category == FailureCategory.LOGIC
    assert "tests failed" in out.failure_reason


async def test_runner_handles_import_error(make_agent):
    """Code that doesn't compile is a LOGIC failure (routes to refinement)."""
    agent = make_agent("test_runner")
    task, state = _state_with(
        "broken",
        code="def f(:\n  pass\n",  # syntax error
        test_code="from solution import f\n\ndef test_x():\n    assert f() is None\n",
    )
    out = await agent.process(task, state)
    assert out.is_failure
    assert out.failure_category == FailureCategory.LOGIC


async def test_runner_without_artifacts_is_data_failure(make_agent):
    """No code artifact is a DATA failure."""
    agent = make_agent("test_runner")
    task, state = _state_with("x", test_code="def test_x():\n    assert True\n")
    out = await agent.process(task, state)
    assert out.is_failure
    assert out.failure_category == FailureCategory.DATA


# --------------------------------------------------------------------------- #
# ReviewerAgent
# --------------------------------------------------------------------------- #
async def test_reviewer_high_score_for_good_code(make_agent):
    """A documented, tested implementation scores at/above threshold."""
    agent = make_agent("reviewer")
    task, state = _state_with(
        "fib", code=CATALOG["fibonacci"]["code"], pass_rate=1.0
    )
    out = await agent.process(task, state)
    assert out.is_success
    assert out.quality_score >= 0.75
    assert out.payload["approved"] is True


async def test_reviewer_rejects_stub(make_agent):
    """A stub implementation is decisively rejected."""
    agent = make_agent("reviewer")
    stub = 'def solution():\n    """stub."""\n    raise NotImplementedError\n'
    task, state = _state_with("x", code=stub, pass_rate=1.0)
    out = await agent.process(task, state)
    assert out.is_success  # the reviewer ran fine...
    assert out.quality_score < 0.75  # ...but flagged the code as low quality
    assert out.payload["approved"] is False


async def test_reviewer_without_code_is_data_failure(make_agent):
    """Reviewer with no code raises a DATA failure."""
    agent = make_agent("reviewer")
    task, state = _state_with("x")
    out = await agent.process(task, state)
    assert out.is_failure
    assert out.failure_category == FailureCategory.DATA


# --------------------------------------------------------------------------- #
# Base wrapper behaviours
# --------------------------------------------------------------------------- #
async def test_cache_serves_repeated_inputs(make_agent):
    """Identical inputs are served from cache on the second call."""
    agent = make_agent("spec_parser")
    task, state = _state_with("Write an is_prime primality test")
    first = await agent.process(task, state)
    second = await agent.process(task, state)
    assert first.cache_hit is False
    assert second.cache_hit is True
    assert second.payload == first.payload


async def test_output_status_enum_roundtrip():
    """OutputStatus / FailureCategory survive dict serialization."""
    from models.agent_output import AgentOutput

    out = AgentOutput.failure("a", "t", FailureCategory.LOGIC, "boom")
    d = out.to_dict()
    assert d["status"] == OutputStatus.FAILURE.value
    assert d["failure_category"] == FailureCategory.LOGIC.value
