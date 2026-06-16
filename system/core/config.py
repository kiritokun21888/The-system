"""Configuration loader.

Loads ``config.yaml`` once and exposes typed, dotted access. No operational
value is hardcoded elsewhere — everything flows from here.
"""

from __future__ import annotations

import os
from typing import Any, Optional

import yaml


class Config:
    """Immutable view over the parsed YAML config with dotted lookups."""

    def __init__(self, data: dict[str, Any]) -> None:
        """Wrap an already-parsed config dict."""
        self._data = data

    @classmethod
    def load(cls, path: Optional[str] = None) -> "Config":
        """Load configuration from ``path`` (defaults to config.yaml next door).

        Args:
            path: Optional explicit path to the YAML file.

        Returns:
            A Config instance.
        """
        if path is None:
            path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        return cls(data or {})

    def get(self, dotted_key: str, default: Any = None) -> Any:
        """Fetch a value by dotted path, e.g. ``"router.max_retries"``.

        Args:
            dotted_key: Dotted path into the config tree.
            default: Value returned when the key is absent.

        Returns:
            The configured value, or ``default``.
        """
        node: Any = self._data
        for part in dotted_key.split("."):
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                return default
        return node

    def require(self, dotted_key: str) -> Any:
        """Fetch a value, raising ``KeyError`` if it is missing."""
        sentinel = object()
        value = self.get(dotted_key, sentinel)
        if value is sentinel:
            raise KeyError(f"Required config key missing: {dotted_key}")
        return value

    def agent_config(self, agent_name: str) -> dict[str, Any]:
        """Return the config block for a named agent."""
        agents = self.get("agents", {})
        if agent_name not in agents:
            raise KeyError(f"No config for agent '{agent_name}'")
        return agents[agent_name]

    @property
    def raw(self) -> dict[str, Any]:
        """The underlying parsed dict."""
        return self._data
