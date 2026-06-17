"""System health agent — monitors CPU/RAM/disk and alerts on pressure.

Broadcasts live stats every few seconds (for the status bar) and raises
notifications when thresholds are crossed, naming the culprit process.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from ..events import bus
from .base import Agent


class HealthAgent(Agent):
    """Continuously monitors system health."""

    name = "health"

    def __init__(self) -> None:
        super().__init__()
        self._cpu_high_since: float | None = None

    def stats(self) -> dict[str, Any]:
        """One-shot stats snapshot."""
        import os
        import psutil

        disk = psutil.disk_usage(os.path.abspath(os.sep))
        return {
            "cpu": psutil.cpu_percent(interval=0.0),
            "ram": psutil.virtual_memory().percent,
            "disk": disk.percent,
            "disk_free_gb": round(disk.free / 1e9, 1),
        }

    def _top_process(self) -> str:
        """Name the process using the most CPU."""
        import psutil

        worst, name = 0.0, "?"
        for p in psutil.process_iter(["name", "cpu_percent"]):
            c = p.info.get("cpu_percent") or 0.0
            if c > worst:
                worst, name = c, p.info.get("name") or "?"
        return name

    async def start(self) -> None:
        """Monitor loop — broadcasts stats and alerts on thresholds."""
        try:
            import psutil

            psutil.cpu_percent(interval=0.0)  # prime
        except Exception:  # noqa: BLE001
            self.set_status("error", last_action="psutil unavailable")
            return
        self.set_status("running", next_action="sampling every 5s")
        tick = 0
        while True:
            try:
                s = self.stats()
                await bus.broadcast("stats", s)
                # CPU sustained-high detection.
                if s["cpu"] > 85:
                    self._cpu_high_since = self._cpu_high_since or time.time()
                    if time.time() - self._cpu_high_since > 30:
                        culprit = await asyncio.to_thread(self._top_process)
                        await bus.notify("High CPU", f"{s['cpu']:.0f}% — top: {culprit}",
                                         level="warning", agent="health")
                        self._cpu_high_since = time.time()
                else:
                    self._cpu_high_since = None
                if tick % 6 == 0:  # every ~30s for the heavier checks
                    if s["ram"] > 90:
                        await bus.notify("High memory", f"RAM at {s['ram']:.0f}%",
                                         level="warning", agent="health")
                    if s["disk_free_gb"] < 10:
                        await bus.notify("Low disk", f"{s['disk_free_gb']} GB free",
                                         level="warning", agent="health")
                self.set_status("running", last_action=f"CPU {s['cpu']:.0f}% RAM {s['ram']:.0f}%",
                                next_action="sampling every 5s")
                tick += 1
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                return
            except Exception:  # noqa: BLE001
                await asyncio.sleep(5)
