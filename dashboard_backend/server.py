"""FastAPI backend for the mission-control dashboard.

Bridges the existing multi-agent Swarm to the UI:

  * runs the Swarm with a small simulated latency so activity is visible,
  * continuously feeds it catalog tasks so the dashboard always has live data,
  * polls live metrics + task state and broadcasts events over ``/ws``:
      agent_status · task_update · metric_update · log_entry · memory_update,
  * serves the Obsidian-style memory vault REST API.

Run with::

    python -m uvicorn dashboard_backend.server:app --port 8000
    # or:  python dashboard_backend/server.py
"""

from __future__ import annotations

import asyncio
import collections
import json
import os
import random
import sys
import time
from typing import Any, Optional

# Make the existing `system` package importable.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SYSTEM = os.path.join(_ROOT, "system")
if _SYSTEM not in sys.path:
    sys.path.insert(0, _SYSTEM)

from fastapi import FastAPI, WebSocket, WebSocketDisconnect  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from pydantic import BaseModel  # noqa: E402
from watchdog.events import FileSystemEventHandler  # noqa: E402
from watchdog.observers import Observer  # noqa: E402

from core.config import Config  # noqa: E402  (from system/)
from main import Swarm  # noqa: E402  (from system/)
from models.task import Task, TaskStatus  # noqa: E402

from dashboard_backend.memory_manager import MemoryManager  # noqa: E402

# --------------------------------------------------------------------------- #
# Paths / config
# --------------------------------------------------------------------------- #
VAULT_PATH = os.environ.get("MEMORY_VAULT", os.path.join(_ROOT, "dashboard", "memory"))
CONFIG_PATH = os.path.join(_SYSTEM, "config.yaml")

# Catalog-ish prompts the generator cycles through (kept lively + varied).
_GEN_PROMPTS = [
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

_AGENT_ICONS = {
    "spec_parser": "parser",
    "coder": "code",
    "test_writer": "tests",
    "test_runner": "play",
    "reviewer": "shield",
}


# --------------------------------------------------------------------------- #
# WebSocket connection manager
# --------------------------------------------------------------------------- #
class ConnectionManager:
    """Tracks active WebSocket clients and broadcasts JSON events to all."""

    def __init__(self) -> None:
        """Initialize an empty client set."""
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        """Accept and register a new client."""
        await ws.accept()
        async with self._lock:
            self._clients.add(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        """Remove a client."""
        async with self._lock:
            self._clients.discard(ws)

    async def broadcast(self, event_type: str, payload: Any) -> None:
        """Send an event to every connected client (dropping dead ones)."""
        message = json.dumps({"type": event_type, "data": payload, "ts": time.time()})
        async with self._lock:
            dead = []
            for ws in self._clients:
                try:
                    await ws.send_text(message)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self._clients.discard(ws)

    @property
    def count(self) -> int:
        """Number of connected clients."""
        return len(self._clients)


# --------------------------------------------------------------------------- #
# App + global state
# --------------------------------------------------------------------------- #
app = FastAPI(title="Swarm Mission Control API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

manager = ConnectionManager()
_state: dict[str, Any] = {"swarm": None, "memory": None, "loop": None, "log_pos": 0}


# --------------------------------------------------------------------------- #
# Event-shaping helpers
# --------------------------------------------------------------------------- #
def _agent_statuses(swarm: Swarm) -> list[dict[str, Any]]:
    """Derive per-agent status from the metrics snapshot + running tasks."""
    snap = swarm.metrics.snapshot()
    # Which stage each running task currently occupies.
    running_stage: dict[str, str] = {}
    running_count: collections.Counter = collections.Counter()
    for tid in swarm.state.all_ids():
        st = swarm.state.load(tid)
        if st and st.status == TaskStatus.RUNNING and st.current_stage:
            running_count[st.current_stage] += 1
            running_stage.setdefault(st.current_stage, st.task.prompt)

    agents = []
    for name in swarm.config.get("pipeline.order", []):
        a = snap["agents"].get(name, {})
        active = running_count.get(name, 0)
        if active:
            status = "running"
        elif a.get("failures", 0) and a.get("error_rate", 0) > 0.4:
            status = "error"
        elif a.get("processed", 0):
            status = "idle"
        else:
            status = "idle"
        agents.append({
            "name": name,
            "icon": _AGENT_ICONS.get(name, "cpu"),
            "status": status,
            "active": active,
            "processed": a.get("processed", 0),
            "failures": a.get("failures", 0),
            "error_rate": a.get("error_rate", 0.0),
            "avg_latency": a.get("avg_latency", 0.0),
            "per_minute": a.get("per_minute", 0.0),
            "cache_hits": a.get("cache_hits", 0),
            "cost_usd": a.get("cost_usd", 0.0),
            "current_task": running_stage.get(name, ""),
        })
    return agents


def _recent_tasks(swarm: Swarm, limit: int = 25) -> list[dict[str, Any]]:
    """Return the most-recently-updated tasks for the live feed."""
    rows = []
    for tid in swarm.state.all_ids():
        st = swarm.state.load(tid)
        if not st:
            continue
        rows.append({
            "id": tid,
            "prompt": st.task.prompt,
            "priority": st.task.priority,
            "status": st.status.value,
            "stage": st.current_stage,
            "loops": st.loop_counts,
            "elapsed": round(st.elapsed_seconds(), 2),
            "updated": st.updated_at,
            "review_score": st.artifacts.get("review", {}).get("quality_score"),
            "pass_rate": st.artifacts.get("pass_rate"),
        })
    rows.sort(key=lambda r: r["updated"], reverse=True)
    return rows[:limit]


def _edge_traffic(swarm: Swarm) -> list[dict[str, Any]]:
    """Approximate per-edge traffic between pipeline stages for the graph."""
    snap = swarm.metrics.snapshot()
    order = swarm.config.get("pipeline.order", [])
    edges = []
    for i in range(len(order) - 1):
        src, dst = order[i], order[i + 1]
        vol = snap["agents"].get(dst, {}).get("processed", 0)
        edges.append({"source": src, "target": dst, "volume": vol})
    # Feedback edges (test_runner -> coder, reviewer -> coder).
    for src in ("test_runner", "reviewer"):
        if src in order and "coder" in order:
            edges.append({"source": src, "target": "coder", "volume":
                          snap["agents"].get(src, {}).get("failures", 0), "feedback": True})
    return edges


def _tail_log(swarm: Swarm) -> list[dict[str, Any]]:
    """Read any new lines appended to the swarm log file since last poll."""
    path = swarm.config.get("logging.file")
    out: list[dict[str, Any]] = []
    if not path or not os.path.exists(path):
        return out
    try:
        with open(path, "r", encoding="utf-8") as fh:
            fh.seek(_state["log_pos"])
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    rec = {"level": "INFO", "logger": "swarm", "msg": line}
                out.append({
                    "level": rec.get("level", "INFO"),
                    "logger": rec.get("logger", ""),
                    "msg": rec.get("msg", ""),
                    "agent": rec.get("agent") or rec.get("stage", ""),
                    "ts": rec.get("ts", ""),
                })
            _state["log_pos"] = fh.tell()
    except OSError:
        pass
    return out[-40:]


def full_snapshot(swarm: Swarm) -> dict[str, Any]:
    """Assemble the full initial-state payload sent to a new client."""
    return {
        "metrics": swarm.metrics.snapshot(),
        "agents": _agent_statuses(swarm),
        "tasks": _recent_tasks(swarm),
        "edges": _edge_traffic(swarm),
        "pipeline": swarm.config.get("pipeline.order", []),
        "connections": manager.count,
    }


# --------------------------------------------------------------------------- #
# Background tasks
# --------------------------------------------------------------------------- #
async def _generator(swarm: Swarm) -> None:
    """Continuously feed the swarm tasks so the dashboard stays live."""
    await asyncio.sleep(1.0)
    while True:
        try:
            if swarm.queue.depth() < 6:
                prompt, prio = random.choice(_GEN_PROMPTS)
                await swarm.submit(Task(prompt=prompt, priority=prio))
            await asyncio.sleep(random.uniform(1.2, 2.6))
        except asyncio.CancelledError:
            return
        except Exception:
            await asyncio.sleep(2.0)


async def _broadcaster(swarm: Swarm) -> None:
    """Poll live state ~4x/sec and broadcast events to all clients."""
    while True:
        try:
            await manager.broadcast("metric_update", swarm.metrics.snapshot())
            await manager.broadcast("agent_status", _agent_statuses(swarm))
            await manager.broadcast("task_update", _recent_tasks(swarm))
            await manager.broadcast("edge_update", _edge_traffic(swarm))
            for entry in _tail_log(swarm):
                await manager.broadcast("log_entry", entry)
            await asyncio.sleep(0.25)
        except asyncio.CancelledError:
            return
        except Exception:
            await asyncio.sleep(0.5)


class _VaultHandler(FileSystemEventHandler):
    """Watchdog handler that reindexes the vault and broadcasts on change."""

    def __init__(self, memory: MemoryManager) -> None:
        self._memory = memory
        self._last = 0.0

    def on_any_event(self, event: Any) -> None:
        if getattr(event, "is_directory", False):
            return
        if not str(getattr(event, "src_path", "")).endswith(".md"):
            return
        now = time.time()
        if now - self._last < 0.3:  # debounce rapid bursts
            return
        self._last = now
        self._memory.notify_change()


def _on_memory_change() -> None:
    """Schedule a memory_update broadcast from the watcher thread."""
    loop = _state.get("loop")
    memory = _state.get("memory")
    if loop is None or memory is None:
        return
    asyncio.run_coroutine_threadsafe(
        manager.broadcast("memory_update", {"graph": memory.graph(),
                                            "memories": memory.list_memories()}),
        loop,
    )


# --------------------------------------------------------------------------- #
# Lifecycle
# --------------------------------------------------------------------------- #
@app.on_event("startup")
async def _startup() -> None:
    """Boot the swarm, memory manager, watcher, and background loops."""
    cfg = Config.load(CONFIG_PATH)
    # Tune for a live, watchable, offline demo.
    cfg.raw.setdefault("system", {})["state_path"] = os.path.join(_ROOT, "dashboard_state.db")
    cfg.raw["llm"]["simulated_latency_seconds"] = 0.45
    cfg.raw["logging"]["console"] = False
    cfg.raw["monitoring"]["dashboard_enabled"] = False

    swarm = Swarm(cfg)
    await swarm.start()
    _state["swarm"] = swarm
    _state["loop"] = asyncio.get_running_loop()

    memory = MemoryManager(VAULT_PATH, on_change=_on_memory_change)
    _state["memory"] = memory
    observer = Observer()
    observer.schedule(_VaultHandler(memory), VAULT_PATH, recursive=True)
    observer.daemon = True
    observer.start()
    _state["observer"] = observer

    _state["gen_task"] = asyncio.create_task(_generator(swarm))
    _state["bc_task"] = asyncio.create_task(_broadcaster(swarm))


@app.on_event("shutdown")
async def _shutdown() -> None:
    """Tear down background tasks and the swarm."""
    for key in ("gen_task", "bc_task"):
        t = _state.get(key)
        if t:
            t.cancel()
    obs = _state.get("observer")
    if obs:
        obs.stop()
    swarm = _state.get("swarm")
    if swarm:
        swarm.close()


# --------------------------------------------------------------------------- #
# WebSocket
# --------------------------------------------------------------------------- #
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    """Stream live swarm + memory events to a client."""
    await manager.connect(ws)
    swarm = _state.get("swarm")
    memory = _state.get("memory")
    try:
        if swarm:
            await ws.send_text(json.dumps({"type": "snapshot",
                                           "data": full_snapshot(swarm), "ts": time.time()}))
        if memory:
            await ws.send_text(json.dumps({
                "type": "memory_update",
                "data": {"graph": memory.graph(), "memories": memory.list_memories()},
                "ts": time.time(),
            }))
        while True:
            # We don't expect inbound messages, but keep the socket alive and
            # allow simple ping/command frames.
            await ws.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(ws)
    except Exception:
        import traceback
        traceback.print_exc()
        await manager.disconnect(ws)


# --------------------------------------------------------------------------- #
# REST: health + submit
# --------------------------------------------------------------------------- #
@app.get("/health")
async def health() -> dict[str, Any]:
    """Liveness probe with quick stats."""
    swarm = _state.get("swarm")
    return {
        "ok": True,
        "connections": manager.count,
        "queue_depth": swarm.queue.depth() if swarm else 0,
        "vault": VAULT_PATH,
    }


class SubmitBody(BaseModel):
    """Request body for submitting a custom task."""

    prompt: str
    priority: int = 2


@app.post("/submit")
async def submit_task(body: SubmitBody) -> dict[str, Any]:
    """Submit a custom task into the running swarm."""
    swarm = _state.get("swarm")
    if not swarm:
        return JSONResponse({"error": "swarm not ready"}, status_code=503)
    task = Task(prompt=body.prompt, priority=max(1, min(5, body.priority)))
    await swarm.submit(task)
    return {"ok": True, "task_id": task.task_id}


@app.get("/config")
async def get_config() -> dict[str, Any]:
    """Return the raw config.yaml text for the in-app editor."""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
            return {"path": CONFIG_PATH, "content": fh.read()}
    except OSError as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# --------------------------------------------------------------------------- #
# REST: memory vault
# --------------------------------------------------------------------------- #
class MemoryBody(BaseModel):
    """Create/update payload for a memory."""

    title: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[list[str]] = None
    importance: Optional[int] = None
    content: Optional[str] = None
    linked: Optional[list[str]] = None


def _memory() -> MemoryManager:
    """Return the live MemoryManager (raises if not ready)."""
    mem = _state.get("memory")
    if mem is None:
        raise RuntimeError("memory manager not ready")
    return mem


@app.get("/memory")
async def memory_list() -> list[dict[str, Any]]:
    """List all memories with metadata."""
    return _memory().list_memories()


@app.get("/memory/graph")
async def memory_graph() -> dict[str, Any]:
    """Return the node/edge graph for the Obsidian-style view."""
    return _memory().graph()


@app.get("/memory/tags")
async def memory_tags() -> list[str]:
    """Return every tag in the vault (for the filter pills)."""
    return _memory().all_tags()


@app.get("/memory/search")
async def memory_search(q: str = "") -> list[dict[str, Any]]:
    """Full-text search across memory content."""
    return _memory().search(q)


@app.get("/memory/{mem_id}")
async def memory_get(mem_id: str) -> Any:
    """Get a single memory by id."""
    mem = _memory().get(mem_id)
    if not mem:
        return JSONResponse({"error": "not found"}, status_code=404)
    return mem


@app.post("/memory")
async def memory_create(body: MemoryBody) -> dict[str, Any]:
    """Create a new memory file."""
    mem = _memory().create(body.model_dump(exclude_none=True))
    _on_memory_change()
    return mem


@app.put("/memory/{mem_id}")
async def memory_update(mem_id: str, body: MemoryBody) -> Any:
    """Update an existing memory."""
    mem = _memory().update(mem_id, body.model_dump(exclude_none=True))
    if not mem:
        return JSONResponse({"error": "not found"}, status_code=404)
    _on_memory_change()
    return mem


@app.delete("/memory/{mem_id}")
async def memory_delete(mem_id: str) -> dict[str, Any]:
    """Delete a memory file."""
    ok = _memory().delete(mem_id)
    _on_memory_change()
    return {"ok": ok}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
