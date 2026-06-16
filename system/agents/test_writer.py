"""TestWriterAgent — writes an executable test module from the Spec.

Role: Solely responsible for producing a test module (plain ``assert``-based
``test_*`` functions importing the implementation from ``solution``) that
encodes the Spec's requirements and examples. The TestRunner executes these
against the Coder's output to produce an objective pass/fail signal.
"""

from __future__ import annotations

from typing import Any, Optional

from agents.base_agent import BaseAgent
from core.failure_handler import DataValidationError
from core.json_util import extract_json
from models.agent_output import AgentOutput
from models.task import Spec, Task, TaskState

_SYSTEM = (
    "You are a meticulous test engineer. Given a specification, write a Python "
    "test module containing multiple `def test_*()` functions that use plain "
    "`assert` statements and import the implementation `from solution import "
    "<name>`. Cover base cases, typical cases, and edge/error cases. Respond as "
    "JSON with key: test_code (str, the full test module source)."
)


class TestWriterAgent(BaseAgent):
    """Generates the test suite for a task."""

    def cache_input(self, task: Task, state: TaskState) -> Optional[Any]:
        """Tests depend only on the spec — safe to cache on it."""
        return {"spec": state.artifacts.get("spec", {})}

    async def _run(self, task: Task, state: TaskState) -> AgentOutput:
        """Produce the test module.

        Raises:
            DataValidationError: If there is no spec to write tests from.
        """
        spec_dict = state.artifacts.get("spec")
        if not spec_dict:
            raise DataValidationError("test writer invoked without a spec artifact")
        spec = Spec.from_dict(spec_dict)

        prompt = (
            f"Specification:\n"
            f"  function: {spec.function_name}\n"
            f"  signature: {spec.signature}\n"
            f"  description: {spec.description}\n"
            f"  requirements: {spec.requirements}\n"
            f"  examples: {spec.examples}\n\n"
            "Write the test module."
        )
        response = await self.llm_complete(
            stage="tests",
            system=_SYSTEM,
            prompt=prompt,
            context={
                "task_key": spec.task_key,
                "function_name": spec.function_name,
                "task_id": task.task_id,
            },
        )
        data = extract_json(response.text)
        test_code = data.get("test_code", "")
        if "def test" not in test_code:
            raise DataValidationError("test writer produced no test functions")

        # Quality proxy: number of distinct test functions.
        n_tests = test_code.count("def test")
        score = min(1.0, round(0.4 + 0.2 * n_tests, 3))

        return AgentOutput.success(
            agent_name=self.name,
            task_id=task.task_id,
            payload={"test_code": test_code, "n_tests": n_tests},
            quality_score=score,
            cost_usd=response.cost_usd,
            tokens_in=response.tokens_in,
            tokens_out=response.tokens_out,
            metadata={"model": response.model, "n_tests": n_tests},
        )
