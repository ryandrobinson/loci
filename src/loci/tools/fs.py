"""Filesystem tools. Every path resolves through the cwd sandbox.

Confirmation/plan gating lives in the agent loop (it knows about batches); these
handlers assume permission has already been granted and only enforce tool-level
preconditions (sandbox boundary, read-before-write) and --dry-run.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from ..sandbox import SandboxError
from .base import ToolContext, ToolError

READ_LIMIT = 100_000  # characters returned by read_file


def _resolve(ctx: ToolContext, path: str) -> Path:
    try:
        return ctx.sandbox.resolve(path)
    except SandboxError as e:
        raise ToolError(str(e))


def list_files(ctx: ToolContext, subdir: str = ".") -> str:
    target = _resolve(ctx, subdir)
    if not target.exists():
        raise ToolError(f"no such directory: {subdir}")
    if not target.is_dir():
        raise ToolError(f"not a directory: {subdir}")
    rows = []
    for entry in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name)):
        rows.append(f"{entry.name}/" if entry.is_dir() else entry.name)
    rel = ctx.sandbox.relative(target)
    header = f"{rel}/ ({len(rows)} entries)"
    return header + ("\n" + "\n".join(rows) if rows else "\n(empty)")


def read_file(ctx: ToolContext, path: str) -> str:
    target = _resolve(ctx, path)
    if not target.exists():
        raise ToolError(f"no such file: {path}")
    if target.is_dir():
        raise ToolError(f"is a directory: {path}")
    try:
        data = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise ToolError(f"not a UTF-8 text file: {path}")
    ctx.read_cache.mark_read(target)   # satisfies read-before-write
    if len(data) > READ_LIMIT:
        return data[:READ_LIMIT] + f"\n... [truncated at {READ_LIMIT} chars]"
    return data


def make_dir(ctx: ToolContext, path: str) -> str:
    target = _resolve(ctx, path)
    rel = ctx.sandbox.relative(target)
    if ctx.dry_run:
        return f"[dry-run] would create directory {rel}/"
    target.mkdir(parents=True, exist_ok=True)
    return f"created directory {rel}/"


def write_file(ctx: ToolContext, path: str, content: str) -> str:
    target = _resolve(ctx, path)
    rel = ctx.sandbox.relative(target)
    # Read before write: an existing file must have been read this session.
    if target.exists() and not ctx.read_cache.was_read(target):
        raise ToolError(
            f"read-before-write: call read_file({rel!r}) before overwriting it"
        )
    if ctx.dry_run:
        return f"[dry-run] would write {len(content)} chars to {rel}"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    ctx.read_cache.mark_read(target)   # now its contents are known
    return f"wrote {len(content)} chars to {rel}"


def rename_file(ctx: ToolContext, src: str, dst: str) -> str:
    source = _resolve(ctx, src)
    target = _resolve(ctx, dst)
    if not source.exists():
        raise ToolError(f"no such file: {src}")
    if target.exists():
        raise ToolError(f"target already exists: {dst}")
    if ctx.dry_run:
        return f"[dry-run] would rename {ctx.sandbox.relative(source)} -> {ctx.sandbox.relative(target)}"
    target.parent.mkdir(parents=True, exist_ok=True)
    source.rename(target)
    return f"renamed {ctx.sandbox.relative(source)} -> {ctx.sandbox.relative(target)}"


def move_file(ctx: ToolContext, src: str, dst: str) -> str:
    source = _resolve(ctx, src)
    target = _resolve(ctx, dst)
    if not source.exists():
        raise ToolError(f"no such file: {src}")
    if ctx.dry_run:
        return f"[dry-run] would move {ctx.sandbox.relative(source)} -> {ctx.sandbox.relative(target)}"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(target))
    return f"moved {ctx.sandbox.relative(source)} -> {ctx.sandbox.relative(target)}"


# Plan rows for batch display (action, source, target). target=None for writes.
def plan_write(inp):   return ("write", inp.get("path"), None)
def plan_rename(inp):  return ("rename", inp.get("src"), inp.get("dst"))
def plan_move(inp):    return ("move", inp.get("src"), inp.get("dst"))
