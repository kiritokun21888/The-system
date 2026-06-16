"""Robust JSON extraction from LLM responses.

Real models sometimes wrap JSON in prose or code fences; this finds and parses
the first balanced JSON object. The deterministic backend returns clean JSON, so
the fast path covers the offline case.
"""

from __future__ import annotations

import json
from typing import Any


def extract_json(text: str) -> dict[str, Any]:
    """Parse the first JSON object found in ``text``.

    Args:
        text: Raw model output.

    Returns:
        The parsed dict.

    Raises:
        ValueError: If no valid JSON object can be extracted.
    """
    text = text.strip()
    # Fast path: the whole string is JSON.
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    # Strip common code fences.
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            candidate = part
            if candidate.lstrip().startswith("json"):
                candidate = candidate.lstrip()[4:]
            try:
                result = json.loads(candidate.strip())
                if isinstance(result, dict):
                    return result
            except json.JSONDecodeError:
                continue

    # Scan for the first balanced {...} block.
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : i + 1]
                    try:
                        result = json.loads(candidate)
                        if isinstance(result, dict):
                            return result
                    except json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)

    raise ValueError("no JSON object found in model response")
