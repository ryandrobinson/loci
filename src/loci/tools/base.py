"""Shared types for tool handlers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from ..memory.okf import Bundle
from ..sandbox import Sandbox
from ..safety import ReadCache
from ..ui import UI


class ToolError(Exception):
    """A tool failure that should be reported back to the model as an error
    tool_result (not a crash). Carries a human-readable message."""


@dataclass
class ToolContext:
    sandbox: Sandbox
    read_cache: ReadCache
    ui: UI
    local_bundle: Bundle
    global_bundle: Bundle
    now: Callable[[], str]          # returns an ISO 8601 timestamp
    dry_run: bool = False

    def bundle(self, scope: str) -> Bundle:
        if scope == "local":
            return self.local_bundle
        if scope == "global":
            return self.global_bundle
        raise ToolError(f"unknown memory scope {scope!r} (use 'local' or 'global')")
