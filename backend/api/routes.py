"""REST endpoints for Z.E.R.O.

Covers conversation, tasks, memory, agents, system control, integrations and
the daily briefing. All routes are mounted under ``/api``.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agents.background_agent import background_agent_manager
from agents.reminder_agent import reminder_agent
from agents.system_agent import system_agent
from agents.task_agent import task_agent
from agents.voice_agent import voice_agent
from core.brain import brain
from core.memory import memory_store
from integrations import connectors

router = APIRouter(prefix="/api")


# --- Schemas ---

class ChatRequest(BaseModel):
    message: str
    speak: bool = False


class TaskCreate(BaseModel):
    title: str
    description: str = ""
    priority: int | None = None
    due_date: str | None = None
    tags: list[str] | None = None
    raw_text: str | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    priority: int | None = None
    status: str | None = None
    due_date: str | None = None
    tags: list[str] | None = None
    subtasks: list[dict] | None = None
    notes: str | None = None


class MemoryCreate(BaseModel):
    content: str
    type: str = "fact"
    tags: list[str] | None = None
    importance: float = 0.5


class MemoryUpdate(BaseModel):
    content: str | None = None
    type: str | None = None
    tags: list[str] | None = None
    importance_score: float | None = None


class AgentSpawn(BaseModel):
    agent_type: str
    input: str


class SystemAction(BaseModel):
    action: str
    args: dict[str, Any] = {}
    confirmed: bool = False


# --- Status ---

@router.get("/status")
async def status() -> dict:
    return {
        "online": True,
        "brain_enabled": brain.enabled,
        "voice_enabled": voice_agent._running,
        "agents_active": len([a for a in background_agent_manager.list_agents()
                              if a["state"] == "running"]),
    }


# --- Conversation ---

@router.post("/chat")
async def chat(req: ChatRequest) -> dict:
    result = await brain.think(req.message)
    if req.speak and result.get("reply"):
        voice_agent.speak(result["reply"])
    return result


# --- Tasks ---

@router.get("/tasks")
async def list_tasks(status: str | None = None) -> dict:
    return {"tasks": await task_agent.list_tasks(status=status)}


@router.post("/tasks")
async def create_task(req: TaskCreate) -> dict:
    return await task_agent.create_task(
        title=req.title, description=req.description, priority=req.priority,
        due_date=req.due_date, tags=req.tags, infer_from=req.raw_text or req.title,
    )


@router.patch("/tasks/{task_id}")
async def update_task(task_id: int, req: TaskUpdate) -> dict:
    result = await task_agent.update_task(task_id, **req.model_dump(exclude_none=True))
    if not result:
        raise HTTPException(404, f"Task {task_id} not found")
    return result


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: int) -> dict:
    if not await task_agent.delete_task(task_id):
        raise HTTPException(404, f"Task {task_id} not found")
    return {"ok": True}


# --- Memory ---

@router.get("/memory")
async def list_memory(limit: int = 100, type: str | None = None) -> dict:
    return {"memories": await memory_store.list_memories(limit=limit, mem_type=type)}


@router.post("/memory")
async def add_memory(req: MemoryCreate) -> dict:
    return await memory_store.add_memory(
        req.content, mem_type=req.type, tags=req.tags, importance=req.importance,
        source="manual",
    )


@router.patch("/memory/{memory_id}")
async def update_memory(memory_id: int, req: MemoryUpdate) -> dict:
    result = await memory_store.update_memory(memory_id, **req.model_dump(exclude_none=True))
    if not result:
        raise HTTPException(404, f"Memory {memory_id} not found")
    return result


@router.delete("/memory/{memory_id}")
async def delete_memory(memory_id: int) -> dict:
    if not await memory_store.delete_memory(memory_id):
        raise HTTPException(404, f"Memory {memory_id} not found")
    return {"ok": True}


# --- Background agents ---

@router.get("/agents")
async def list_agents() -> dict:
    return {"agents": background_agent_manager.list_agents()}


@router.post("/agents")
async def spawn_agent(req: AgentSpawn) -> dict:
    try:
        agent_id = await background_agent_manager.spawn(req.agent_type, req.input)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True, "agent_id": agent_id}


@router.delete("/agents/{agent_id}")
async def stop_agent(agent_id: str) -> dict:
    return {"ok": await background_agent_manager.stop_agent(agent_id)}


# --- System control ---

@router.get("/system/stats")
async def system_stats() -> dict:
    return system_agent.get_system_stats()


@router.get("/system/apps")
async def running_apps() -> dict:
    return system_agent.list_running_apps()


@router.post("/system/action")
async def system_action(req: SystemAction) -> dict:
    fn = getattr(system_agent, req.action, None)
    if fn is None or not callable(fn):
        raise HTTPException(400, f"Unknown system action: {req.action}")
    args = dict(req.args)
    if req.action in system_agent.DESTRUCTIVE_ACTIONS:
        args["confirmed"] = req.confirmed
    return fn(**args)


# --- Integrations / briefing ---

@router.get("/connections")
async def connections() -> dict:
    return {"connections": connectors.connection_states()}


@router.get("/weather")
async def weather(city: str | None = None) -> dict:
    return await connectors.weather.current(city)


@router.post("/briefing")
async def trigger_briefing() -> dict:
    await reminder_agent.trigger_briefing_now()
    return {"ok": True}
