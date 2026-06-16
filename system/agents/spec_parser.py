"""SpecParserAgent — turns a free-form prompt into a structured Spec.

Role: Solely responsible for converting the natural-language task description
into a validated, machine-usable specification (function name, signature,
requirements, examples) that the Coder and TestWriter build against.
"""

from __future__ import annotations

from typing import Any, Optional

from agents.base_agent import BaseAgent
from core.failure_handler import DataValidationError
from core.json_util import extract_json
from models.agent_output import AgentOutput
from models.task import Spec, Task, TaskState

_SYSTEM = (
    "You are a precise software specification parser. Given a coding task, "
    "produce a JSON object with keys: function_name (str), signature (str), "
    "description (str), requirements (list of str), examples (list of "
    "{input, output}), task_key (str, may be empty), trivial (bool). "
    "Be exact and complete."
)


class SpecParserAgent(BaseAgent):
    """Parses the task prompt into a :class:`Spec`."""

    def cache_input(self, task: Task, state: TaskState) -> Optional[Any]:
        """Cache keyed purely on the prompt + language (deterministic input)."""
        return {"prompt": task.prompt, "language": task.language}

    async def _run(self, task: Task, state: TaskState) -> AgentOutput:
        """Produce a structured spec.

        Raises:
            DataValidationError: If the task prompt is empty/too short.
        """
        if not task.prompt or len(task.prompt.strip()) < 3:
            raise DataValidationError("task prompt is empty or too short to parse")

        prompt = (
            f"Task description:\n{task.prompt}\n\nTarget language: {task.language}\n"
            "Produce the specification JSON."
        )
        response = await self.llm_complete(
            stage="spec",
            system=_SYSTEM,
            prompt=prompt,
            context={"prompt": task.prompt, "task_id": task.task_id},
        )
        data = extract_json(response.text)

        # Validate the parsed spec shape (DATA failure if malformed).
        if "function_name" not in data or not data["function_name"]:
            raise DataValidationError("spec missing function_name")

        spec = Spec.from_dict(data)

        # Quality score: completeness of the produced spec.
        score = 0.4
        if spec.requirements:
            score += 0.3
        if spec.examples:
            score += 0.2
        if spec.signature:
            score += 0.1
        score = min(1.0, round(score, 3))

        return AgentOutput.success(
            agent_name=self.name,
            task_id=task.task_id,
            payload={"spec": spec.to_dict()},
            quality_score=score,
            cost_usd=response.cost_usd,
            tokens_in=response.tokens_in,
            tokens_out=response.tokens_out,
            metadata={"model": response.model, "function_name": spec.function_name},
        )
