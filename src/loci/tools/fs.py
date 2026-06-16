"""Filesystem tools. Every path resolves through the cwd sandbox.

Confirmation/plan gating lives in the agent loop (it knows about batches); these
handlers assume permission has already been granted and only enforce tool-level
preconditions (sandbox boundary, read-before-write) and --dry-run.
"""

from __future__ import annotations

import fnmatch
import os
import re
import shutil
from pathlib import Path

from ..sandbox import SandboxError
from .base import ToolContext, ToolError

READ_LIMIT = 100_000          # characters returned by read_file
SEARCH_MAX_RESULTS = 200      # match lines returned by search_text
SEARCH_MAX_FILE_BYTES = 2_000_000
FIND_MAX_RESULTS = 500
# Noise directories skipped by recursive search/find.
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", ".mypy_cache",
             ".pytest_cache"}


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


def delete_file(ctx: ToolContext, path: str) -> str:
    target = _resolve(ctx, path)
    rel = ctx.sandbox.relative(target)
    if not target.exists():
        raise ToolError(f"no such file: {path}")
    if target.is_dir():
        raise ToolError(f"is a directory (delete files individually): {path}")
    if ctx.dry_run:
        return f"[dry-run] would delete {rel}"
    target.unlink()
    return f"deleted {rel}"


def edit_file(ctx: ToolContext, path: str, old: str, new: str,
             replace_all: bool = False) -> str:
    """Replace `old` with `new` in an existing file. `old` must be unique unless
    replace_all is set. Read-before-write applies, as with write_file."""
    target = _resolve(ctx, path)
    rel = ctx.sandbox.relative(target)
    if not target.exists():
        raise ToolError(f"no such file: {path}")
    if target.is_dir():
        raise ToolError(f"is a directory: {path}")
    if not ctx.read_cache.was_read(target):
        raise ToolError(f"read-before-write: call read_file({rel!r}) before editing it")
    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise ToolError(f"not a UTF-8 text file: {path}")
    count = content.count(old)
    if count == 0:
        raise ToolError(f"old text not found in {rel}")
    if count > 1 and not replace_all:
        raise ToolError(
            f"old text appears {count}× in {rel}; pass replace_all=true or include "
            "more surrounding context to make it unique"
        )
    n = count if replace_all else 1
    if ctx.dry_run:
        return f"[dry-run] would make {n} replacement(s) in {rel}"
    updated = content.replace(old, new) if replace_all else content.replace(old, new, 1)
    target.write_text(updated, encoding="utf-8")
    ctx.read_cache.mark_read(target)
    return f"edited {rel} ({n} replacement(s))"


def search_text(ctx: ToolContext, pattern: str, subdir: str = ".",
               glob: str = None, ignore_case: bool = False) -> str:
    """Search file contents (regex) under subdir, grep-style. Read-only."""
    root = _resolve(ctx, subdir)
    if not root.is_dir():
        raise ToolError(f"not a directory: {subdir}")
    try:
        rx = re.compile(pattern, re.IGNORECASE if ignore_case else 0)
    except re.error as e:
        raise ToolError(f"invalid regex: {e}")
    matches = []
    truncated = False
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in sorted(filenames):
            if glob and not fnmatch.fnmatch(fn, glob):
                continue
            fp = Path(dirpath) / fn
            try:
                if fp.stat().st_size > SEARCH_MAX_FILE_BYTES:
                    continue
                text = fp.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue  # skip binaries / unreadable files
            for i, line in enumerate(text.splitlines(), 1):
                if rx.search(line):
                    rel = ctx.sandbox.relative(fp)
                    matches.append(f"{rel}:{i}: {line.strip()[:200]}")
                    if len(matches) >= SEARCH_MAX_RESULTS:
                        truncated = True
                        break
            if truncated:
                break
        if truncated:
            break
    if not matches:
        return f"no matches for {pattern!r}"
    out = "\n".join(matches)
    return out + (f"\n... [stopped at {SEARCH_MAX_RESULTS} matches]" if truncated else "")


def find_files(ctx: ToolContext, pattern: str = "*", subdir: str = ".") -> str:
    """Find files by name glob (e.g. '*.py') recursively under subdir. Read-only."""
    root = _resolve(ctx, subdir)
    if not root.is_dir():
        raise ToolError(f"not a directory: {subdir}")
    results = []
    truncated = False
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fnmatch.fnmatch(fn, pattern):
                results.append(ctx.sandbox.relative(Path(dirpath) / fn))
                if len(results) >= FIND_MAX_RESULTS:
                    truncated = True
                    break
        if truncated:
            break
    if not results:
        return f"no files matching {pattern!r}"
    out = "\n".join(sorted(results))
    return out + (f"\n... [stopped at {FIND_MAX_RESULTS}]" if truncated else "")


# Plan rows for batch display (action, source, target). target=None for in-place.
def plan_write(inp):   return ("write", inp.get("path"), None)
def plan_rename(inp):  return ("rename", inp.get("src"), inp.get("dst"))
def plan_move(inp):    return ("move", inp.get("src"), inp.get("dst"))
def plan_delete(inp):  return ("delete", inp.get("path"), None)
def plan_edit(inp):    return ("edit", inp.get("path"), None)
