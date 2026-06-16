"""TokyoNight ANSI styling — zero dependencies, no TUI framework.

Honours NO_COLOR and non-tty output by falling back to clean plain text. The
palette matches the izakaya / Ghostwheel family.
"""

from __future__ import annotations

import os
import sys

# TokyoNight palette (hex -> RGB).
GROUND = (0x1a, 0x1b, 0x26)
CYAN = (0x7d, 0xcf, 0xff)
BLUE = (0x7a, 0xa2, 0xf7)
PURPLE = (0xbb, 0x9a, 0xf7)
GREEN = (0x9e, 0xce, 0x6a)
RED = (0xf7, 0x76, 0x8e)
DIM = (0x56, 0x5f, 0x89)

# The loci wordmark (figlet "standard").
WORDMARK = r"""
 _            _
| | ___   ___(_)
| |/ _ \ / __| |
| | (_) | (__| |
|_|\___/ \___|_|
"""

TAGLINE = "the genius of the place · summon with //"


def color_enabled(stream=None) -> bool:
    stream = stream or sys.stdout
    if os.environ.get("NO_COLOR") is not None:
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    return bool(getattr(stream, "isatty", lambda: False)())


class UI:
    def __init__(self, stream=None, color: bool = None, verbosity: str = "normal"):
        self.stream = stream or sys.stdout
        self.color = color_enabled(self.stream) if color is None else color
        self.verbosity = verbosity

    # -- low-level ---------------------------------------------------------- #

    def _fg(self, rgb) -> str:
        return f"\x1b[38;2;{rgb[0]};{rgb[1]};{rgb[2]}m" if self.color else ""

    def _reset(self) -> str:
        return "\x1b[0m" if self.color else ""

    def paint(self, text: str, rgb) -> str:
        return f"{self._fg(rgb)}{text}{self._reset()}"

    def write(self, text: str = "") -> None:
        self.stream.write(text)
        self.stream.flush()

    def line(self, text: str = "") -> None:
        self.write(text + "\n")

    # -- elements ----------------------------------------------------------- #

    def _gradient_stops(self, t: float):
        """Three-stop cyan -> blue -> purple interpolation, t in [0, 1]."""
        if t < 0.5:
            a, b, u = CYAN, BLUE, t / 0.5
        else:
            a, b, u = BLUE, PURPLE, (t - 0.5) / 0.5
        return tuple(round(a[i] + (b[i] - a[i]) * u) for i in range(3))

    def banner(self) -> None:
        lines = WORDMARK.strip("\n").splitlines()
        width = max(len(l) for l in lines)
        for row in lines:
            if not self.color:
                self.line(row)
                continue
            out = []
            for col, ch in enumerate(row):
                rgb = self._gradient_stops(col / max(width - 1, 1))
                out.append(self.paint(ch, rgb))
            self.line("".join(out))
        self.line(self.paint(TAGLINE, DIM))

    def rule(self, label: str = "") -> None:
        bar = "─" * 56
        if label:
            self.line(self.paint(f"── {label} " + "─" * (52 - len(label)), BLUE))
        else:
            self.line(self.paint(bar, BLUE))

    def panel(self, title: str, body_lines) -> None:
        self.line(self.paint(f"┌─ {title} " + "─" * max(0, 50 - len(title)), BLUE))
        for ln in body_lines:
            self.line(self.paint("│ ", BLUE) + ln)
        self.line(self.paint("└" + "─" * 54, BLUE))

    def ok(self, msg: str) -> None:
        self.line(self.paint("✓", GREEN) + " " + msg)

    def fail(self, msg: str) -> None:
        self.line(self.paint("✗", RED) + " " + msg)

    def info(self, msg: str) -> None:
        self.line(self.paint("·", DIM) + " " + msg)

    def warn(self, msg: str) -> None:
        self.line(self.paint("!", PURPLE) + " " + msg)

    def agent(self, text: str) -> None:
        """Stream a chunk of the agent's own speech (kept plain for readability)."""
        self.write(text)

    def prompt(self, label: str) -> None:
        self.write(self.paint(label, CYAN))
