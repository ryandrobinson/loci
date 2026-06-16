"""run_shell — the largest blast radius. Always shown, always waits.

The agent loop shows the exact command and gets an explicit y/N before this is
ever called, and refuses entirely when run_shell is disabled in config. Here we
just execute (or, under --dry-run, describe) inside the sandbox root.
"""

from __future__ import annotations

import subprocess

from .base import ToolContext, ToolError

SHELL_TIMEOUT = 120          # seconds
OUTPUT_LIMIT = 20_000        # characters of combined output returned


def run_shell(ctx: ToolContext, command: str) -> str:
    if not command or not command.strip():
        raise ToolError("empty command")
    if ctx.dry_run:
        return f"[dry-run] would run: {command}"
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=str(ctx.sandbox.root),
            capture_output=True,
            text=True,
            timeout=SHELL_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        raise ToolError(f"command timed out after {SHELL_TIMEOUT}s")
    out = (proc.stdout or "") + (proc.stderr or "")
    if len(out) > OUTPUT_LIMIT:
        out = out[:OUTPUT_LIMIT] + f"\n... [truncated at {OUTPUT_LIMIT} chars]"
    return f"exit {proc.returncode}\n{out}".rstrip()


def plan_shell(inp):
    return ("run", inp.get("command"), None)
