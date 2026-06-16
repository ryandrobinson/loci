"""Session memory — a lightweight rolling transcript on disk.

Ephemeral and recency-shaped, keyed to the terminal session (LOCI_SESSION) so
different windows hold different threads. Each // invocation loads recent turns,
appends, and trims to a token budget. This is NOT OKF — it is just the last
little while of conversation, stored as Anthropic message dicts.

  // :new     start a fresh session
  // :forget  wipe this session's transcript
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import List

from .. import config


def session_key() -> str:
    key = os.environ.get("LOCI_SESSION") or f"ppid-{os.getppid()}"
    # Keep it filesystem-safe.
    return re.sub(r"[^A-Za-z0-9._-]", "_", key)


def _estimate_tokens(messages: List[dict]) -> int:
    # Cheap heuristic: ~4 chars per token over the serialized content.
    return len(json.dumps(messages)) // 4


class Session:
    def __init__(self, key: str = None, budget: int = None):
        self.key = key or session_key()
        self.budget = budget or config.DEFAULT_SESSION_TOKEN_BUDGET
        self.path = config.sessions_dir() / f"{self.key}.json"

    def load(self) -> List[dict]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data.get("messages", [])
        except (json.JSONDecodeError, OSError):
            return []

    def save(self, messages: List[dict]) -> None:
        messages = self._trim(messages)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"messages": messages}, indent=2), encoding="utf-8"
        )

    def reset(self) -> None:
        """`:new` — start fresh by clearing this session's transcript."""
        self.save([])

    def forget(self) -> None:
        """`:forget` — wipe this session's transcript from disk."""
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass

    def _trim(self, messages: List[dict]) -> List[dict]:
        """Drop oldest messages until under budget, never orphaning a tool_result.

        A user message whose content leads with a tool_result must stay paired
        with the assistant tool_use that precedes it, so we always trim from the
        front in a way that leaves a clean, self-consistent prefix.
        """
        msgs = list(messages)
        while _estimate_tokens(msgs) > self.budget and len(msgs) > 1:
            msgs.pop(0)
            # Never let the transcript begin with an orphaned tool_result.
            while msgs and _leads_with_tool_result(msgs[0]):
                msgs.pop(0)
        return msgs


def _leads_with_tool_result(message: dict) -> bool:
    content = message.get("content")
    if isinstance(content, list) and content:
        first = content[0]
        return isinstance(first, dict) and first.get("type") == "tool_result"
    return False
