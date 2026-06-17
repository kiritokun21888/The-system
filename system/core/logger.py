"""Structured logging.

Emits either JSON lines (machine-readable, for audit trails) or human text.
Every routing decision, failure, and agent invocation is logged through here so
the system has a complete audit trail.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from typing import Any, Optional


class _JsonFormatter(logging.Formatter):
    """Format log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        """Render a record as a JSON line, merging any ``extra`` fields."""
        payload: dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Merge structured fields attached via logger.<level>(..., extra={"fields": {...}}).
        fields = getattr(record, "fields", None)
        if isinstance(fields, dict):
            payload.update(fields)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def get_logger(
    name: str,
    level: str = "INFO",
    fmt: str = "json",
    file: Optional[str] = None,
    console: bool = True,
) -> logging.Logger:
    """Create or fetch a configured logger.

    Args:
        name: Logger name.
        level: Logging level string (e.g. "INFO", "DEBUG").
        fmt: "json" or "text".
        file: Optional file path to also write logs to.
        console: When False, no stderr handler is attached (logs go to the file
            only). Used so the live dashboard owns the terminal.

    Returns:
        A configured ``logging.Logger`` (idempotent across calls).
    """
    logger = logging.getLogger(name)
    if getattr(logger, "_swarm_configured", False):
        return logger

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.handlers.clear()

    if fmt == "json":
        formatter: logging.Formatter = _JsonFormatter()
    else:
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    if console:
        stream = logging.StreamHandler(sys.stderr)
        stream.setFormatter(formatter)
        logger.addHandler(stream)

    if file:
        fh = logging.FileHandler(file)
        fh.setFormatter(formatter)
        logger.addHandler(fh)

    # Always keep at least one handler so records aren't dropped with a warning.
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())

    logger.propagate = False
    logger._swarm_configured = True  # type: ignore[attr-defined]
    return logger


def log_event(logger: logging.Logger, level: str, msg: str, **fields: Any) -> None:
    """Log a structured event with arbitrary key/value fields.

    Args:
        logger: Target logger.
        level: Level name ("info", "warning", "error", "debug").
        msg: Human-readable message.
        **fields: Structured fields included in the JSON payload.
    """
    log_fn = getattr(logger, level.lower(), logger.info)
    log_fn(msg, extra={"fields": fields})
