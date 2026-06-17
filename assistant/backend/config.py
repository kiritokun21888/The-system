"""Persistent JSON configuration for the assistant.

Stored in ``config.json`` next to the backend. Every setting the Settings panel
edits lives here and is applied immediately.
"""

from __future__ import annotations

import json
import os
import threading
from typing import Any

_DEFAULTS: dict[str, Any] = {
    "wake_word": "hey system",
    "voice": {"enabled": True, "rate": 175, "volume": 1.0, "voice_index": 0},
    "morning_briefing": {"enabled": True, "time": "08:30"},
    "agents": {
        "routine": True,
        "research": True,
        "reminder": True,
        "task": True,
        "file_watcher": True,
        "clipboard": True,
        "health": True,
        "morning_briefing": True,
    },
    "app_paths": {},  # user overrides: {"spotify": "C:/.../Spotify.exe"}
    "accent": "#00D2FF",
    "vault_path": "",  # empty -> default ./memory next to backend
    "watch_folders": [],  # empty -> auto Desktop + Downloads
    "confirm_destructive": True,
}

_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
_lock = threading.RLock()


def _deep_merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge ``over`` into a copy of ``base``."""
    out = dict(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load() -> dict[str, Any]:
    """Load config from disk, merged over defaults (creates the file if absent)."""
    with _lock:
        data: dict[str, Any] = {}
        if os.path.exists(_CONFIG_PATH):
            try:
                with open(_CONFIG_PATH, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
            except (OSError, json.JSONDecodeError):
                data = {}
        merged = _deep_merge(_DEFAULTS, data)
        if not os.path.exists(_CONFIG_PATH):
            save(merged)
        return merged


def save(cfg: dict[str, Any]) -> dict[str, Any]:
    """Persist the full config dict to disk and return it."""
    with _lock:
        with open(_CONFIG_PATH, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, indent=2)
        return cfg


def update(patch: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge a partial patch into the saved config and persist it."""
    with _lock:
        merged = _deep_merge(load(), patch)
        return save(merged)
