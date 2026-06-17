"""Routine learning agent — learns the user's app + activity patterns.

Records which apps are open and when, builds an hourly/weekday profile, writes it
to ``/memory/routines/profile.md``, and proactively notifies before habitual
actions (e.g. a morning briefing nudge near the usual start time).
"""

from __future__ import annotations

import asyncio
import time
from collections import Counter, defaultdict
from typing import Any

from .. import db, memory
from ..events import bus
from .base import Agent


class RoutineAgent(Agent):
    """Observes activity and derives routines."""

    name = "routine"

    def __init__(self) -> None:
        super().__init__()
        self._seen: set[str] = set()

    async def _sample_apps(self) -> None:
        """Record currently-open notable apps as activity events."""
        try:
            import psutil
        except Exception:  # noqa: BLE001
            return
        notable = {"chrome.exe", "spotify.exe", "code.exe", "discord.exe",
                   "msedge.exe", "firefox.exe", "explorer.exe"}
        current = set()
        for p in psutil.process_iter(["name"]):
            n = (p.info.get("name") or "").lower()
            if n in notable:
                current.add(n)
        # Record only newly-appeared apps (an "open" event).
        for n in current - self._seen:
            await db.add_activity("app_open", n)
        self._seen = current

    async def build_profile(self) -> dict[str, Any]:
        """Build and persist a routine profile from recorded activity."""
        events = await db.activity_since(7 * 24 * 3600)
        if not events:
            return {"ok": True, "message": "Not enough data yet — learning…", "lines": []}
        by_app_hour: dict[str, Counter] = defaultdict(Counter)
        hours = Counter()
        for e in events:
            if e["kind"] == "app_open" and e["name"]:
                by_app_hour[e["name"]][e["hour"]] += 1
            hours[e["hour"]] += 1
        lines = []
        for app, counter in by_app_hour.items():
            hour, _ = counter.most_common(1)[0]
            lines.append(f"- You usually open **{app}** around {hour:02d}:00")
        if hours:
            peak = hours.most_common(1)[0][0]
            lines.append(f"- Most active around **{peak:02d}:00**")
        content = "# Learned Routine\n\n" + "\n".join(lines)
        memory.save_note("routines", "profile", content, tags=["routine"])
        return {"ok": True, "message": f"Profile built from {len(events)} events", "lines": lines}

    async def start(self) -> None:
        """Sample activity periodically and refresh the profile."""
        self.set_status("running", next_action="observing activity")
        ticks = 0
        while True:
            try:
                await self._sample_apps()
                if ticks % 30 == 0:  # roughly every 15 min
                    prof = await self.build_profile()
                    self.set_status("running", last_action=prof["message"],
                                    next_action="observing activity")
                ticks += 1
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                return
            except Exception:  # noqa: BLE001
                await asyncio.sleep(30)
