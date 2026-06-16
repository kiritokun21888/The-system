"""ReviewerAgent — judges code quality and approves or requests refinement.

Role: Solely responsible for a holistic quality verdict on code that has already
passed its tests — readability, documentation, robustness. Its score drives the
review-refine feedback loop: below threshold routes back to the Coder.

Uses the cheaper validation model (cost optimization) since judging is lighter
than generating.
"""

from __future__ import annotations

from typing import Any, Optional

from agents.base_agent import BaseAgent
from core.failure_handler import DataValidationError
from core.json_util import extract_json
from models.agent_output import AgentOutput
from models.task import Task, TaskState

_SYSTEM = (
    "You are a senior code reviewer. Given source code that already passes its "
    "tests, judge its overall quality (correctness clarity, documentation, "
    "robustness, style). Respond as JSON with keys: quality_score (float 0..1), "
    "issues (list of str), approved (bool). Report every issue you find, "
    "including low-severity ones; a downstream gate decides what blocks."
)


class ReviewerAgent(BaseAgent):
    """Scores code quality and lists issues."""

    def cache_input(self, task: Task, state: TaskState) -> Optional[Any]:
        """Review depends on the exact code under review."""
        return {"code": state.artifacts.get("code", "")}

    async def _run(self, task: Task, state: TaskState) -> AgentOutput:
        """Produce a quality verdict.

        Raises:
            DataValidationError: If there is no code artifact to review.
        """
        code = state.artifacts.get("code")
        if not code:
            raise DataValidationError("reviewer invoked without code artifact")

        # Whether tests are currently passing is a strong input to the review.
        # The orchestrator stores the pass rate under the "pass_rate" artifact.
        tests_passed = bool(state.artifacts.get("pass_rate", 0.0) >= 1.0)

        prompt = (
            f"Code under review:\n```python\n{code}\n```\n\n"
            f"Tests passing: {tests_passed}\n"
            "Provide your review JSON."
        )
        response = await self.llm_complete(
            stage="review",
            system=_SYSTEM,
            prompt=prompt,
            context={
                "code": code,
                "tests_passed": tests_passed,
                "task_id": task.task_id,
            },
        )
        data = extract_json(response.text)
        score = float(data.get("quality_score", 0.0))
        issues = data.get("issues", [])

        return AgentOutput.success(
            agent_name=self.name,
            task_id=task.task_id,
            payload={
                "quality_score": score,
                "issues": issues,
                "approved": bool(data.get("approved", score >= self.quality_threshold)),
            },
            quality_score=score,
            cost_usd=response.cost_usd,
            tokens_in=response.tokens_in,
            tokens_out=response.tokens_out,
            metadata={"model": response.model, "n_issues": len(issues)},
        )
