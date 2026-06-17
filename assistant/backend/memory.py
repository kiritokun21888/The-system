"""Obsidian-style memory vault.

Creates the folder structure, logs every interaction, stores agent outputs as
markdown, and provides retrieval (search across conversations / research / etc.)
so agents "remember" prior context.
"""

from __future__ import annotations

import os
import re
import time
from datetime import datetime
from typing import Any, Optional

from . import config

_SUBDIRS = [
    "routines", "research", "tasks", "conversations",
    "clipboard", "screenshots", "preferences",
]


def vault_root() -> str:
    """Resolve the vault root (config override or ./memory next to backend)."""
    cfg = config.load()
    override = cfg.get("vault_path") or ""
    root = override if override else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "memory"
    )
    return os.path.abspath(root)


def ensure_vault() -> str:
    """Create the vault folder structure; return the root path."""
    root = vault_root()
    for sub in _SUBDIRS:
        os.makedirs(os.path.join(root, sub), exist_ok=True)
    ctx = os.path.join(root, "context.md")
    if not os.path.exists(ctx):
        with open(ctx, "w", encoding="utf-8") as fh:
            fh.write("# Running Context\n\nThis file summarizes everything the system knows.\n")
    return root


def _slug(text: str) -> str:
    """Filesystem-safe slug from text."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "note"


def log_conversation(command: str, action: str, result: str) -> str:
    """Append an interaction record to today's conversation log.

    Returns the path written to.
    """
    root = ensure_vault()
    day = datetime.now().strftime("%Y-%m-%d")
    path = os.path.join(root, "conversations", f"{day}.md")
    stamp = datetime.now().strftime("%H:%M:%S")
    entry = (
        f"\n### {stamp}\n"
        f"- **command:** {command}\n"
        f"- **action:** {action}\n"
        f"- **result:** {result}\n"
    )
    header_needed = not os.path.exists(path)
    with open(path, "a", encoding="utf-8") as fh:
        if header_needed:
            fh.write(f"# Conversations — {day}\n")
        fh.write(entry)
    return path


def save_note(subdir: str, title: str, content: str, tags: Optional[list[str]] = None) -> str:
    """Write a markdown note with frontmatter into a vault subdir; return path."""
    root = ensure_vault()
    os.makedirs(os.path.join(root, subdir), exist_ok=True)
    path = os.path.join(root, subdir, f"{_slug(title)}.md")
    now = datetime.now().isoformat()
    fm = (
        "---\n"
        f"title: {title}\n"
        f"category: {subdir}\n"
        f"tags: [{', '.join(tags or [])}]\n"
        f"created: {now}\n"
        "---\n\n"
    )
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(fm + content.strip() + "\n")
    return path


def search(query: str, subdir: Optional[str] = None) -> list[dict[str, Any]]:
    """Full-text search across the vault (optionally scoped to one subdir)."""
    root = ensure_vault()
    base = os.path.join(root, subdir) if subdir else root
    q = query.strip().lower()
    hits: list[dict[str, Any]] = []
    for dirpath, _dirs, files in os.walk(base):
        for name in files:
            if not name.endswith(".md"):
                continue
            full = os.path.join(dirpath, name)
            try:
                with open(full, "r", encoding="utf-8") as fh:
                    text = fh.read()
            except OSError:
                continue
            if not q or q in text.lower() or q in name.lower():
                rel = os.path.relpath(full, root)
                snippet = _snippet(text, q)
                hits.append({"path": rel, "title": name[:-3], "snippet": snippet,
                             "mtime": os.path.getmtime(full)})
    hits.sort(key=lambda h: h["mtime"], reverse=True)
    return hits


def _snippet(text: str, q: str) -> str:
    """Return a short snippet around the first match of ``q``."""
    if not q:
        return text.strip().replace("\n", " ")[:160]
    idx = text.lower().find(q)
    if idx < 0:
        return text.strip().replace("\n", " ")[:160]
    start = max(0, idx - 60)
    return ("…" + text[start:idx + 100].replace("\n", " ").strip() + "…")


def vault_size_bytes() -> int:
    """Total size of the vault in bytes (for the status bar)."""
    root = vault_root()
    total = 0
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(dirpath, name))
            except OSError:
                pass
    return total
