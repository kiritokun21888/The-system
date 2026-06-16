"""Caching layer with per-key TTL.

Any agent that receives identical inputs returns a cached output instead of
recomputing. Keys are derived from (agent_name + a stable hash of the inputs).
TTL is configurable per agent. The cache is also used by the LLM layer to cache
repeated prompts for token/cost optimization.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class _Entry:
    """A single cached value with an expiry timestamp."""

    value: Any
    expires_at: float


class TTLCache:
    """A thread-safe in-memory cache with per-entry TTL and LRU-ish eviction.

    For distributed deployments this can be replaced by Redis with the same
    ``get`` / ``set`` interface.
    """

    def __init__(self, max_entries: int = 1024) -> None:
        """Create a cache.

        Args:
            max_entries: Soft cap; oldest entries are evicted past this.
        """
        self._lock = threading.Lock()
        self._store: dict[str, _Entry] = {}
        self._max_entries = max_entries
        self.hits = 0
        self.misses = 0

    @staticmethod
    def make_key(namespace: str, payload: Any) -> str:
        """Build a stable cache key from a namespace and an arbitrary payload.

        The payload is serialized with sorted keys so logically-identical inputs
        always hash the same (no silent cache misses from key ordering).

        Args:
            namespace: Logical namespace (usually the agent name + stage).
            payload: Any JSON-serializable structure.

        Returns:
            A hex digest cache key.
        """
        blob = json.dumps(payload, sort_keys=True, default=str)
        digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()
        return f"{namespace}:{digest}"

    def get(self, key: str) -> Optional[Any]:
        """Return the cached value for ``key`` if present and unexpired."""
        now = time.time()
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self.misses += 1
                return None
            if entry.expires_at < now:
                # Expired: evict and miss.
                del self._store[key]
                self.misses += 1
                return None
            self.hits += 1
            return entry.value

    def set(self, key: str, value: Any, ttl_seconds: float) -> None:
        """Store ``value`` under ``key`` for ``ttl_seconds``.

        A ttl <= 0 disables caching for that entry (never stored).
        """
        if ttl_seconds <= 0:
            return
        with self._lock:
            if len(self._store) >= self._max_entries:
                self._evict_oldest_locked()
            self._store[key] = _Entry(value=value, expires_at=time.time() + ttl_seconds)

    def _evict_oldest_locked(self) -> None:
        """Evict the entry with the soonest expiry (caller holds the lock)."""
        if not self._store:
            return
        oldest = min(self._store.items(), key=lambda kv: kv[1].expires_at)[0]
        del self._store[oldest]

    def clear(self) -> None:
        """Empty the cache and reset counters."""
        with self._lock:
            self._store.clear()
            self.hits = 0
            self.misses = 0

    def stats(self) -> dict[str, Any]:
        """Return hit/miss statistics."""
        with self._lock:
            total = self.hits + self.misses
            return {
                "size": len(self._store),
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate": round(self.hits / total, 4) if total else 0.0,
            }
