"""TestRunnerAgent — executes the generated code against the generated tests.

Role: Solely responsible for producing an objective pass/fail signal. It writes
the Coder's code to ``solution.py`` and the TestWriter's tests to
``test_solution.py`` in an isolated temp directory, runs them in a subprocess
with a hard timeout, and reports per-test results plus a pass rate.

This is the source of truth that drives the test-fix feedback loop. It is NOT an
LLM agent — ``model_role`` is "none" and no API call is made.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from typing import Any, Optional

from agents.base_agent import BaseAgent
from core.failure_handler import DataValidationError
from models.agent_output import AgentOutput, FailureCategory
from models.task import Task, TaskState

# Harness executed inside the temp dir. It imports the test module, runs every
# `test_*` callable, and prints a JSON report. Plain-assert tests (no pytest
# dependency) keep the sandbox minimal.
_HARNESS = r'''
import importlib, json, traceback, sys

report = {"passed": 0, "failed": 0, "errors": [], "collected": 0, "ok": True}
try:
    tests = importlib.import_module("test_solution")
except Exception:
    report["ok"] = False
    report["import_error"] = traceback.format_exc()
    print(json.dumps(report))
    sys.exit(0)

names = [n for n in dir(tests) if n.startswith("test")]
report["collected"] = len(names)
for name in names:
    fn = getattr(tests, name)
    if not callable(fn):
        continue
    try:
        fn()
        report["passed"] += 1
    except Exception:
        report["failed"] += 1
        report["errors"].append({"test": name, "trace": traceback.format_exc()})
print(json.dumps(report))
'''


class TestRunnerAgent(BaseAgent):
    """Runs code + tests in a subprocess and reports results."""

    def cache_input(self, task: Task, state: TaskState) -> Optional[Any]:
        """Execution results are never cached (config sets ttl 0)."""
        return None

    async def _run(self, task: Task, state: TaskState) -> AgentOutput:
        """Execute the tests and return a pass/fail report.

        Returns:
            SUCCESS with quality_score == pass-rate when all tests pass; FAILURE
            with category LOGIC (routes to refinement) when any test fails or the
            code does not import; raises ``asyncio.TimeoutError`` -> TIMEOUT when
            execution exceeds the agent timeout.

        Raises:
            DataValidationError: If code or tests artifacts are missing.
        """
        code = state.artifacts.get("code")
        tests = state.artifacts.get("test_code")
        if not code:
            raise DataValidationError("test runner invoked without code artifact")
        if not tests:
            raise DataValidationError("test runner invoked without test_code artifact")

        report = await self._execute(code, tests)

        # Hard execution failure (syntax/import error) — route to refinement.
        if not report.get("ok", True) or "import_error" in report:
            return AgentOutput.failure(
                agent_name=self.name,
                task_id=task.task_id,
                category=FailureCategory.LOGIC,
                reason="code failed to import/compile:\n"
                + report.get("import_error", "unknown import error"),
                payload={"report": report},
            )

        collected = report.get("collected", 0)
        passed = report.get("passed", 0)
        failed = report.get("failed", 0)
        pass_rate = (passed / collected) if collected else 0.0

        if failed == 0 and collected > 0:
            return AgentOutput.success(
                agent_name=self.name,
                task_id=task.task_id,
                payload={"report": report, "pass_rate": pass_rate},
                quality_score=pass_rate,
                metadata={"passed": passed, "failed": failed, "collected": collected},
            )

        # Some tests failed — LOGIC failure with the failing traces as context.
        failures = "\n".join(
            f"- {e['test']}: {e['trace'].strip().splitlines()[-1]}"
            for e in report.get("errors", [])
        )
        return AgentOutput.failure(
            agent_name=self.name,
            task_id=task.task_id,
            category=FailureCategory.LOGIC,
            reason=f"{failed}/{collected} tests failed:\n{failures}",
            payload={"report": report, "pass_rate": pass_rate},
            metadata={"passed": passed, "failed": failed, "collected": collected},
        )

    async def _execute(self, code: str, tests: str) -> dict[str, Any]:
        """Write the files and run the harness in a subprocess.

        Returns:
            The parsed JSON report from the harness.
        """
        with tempfile.TemporaryDirectory(prefix="swarm_run_") as tmp:
            self._write(tmp, "solution.py", code)
            self._write(tmp, "test_solution.py", tests)
            self._write(tmp, "_harness.py", _HARNESS)

            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                "_harness.py",
                cwd=tmp,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                # Isolate: don't inherit the parent's import path.
                env={**os.environ, "PYTHONPATH": tmp, "PYTHONDONTWRITEBYTECODE": "1"},
            )
            # Leave headroom under the agent timeout (process wrapper also guards).
            inner_timeout = max(2.0, self.timeout_seconds - 2.0)
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=inner_timeout
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                raise

            out = stdout.decode("utf-8", "replace").strip()
            if not out:
                return {
                    "ok": False,
                    "import_error": stderr.decode("utf-8", "replace")[:2000]
                    or "harness produced no output",
                }
            try:
                # The report is the last JSON line printed by the harness.
                return json.loads(out.splitlines()[-1])
            except json.JSONDecodeError:
                return {"ok": False, "import_error": f"unparseable harness output: {out[:500]}"}

    @staticmethod
    def _write(directory: str, name: str, content: str) -> None:
        """Write ``content`` to ``directory/name``."""
        with open(os.path.join(directory, name), "w", encoding="utf-8") as fh:
            fh.write(content)
