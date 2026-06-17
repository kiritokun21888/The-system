"""The real entrypoint — FastAPI server + all agents.

Run from the ``assistant`` directory with::

    python -m backend.main

On startup it: initializes the SQLite DB and memory vault, constructs every
agent, starts the autonomous agents as asyncio tasks, starts the reminder
scheduler and the voice listener thread, binds the event loop to the broadcaster,
logs "SYSTEM ONLINE", and begins routine learning.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from . import config, db, memory
from .command_processor import CommandProcessor
from .events import bus
from .agents.system_agent import SystemAgent
from .agents.task_agent import TaskAgent
from .agents.reminder_agent import ReminderAgent
from .agents.research_agent import ResearchAgent
from .agents.health_agent import HealthAgent
from .agents.routine_agent import RoutineAgent
from .agents.clipboard_agent import ClipboardAgent
from .agents.file_watcher_agent import FileWatcherAgent
from .agents.voice_agent import VoiceAgent

app = FastAPI(title="System AI")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

STATE: dict[str, Any] = {}


# --------------------------------------------------------------------------- #
# Startup
# --------------------------------------------------------------------------- #
@app.on_event("startup")
async def startup() -> None:
    """Boot the whole system."""
    cfg = config.load()
    await db.init()
    memory.ensure_vault()

    loop = asyncio.get_running_loop()
    bus.bind_loop(loop)

    # Build agents.
    voice = VoiceAgent(wake_word=cfg.get("wake_word", "hey system"))
    system = SystemAgent()
    task = TaskAgent()
    reminder = ReminderAgent(speak=voice.speak)
    research = ResearchAgent(speak=voice.speak)
    health = HealthAgent()
    routine = RoutineAgent()
    clipboard = ClipboardAgent()
    file_watcher = FileWatcherAgent()

    agents = {
        "system": system, "task": task, "reminder": reminder, "research": research,
        "health": health, "routine": routine, "clipboard": clipboard,
        "file_watcher": file_watcher, "voice": voice,
    }
    STATE["agents"] = agents
    processor = CommandProcessor(agents)
    STATE["processor"] = processor

    # Voice -> command bridge (sync handler called from the voice thread).
    def voice_handler(text: str) -> str:
        fut = asyncio.run_coroutine_threadsafe(processor.process(text), loop)
        try:
            return str(fut.result(timeout=90).get("response", ""))
        except Exception:  # noqa: BLE001
            return ""

    voice.set_handler(voice_handler)

    # Start the reminder scheduler.
    reminder.start_scheduler()

    # Start autonomous agents per config toggles.
    enabled = cfg.get("agents", {})
    tasks = []
    if enabled.get("health", True):
        tasks.append(asyncio.create_task(health.start()))
    if enabled.get("routine", True):
        tasks.append(asyncio.create_task(routine.start()))
    if enabled.get("clipboard", True):
        tasks.append(asyncio.create_task(clipboard.start()))
    if enabled.get("file_watcher", True):
        tasks.append(asyncio.create_task(file_watcher.start()))
    if enabled.get("task", True):
        tasks.append(asyncio.create_task(task.start()))
    STATE["tasks"] = tasks

    # Start voice listener in a background thread (offline; safe if libs absent).
    if cfg.get("voice", {}).get("enabled", True):
        voice.start_thread()

    # Periodic status broadcaster.
    STATE["status_task"] = asyncio.create_task(_status_loop())

    STATE["started"] = time.time()
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] SYSTEM ONLINE")
    memory.log_conversation("[boot]", "startup", "SYSTEM ONLINE")


@app.on_event("shutdown")
async def shutdown() -> None:
    """Cancel background tasks."""
    for t in STATE.get("tasks", []):
        t.cancel()
    if STATE.get("status_task"):
        STATE["status_task"].cancel()
    voice = STATE.get("agents", {}).get("voice")
    if voice:
        voice.stop()


async def _status_loop() -> None:
    """Broadcast agent statuses + stats + uptime on an interval."""
    while True:
        try:
            agents = STATE.get("agents", {})
            await bus.broadcast("agent_status_all",
                                [a.snapshot() for a in agents.values()])
            health = agents.get("health")
            if health:
                try:
                    await bus.broadcast("stats", health.stats())
                except Exception:  # noqa: BLE001
                    pass
            await bus.broadcast("system", {
                "uptime": round(time.time() - STATE.get("started", time.time())),
                "vault_bytes": memory.vault_size_bytes(),
                "connections": bus.count,
            })
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            return
        except Exception:  # noqa: BLE001
            await asyncio.sleep(5)


# --------------------------------------------------------------------------- #
# WebSocket
# --------------------------------------------------------------------------- #
@app.websocket("/ws")
async def ws(websocket: WebSocket) -> None:
    """Stream all events to the UI and accept inbound commands."""
    await bus.connect(websocket)
    try:
        await _send_snapshot(websocket)
        while True:
            raw = await websocket.receive_text()
            await _handle_ws_message(raw)
    except WebSocketDisconnect:
        await bus.disconnect(websocket)
    except Exception:  # noqa: BLE001
        await bus.disconnect(websocket)


async def _handle_ws_message(raw: str) -> None:
    """Handle an inbound WS frame (a command, typically)."""
    import json

    try:
        msg = json.loads(raw)
    except json.JSONDecodeError:
        return
    if msg.get("type") == "command" and msg.get("text"):
        proc: CommandProcessor = STATE["processor"]
        await proc.process(msg["text"])


async def _send_snapshot(websocket: WebSocket) -> None:
    """Send initial state to a freshly connected client."""
    import json

    agents = STATE.get("agents", {})
    snapshot = {
        "type": "snapshot",
        "data": {
            "agents": [a.snapshot() for a in agents.values()],
            "tasks": await db.list_tasks(),
            "reminders": await db.list_reminders(),
            "stats": agents["health"].stats() if "health" in agents else {},
            "config": config.load(),
            "voice_available": getattr(agents.get("voice"), "available", False),
        },
        "ts": time.time(),
    }
    await websocket.send_text(json.dumps(snapshot, default=str))


# --------------------------------------------------------------------------- #
# REST API
# --------------------------------------------------------------------------- #
class CommandBody(BaseModel):
    """A text command from the UI."""

    text: str


@app.post("/command")
async def command(body: CommandBody) -> dict[str, Any]:
    """Execute a text command and return the result."""
    proc: CommandProcessor = STATE["processor"]
    return await proc.process(body.text)


@app.get("/health")
async def health() -> dict[str, Any]:
    """Liveness + quick stats."""
    agents = STATE.get("agents", {})
    return {
        "ok": True,
        "online": "started" in STATE,
        "connections": bus.count,
        "voice_available": getattr(agents.get("voice"), "available", False),
    }


@app.get("/stats")
async def stats() -> dict[str, Any]:
    """Current system stats."""
    health_agent = STATE.get("agents", {}).get("health")
    return health_agent.stats() if health_agent else {}


@app.get("/agents")
async def agents_list() -> list[dict[str, Any]]:
    """All agent statuses."""
    return [a.snapshot() for a in STATE.get("agents", {}).values()]


@app.get("/tasks")
async def tasks() -> list[dict[str, Any]]:
    """All open tasks."""
    return await db.list_tasks()


@app.post("/tasks")
async def add_task(body: CommandBody) -> dict[str, Any]:
    """Add a task from the inline form."""
    return await STATE["agents"]["task"].add(body.text)


@app.post("/tasks/{task_id}/complete")
async def complete_task(task_id: int) -> dict[str, Any]:
    """Complete a task."""
    return await STATE["agents"]["task"].complete(task_id)


@app.delete("/tasks/{task_id}")
async def remove_task(task_id: int) -> dict[str, Any]:
    """Delete a task."""
    return await STATE["agents"]["task"].remove(task_id)


@app.get("/reminders")
async def reminders() -> list[dict[str, Any]]:
    """Pending reminders."""
    return await db.list_reminders()


@app.get("/clipboard")
async def clipboard() -> list[dict[str, Any]]:
    """Clipboard history."""
    return await db.list_clips()


@app.get("/memory/search")
async def memory_search(q: str = "", scope: str = "") -> list[dict[str, Any]]:
    """Search the memory vault."""
    return memory.search(q, scope or None)


@app.get("/config")
async def get_config() -> dict[str, Any]:
    """Return the live config."""
    return config.load()


@app.post("/config")
async def set_config(patch: dict[str, Any]) -> dict[str, Any]:
    """Patch + persist config; apply immediately where possible."""
    cfg = config.update(patch)
    # Apply wake word live.
    voice = STATE.get("agents", {}).get("voice")
    if voice and "wake_word" in patch:
        voice.wake_word = str(patch["wake_word"]).lower()
    await bus.broadcast("config", cfg)
    return cfg


class SpeakBody(BaseModel):
    """Text to speak aloud."""

    text: str


@app.post("/speak")
async def speak(body: SpeakBody) -> dict[str, Any]:
    """Speak text via offline TTS."""
    voice = STATE.get("agents", {}).get("voice")
    if voice:
        await asyncio.to_thread(voice.speak, body.text)
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
