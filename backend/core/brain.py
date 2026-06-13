"""brain.py — ZERO's reasoning core.

Wraps the Anthropic SDK with a tool-use loop, ZERO's personality system
prompt, long-term memory injection, and conversation logging. When no API key
is configured the brain runs in a deterministic offline mode so the rest of
the system still works for local development and demos.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from core.config import settings
from core.events import event_bus
from core.memory import memory_store
from core.tools import TOOL_SCHEMAS, dispatch_tool

logger = logging.getLogger("zero.brain")

ZERO_PERSONA = """You are Z.E.R.O — the Zero-latency Executive Reasoning Operator, \
a highly capable personal AI operator running natively on the user's machine.

Personality and voice:
- Direct, confident, and slightly formal. You address the user respectfully.
- You are never uncertain about what you can do. You state actions plainly: \
"Launching Spotify." "Task created." "Research agent dispatched."
- You are concise. You do not pad responses with filler or apologies.
- You think like an executive operator: anticipate needs, surface what matters, \
and take initiative within your tools.

Operating rules:
- You have real tools that control the local machine, manage tasks, run \
background agents, search the web, and recall long-term memory. Use them \
rather than describing what the user should do manually.
- For destructive system actions (deleting files, restart, sleep, lock) the \
local app will request explicit confirmation — proceed by issuing the action; \
the UI handles the confirmation gate.
- When the user states a durable fact or preference, persist it with the \
remember tool so you recall it later.
- When asked to research, draft, monitor, or summarize over time, delegate to \
a background agent with run_agent instead of doing it inline.
- Keep spoken responses tight enough to be read aloud by text-to-speech.

You are the user's operator. Be useful, be precise, be fast."""


class Brain:
    def __init__(self) -> None:
        self._client = None
        self._model = settings.claude_model
        if settings.claude_enabled:
            try:
                from anthropic import AsyncAnthropic
                self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)
                logger.info("Brain online with model %s", self._model)
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to init Anthropic client: %s", exc)
                self._client = None
        else:
            logger.warning("ANTHROPIC_API_KEY not set — brain running in offline mode.")

    @property
    def enabled(self) -> bool:
        return self._client is not None

    async def _system_prompt(self) -> str:
        memory_block = await memory_store.build_context_block()
        now = datetime.now(timezone.utc).astimezone().strftime("%A, %d %B %Y %H:%M")
        return (
            f"{ZERO_PERSONA}\n\n"
            f"Current local time: {now}.\n\n"
            f"What you remember about the user:\n{memory_block}"
        )

    async def complete_text(self, prompt: str, max_tokens: int = 1024) -> str:
        """Single-shot completion with no tools — used by agents and extraction."""
        if not self.enabled:
            return ""
        resp = await self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(b.text for b in resp.content if b.type == "text")

    async def think(self, user_input: str, max_iterations: int = 6) -> dict:
        """Full reasoning turn with the tool-use loop.

        Returns ``{"reply": str, "tools_used": [...]}``.
        """
        await memory_store.log_turn("user", user_input)
        await event_bus.publish("brain.thinking", {"input": user_input})

        if not self.enabled:
            reply = self._offline_reply(user_input)
            await memory_store.log_turn("assistant", reply)
            await event_bus.publish("brain.reply", {"reply": reply, "offline": True})
            return {"reply": reply, "tools_used": [], "offline": True}

        system_prompt = await self._system_prompt()
        history = await memory_store.recent_turns(limit=12)
        messages = [
            {"role": t["role"], "content": t["content"]}
            for t in history
            if t["role"] in ("user", "assistant")
        ]
        if not messages or messages[-1]["content"] != user_input:
            messages.append({"role": "user", "content": user_input})

        tools_used: list[dict] = []
        reply_text = ""

        for _ in range(max_iterations):
            resp = await self._client.messages.create(
                model=self._model,
                max_tokens=settings.claude_max_tokens,
                system=system_prompt,
                tools=TOOL_SCHEMAS,
                messages=messages,
            )
            text_parts = [b.text for b in resp.content if b.type == "text"]
            reply_text = "".join(text_parts).strip()
            tool_calls = [b for b in resp.content if b.type == "tool_use"]

            # Persist the assistant turn (content blocks) for the next round.
            messages.append({"role": "assistant", "content": resp.content})

            if resp.stop_reason != "tool_use" or not tool_calls:
                break

            tool_results = []
            for call in tool_calls:
                await event_bus.publish("brain.tool", {"name": call.name, "input": call.input})
                result = await dispatch_tool(call.name, call.input or {})
                tools_used.append({"name": call.name, "input": call.input, "result": result})
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": call.id,
                    "content": _stringify(result),
                })
            messages.append({"role": "user", "content": tool_results})

        if reply_text:
            await memory_store.log_turn("assistant", reply_text)
        await event_bus.publish("brain.reply", {"reply": reply_text, "tools_used": tools_used})

        # Fire-and-forget memory extraction over this exchange.
        asyncio.create_task(self._extract_memory(user_input, reply_text))
        return {"reply": reply_text, "tools_used": tools_used}

    async def _extract_memory(self, user_input: str, reply: str) -> None:
        try:
            convo = f"User: {user_input}\nZERO: {reply}"
            await memory_store.extract_and_store(self, convo)
        except Exception as exc:  # noqa: BLE001
            logger.debug("memory extraction skipped: %s", exc)

    def _offline_reply(self, user_input: str) -> str:
        text = user_input.lower()
        if any(g in text for g in ("hello", "hi", "hey")):
            return "Z.E.R.O online. How can I serve?"
        if "status" in text or "online" in text:
            return "All systems nominal. Brain is in offline mode — set ANTHROPIC_API_KEY to enable full reasoning."
        return ("Brain is in offline mode. I can still run tasks, system control, and "
                "agents directly, but set ANTHROPIC_API_KEY for natural-language reasoning.")


def _stringify(result) -> str:
    import json
    try:
        return json.dumps(result, default=str)
    except (TypeError, ValueError):
        return str(result)


brain = Brain()
