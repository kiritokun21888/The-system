"""Tool registry — the catalogue of actions ZERO's brain can invoke.

Each tool exposes an Anthropic tool schema (``TOOL_SCHEMAS``) and an async
handler. ``dispatch_tool`` runs the handler, normalising sync handlers onto a
thread so the event loop stays responsive.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable

from agents.system_agent import system_agent
from agents.task_agent import task_agent
from core.memory import memory_store
from integrations import connectors

logger = logging.getLogger("zero.tools")

# --- Anthropic tool schemas ---------------------------------------------------

TOOL_SCHEMAS: list[dict] = [
    {
        "name": "create_task",
        "description": "Create a task. Infers priority and due date from natural "
                       "language when not explicitly given.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Short task title."},
                "description": {"type": "string"},
                "priority": {"type": "integer", "minimum": 1, "maximum": 5},
                "due_date": {"type": "string", "description": "ISO 8601 datetime."},
                "tags": {"type": "array", "items": {"type": "string"}},
                "raw_text": {"type": "string",
                             "description": "Original phrasing for priority/date inference."},
            },
            "required": ["title"],
        },
    },
    {
        "name": "list_tasks",
        "description": "List tasks, optionally filtered by status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string",
                           "enum": ["pending", "in_progress", "done", "delegated_to_agent"]}
            },
        },
    },
    {
        "name": "update_task",
        "description": "Update an existing task by id (status, priority, notes, etc.).",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer"},
                "status": {"type": "string"},
                "priority": {"type": "integer"},
                "title": {"type": "string"},
                "notes": {"type": "string"},
                "subtasks": {"type": "array", "items": {"type": "object"}},
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "open_application",
        "description": "Launch a desktop application by friendly name (e.g. 'Spotify').",
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    },
    {
        "name": "close_application",
        "description": "Terminate a running application by name.",
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    },
    {
        "name": "get_system_stats",
        "description": "Return CPU, memory, disk and battery statistics.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "open_url",
        "description": "Open a URL in the default browser.",
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    },
    {
        "name": "get_weather",
        "description": "Get current weather for a city (defaults to the configured city).",
        "input_schema": {
            "type": "object",
            "properties": {"city": {"type": "string"}},
        },
    },
    {
        "name": "web_search",
        "description": "Search the web and return top results.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}, "count": {"type": "integer"}},
            "required": ["query"],
        },
    },
    {
        "name": "remember",
        "description": "Persist a durable fact or preference about the user.",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {"type": "string"},
                "type": {"type": "string",
                         "enum": ["fact", "preference", "task_context", "conversation"]},
                "importance": {"type": "number"},
            },
            "required": ["content"],
        },
    },
    {
        "name": "recall",
        "description": "Search ZERO's long-term memory for relevant facts.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "run_agent",
        "description": "Spawn a background agent. Types: research, draft, monitor, "
                       "calendar, email, focus.",
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_type": {"type": "string",
                               "enum": ["research", "draft", "monitor",
                                        "calendar", "email", "focus"]},
                "input": {"type": "string",
                          "description": "Topic, writing brief, URL, or parameter."},
            },
            "required": ["agent_type", "input"],
        },
    },
    {
        "name": "schedule_reminder",
        "description": "Schedule a one-off reminder at a specific time.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {"type": "string"},
                "at": {"type": "string", "description": "ISO 8601 datetime."},
            },
            "required": ["message", "at"],
        },
    },
]


# --- Handlers ----------------------------------------------------------------


async def _create_task(title: str, description: str = "", priority: int | None = None,
                       due_date: str | None = None, tags: list | None = None,
                       raw_text: str | None = None) -> dict:
    return await task_agent.create_task(
        title=title, description=description, priority=priority,
        due_date=due_date, tags=tags, infer_from=raw_text or title,
    )


async def _list_tasks(status: str | None = None) -> dict:
    return {"tasks": await task_agent.list_tasks(status=status)}


async def _update_task(task_id: int, **fields) -> dict:
    result = await task_agent.update_task(task_id, **fields)
    return result or {"ok": False, "error": f"Task {task_id} not found."}


async def _get_weather(city: str | None = None) -> dict:
    return await connectors.weather.current(city)


async def _web_search(query: str, count: int = 5) -> dict:
    return await connectors.brave.search(query, count=count)


async def _remember(content: str, type: str = "fact", importance: float = 0.5) -> dict:
    return await memory_store.add_memory(content, mem_type=type, source="zero", importance=importance)


async def _recall(query: str) -> dict:
    return {"memories": await memory_store.search_memories(query)}


async def _run_agent(agent_type: str, input: str) -> dict:
    from agents.background_agent import background_agent_manager  # lazy import
    agent_id = await background_agent_manager.spawn(agent_type, input)
    return {"ok": True, "agent_id": agent_id,
            "message": f"{agent_type.title()} agent started."}


async def _schedule_reminder(message: str, at: str) -> dict:
    from agents.reminder_agent import reminder_agent  # lazy import
    return await reminder_agent.schedule_one_off(message, at)


# Map tool name -> (handler, is_async)
_SYNC_HANDLERS: dict[str, Callable[..., dict]] = {
    "open_application": lambda **kw: system_agent.open_application(**kw),
    "close_application": lambda **kw: system_agent.close_application(**kw),
    "get_system_stats": lambda **kw: system_agent.get_system_stats(),
    "open_url": lambda **kw: system_agent.open_url(**kw),
}

_ASYNC_HANDLERS: dict[str, Callable[..., Awaitable[dict]]] = {
    "create_task": _create_task,
    "list_tasks": _list_tasks,
    "update_task": _update_task,
    "get_weather": _get_weather,
    "web_search": _web_search,
    "remember": _remember,
    "recall": _recall,
    "run_agent": _run_agent,
    "schedule_reminder": _schedule_reminder,
}


async def dispatch_tool(name: str, tool_input: dict[str, Any]) -> dict:
    """Execute a tool by name and return a JSON-serialisable result."""
    try:
        if name in _ASYNC_HANDLERS:
            return await _ASYNC_HANDLERS[name](**tool_input)
        if name in _SYNC_HANDLERS:
            return await asyncio.to_thread(_SYNC_HANDLERS[name], **tool_input)
        return {"ok": False, "error": f"Unknown tool: {name}"}
    except TypeError as exc:
        return {"ok": False, "error": f"Bad arguments for {name}: {exc}"}
    except Exception as exc:  # noqa: BLE001
        logger.exception("Tool %s failed", name)
        return {"ok": False, "error": str(exc)}
