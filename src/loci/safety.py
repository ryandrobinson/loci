"""The safety model.

Invariants (documented in README "Safety" and CLAUDE.md, never to be weakened):

  - Read before write.
  - Any single destructive action needs an inline y/N confirm.
  - Any MULTI-file change prints a SHOWN PLAN first (the full source->target
    mapping) then ONE y/N for the whole batch. No silent batch mutations.
  - run_shell always shows the exact command and waits; never auto-executes.
  - --dry-run mutates nothing and only prints intended actions.
  - Confirms fail safe: anything but an explicit yes (including EOF) is a no.
"""

from __future__ import annotations

from typing import Callable, Iterable, Optional


def _default_reader() -> str:
    """Read one line of confirmation, preferring the controlling terminal.

    Reading /dev/tty means a y/N prompt still works even when loci's stdin is a
    pipe. EOF (Ctrl-D, closed tty) surfaces as EOFError -> a safe "no".
    """
    try:
        with open("/dev/tty", "r", encoding="utf-8") as tty:
            line = tty.readline()
    except OSError:
        line = input()  # fall back to stdin
    if line == "":
        raise EOFError
    return line


def confirm(prompt: str, reader: Optional[Callable[[], str]] = None) -> bool:
    """Return True only for an explicit yes. EOF or anything else is a no.

    `reader` is injectable so tests can drive the prompt deterministically.
    """
    read = reader or _default_reader
    try:
        answer = read()
    except EOFError:
        return False
    return answer.strip().lower() in ("y", "yes")


def render_plan(items: Iterable[tuple]) -> str:
    """Render a batch plan: a list of (action, source, target) rows.

    target may be None for actions like delete/write that have a single path.
    """
    lines = ["Planned changes:"]
    for action, source, target in items:
        if target:
            lines.append(f"  {action:<8} {source}  ->  {target}")
        else:
            lines.append(f"  {action:<8} {source}")
    return "\n".join(lines)


class ReadCache:
    """Tracks which paths have been read this process, enforcing read-before-write.

    A brand-new file (one that does not exist yet) needs no prior read.
    """

    def __init__(self):
        self._read: set = set()

    def mark_read(self, resolved_path) -> None:
        self._read.add(str(resolved_path))

    def was_read(self, resolved_path) -> bool:
        return str(resolved_path) in self._read
