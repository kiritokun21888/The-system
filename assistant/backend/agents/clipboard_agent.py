"""Clipboard agent — monitors the clipboard and keeps a history.

Polls the clipboard, stores the last 50 distinct entries, and when a URL is
copied offers to research it (notification the UI can action).
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

from .. import db
from ..events import bus
from .base import Agent

_URL_RE = re.compile(r"^https?://\S+$")


class ClipboardAgent(Agent):
    """Tracks clipboard history."""

    name = "clipboard"

    def __init__(self) -> None:
        super().__init__()
        self._last = ""

    async def history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return clipboard history (newest first)."""
        return await db.list_clips(limit)

    async def start(self) -> None:
        """Poll the clipboard for changes."""
        try:
            import pyperclip

            pyperclip.paste()  # probe availability
        except Exception:  # noqa: BLE001
            self.set_status("error", last_action="clipboard unavailable on this OS")
            return
        self.set_status("running", next_action="watching clipboard")
        while True:
            try:
                import pyperclip

                current = pyperclip.paste()
                if current and current != self._last:
                    self._last = current
                    is_url = bool(_URL_RE.match(current.strip()))
                    await db.add_clip(current[:5000], is_url)
                    await bus.broadcast("clipboard_update",
                                        {"content": current[:300], "is_url": is_url})
                    if is_url:
                        await bus.notify("URL copied",
                                         f"Say 'research it' to summarize: {current[:60]}",
                                         agent="clipboard")
                    self.set_status("running", last_action="captured clip",
                                    next_action="watching clipboard")
                await asyncio.sleep(1.5)
            except asyncio.CancelledError:
                return
            except Exception:  # noqa: BLE001
                await asyncio.sleep(3)
