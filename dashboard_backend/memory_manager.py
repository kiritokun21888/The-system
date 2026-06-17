"""Obsidian-style markdown memory vault manager.

Indexes a folder of ``.md`` files (each with YAML frontmatter), watches it for
changes with ``watchdog``, and exposes the data the dashboard needs:

  * list / get / create / update / delete memories
  * full-text search across content + titles + tags
  * a graph (nodes + edges) for the Obsidian-style graph view, where edges come
    from explicit ``linked`` frontmatter ids AND from shared tags.

Frontmatter schema per file::

    ---
    id: uuid
    title: Memory title
    category: technical | project | task | preference
    tags: [tag1, tag2]
    importance: 1-10
    created: ISO date
    updated: ISO date
    linked: [other-file-ids]
    ---
    Markdown body...
"""

from __future__ import annotations

import os
import re
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Optional

import yaml

_CATEGORY_DIR = {
    "technical": "technical",
    "project": "projects",
    "task": "tasks",
    "preference": "preferences",
}

# Stable colour per category (mirrors the frontend design system).
CATEGORY_COLOR = {
    "technical": "#00D2FF",
    "project": "#7B2FFF",
    "task": "#00FF88",
    "preference": "#FF9500",
    "error": "#FF3366",
}

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)


def _now() -> str:
    """Return an ISO-8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


class MemoryManager:
    """Indexes and mutates an Obsidian-style markdown vault."""

    def __init__(self, vault_path: str, on_change: Optional[Callable[[], None]] = None) -> None:
        """Create the manager.

        Args:
            vault_path: Root folder of the vault.
            on_change: Optional callback fired (debounced) when files change on
                disk — used to broadcast ``memory_update`` over the WebSocket.
        """
        self.vault_path = os.path.abspath(vault_path)
        self._on_change = on_change
        self._lock = threading.RLock()
        self._memories: dict[str, dict[str, Any]] = {}
        for sub in _CATEGORY_DIR.values():
            os.makedirs(os.path.join(self.vault_path, sub), exist_ok=True)
        self.reindex()

    # ------------------------------------------------------------------ #
    # Parsing / indexing
    # ------------------------------------------------------------------ #
    def _parse_file(self, path: str) -> Optional[dict[str, Any]]:
        """Parse a single markdown file into a memory record (or None)."""
        try:
            with open(path, "r", encoding="utf-8") as fh:
                raw = fh.read()
        except OSError:
            return None
        match = _FRONTMATTER_RE.match(raw)
        if not match:
            return None
        try:
            meta = yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError:
            return None
        body = match.group(2).strip()
        mem_id = str(meta.get("id") or os.path.splitext(os.path.basename(path))[0])
        return {
            "id": mem_id,
            "title": str(meta.get("title", "Untitled")),
            "category": str(meta.get("category", "technical")),
            "tags": [str(t) for t in (meta.get("tags", []) or [])],
            "importance": int(meta.get("importance", 5)),
            # YAML may parse ISO timestamps into datetime objects; keep strings
            # so the records are always JSON-serializable for the WebSocket.
            "created": str(meta.get("created", _now())),
            "updated": str(meta.get("updated", _now())),
            "linked": [str(x) for x in (meta.get("linked", []) or [])],
            "content": body,
            "path": path,
        }

    def reindex(self) -> None:
        """Rescan the entire vault from disk."""
        with self._lock:
            self._memories.clear()
            for root, _dirs, files in os.walk(self.vault_path):
                for name in files:
                    if not name.endswith(".md") or name == "index.md":
                        continue
                    rec = self._parse_file(os.path.join(root, name))
                    if rec:
                        self._memories[rec["id"]] = rec
            self._write_index()

    def _write_index(self) -> None:
        """Regenerate index.md listing every memory (auto-updated)."""
        lines = ["# Memory Vault Index", "", f"_Updated {_now()}_", ""]
        by_cat: dict[str, list[dict[str, Any]]] = {}
        for mem in self._memories.values():
            by_cat.setdefault(mem["category"], []).append(mem)
        for cat in sorted(by_cat):
            lines.append(f"## {cat.title()}")
            for mem in sorted(by_cat[cat], key=lambda m: -m["importance"]):
                tags = " ".join(f"#{t}" for t in mem["tags"])
                lines.append(f"- **{mem['title']}** (imp {mem['importance']}) {tags}")
            lines.append("")
        try:
            with open(os.path.join(self.vault_path, "index.md"), "w", encoding="utf-8") as fh:
                fh.write("\n".join(lines))
        except OSError:
            pass

    def notify_change(self) -> None:
        """Reindex and fire the change callback (called by the watcher)."""
        self.reindex()
        if self._on_change:
            self._on_change()

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #
    def list_memories(self) -> list[dict[str, Any]]:
        """Return all memories (metadata only, no path) sorted by importance."""
        with self._lock:
            out = [self._public(m) for m in self._memories.values()]
        return sorted(out, key=lambda m: (-m["importance"], m["title"]))

    def get(self, mem_id: str) -> Optional[dict[str, Any]]:
        """Return a single memory by id (with content)."""
        with self._lock:
            mem = self._memories.get(mem_id)
            return self._public(mem) if mem else None

    @staticmethod
    def _public(mem: dict[str, Any]) -> dict[str, Any]:
        """Strip the on-disk path from a record for API responses."""
        return {k: v for k, v in mem.items() if k != "path"}

    def search(self, query: str) -> list[dict[str, Any]]:
        """Case-insensitive substring search over title, tags, and content."""
        q = query.strip().lower()
        if not q:
            return self.list_memories()
        with self._lock:
            hits = []
            for mem in self._memories.values():
                haystack = " ".join(
                    [mem["title"], " ".join(mem["tags"]), mem["content"]]
                ).lower()
                if q in haystack:
                    hits.append(self._public(mem))
        return sorted(hits, key=lambda m: -m["importance"])

    def graph(self) -> dict[str, Any]:
        """Build the node/edge graph for the Obsidian-style view.

        Edges are created from explicit ``linked`` ids and, additionally,
        between any two memories that share at least one tag.
        """
        with self._lock:
            mems = list(self._memories.values())
        nodes = [
            {
                "id": m["id"],
                "title": m["title"],
                "category": m["category"],
                "color": CATEGORY_COLOR.get(m["category"], "#00D2FF"),
                "importance": m["importance"],
                "tags": m["tags"],
            }
            for m in mems
        ]
        ids = {m["id"] for m in mems}
        edges: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()

        def add_edge(a: str, b: str, kind: str) -> None:
            if a == b or a not in ids or b not in ids:
                return
            key = tuple(sorted((a, b)))
            if key in seen:
                return
            seen.add(key)
            edges.append({"id": f"{key[0]}__{key[1]}", "source": key[0],
                          "target": key[1], "kind": kind})

        for m in mems:
            for linked in m["linked"]:
                add_edge(m["id"], linked, "explicit")
        # Shared-tag edges.
        by_tag: dict[str, list[str]] = {}
        for m in mems:
            for tag in m["tags"]:
                by_tag.setdefault(tag, []).append(m["id"])
        for members in by_tag.values():
            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    add_edge(members[i], members[j], "tag")
        return {"nodes": nodes, "edges": edges}

    def all_tags(self) -> list[str]:
        """Return the sorted set of all tags in the vault."""
        with self._lock:
            tags: set[str] = set()
            for m in self._memories.values():
                tags.update(m["tags"])
        return sorted(tags)

    # ------------------------------------------------------------------ #
    # Mutations
    # ------------------------------------------------------------------ #
    def _path_for(self, mem_id: str, category: str, title: str) -> str:
        """Compute the on-disk path for a memory."""
        sub = _CATEGORY_DIR.get(category, "technical")
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:48] or mem_id[:8]
        return os.path.join(self.vault_path, sub, f"{slug}-{mem_id[:8]}.md")

    def _serialize(self, mem: dict[str, Any]) -> str:
        """Render a memory record back to frontmatter + body."""
        meta = {
            "id": mem["id"],
            "title": mem["title"],
            "category": mem["category"],
            "tags": mem["tags"],
            "importance": mem["importance"],
            "created": mem["created"],
            "updated": mem["updated"],
            "linked": mem["linked"],
        }
        fm = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True).strip()
        return f"---\n{fm}\n---\n\n{mem['content'].strip()}\n"

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a new memory file and return its record."""
        mem_id = str(uuid.uuid4())
        rec = {
            "id": mem_id,
            "title": data.get("title", "Untitled"),
            "category": data.get("category", "technical"),
            "tags": list(data.get("tags", []) or []),
            "importance": int(data.get("importance", 5)),
            "created": _now(),
            "updated": _now(),
            "linked": [str(x) for x in (data.get("linked", []) or [])],
            "content": data.get("content", ""),
        }
        path = self._path_for(mem_id, rec["category"], rec["title"])
        rec["path"] = path
        with self._lock:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self._serialize(rec))
            self._memories[mem_id] = rec
            self._write_index()
        return self._public(rec)

    def update(self, mem_id: str, data: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Update an existing memory and return the new record."""
        with self._lock:
            mem = self._memories.get(mem_id)
            if not mem:
                return None
            for field in ("title", "category", "tags", "importance", "content", "linked"):
                if field in data and data[field] is not None:
                    mem[field] = data[field]
            mem["importance"] = int(mem["importance"])
            mem["tags"] = list(mem["tags"])
            mem["linked"] = [str(x) for x in mem["linked"]]
            mem["updated"] = _now()
            with open(mem["path"], "w", encoding="utf-8") as fh:
                fh.write(self._serialize(mem))
            self._write_index()
            return self._public(mem)

    def delete(self, mem_id: str) -> bool:
        """Delete a memory file. Returns True if it existed."""
        with self._lock:
            mem = self._memories.pop(mem_id, None)
            if not mem:
                return False
            try:
                os.remove(mem["path"])
            except OSError:
                pass
            self._write_index()
            return True
