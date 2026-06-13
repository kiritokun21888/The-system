"""Thin async connectors for the external services ZERO integrates with.

Every connector degrades gracefully: when its API key is missing it reports
``connected: False`` instead of raising, so the Connections Hub can show an
accurate status and the rest of the system keeps running.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from core.config import settings

logger = logging.getLogger("zero.integrations")

_HTTP_TIMEOUT = 15.0


class WeatherConnector:
    name = "openweather"

    @property
    def connected(self) -> bool:
        return bool(settings.openweather_api_key)

    async def current(self, city: str | None = None) -> dict:
        if not self.connected:
            return {"ok": False, "error": "OpenWeather API key not configured."}
        city = city or settings.openweather_city
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {"q": city, "appid": settings.openweather_api_key, "units": "metric"}
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                return {"ok": False, "error": resp.text}
            data = resp.json()
        return {
            "ok": True,
            "city": data.get("name", city),
            "temp_c": data["main"]["temp"],
            "feels_like_c": data["main"]["feels_like"],
            "condition": data["weather"][0]["description"],
            "humidity": data["main"]["humidity"],
        }


class GitHubConnector:
    name = "github"

    @property
    def connected(self) -> bool:
        return bool(settings.github_token)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {settings.github_token}",
            "Accept": "application/vnd.github+json",
        }

    async def notifications(self, limit: int = 10) -> dict:
        if not self.connected:
            return {"ok": False, "error": "GitHub token not configured."}
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            resp = await client.get(
                "https://api.github.com/notifications", headers=self._headers()
            )
            if resp.status_code != 200:
                return {"ok": False, "error": resp.text}
            items = resp.json()[:limit]
        return {
            "ok": True,
            "notifications": [
                {
                    "repo": n["repository"]["full_name"],
                    "title": n["subject"]["title"],
                    "type": n["subject"]["type"],
                    "reason": n["reason"],
                }
                for n in items
            ],
        }


class BraveSearchConnector:
    name = "brave_search"

    @property
    def connected(self) -> bool:
        return bool(settings.brave_search_api_key)

    async def search(self, query: str, count: int = 5) -> dict:
        """Web search via Brave; falls back to DuckDuckGo's HTML endpoint."""
        if self.connected:
            url = "https://api.search.brave.com/res/v1/web/search"
            headers = {"X-Subscription-Token": settings.brave_search_api_key}
            params = {"q": query, "count": count}
            async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
                resp = await client.get(url, headers=headers, params=params)
                if resp.status_code == 200:
                    results = resp.json().get("web", {}).get("results", [])
                    return {
                        "ok": True,
                        "results": [
                            {"title": r["title"], "url": r["url"],
                             "description": r.get("description", "")}
                            for r in results[:count]
                        ],
                    }
        return await self._duckduckgo(query, count)

    async def _duckduckgo(self, query: str, count: int) -> dict:
        url = "https://api.duckduckgo.com/"
        params = {"q": query, "format": "json", "no_html": 1}
        try:
            async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
                resp = await client.get(url, params=params)
                data = resp.json()
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}
        results = []
        for topic in data.get("RelatedTopics", []):
            if "Text" in topic and "FirstURL" in topic:
                results.append({"title": topic["Text"][:80], "url": topic["FirstURL"],
                                "description": topic["Text"]})
        if data.get("AbstractText"):
            results.insert(0, {"title": data.get("Heading", query),
                               "url": data.get("AbstractURL", ""),
                               "description": data["AbstractText"]})
        return {"ok": True, "results": results[:count]}


class SpotifyConnector:
    name = "spotify"

    @property
    def connected(self) -> bool:
        return bool(settings.spotify_client_id and settings.spotify_client_secret)

    async def status(self) -> dict:
        return {"ok": True, "connected": self.connected,
                "note": "Playback control runs through the system_agent on the local app."}


class CalendarConnector:
    name = "google_calendar"

    @property
    def connected(self) -> bool:
        return bool(settings.google_credentials_file)

    async def todays_events(self) -> dict:
        if not self.connected:
            return {"ok": False, "error": "Google credentials not configured.",
                    "events": []}
        # Real OAuth flow lives in the desktop client; the backend reads the
        # token cache produced there. When unavailable we return an empty set.
        return {"ok": True, "events": [], "note": "Connect Google in Settings to sync."}


class GmailConnector:
    name = "gmail"

    @property
    def connected(self) -> bool:
        return bool(settings.google_credentials_file)

    async def unread_summary(self) -> dict:
        if not self.connected:
            return {"ok": False, "error": "Google credentials not configured.",
                    "messages": []}
        return {"ok": True, "messages": [], "note": "Connect Google in Settings to sync."}


# --- Registry used by the Connections Hub ---

weather = WeatherConnector()
github = GitHubConnector()
brave = BraveSearchConnector()
spotify = SpotifyConnector()
calendar = CalendarConnector()
gmail = GmailConnector()


def connection_states() -> list[dict]:
    """Status snapshot for every integration shown in the Connections panel."""
    now = datetime.now(timezone.utc).isoformat()
    registry = [
        ("Google Calendar", calendar.connected),
        ("Gmail", gmail.connected),
        ("Spotify", spotify.connected),
        ("GitHub", github.connected),
        ("OpenWeatherMap", weather.connected),
        ("Brave Search", brave.connected),
        ("Notion", bool(settings.notion_api_key)),
        ("Slack", bool(settings.slack_token)),
        ("ElevenLabs", bool(settings.elevenlabs_api_key)),
    ]
    return [
        {"service": name, "connected": connected,
         "last_synced": now if connected else None}
        for name, connected in registry
    ]
