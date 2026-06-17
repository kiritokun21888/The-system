"""Central Router / Orchestrator and the pluggable Agent Registry.

The :class:`AgentRegistry` instantiates every enabled agent from config (so a
new agent is added by writing one file and registering it in ``config.yaml`` —
no core changes), wrapping bottleneck agents in a round-robin pool.

The :class:`Orchestrator` is the state machine that drives a task through the
pipeline. It:
  * evaluates each agent output against the configured completion thresholds,
  * routes to the next agent, a feedback loop, or termination,
  * tracks task state across the whole pipeline (persisting after every step,
    so the system can stop and resume without data loss),
  * enforces per-agent retry limits and per-loop iteration caps,
  * escalates to human review on exhaustion,
  * logs every routing decision with a timestamp and reason (full audit trail).
"""

from __future__ import annotations

import asyncio
import enum
import importlib
from dataclasses import dataclass
from typing import Any, Optional, Union

from core.config import Config
from core.failure_handler import FailureHandler
from core.llm_client import LLMClient
from core.load_balancer import RoundRobinDispatcher
from core.logger import get_logger, log_event
from core.metrics import MetricsRegistry
from core.cache import TTLCache
from models.agent_output import AgentOutput, FailureCategory, OutputStatus
from models.task import Spec, Task, TaskState, TaskStatus
from core.state_manager import StateManager

# An "agent-like" is either a single agent or a round-robin dispatcher; both
# expose ``name`` and ``async process(task, state)``.
AgentLike = Union["RoundRobinDispatcher", Any]


class RouteAction(str, enum.Enum):
    """The possible routing outcomes the router can choose."""

    ADVANCE = "advance"            # move to the next stage in the pipeline
    RETRY_SAME = "retry_same"      # re-run the current agent
    GOTO = "goto"                  # jump to a named stage (feedback loop)
    COMPLETE = "complete"          # task finished successfully
    ESCALATE = "escalate"          # hand to human review
    ABORT = "abort"                # give up
    FREEZE = "freeze"              # critical failure; preserve & stop
    CHECKPOINT = "checkpoint"      # timeout; persist resumable state & stop


@dataclass
class RouteDecision:
    """A routing decision plus the reason it was made (for the audit log)."""

    action: RouteAction
    reason: str
    target: Optional[str] = None   # stage name for GOTO


# Maps each stage's successful output payload to the artifacts it contributes.
def _artifacts_for(stage: str, output: AgentOutput) -> dict[str, Any]:
    """Extract the artifacts a stage contributes from its output payload."""
    p = output.payload
    if stage == "spec_parser":
        return {"spec": p.get("spec", {})}
    if stage == "coder":
        return {"code": p.get("code", ""), "language": p.get("language", "python")}
    if stage == "test_writer":
        return {"test_code": p.get("test_code", "")}
    if stage == "test_runner":
        # Stored on success AND failure so the reviewer/loops can see the report.
        return {"test_report": p.get("report", {}), "pass_rate": p.get("pass_rate", 0.0)}
    if stage == "reviewer":
        return {"review": p}
    return {}


class AgentRegistry:
    """Builds and holds agent instances from configuration."""

    def __init__(
        self,
        config: Config,
        llm: LLMClient,
        cache: TTLCache,
        metrics: MetricsRegistry,
        failure_handler: FailureHandler,
    ) -> None:
        """Instantiate every enabled agent declared in config.

        Bottleneck agents (``optimization.load_balancing.bottleneck_agents``) are
        instantiated N times and wrapped in a round-robin dispatcher.
        """
        self._config = config
        self._agents: dict[str, AgentLike] = {}
        balanced = config.get("optimization.load_balancing.bottleneck_agents", {}) or {}

        for name, acfg in (config.get("agents", {}) or {}).items():
            if not acfg.get("enabled", True):
                continue
            module = importlib.import_module(acfg["module"])
            cls = getattr(module, acfg["class_name"])
            n_instances = int(balanced.get(name, acfg.get("instances", 1)))
            instances = [
                cls(name, config, llm, cache, metrics, failure_handler)
                for _ in range(max(1, n_instances))
            ]
            self._agents[name] = (
                RoundRobinDispatcher(instances) if len(instances) > 1 else instances[0]
            )

    def get(self, name: str) -> AgentLike:
        """Return the agent (or dispatcher) registered under ``name``."""
        if name not in self._agents:
            raise KeyError(f"agent '{name}' is not registered/enabled")
        return self._agents[name]

    def has(self, name: str) -> bool:
        """Whether an agent is registered."""
        return name in self._agents

    def threshold(self, name: str) -> float:
        """The configured quality threshold for an agent."""
        return self._config.agent_config(name).get(
            "quality_threshold", self._config.get("router.default_quality_threshold", 0.75)
        )

    def max_retries(self, name: str) -> int:
        """The configured max retries for an agent."""
        return self._config.agent_config(name).get(
            "max_retries", self._config.get("router.max_retries", 3)
        )


class Orchestrator:
    """The router / state manager that drives a task through the pipeline."""

    def __init__(
        self,
        config: Config,
        registry: AgentRegistry,
        state_manager: StateManager,
        failure_handler: FailureHandler,
        metrics: MetricsRegistry,
    ) -> None:
        """Wire the orchestrator to its dependencies."""
        self.config = config
        self.registry = registry
        self.state = state_manager
        self.failure = failure_handler
        self.metrics = metrics
        self.logger = get_logger(
            "orchestrator",
            level=config.get("logging.level", "INFO"),
            fmt=config.get("logging.format", "json"),
            file=config.get("logging.file"),
            console=config.get("logging.console", True),
        )
        self.pipeline: list[str] = config.get("pipeline.order", [])
        self.task_timeout: float = config.get("system.task_timeout_seconds", 120)
        self.escalate_on_exhaustion: bool = config.get(
            "router.escalate_on_exhaustion", True
        )
        self.early_term: bool = config.get("optimization.early_termination.enabled", True)
        self.parallel_groups: list[list[str]] = config.get(
            "optimization.parallel_execution.groups", []
        ) or []

    # ------------------------------------------------------------------ #
    # Public entrypoint
    # ------------------------------------------------------------------ #
    async def run_task(self, task: Task, resume: bool = False) -> TaskState:
        """Run (or resume) a task through the full pipeline.

        Args:
            task: The task to run.
            resume: If True, load existing state and continue from its stage.

        Returns:
            The terminal :class:`TaskState`.
        """
        state = self.state.load(task.task_id) if resume else None
        if state is None:
            state = TaskState(task=task)
        state.status = TaskStatus.RUNNING
        self.state.save(state)

        # Determine the starting index in the pipeline.
        idx = (
            self.pipeline.index(state.current_stage)
            if state.current_stage in self.pipeline
            else 0
        )

        while idx < len(self.pipeline):
            # --- Global timeout (TIMEOUT category) ---
            if state.elapsed_seconds() > self.task_timeout:
                self._checkpoint(state, "task exceeded max duration")
                return state

            # --- Optimization: parallel fan-out for independent stages ---
            group = self._parallel_group_at(idx, state)
            if group:
                stage_outputs = await self._run_group(group, task, state)
            else:
                stage = self.pipeline[idx]
                state.current_stage = stage
                output = await self.registry.get(stage).process(task, state)
                stage_outputs = [(stage, output)]

            # --- Route each produced output in order; first non-ADVANCE wins ---
            for stage, output in stage_outputs:
                state.record_output(output.to_dict())
                self._store_artifacts(stage, output, state)
                decision = self._route(stage, output, state)
                state.record_routing(
                    decision.action.value, decision.reason,
                    {"quality_score": output.quality_score},
                )
                log_event(
                    self.logger, "info", "routing decision",
                    task_id=task.task_id, stage=stage, action=decision.action.value,
                    reason=decision.reason, target=decision.target,
                    quality=output.quality_score, status=output.status.value,
                )
                self.state.save(state)

                idx, terminal, _ = self._apply(decision, stage, idx, state, task)
                if terminal is not None:
                    return terminal
                if decision.action == RouteAction.RETRY_SAME:
                    await self._maybe_backoff(state, stage)
                if decision.action != RouteAction.ADVANCE:
                    # A redirect/retry overrides any remaining group members.
                    break

        # Fell off the end of the pipeline without an explicit COMPLETE.
        state.status = TaskStatus.COMPLETED
        self.state.save(state)
        self.metrics.record_task_completed()
        return state

    def _apply(
        self,
        decision: RouteDecision,
        stage: str,
        idx: int,
        state: TaskState,
        task: Task,
    ) -> tuple[int, Optional[TaskState], int]:
        """Apply a routing decision.

        Returns:
            ``(new_idx, terminal_state_or_None, advance_delta)``. When the second
            element is not None, the task has reached a terminal state and the
            caller should return it.
        """
        if decision.action == RouteAction.ADVANCE:
            state.reset_retry(stage)
            state.failure_reason = ""
            return idx + 1, None, 1
        if decision.action == RouteAction.RETRY_SAME:
            # Note: backoff is awaited by the caller path for single stages; for
            # simplicity we record the retry and re-enter at the same index.
            return idx, None, 0
        if decision.action == RouteAction.GOTO:
            assert decision.target is not None
            return self.pipeline.index(decision.target), None, 0
        if decision.action == RouteAction.COMPLETE:
            state.status = TaskStatus.COMPLETED
            self.state.save(state)
            self.metrics.record_task_completed()
            log_event(self.logger, "info", "task completed", task_id=task.task_id)
            return idx, state, 0
        if decision.action == RouteAction.ESCALATE:
            self._escalate(state, decision.reason)
            return idx, state, 0
        if decision.action == RouteAction.ABORT:
            state.status = TaskStatus.ABORTED
            self.state.save(state)
            self.metrics.record_task_aborted()
            return idx, state, 0
        if decision.action == RouteAction.FREEZE:
            self._freeze(state, decision.reason)
            return idx, state, 0
        if decision.action == RouteAction.CHECKPOINT:
            self._checkpoint(state, decision.reason)
            return idx, state, 0
        return idx, None, 0

    # ------------------------------------------------------------------ #
    # Parallel execution (Deliverable 6)
    # ------------------------------------------------------------------ #
    def _parallel_group_at(self, idx: int, state: TaskState) -> Optional[list[str]]:
        """Return a runnable parallel group starting at pipeline index ``idx``.

        A group is eligible only when its stages are contiguous in the pipeline
        starting at ``idx`` AND none of their artifacts exist yet (i.e. this is
        the first pass, not a refinement loop where only the Coder re-runs).
        """
        for group in self.parallel_groups:
            if len(group) < 2:
                continue
            contiguous = self.pipeline[idx : idx + len(group)]
            if contiguous != group:
                continue
            # Skip parallelization during refinement (test_code already exists).
            if "test_writer" in group and state.artifacts.get("test_code"):
                return None
            return group
        return None

    async def _run_group(
        self, group: list[str], task: Task, state: TaskState
    ) -> list[tuple[str, AgentOutput]]:
        """Run a group of independent stages concurrently with asyncio.gather."""
        state.current_stage = group[0]
        log_event(self.logger, "info", "parallel fan-out",
                  task_id=task.task_id, stages=group)
        outputs = await asyncio.gather(
            *[self.registry.get(s).process(task, state) for s in group]
        )
        return list(zip(group, outputs))

    # ------------------------------------------------------------------ #
    # Routing logic (Deliverable 3)
    # ------------------------------------------------------------------ #
    def _route(self, stage: str, output: AgentOutput, state: TaskState) -> RouteDecision:
        """Decide where a task goes after an agent output.

        Pseudocode shape (per spec):
            if output.quality_score >= threshold: route_to(NEXT_AGENT)
            elif retry_count < MAX_RETRIES:       route_to(REFINEMENT_AGENT, ctx)
            else:                                 escalate_to(HUMAN_REVIEW, trace)
        """
        if output.status == OutputStatus.SKIPPED:
            return RouteDecision(RouteAction.ADVANCE, f"{stage} skipped (early termination)")

        if output.is_failure:
            return self._route_failure(stage, output, state)

        threshold = self.registry.threshold(stage)
        if output.quality_score >= threshold:
            return self._route_success(stage, state)
        return self._route_quality_miss(stage, output, state)

    def _route_failure(
        self, stage: str, output: AgentOutput, state: TaskState
    ) -> RouteDecision:
        """Route a FAILURE output by its category."""
        cat = output.failure_category

        if cat == FailureCategory.CRITICAL:
            return RouteDecision(RouteAction.FREEZE, f"critical failure in {stage}: "
                                 f"{output.failure_reason}")

        if cat == FailureCategory.TIMEOUT:
            return RouteDecision(RouteAction.CHECKPOINT, f"timeout in {stage}")

        if cat == FailureCategory.TRANSIENT:
            # Backoff retries already exhausted inside the agent; give the stage
            # a bounded number of fresh attempts before escalating.
            if state.retry_count(stage) < self.registry.max_retries(stage):
                state.incr_retry(stage)
                return RouteDecision(RouteAction.RETRY_SAME,
                                     f"transient fault in {stage}; retrying")
            return self._exhausted(f"transient faults exhausted in {stage}")

        if cat == FailureCategory.DATA:
            # Data repair: malformed/missing input routes back to the spec
            # parser (the data-producing agent). At the parser itself, retry.
            if stage == "spec_parser":
                if state.retry_count(stage) < self.registry.max_retries(stage):
                    state.incr_retry(stage)
                    return RouteDecision(RouteAction.RETRY_SAME,
                                         "spec parse data error; retrying parse")
                return self._exhausted("spec parsing data errors exhausted")
            if state.retry_count("data_repair") < self.registry.max_retries("spec_parser"):
                state.incr_retry("data_repair")
                state.failure_reason = output.failure_reason
                return RouteDecision(RouteAction.GOTO,
                                     f"data error in {stage}; routing to spec repair",
                                     target="spec_parser")
            return self._exhausted("data repair exhausted")

        if cat == FailureCategory.LOGIC:
            # The test-fix feedback loop: failing tests route to the Coder.
            return self._logic_refine(stage, output, state)

        return self._exhausted(f"unclassified failure in {stage}")

    def _route_success(self, stage: str, state: TaskState) -> RouteDecision:
        """Route a SUCCESS output that meets its quality threshold."""
        if stage == "test_runner":
            # Tests pass. Clear failure context. Optionally skip review.
            spec = Spec.from_dict(state.artifacts.get("spec", {}))
            pass_rate = state.artifacts.get("pass_rate", 0.0)
            if self.early_term and spec.trivial and pass_rate >= 1.0:
                return RouteDecision(
                    RouteAction.COMPLETE,
                    "early termination: trivial task with all tests passing; "
                    "review stage skipped",
                )
            return RouteDecision(RouteAction.ADVANCE, "tests passed; advancing to review")

        if stage == "reviewer":
            return RouteDecision(RouteAction.COMPLETE,
                                 "review approved above quality threshold")

        return RouteDecision(RouteAction.ADVANCE, f"{stage} succeeded; advancing")

    def _route_quality_miss(
        self, stage: str, output: AgentOutput, state: TaskState
    ) -> RouteDecision:
        """Route a SUCCESS output whose quality is below threshold."""
        if stage == "reviewer":
            # The review-refine feedback loop.
            loop = self.config.get("feedback_loops.review_refine_loop", {})
            max_iter = loop.get("max_iterations", 3)
            refine = loop.get("refine_agent", "coder")
            n = state.incr_loop("review_refine_loop")
            if n <= max_iter:
                issues = output.payload.get("issues", [])
                state.failure_reason = (
                    "Reviewer requested improvements (quality "
                    f"{output.quality_score:.2f} < {self.registry.threshold('reviewer'):.2f}). "
                    f"Issues: {issues}"
                )
                return RouteDecision(
                    RouteAction.GOTO,
                    f"review below threshold (iter {n}/{max_iter}); refining",
                    target=refine,
                )
            return self._exhausted("review-refine loop did not converge")

        # Generic quality miss for other stages: retry the same agent.
        if state.retry_count(stage) < self.registry.max_retries(stage):
            state.incr_retry(stage)
            return RouteDecision(
                RouteAction.RETRY_SAME,
                f"{stage} below quality threshold; retrying "
                f"({state.retry_count(stage)}/{self.registry.max_retries(stage)})",
            )
        return self._exhausted(f"{stage} never reached quality threshold")

    def _logic_refine(
        self, stage: str, output: AgentOutput, state: TaskState
    ) -> RouteDecision:
        """The test-fix loop: route a LOGIC failure to the refinement agent."""
        loop = self.config.get("feedback_loops.test_fix_loop", {})
        max_iter = loop.get("max_iterations", 4)
        refine = loop.get("refine_agent", "coder")
        n = state.incr_loop("test_fix_loop")
        if n <= max_iter:
            state.failure_reason = output.failure_reason
            return RouteDecision(
                RouteAction.GOTO,
                f"{stage} reported failing tests (iter {n}/{max_iter}); "
                f"routing to {refine} with failure context",
                target=refine,
            )
        return self._exhausted("test-fix loop did not converge (divergence guard)")

    def _exhausted(self, reason: str) -> RouteDecision:
        """Convert an exhaustion into escalation or abort per config."""
        if self.escalate_on_exhaustion:
            return RouteDecision(RouteAction.ESCALATE, reason)
        return RouteDecision(RouteAction.ABORT, reason)

    # ------------------------------------------------------------------ #
    # State transitions / terminal handlers
    # ------------------------------------------------------------------ #
    def _store_artifacts(self, stage: str, output: AgentOutput, state: TaskState) -> None:
        """Merge a stage's contributed artifacts into the task state."""
        if output.is_success or stage == "test_runner":
            state.artifacts.update(_artifacts_for(stage, output))
            state.touch()

    async def _maybe_backoff(self, state: TaskState, stage: str) -> None:
        """Sleep an exponential backoff before a same-stage retry."""
        attempt = max(0, state.retry_count(stage) - 1)
        delay = self.failure.backoff_delay(attempt)
        if delay > 0:
            await asyncio.sleep(min(delay, 8.0))

    def _build_bundle(self, state: TaskState, reason: str) -> dict[str, Any]:
        """Assemble the full context bundle for escalation / freeze."""
        return {
            "task": state.task.to_dict(),
            "status": state.status.value,
            "reason": reason,
            "artifacts": state.artifacts,
            "outputs": state.outputs,
            "routing_log": state.routing_log,
            "retry_counts": state.retry_counts,
            "loop_counts": state.loop_counts,
            "elapsed_seconds": state.elapsed_seconds(),
        }

    def _escalate(self, state: TaskState, reason: str) -> None:
        """Escalate to human review with a full context bundle."""
        bundle = self._build_bundle(state, reason)
        path = self.failure.preserve_context(state.task.task_id, bundle)
        state.escalation_context = {"reason": reason, "bundle_path": path}
        state.status = TaskStatus.ESCALATED
        self.state.save(state)
        self.failure.alert(
            "task escalated to human review",
            {"task_id": state.task.task_id, "reason": reason, "bundle": path},
        )
        self.metrics.record_task_escalated()
        log_event(self.logger, "warning", "task escalated",
                  task_id=state.task.task_id, reason=reason, bundle=path)

    def _freeze(self, state: TaskState, reason: str) -> None:
        """Freeze a critically-failed task: preserve everything and alert."""
        bundle = self._build_bundle(state, reason)
        path = self.failure.preserve_context(state.task.task_id, bundle)
        state.escalation_context = {"reason": reason, "bundle_path": path}
        state.status = TaskStatus.FROZEN
        self.state.save(state)
        self.failure.alert(
            "CRITICAL: task frozen",
            {"task_id": state.task.task_id, "reason": reason, "bundle": path},
        )
        self.metrics.record_task_escalated()
        log_event(self.logger, "error", "task frozen (critical)",
                  task_id=state.task.task_id, reason=reason, bundle=path)

    def _checkpoint(self, state: TaskState, reason: str) -> None:
        """Checkpoint a timed-out task so it can be resumed later."""
        state.status = TaskStatus.CHECKPOINTED
        state.failure_reason = reason
        self.state.save(state)
        self.failure.alert(
            "task checkpointed (timeout)",
            {"task_id": state.task.task_id, "reason": reason,
             "stage": state.current_stage},
        )
        log_event(self.logger, "warning", "task checkpointed",
                  task_id=state.task.task_id, reason=reason, stage=state.current_stage)
