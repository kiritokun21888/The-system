"""Performance metrics collection and a terminal dashboard.

Every agent emits metrics through :class:`MetricsRegistry`:
  - tasks processed per minute
  - average latency
  - error rate
  - queue depth
  - token / cost accounting

The registry is process-local but thread/async safe via a lock. For distributed
deployments, swap the backing store for Redis counters — the interface is the
same.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Callable, Deque, Optional


@dataclass
class AgentMetrics:
    """Rolling metrics for a single agent."""

    processed: int = 0
    failures: int = 0
    total_latency: float = 0.0
    total_cost: float = 0.0
    total_tokens_in: int = 0
    total_tokens_out: int = 0
    cache_hits: int = 0
    # Timestamps of recent completions (for per-minute throughput).
    recent_completions: Deque[float] = field(default_factory=lambda: deque(maxlen=1000))

    @property
    def avg_latency(self) -> float:
        """Average latency across all processed invocations."""
        return self.total_latency / self.processed if self.processed else 0.0

    @property
    def error_rate(self) -> float:
        """Fraction of invocations that failed."""
        return self.failures / self.processed if self.processed else 0.0

    def per_minute(self) -> float:
        """Completions in the last 60 seconds."""
        cutoff = time.time() - 60.0
        return float(sum(1 for t in self.recent_completions if t >= cutoff))


class MetricsRegistry:
    """Thread-safe registry aggregating metrics across agents and queues."""

    def __init__(self) -> None:
        """Initialize empty metric tables."""
        self._lock = threading.Lock()
        self._agents: dict[str, AgentMetrics] = defaultdict(AgentMetrics)
        self._queue_depth_fn: Optional[Callable[[], int]] = None
        self._tasks_submitted = 0
        self._tasks_completed = 0
        self._tasks_escalated = 0
        self._tasks_aborted = 0
        self._started = time.time()

    def record_invocation(
        self,
        agent_name: str,
        latency: float,
        success: bool,
        cost: float = 0.0,
        tokens_in: int = 0,
        tokens_out: int = 0,
        cache_hit: bool = False,
    ) -> None:
        """Record one agent invocation.

        Args:
            agent_name: Producing agent.
            latency: Wall-clock seconds.
            success: Whether the invocation succeeded.
            cost: Estimated USD cost.
            tokens_in / tokens_out: Token usage.
            cache_hit: Whether served from cache.
        """
        with self._lock:
            m = self._agents[agent_name]
            m.processed += 1
            if not success:
                m.failures += 1
            m.total_latency += latency
            m.total_cost += cost
            m.total_tokens_in += tokens_in
            m.total_tokens_out += tokens_out
            if cache_hit:
                m.cache_hits += 1
            m.recent_completions.append(time.time())

    def record_task_submitted(self) -> None:
        """Increment submitted task counter (used to gauge active tasks)."""
        with self._lock:
            self._tasks_submitted += 1

    def record_task_completed(self) -> None:
        """Increment completed task counter."""
        with self._lock:
            self._tasks_completed += 1

    def record_task_escalated(self) -> None:
        """Increment escalated task counter."""
        with self._lock:
            self._tasks_escalated += 1

    def record_task_aborted(self) -> None:
        """Increment aborted task counter."""
        with self._lock:
            self._tasks_aborted += 1

    def set_queue_depth_source(self, fn: Callable[[], int]) -> None:
        """Register a callable that returns current queue depth."""
        self._queue_depth_fn = fn

    def queue_depth(self) -> int:
        """Current queue depth (0 if no source registered)."""
        if self._queue_depth_fn is None:
            return 0
        try:
            return self._queue_depth_fn()
        except Exception:
            return 0

    def snapshot(self) -> dict[str, Any]:
        """Return a point-in-time snapshot of all metrics."""
        with self._lock:
            agents = {
                name: {
                    "processed": m.processed,
                    "failures": m.failures,
                    "error_rate": round(m.error_rate, 4),
                    "avg_latency": round(m.avg_latency, 4),
                    "per_minute": m.per_minute(),
                    "cost_usd": round(m.total_cost, 6),
                    "tokens_in": m.total_tokens_in,
                    "tokens_out": m.total_tokens_out,
                    "cache_hits": m.cache_hits,
                }
                for name, m in self._agents.items()
            }
            total_cost = sum(m.total_cost for m in self._agents.values())
            finished = self._tasks_completed + self._tasks_escalated + self._tasks_aborted
            active = max(0, self._tasks_submitted - finished)
            return {
                "uptime_seconds": round(time.time() - self._started, 1),
                "queue_depth": self.queue_depth(),
                "tasks_submitted": self._tasks_submitted,
                "tasks_active": active,
                "tasks_completed": self._tasks_completed,
                "tasks_escalated": self._tasks_escalated,
                "tasks_aborted": self._tasks_aborted,
                "total_cost_usd": round(total_cost, 6),
                "agents": agents,
            }

    def render_dashboard(self, title: str = "SWARM DASHBOARD") -> str:
        """Render an ASCII dashboard of current metrics for the terminal.

        Args:
            title: Heading shown on the first line.

        Returns:
            A multi-line string ready to print.
        """
        snap = self.snapshot()
        clock = time.strftime("%H:%M:%S")
        lines = []
        lines.append("=" * 78)
        lines.append(
            f" {title}  | {clock} | uptime {snap['uptime_seconds']}s "
            f"| queue {snap['queue_depth']} | active {snap['tasks_active']}"
        )
        lines.append(
            f"   tasks: done {snap['tasks_completed']} "
            f"| escalated {snap['tasks_escalated']} "
            f"| aborted {snap['tasks_aborted']} "
            f"| submitted {snap['tasks_submitted']} "
            f"| cost ${snap['total_cost_usd']}"
        )
        lines.append("=" * 78)
        header = (
            f" {'agent':<16}{'proc':>6}{'fail':>6}{'err%':>7}"
            f"{'avg_lat':>9}{'/min':>7}{'$':>10}"
        )
        lines.append(header)
        lines.append("-" * 78)
        for name, a in sorted(snap["agents"].items()):
            lines.append(
                f" {name:<16}{a['processed']:>6}{a['failures']:>6}"
                f"{a['error_rate'] * 100:>6.1f}%{a['avg_latency']:>9.3f}"
                f"{a['per_minute']:>7.0f}{a['cost_usd']:>10.5f}"
            )
        lines.append("=" * 78)
        return "\n".join(lines)
