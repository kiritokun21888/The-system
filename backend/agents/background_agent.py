"""Background agent system.

Autonomous async workers (Research, Draft, Monitor, Calendar, Email, Focus)
that run concurrently, report state through the event bus as glowing orbs in
the UI, and store their results in memory or the file system.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from core.config import settings
from core.events import event_bus
from core.memory import memory_store
from integrations import connectors

logger = logging.getLogger("zero.agents")

# Agent lifecycle states map directly to orb colors in the frontend.
STATE_IDLE = "idle"
STATE_RUNNING = "running"
STATE_DONE = "done"
STATE_ERROR = "error"


class BaseAgent:
    type_name = "base"

    def __init__(self, agent_id: str, agent_input: str) -> None:
        self.id = agent_id
        self.input = agent_input
        self.state = STATE_IDLE
        self.result: str | None = None
        self.error: str | None = None
        self.created_at = datetime.now(timezone.utc)

    def snapshot(self) -> dict:
        return {
            "id": self.id,
            "type": self.type_name,
            "input": self.input,
            "state": self.state,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
        }

    async def _set_state(self, state: str) -> None:
        self.state = state
        await event_bus.publish("agent.state", self.snapshot())

    async def run(self) -> None:
        await self._set_state(STATE_RUNNING)
        try:
            self.result = await self.execute()
            await self._set_state(STATE_DONE)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Agent %s failed", self.type_name)
            self.error = str(exc)
            await self._set_state(STATE_ERROR)

    async def execute(self) -> str:  # pragma: no cover - overridden
        raise NotImplementedError


class ResearchAgent(BaseAgent):
    type_name = "research"

    async def execute(self) -> str:
        from core.brain import brain
        search = await connectors.brave.search(self.input, count=6)
        results = search.get("results", [])
        sources = "\n".join(f"- {r['title']}: {r['description']}" for r in results)
        if brain.enabled and sources:
            summary = await brain.complete_text(
                f"Summarize the key findings about '{self.input}' from these search "
                f"results into a tight briefing with 3-5 bullet points:\n\n{sources}",
                max_tokens=700,
            )
        else:
            summary = sources or f"No results found for '{self.input}'."
        await memory_store.add_memory(
            f"Research on '{self.input}': {summary}",
            mem_type="task_context", source="research_agent", importance=0.6,
        )
        await event_bus.publish("notification", {
            "level": "success", "title": "Research complete",
            "message": f"Findings on '{self.input}' saved to memory.",
        })
        return summary


class DraftAgent(BaseAgent):
    type_name = "draft"

    async def execute(self) -> str:
        from core.brain import brain
        if brain.enabled:
            draft = await brain.complete_text(
                f"Write a complete, well-structured draft for the following request. "
                f"Be thorough and ready-to-use:\n\n{self.input}",
                max_tokens=1500,
            )
        else:
            draft = f"# Draft: {self.input}\n\n(Offline mode — connect Claude to generate.)"
        out_dir = settings.data_dir / "drafts"
        out_dir.mkdir(parents=True, exist_ok=True)
        fname = out_dir / f"draft_{datetime.now():%Y%m%d_%H%M%S}.md"
        fname.write_text(draft, encoding="utf-8")
        await event_bus.publish("notification", {
            "level": "success", "title": "Draft ready",
            "message": f"Saved to {fname.name}",
        })
        return f"Draft saved to {fname}"


class MonitorAgent(BaseAgent):
    type_name = "monitor"

    async def execute(self) -> str:
        """Poll a URL a few times and report when its content changes."""
        import httpx
        target = self.input.strip()
        if not target.startswith("http"):
            target = "https://" + target
        last_hash: int | None = None
        checks = 0
        async with httpx.AsyncClient(timeout=20.0) as client:
            while checks < 5:
                checks += 1
                try:
                    resp = await client.get(target)
                    current = hash(resp.text)
                except Exception as exc:  # noqa: BLE001
                    return f"Monitor stopped: {exc}"
                if last_hash is not None and current != last_hash:
                    await event_bus.publish("notification", {
                        "level": "warn", "title": "Change detected",
                        "message": f"{target} changed.",
                    })
                    return f"Change detected at {target} after {checks} checks."
                last_hash = current
                await asyncio.sleep(30)
        return f"No changes detected at {target} after {checks} checks."


class CalendarAgent(BaseAgent):
    type_name = "calendar"

    async def execute(self) -> str:
        events = await connectors.calendar.todays_events()
        items = events.get("events", [])
        if not items:
            return events.get("note", "No calendar events found.")
        lines = [f"- {e}" for e in items]
        return "Today's events:\n" + "\n".join(lines)


class EmailAgent(BaseAgent):
    type_name = "email"

    async def execute(self) -> str:
        summary = await connectors.gmail.unread_summary()
        msgs = summary.get("messages", [])
        if not msgs:
            return summary.get("note", "No unread mail to summarize.")
        return f"{len(msgs)} unread messages flagged."


class FocusAgent(BaseAgent):
    type_name = "focus"

    # Sites blocked during a focus session.
    DISTRACTING = ["news.ycombinator.com", "reddit.com", "twitter.com",
                   "x.com", "youtube.com", "instagram.com", "tiktok.com"]
    MARKER = "# ZERO-FOCUS"

    def _hosts_path(self) -> Path:
        import platform
        if platform.system() == "Windows":
            return Path(r"C:\Windows\System32\drivers\etc\hosts")
        return Path("/etc/hosts")

    async def execute(self) -> str:
        """Block distracting sites for the requested duration (minutes)."""
        try:
            minutes = int("".join(c for c in self.input if c.isdigit()) or "25")
        except ValueError:
            minutes = 25
        hosts = self._hosts_path()
        block = "\n".join(f"127.0.0.1 {d} {self.MARKER}" for d in self.DISTRACTING)
        try:
            original = hosts.read_text(encoding="utf-8")
            hosts.write_text(original + "\n" + block + "\n", encoding="utf-8")
        except PermissionError:
            return ("Focus mode needs elevated permissions to edit the hosts file. "
                    "Run the backend with sufficient privileges to enable site blocking.")
        await event_bus.publish("notification", {
            "level": "info", "title": "Focus mode on",
            "message": f"Blocking distractions for {minutes} minutes.",
        })
        await asyncio.sleep(minutes * 60)
        try:
            cleaned = "\n".join(
                ln for ln in hosts.read_text(encoding="utf-8").splitlines()
                if self.MARKER not in ln
            )
            hosts.write_text(cleaned + "\n", encoding="utf-8")
        except PermissionError:
            pass
        await event_bus.publish("notification", {
            "level": "success", "title": "Focus complete",
            "message": f"{minutes}-minute focus session finished.",
        })
        return f"Focus session complete ({minutes} minutes)."


_AGENT_TYPES: dict[str, type[BaseAgent]] = {
    "research": ResearchAgent,
    "draft": DraftAgent,
    "monitor": MonitorAgent,
    "calendar": CalendarAgent,
    "email": EmailAgent,
    "focus": FocusAgent,
}


class BackgroundAgentManager:
    """Tracks running agents and exposes them to the API / UI."""

    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}
        self._tasks: dict[str, asyncio.Task] = {}

    async def spawn(self, agent_type: str, agent_input: str) -> str:
        cls = _AGENT_TYPES.get(agent_type.lower())
        if cls is None:
            raise ValueError(f"Unknown agent type: {agent_type}")
        agent_id = f"{agent_type}-{uuid.uuid4().hex[:8]}"
        agent = cls(agent_id, agent_input)
        self._agents[agent_id] = agent
        task = asyncio.create_task(self._run_and_cleanup(agent))
        self._tasks[agent_id] = task
        await event_bus.publish("agent.spawned", agent.snapshot())
        return agent_id

    async def _run_and_cleanup(self, agent: BaseAgent) -> None:
        await agent.run()
        self._tasks.pop(agent.id, None)

    def list_agents(self) -> list[dict]:
        return [a.snapshot() for a in self._agents.values()]

    def get_agent(self, agent_id: str) -> dict | None:
        agent = self._agents.get(agent_id)
        return agent.snapshot() if agent else None

    async def stop_agent(self, agent_id: str) -> bool:
        task = self._tasks.get(agent_id)
        if task and not task.done():
            task.cancel()
            agent = self._agents.get(agent_id)
            if agent:
                await agent._set_state(STATE_IDLE)
            return True
        return False


background_agent_manager = BackgroundAgentManager()
