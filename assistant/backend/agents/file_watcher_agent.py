"""File watcher agent — watches Desktop + Downloads for new files.

When a new file appears it categorizes it by extension and emits a dismissable
suggestion (e.g. "You downloaded invoice.pdf — move to Documents/Invoices?").
"""

from __future__ import annotations

import asyncio
import os
from typing import Any, Optional

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from ..events import bus
from .base import Agent

_CATEGORY = {
    ".pdf": "Documents", ".docx": "Documents", ".txt": "Documents",
    ".jpg": "Pictures", ".jpeg": "Pictures", ".png": "Pictures", ".gif": "Pictures",
    ".mp4": "Videos", ".mov": "Videos",
    ".mp3": "Music", ".wav": "Music",
    ".zip": "Archives", ".rar": "Archives", ".7z": "Archives",
    ".exe": "Installers", ".msi": "Installers",
    ".csv": "Data", ".xlsx": "Data", ".json": "Data",
}


def _watch_dirs(cfg: dict[str, Any]) -> list[str]:
    """Resolve folders to watch (config override or Desktop+Downloads)."""
    folders = cfg.get("watch_folders") or []
    if folders:
        return [os.path.expanduser(f) for f in folders]
    home = os.path.expanduser("~")
    return [os.path.join(home, "Desktop"), os.path.join(home, "Downloads")]


class _Handler(FileSystemEventHandler):
    """Forwards new-file events to the agent."""

    def __init__(self, agent: "FileWatcherAgent") -> None:
        self._agent = agent

    def on_created(self, event: Any) -> None:
        if getattr(event, "is_directory", False):
            return
        self._agent.on_new_file(str(event.src_path))


class FileWatcherAgent(Agent):
    """Watches folders and suggests organization."""

    name = "file_watcher"

    def __init__(self) -> None:
        super().__init__()
        self._observer: Optional[Observer] = None

    def on_new_file(self, path: str) -> None:
        """Handle a newly created file (called from the watchdog thread)."""
        name = os.path.basename(path)
        ext = os.path.splitext(name)[1].lower()
        category = _CATEGORY.get(ext)
        body = (f"Move to {category}?" if category else "New file detected.")
        bus.broadcast_threadsafe("notification", {
            "title": f"New file: {name}", "body": body, "level": "info",
            "agent": "file_watcher", "action": {"type": "organize", "path": path,
                                                "category": category},
        })
        self.set_status("running", last_action=f"saw {name}")

    async def start(self) -> None:
        """Start watching the configured folders."""
        from .. import config

        dirs = [d for d in _watch_dirs(config.load()) if os.path.isdir(d)]
        if not dirs:
            self.set_status("idle", last_action="no watchable folders found")
            return
        self._observer = Observer()
        for d in dirs:
            self._observer.schedule(_Handler(self), d, recursive=False)
        self._observer.daemon = True
        self._observer.start()
        self.set_status("running", next_action=f"watching {len(dirs)} folders")
        try:
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            if self._observer:
                self._observer.stop()
            return
