"""Reminder agent — natural-language scheduling via APScheduler + dateparser.

"remind me in 30 minutes to stretch" / "remind me every Monday at 9am to plan".
When a reminder fires it triggers a UI popup + voice announcement and is logged.
"""

from __future__ import annotations

import re
import time
from typing import Any, Callable, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from .. import db, memory
from ..events import bus
from .base import Agent

_WEEKDAYS = {
    "monday": "mon", "tuesday": "tue", "wednesday": "wed", "thursday": "thu",
    "friday": "fri", "saturday": "sat", "sunday": "sun",
}


class ReminderAgent(Agent):
    """Schedules and fires reminders."""

    name = "reminder"

    def __init__(self, speak: Optional[Callable[[str], None]] = None) -> None:
        super().__init__()
        self._sched = AsyncIOScheduler()
        self._speak = speak

    def start_scheduler(self) -> None:
        """Start the APScheduler event loop integration."""
        if not self._sched.running:
            self._sched.start()
            self.set_status("running", next_action="awaiting reminders")

    async def schedule(self, text: str) -> dict[str, Any]:
        """Parse a natural-language reminder and schedule it."""
        what, recurring = self._extract(text)
        if recurring:
            trig = self._cron_from(recurring)
            if trig is None:
                return {"ok": False, "message": "Could not parse the recurring time"}
            rem_id = await db.add_reminder(what, None, recurring)
            self._sched.add_job(self._fire, trig, args=[rem_id, what, True],
                                id=f"rem-{rem_id}", replace_existing=True)
            self.set_status("running", last_action=f"Recurring reminder set: {what}")
            return {"ok": True, "message": f"Recurring reminder set: {what}"}

        when = self._parse_when(text)
        if when is None:
            return {"ok": False, "message": "Could not understand the time. Try 'in 20 minutes'."}
        rem_id = await db.add_reminder(what, when, None)
        self._sched.add_job(self._fire, DateTrigger(run_date=_dt(when)),
                            args=[rem_id, what, False], id=f"rem-{rem_id}",
                            replace_existing=True)
        mins = max(0, round((when - time.time()) / 60))
        self.set_status("running", last_action=f"Reminder set: {what}",
                        next_action=f"fires in ~{mins} min")
        return {"ok": True, "message": f"Reminder set: '{what}' (~{mins} min)"}

    async def list(self) -> list[dict[str, Any]]:
        """Return pending reminders."""
        return await db.list_reminders()

    def _fire(self, rem_id: int, what: str, recurring: bool) -> None:
        """Reminder callback (runs on the loop). Announces + popups + logs."""
        bus.broadcast_threadsafe("reminder_fired", {"id": rem_id, "text": what})
        bus.broadcast_threadsafe("notification",
                                 {"title": "Reminder", "body": what, "level": "info",
                                  "agent": "reminder"})
        if self._speak:
            try:
                self._speak(f"Reminder: {what}")
            except Exception:  # noqa: BLE001
                pass
        memory.log_conversation(f"[reminder fired] {what}", "announce", "delivered")
        if not recurring:
            import asyncio

            try:
                asyncio.get_event_loop().create_task(db.mark_reminder_fired(rem_id))
            except Exception:  # noqa: BLE001
                pass

    # ------------------------------------------------------------------ #
    @staticmethod
    def _extract(text: str) -> tuple[str, Optional[str]]:
        """Split into the reminder body and an optional recurring phrase."""
        low = text.lower()
        body = re.sub(r"^\s*remind me\s*", "", text, flags=re.I).strip()
        # Prefer the clause after "to" / "that" as the message.
        m = re.search(r"\b(?:to|that)\s+(.+)$", body, flags=re.I)
        if m:
            body = m.group(1).strip()
        # Strip any trailing time phrase from the message.
        body = re.sub(r"\s*\b(in \d+\s*\w+.*|at \d.*|every .*|tomorrow.*|tonight.*)$", "",
                      body, flags=re.I).strip() or body
        recurring = None
        if "every" in low:
            mm = re.search(r"every\s+(.*?)(?:\s+to\b|$)", low)
            recurring = mm.group(1) if mm else None
        return body, recurring

    @staticmethod
    def _parse_when(text: str) -> Optional[float]:
        """Parse an absolute/relative time to an epoch using dateparser."""
        import dateparser

        m = re.search(r"\b(in .+?|at .+?|tomorrow.*?|tonight.*?)(?:\s+to\b|$)", text, flags=re.I)
        phrase = m.group(1) if m else text
        dt = dateparser.parse(phrase, settings={"PREFER_DATES_FROM": "future"})
        return dt.timestamp() if dt else None

    @staticmethod
    def _cron_from(phrase: str) -> Optional[CronTrigger]:
        """Build a CronTrigger from 'monday at 9am' style phrases."""
        low = phrase.lower()
        day = None
        for name, abbr in _WEEKDAYS.items():
            if name in low:
                day = abbr
                break
        hour, minute = 9, 0
        tm = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", low)
        if tm:
            hour = int(tm.group(1))
            minute = int(tm.group(2) or 0)
            if tm.group(3) == "pm" and hour < 12:
                hour += 12
            if tm.group(3) == "am" and hour == 12:
                hour = 0
        try:
            if day:
                return CronTrigger(day_of_week=day, hour=hour, minute=minute)
            return CronTrigger(hour=hour, minute=minute)
        except Exception:  # noqa: BLE001
            return None


def _dt(epoch: float):
    """Epoch -> datetime for APScheduler."""
    import datetime as _d

    return _d.datetime.fromtimestamp(epoch)
