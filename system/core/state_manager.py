"""Task state persistence.

All task state lives in a central store so agents stay stateless and any worker
can resume any task (horizontal scaling). The default backend is SQLite; the
interface is deliberately tiny (``save`` / ``load`` / ``delete`` / ``all_ids``)
so it can be swapped for Redis without touching callers.

The system can be stopped and resumed without data loss: every state mutation
the orchestrator makes is followed by a ``save``.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Optional

from models.task import TaskState


class StateManager:
    """SQLite-backed persistence for :class:`TaskState`.

    Thread-safe via a lock plus per-connection usage. SQLite is opened with
    ``check_same_thread=False`` and guarded so the async event loop's executor
    threads can share it.
    """

    def __init__(self, db_path: str = "./swarm_state.db") -> None:
        """Open (and initialize) the state database.

        Args:
            db_path: Path to the SQLite file. Use ":memory:" for ephemeral state.
        """
        self._db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS task_state (
                task_id TEXT PRIMARY KEY,
                status  TEXT NOT NULL,
                data    TEXT NOT NULL,
                updated REAL NOT NULL
            )
            """
        )
        self._conn.commit()

    def save(self, state: TaskState) -> None:
        """Persist (insert or replace) a task state.

        Args:
            state: The state to persist.
        """
        blob = json.dumps(state.to_dict(), default=str)
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO task_state (task_id, status, data, updated) "
                "VALUES (?, ?, ?, ?)",
                (state.task.task_id, state.status.value, blob, state.updated_at),
            )
            self._conn.commit()

    def load(self, task_id: str) -> Optional[TaskState]:
        """Load a task state by id, or ``None`` if absent.

        Args:
            task_id: The task id.

        Returns:
            The reconstructed :class:`TaskState` or ``None``.
        """
        with self._lock:
            cur = self._conn.execute(
                "SELECT data FROM task_state WHERE task_id = ?", (task_id,)
            )
            row = cur.fetchone()
        if row is None:
            return None
        return TaskState.from_dict(json.loads(row[0]))

    def delete(self, task_id: str) -> None:
        """Delete a task state by id."""
        with self._lock:
            self._conn.execute("DELETE FROM task_state WHERE task_id = ?", (task_id,))
            self._conn.commit()

    def all_ids(self, status: Optional[str] = None) -> list[str]:
        """Return all task ids, optionally filtered by status.

        Args:
            status: If given, only ids with this status are returned.

        Returns:
            A list of task ids.
        """
        with self._lock:
            if status is None:
                cur = self._conn.execute("SELECT task_id FROM task_state")
            else:
                cur = self._conn.execute(
                    "SELECT task_id FROM task_state WHERE status = ?", (status,)
                )
            return [r[0] for r in cur.fetchall()]

    def resumable_ids(self) -> list[str]:
        """Return ids of tasks that were mid-flight and can be resumed.

        Tasks left RUNNING / AWAITING_RETRY / CHECKPOINTED when the process
        stopped are resumable; COMPLETED / ABORTED / ESCALATED are terminal.
        """
        resumable = {"running", "awaiting_retry", "checkpointed", "queued"}
        return [tid for tid in self.all_ids() if (self.load(tid) and
                self.load(tid).status.value in resumable)]  # type: ignore[union-attr]

    def close(self) -> None:
        """Close the underlying connection."""
        with self._lock:
            self._conn.close()
