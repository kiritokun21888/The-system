"""Command processor — parses intent and routes to the correct agent.

Accepts a natural-language command (from text or voice) and dispatches it. Every
command returns ``{"ok", "response", ...}`` where ``response`` is the text shown
in the UI and spoken aloud. Unknown commands fall through to a best-effort
interpreter.

All interactions are logged to the memory vault.
"""

from __future__ import annotations

import re
from typing import Any

from . import memory
from .events import bus


class CommandProcessor:
    """Routes commands to agents."""

    def __init__(self, agents: dict[str, Any]) -> None:
        """Store references to the live agent instances."""
        self.a = agents

    async def process(self, command: str) -> dict[str, Any]:
        """Parse and execute a command; return a result with a spoken response."""
        text = command.strip()
        low = text.lower()
        await bus.broadcast("command", {"text": text})
        result = await self._route(text, low)
        response = result.get("response") or result.get("message") or "Done."
        memory.log_conversation(text, result.get("intent", "?"), response)
        await bus.broadcast("response", {"text": response, "ok": result.get("ok", True)})
        return result

    async def _route(self, text: str, low: str) -> dict[str, Any]:
        """The intent router."""
        sys_agent = self.a.get("system")
        task_agent = self.a.get("task")
        rem_agent = self.a.get("reminder")
        research_agent = self.a.get("research")
        health = self.a.get("health")

        # ---- greetings / help / time ----
        if re.fullmatch(r"(hi|hey|hello|yo|sup|hey system)\W*", low):
            return {"ok": True, "intent": "greet",
                    "response": "Hi — I'm online. Try 'system stats', 'open chrome', "
                                "'add task buy milk', or say 'help'."}
        if low in ("help", "what can you do", "commands", "?"):
            return {"ok": True, "intent": "help", "response": _HELP}
        if re.search(r"\bwhat('?s| is) the time|what time is it\b", low):
            import time as _t
            return {"ok": True, "intent": "time",
                    "response": f"It's {_t.strftime('%I:%M %p')}."}

        # ---- system stats ----
        if re.search(r"\b(system stats|how('?s| is) my (system|pc|computer)|cpu|memory usage)\b", low):
            s = health.stats() if health else sys_agent.get_system_stats()
            msg = f"CPU {s.get('cpu', 0):.0f}%, RAM {s.get('ram', 0):.0f}%, disk {s.get('disk', 0):.0f}% used"
            return {"ok": True, "intent": "system_stats", "response": msg, "data": s}

        # ---- volume ----
        m = re.search(r"\b(?:set )?volume (?:to )?(\d{1,3})\b", low)
        if m:
            r = sys_agent.set_volume(int(m.group(1)))
            return {"ok": r["ok"], "intent": "set_volume", "response": r["message"]}

        # ---- open url / website ----
        m = re.search(r"\b(?:open|go to|visit)\s+((?:https?://)?[\w.-]+\.\w{2,}(?:/\S*)?)\b", low)
        if m:
            r = sys_agent.open_url(m.group(1))
            return {"ok": r["ok"], "intent": "open_url", "response": r["message"]}

        # ---- open / close app ----
        m = re.match(r"(?:please |can you )?(?:open|launch|start|run) (?:the |my |up )?(.+)", low)
        if m and "http" not in m.group(1):
            app = m.group(1).strip().rstrip("?.!")
            r = sys_agent.open_app(app)
            return {"ok": r["ok"], "intent": "open_app", "response": r["message"]}
        m = re.match(r"(?:please )?(?:close|quit|kill|exit|stop) (?:the |my )?(.+)", low)
        if m:
            app = m.group(1).strip().rstrip("?.!")
            r = sys_agent.close_app(app)
            return {"ok": r["ok"], "intent": "close_app", "response": r["message"]}

        # ---- list apps ----
        if re.search(r"\b(what('?s| is) running|list (open )?apps|open apps)\b", low):
            r = sys_agent.list_open_apps()
            return {"ok": r["ok"], "intent": "list_apps", "response": r["message"], "data": r}

        # ---- screenshot / what's on screen ----
        if re.search(r"\b(screenshot|what('?s| is) on (my )?screen|capture screen)\b", low):
            r = sys_agent.take_screenshot()
            return {"ok": r["ok"], "intent": "screenshot", "response": r["message"], "data": r}

        # ---- research / search ----
        m = re.search(
            r"\b(?:research|search(?: the web)?(?: for)?|look up|find info on|google)\s+(.+)",
            low,
        )
        if m and research_agent:
            topic = m.group(1).strip().rstrip("?.!")
            # Kick off in background; respond immediately.
            import asyncio

            asyncio.create_task(research_agent.research(topic))
            return {"ok": True, "intent": "research",
                    "response": f"Researching '{topic}' — I'll notify you when it's ready."}

        # ---- reminders ----
        if "remind" in low and rem_agent:
            r = await rem_agent.schedule(text)
            return {"ok": r["ok"], "intent": "reminder", "response": r["message"]}

        # ---- tasks ----
        m = re.match(r"(?:add|new|create)(?: a)? task(?: to| called|:)?\s+(.+)", low)
        if m and task_agent:
            r = await task_agent.add(m.group(1).strip())
            return {"ok": r["ok"], "intent": "add_task", "response": r["message"]}
        m = re.match(r"break (?:this )?(?:task )?(?:down )?(?:into steps[:\s]*)?(.+)", low)
        if m and "step" in low and task_agent:
            r = await task_agent.decompose(m.group(1).strip())
            return {"ok": r["ok"], "intent": "decompose", "response": r["message"]}
        if re.search(r"\b(list|show|my) tasks\b", low) and task_agent:
            tasks = await task_agent.list()
            top = "; ".join(f"{t['title']}" for t in tasks[:5]) or "no open tasks"
            return {"ok": True, "intent": "list_tasks",
                    "response": f"You have {len(tasks)} tasks. Top: {top}", "data": tasks}
        m = re.match(r"(?:complete|done|finish) task #?(\d+)", low)
        if m and task_agent:
            r = await task_agent.complete(int(m.group(1)))
            return {"ok": r["ok"], "intent": "complete_task", "response": r["message"]}

        # ---- write a note / document ----
        m = re.match(r"write (?:a )?(?:note|document)(?: called| titled)?\s+(.+)", low)
        if m:
            title = m.group(1).strip()
            path = memory.save_note("preferences", title, f"# {title}\n\n(created via command)")
            return {"ok": True, "intent": "write", "response": f"Created note '{title}'."}

        # ---- memory retrieval ----
        if re.search(r"\bwhat did i (ask|say|do)\b", low):
            hits = memory.search(_keywords(low) or "", "conversations")
            n = len(hits)
            return {"ok": True, "intent": "recall",
                    "response": f"Found {n} matching conversation log(s).",
                    "data": hits[:10]}
        m = re.search(r"\bfind (?:my )?research on\s+(.+)", low)
        if m:
            hits = memory.search(m.group(1).strip(), "research")
            return {"ok": True, "intent": "find_research",
                    "response": f"Found {len(hits)} research note(s).", "data": hits[:10]}

        # ---- fallback ----
        return await self._fallback(text, low)

    async def _fallback(self, text: str, low: str) -> dict[str, Any]:
        """Helpful response for an unrecognized command (predictable, no surprises)."""
        return {"ok": False, "intent": "unknown",
                "response": "I didn't catch a command there. Try one of: "
                            "'open chrome' · 'add task buy milk' · "
                            "'remind me in 20 minutes to stretch' · 'system stats' · "
                            "'research electric cars' · 'what's running'. Say 'help' for more."}


def _keywords(text: str) -> str:
    """Strip filler words to get search keywords."""
    return re.sub(r"\b(what|did|i|ask|say|do|you|yesterday|me|my)\b", "", text).strip()


_HELP = (
    "Here's what I can do — just type it: "
    "open/close an app (open chrome) · system stats · what's running · "
    "volume 30 · add task <thing> · list tasks · complete task 1 · "
    "remind me in 20 minutes to <thing> · research <topic> · "
    "open <website> · take a screenshot · what time is it · "
    "what did I ask · find my research on <topic>."
)
