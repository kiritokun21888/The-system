"""CoderAgent — generates (and refines) the implementation from the Spec.

Role: Solely responsible for producing source code that satisfies the Spec.
It is also the refinement target for both feedback loops: when tests fail or a
review is below threshold, the orchestrator routes back here with the failure
context, and the Coder regenerates an improved implementation.
"""

from __future__ import annotations

from typing import Any, Optional

from agents.base_agent import BaseAgent
from core.failure_handler import DataValidationError
from core.json_util import extract_json
from models.agent_output import AgentOutput
from models.task import Spec, Task, TaskState

_SYSTEM = (
    "You are an expert software engineer. Given a specification and optional "
    "failure feedback from a previous attempt, write a correct, clean, fully "
    "implemented function. Include a docstring. Respond as JSON with keys: "
    "code (str, the full module source), language (str)."
)


class CoderAgent(BaseAgent):
    """Generates code; refines it on feedback."""

    def cache_input(self, task: Task, state: TaskState) -> Optional[Any]:
        """Cache key includes the combined loop attempt so refinements bypass cache.

        On the first generation the inputs are stable and cacheable; once any
        feedback loop has iterated, the attempt counter changes the key, so a
        retry always produces a fresh generation rather than the cached one.
        """
        attempt = self._attempt(state)
        spec = state.artifacts.get("spec", {})
        return {
            "spec": spec,
            "attempt": attempt,
            "failure_reason": state.failure_reason,
        }

    def _attempt(self, state: TaskState) -> int:
        """Combined attempt counter across both feedback loops."""
        return state.loop_count("test_fix_loop") + state.loop_count("review_refine_loop")

    async def _run(self, task: Task, state: TaskState) -> AgentOutput:
        """Generate or refine the implementation.

        Raises:
            DataValidationError: If there is no spec to build against.
        """
        spec_dict = state.artifacts.get("spec")
        if not spec_dict:
            raise DataValidationError("coder invoked without a spec artifact")
        spec = Spec.from_dict(spec_dict)
        attempt = self._attempt(state)

        feedback = ""
        if state.failure_reason:
            feedback = (
                "\n\nThe previous attempt failed. Fix it. Failure details:\n"
                f"{state.failure_reason}\n"
            )

        prompt = (
            f"Specification:\n"
            f"  function: {spec.function_name}\n"
            f"  signature: {spec.signature}\n"
            f"  description: {spec.description}\n"
            f"  requirements: {spec.requirements}\n"
            f"  examples: {spec.examples}\n"
            f"{feedback}\n"
            "Write the complete module source."
        )

        response = await self.llm_complete(
            stage="code",
            system=_SYSTEM,
            prompt=prompt,
            context={
                "task_key": spec.task_key,
                "function_name": spec.function_name,
                "task_id": task.task_id,
            },
            attempt=attempt,
        )
        data = extract_json(response.text)
        code = data.get("code", "")
        if not code.strip():
            raise DataValidationError("coder produced empty code")

        # Quality is a self-estimate; the real signal comes from TestRunner.
        score = 0.6 if "def " in code else 0.3
        if '"""' in code or "'''" in code:
            score += 0.1
        score = min(1.0, round(score, 3))

        return AgentOutput.success(
            agent_name=self.name,
            task_id=task.task_id,
            payload={"code": code, "language": data.get("language", "python")},
            quality_score=score,
            cost_usd=response.cost_usd,
            tokens_in=response.tokens_in,
            tokens_out=response.tokens_out,
            metadata={"model": response.model, "attempt": attempt},
        )
