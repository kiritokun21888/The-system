"""Reminder & scheduling agent built on APScheduler.

Owns the daily briefing trigger, recurring overdue-task nudges, and one-off
reminders requested through voice or the brain.
"""
from __future__ import annotations

import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from core.config import settings
from core.events import event_bus

logger = logging.getLogger("zero.reminders")


class ReminderAgent:
    def __init__(self) -> None:
        self.scheduler = AsyncIOScheduler()
        self._started = False

    def start(self) -> None:
        if self._started:
            return
        self.scheduler.add_job(
            self._fire_daily_briefing,
            CronTrigger(hour=settings.briefing_hour, minute=settings.briefing_minute),
            id="daily_briefing", replace_existing=True,
        )
        self.scheduler.add_job(
            self._check_overdue, CronTrigger(minute="*/30"),
            id="overdue_check", replace_existing=True,
        )
        self.scheduler.start()
        self._started = True
        logger.info("Reminder agent started (briefing at %02d:%02d).",
                    settings.briefing_hour, settings.briefing_minute)

    def shutdown(self) -> None:
        if self._started:
            self.scheduler.shutdown(wait=False)
            self._started = False

    async def _fire_daily_briefing(self) -> None:
        from agents.task_agent import task_agent
        from integrations import connectors

        weather = await connectors.weather.current()
        events = await connectors.calendar.todays_events()
        top = await task_agent.top_tasks(limit=3)
        briefing = {
            "greeting": "Good morning. Here's your day.",
            "weather": weather if weather.get("ok") else None,
            "events": events.get("events", []),
            "top_tasks": top,
            "generated_at": datetime.now().isoformat(),
        }
        await event_bus.publish("briefing", briefing)
        logger.info("Daily briefing fired.")

    async def _check_overdue(self) -> None:
        from agents.task_agent import task_agent
        overdue = await task_agent.overdue_tasks()
        for task in overdue:
            await event_bus.publish("notification", {
                "level": "warn", "title": "Task overdue",
                "message": f"'{task['title']}' is past due.",
                "task_id": task["id"],
            })

    async def schedule_one_off(self, message: str, at: str) -> dict:
        try:
            when = datetime.fromisoformat(at)
        except ValueError:
            return {"ok": False, "error": f"Could not parse time: {at}"}
        if not self._started:
            self.start()
        job_id = f"reminder-{when.timestamp()}"
        self.scheduler.add_job(
            self._fire_reminder, DateTrigger(run_date=when),
            args=[message], id=job_id, replace_existing=True,
        )
        return {"ok": True, "message": f"Reminder set for {when.isoformat()}",
                "job_id": job_id}

    async def _fire_reminder(self, message: str) -> None:
        await event_bus.publish("notification", {
            "level": "info", "title": "Reminder", "message": message, "speak": True,
        })

    async def trigger_briefing_now(self) -> None:
        await self._fire_daily_briefing()


reminder_agent = ReminderAgent()
