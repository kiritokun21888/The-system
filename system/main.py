"""Entrypoint — wires the system together and runs the pipeline.

Builds every component from ``config.yaml``, starts a pool of concurrent workers
that pull tasks from a priority queue, runs a live terminal dashboard, and
exposes a small CLI:

    python main.py demo            # run a built-in batch of demo tasks
    python main.py watch           # larger batch + live, in-place dashboard
    python main.py "Write a function that returns the nth fibonacci number"
    python main.py resume          # resume any checkpointed/in-flight tasks

The whole graph is assembled here; nothing below ``main`` hardcodes operational
values — they all come from config.
"""

from __future__ import annotations

import asyncio
import sys
from typing import Optional

from agents.orchestrator import AgentRegistry, Orchestrator
from core.cache import TTLCache
from core.config import Config
from core.failure_handler import FailureHandler
from core.llm_client import build_llm_client
from core.logger import get_logger, log_event
from core.metrics import MetricsRegistry
from core.queue_manager import PriorityQueueManager
from core.state_manager import StateManager
from models.task import Task, TaskState

# Sentinel pushed onto the queue to signal a worker to stop.
_STOP = object()


class Swarm:
    """Owns the queue, worker pool, dashboard, and the orchestrator."""

    def __init__(self, config: Config) -> None:
        """Assemble every component from configuration."""
        self.config = config
        self.logger = get_logger(
            "swarm",
            level=config.get("logging.level", "INFO"),
            fmt=config.get("logging.format", "json"),
            file=config.get("logging.file"),
            console=config.get("logging.console", True),
        )
        self.metrics = MetricsRegistry()
        self.cache = TTLCache(
            max_entries=config.get("optimization.cache.max_entries", 1024)
        )
        self.llm = build_llm_client(config, cache=self.cache)
        self.failure = FailureHandler(config)
        self.state = StateManager(
            db_path=config.get("system.state_path", "./swarm_state.db")
        )
        self.registry = AgentRegistry(
            config, self.llm, self.cache, self.metrics, self.failure
        )
        self.orchestrator = Orchestrator(
            config, self.registry, self.state, self.failure, self.metrics
        )
        self.queue = PriorityQueueManager(
            levels=config.get("priority_queue.levels", 5)
        )
        self.metrics.set_queue_depth_source(self.queue.depth)
        self._workers: list[asyncio.Task] = []
        self._dashboard_task: Optional[asyncio.Task] = None

    # ------------------------------------------------------------------ #
    # Submission
    # ------------------------------------------------------------------ #
    async def submit(self, task: Task) -> None:
        """Enqueue a task at its priority and persist its initial state."""
        state = TaskState(task=task)
        self.state.save(state)
        self.metrics.record_task_submitted()
        await self.queue.put(task, priority=task.priority)
        log_event(self.logger, "info", "task submitted",
                  task_id=task.task_id, priority=task.priority, prompt=task.prompt)

    # ------------------------------------------------------------------ #
    # Workers
    # ------------------------------------------------------------------ #
    async def _worker(self, worker_id: int) -> None:
        """Pull tasks from the queue and run them through the orchestrator."""
        while True:
            item = await self.queue.get()
            try:
                if item is _STOP:
                    return
                await self.orchestrator.run_task(item)
            except Exception as exc:  # noqa: BLE001 - workers never die silently
                log_event(self.logger, "error", "worker crashed handling task",
                          worker=worker_id, error=repr(exc))
            finally:
                self.queue.task_done()

    async def _dashboard(self) -> None:
        """Periodically render the metrics dashboard to the terminal.

        In "live" mode the screen is cleared and the dashboard redrawn in place
        (top-style); in "append" mode each refresh prints a fresh snapshot to
        the scrollback.
        """
        refresh = self.config.get("monitoring.refresh_seconds", 2)
        live = self.config.get("monitoring.mode", "append") == "live"
        try:
            while True:
                await asyncio.sleep(refresh)
                board = self.metrics.render_dashboard(
                    title="SWARM — LIVE" if live else "SWARM DASHBOARD"
                )
                if live:
                    # ANSI: cursor home + clear-to-end, then redraw in place.
                    sys.stdout.write("\033[H\033[J" + board + "\n")
                    sys.stdout.write(
                        "   (live view — refreshing every "
                        f"{refresh}s; Ctrl-C to stop)\n"
                    )
                    sys.stdout.flush()
                else:
                    print("\n" + board, flush=True)
        except asyncio.CancelledError:
            return

    async def start(self) -> None:
        """Launch the worker pool and (optionally) the dashboard."""
        n = self.config.get("system.workers", 3)
        self._workers = [asyncio.create_task(self._worker(i)) for i in range(n)]
        if self.config.get("monitoring.dashboard_enabled", True):
            self._dashboard_task = asyncio.create_task(self._dashboard())

    async def drain_and_stop(self) -> None:
        """Wait for all queued work, then stop workers and the dashboard."""
        await self.queue.join()
        for _ in self._workers:
            await self.queue.put(_STOP, priority=1)
        await asyncio.gather(*self._workers, return_exceptions=True)
        if self._dashboard_task:
            self._dashboard_task.cancel()
            await asyncio.gather(self._dashboard_task, return_exceptions=True)

    def close(self) -> None:
        """Release resources."""
        self.state.close()

    # ------------------------------------------------------------------ #
    # Resume
    # ------------------------------------------------------------------ #
    async def resume_all(self) -> None:
        """Re-enqueue every resumable (mid-flight/checkpointed) task."""
        for task_id in self.state.resumable_ids():
            st = self.state.load(task_id)
            if st is None:
                continue
            log_event(self.logger, "info", "resuming task",
                      task_id=task_id, stage=st.current_stage)
            await self.queue.put(st.task, priority=st.task.priority)


# --------------------------------------------------------------------------- #
# Demo / CLI
# --------------------------------------------------------------------------- #
_DEMO_TASKS = [
    # Catalog task flagged buggy-first: demonstrates the test-fix loop converging.
    ("Write a function that returns the nth fibonacci number", 1),
    # Trivial catalog task: demonstrates early termination (review skipped).
    ("Write a function to compute the factorial of n", 3),
    # Standard catalog task: full pipeline incl. review.
    ("Implement an is_prime primality test", 2),
    # Trivial task: reverse a string.
    ("Write a function to reverse a string", 4),
    # Non-trivial buggy-first task: a second test-fix loop demonstration.
    ("Implement Kadane's maximum subarray sum", 2),
    # Unknown task: demonstrates failure -> review-refine loop -> escalation.
    ("Build an optimal multi-depot vehicle routing solver", 5),
]

# A larger, varied batch for the live dashboard. Two copies of the catalog at
# mixed priorities keeps the pipeline busy so the dashboard visibly updates.
_WATCH_TASKS = [
    ("Write a function that returns the nth fibonacci number", 1),
    ("Implement an is_prime primality test", 2),
    ("Write a function to compute the factorial of n", 3),
    ("Write a function to reverse a string", 4),
    ("Compute the greatest common divisor (gcd) of two numbers", 3),
    ("Check whether a string is a palindrome", 2),
    ("Sum a list of numbers", 4),
    ("Sort a list of numbers (ascending)", 2),
    ("Count the vowels in a string", 4),
    ("Implement binary search over a sorted list", 1),
    ("Generate fizzbuzz output up to n", 3),
    ("Implement Kadane's maximum subarray sum", 1),
    ("Check whether two strings are anagrams", 3),
    ("Build an optimal multi-depot vehicle routing solver", 5),
]


async def run_demo(swarm: Swarm) -> None:
    """Submit the demo batch and wait for completion, then summarize."""
    for prompt, priority in _DEMO_TASKS:
        await swarm.submit(Task(prompt=prompt, priority=priority))
    await swarm.start()
    await swarm.drain_and_stop()
    _summarize(swarm)


async def run_single(swarm: Swarm, prompt: str) -> None:
    """Run a single user-supplied task."""
    await swarm.submit(Task(prompt=prompt, priority=1))
    await swarm.start()
    await swarm.drain_and_stop()
    _summarize(swarm)


async def run_resume(swarm: Swarm) -> None:
    """Resume any tasks left mid-flight from a previous run."""
    await swarm.resume_all()
    await swarm.start()
    await swarm.drain_and_stop()
    _summarize(swarm)


async def run_watch(swarm: Swarm) -> None:
    """Run the larger batch with a live, in-place dashboard."""
    for prompt, priority in _WATCH_TASKS:
        await swarm.submit(Task(prompt=prompt, priority=priority))
    await swarm.start()
    await swarm.drain_and_stop()
    # Clear once more and print the final board + summary cleanly.
    sys.stdout.write("\033[H\033[J")
    _summarize(swarm)


def _summarize(swarm: Swarm) -> None:
    """Print a final per-task summary plus the metrics dashboard."""
    print("\n" + "=" * 78)
    print(" FINAL TASK SUMMARY")
    print("=" * 78)
    for task_id in swarm.state.all_ids():
        st = swarm.state.load(task_id)
        if st is None:
            continue
        review = st.artifacts.get("review", {})
        score = review.get("quality_score", "-")
        loops = st.loop_counts
        print(
            f" [{st.status.value:<12}] {st.task.prompt[:48]:<48} "
            f"score={score} loops={loops}"
        )
    print(swarm.metrics.render_dashboard())


def _set(cfg: Config, dotted: str, value: object) -> None:
    """Set a nested config value via a dotted key (for CLI overrides)."""
    node = cfg.raw
    parts = dotted.split(".")
    for p in parts[:-1]:
        node = node.setdefault(p, {})
    node[parts[-1]] = value


def main(argv: list[str]) -> int:
    """CLI entrypoint."""
    config = Config.load()

    # The `watch` command tunes config for a clean live dashboard: route logs to
    # the file only, redraw the dashboard in place, refresh fast, and add a small
    # simulated latency so work is visible as it flows through the pipeline.
    if len(argv) >= 2 and argv[1] == "watch":
        _set(config, "logging.console", False)
        _set(config, "monitoring.mode", "live")
        _set(config, "monitoring.refresh_seconds", 0.5)
        _set(config, "monitoring.dashboard_enabled", True)
        if config.get("llm.backend") == "deterministic":
            _set(config, "llm.simulated_latency_seconds", 0.35)

    swarm = Swarm(config)
    try:
        if len(argv) >= 2 and argv[1] == "demo":
            asyncio.run(run_demo(swarm))
        elif len(argv) >= 2 and argv[1] == "watch":
            asyncio.run(run_watch(swarm))
        elif len(argv) >= 2 and argv[1] == "resume":
            asyncio.run(run_resume(swarm))
        elif len(argv) >= 2:
            asyncio.run(run_single(swarm, " ".join(argv[1:])))
        else:
            print(__doc__)
            asyncio.run(run_demo(swarm))
    finally:
        swarm.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
