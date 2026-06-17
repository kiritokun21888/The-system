"""Research agent — offline-keyless web research.

Uses DuckDuckGo (no API key) to find results, fetches the top pages with httpx,
extracts readable text with BeautifulSoup, builds an extractive summary, saves it
to the memory vault, and notifies the user (UI + voice).
"""

from __future__ import annotations

import asyncio
import re
from typing import Any, Callable, Optional

from .. import memory
from ..events import bus
from .base import Agent


def _ddgs():
    """Return a DDGS class from whichever package is installed."""
    try:
        from duckduckgo_search import DDGS  # older package name
        return DDGS
    except Exception:  # noqa: BLE001
        from ddgs import DDGS  # newer renamed package
        return DDGS


class ResearchAgent(Agent):
    """Searches, scrapes, summarizes, and saves research."""

    name = "research"

    def __init__(self, speak: Optional[Callable[[str], None]] = None) -> None:
        super().__init__()
        self._speak = speak

    async def research(self, topic: str) -> dict[str, Any]:
        """Run a full research pass on ``topic`` in the background."""
        self.set_status("running", last_action=f"Researching '{topic}'…")
        await self.emit()
        try:
            results = await asyncio.to_thread(self._search, topic, 3)
        except Exception as exc:  # noqa: BLE001
            self.set_status("error", last_action=f"Search failed: {exc}")
            return {"ok": False, "message": f"Search failed: {exc}"}

        if not results:
            self.set_status("idle", last_action="No results")
            return {"ok": False, "message": "No results found."}

        sections: list[str] = []
        for r in results:
            url = r.get("href") or r.get("url") or ""
            title = r.get("title", url)
            body = r.get("body", "")
            text = await self._fetch(url)
            summary = self._summarize(text or body, 5)
            sections.append(f"## {title}\n<{url}>\n\n{summary}\n")

        content = f"# Research: {topic}\n\n" + "\n".join(sections)
        path = memory.save_note("research", topic, content, tags=["research"])
        memory.log_conversation(f"research {topic}", "web research", f"saved {path}")
        self.set_status("idle", last_action=f"Saved research on '{topic}'")
        await self.emit()
        await bus.notify("Research complete", f"'{topic}' saved to memory", agent="research")
        if self._speak:
            try:
                self._speak(f"Research on {topic} is complete.")
            except Exception:  # noqa: BLE001
                pass
        return {"ok": True, "message": f"Research on '{topic}' saved.",
                "path": path, "summary": sections[0][:400] if sections else ""}

    def _search(self, topic: str, n: int) -> list[dict[str, Any]]:
        """Blocking DDG text search (run in a thread)."""
        DDGS = _ddgs()
        with DDGS() as ddgs:
            return list(ddgs.text(topic, max_results=n))

    async def _fetch(self, url: str) -> str:
        """Fetch and extract readable text from a page."""
        if not url:
            return ""
        try:
            import httpx
            from bs4 import BeautifulSoup

            async with httpx.AsyncClient(timeout=12, follow_redirects=True,
                                         headers={"User-Agent": "Mozilla/5.0"}) as client:
                resp = await client.get(url)
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            return re.sub(r"\s+", " ", soup.get_text(" ")).strip()
        except Exception:  # noqa: BLE001
            return ""

    @staticmethod
    def _summarize(text: str, sentences: int) -> str:
        """Extractive summary: the first few substantive sentences."""
        if not text:
            return "_(no readable content)_"
        parts = re.split(r"(?<=[.!?])\s+", text)
        good = [p.strip() for p in parts if len(p.strip()) > 40][:sentences]
        return " ".join(good) if good else text[:500]
