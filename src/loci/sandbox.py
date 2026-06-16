"""The cwd boundary — loci's sandbox.

Every file tool resolves its paths through a Sandbox. The directory loci is
summoned from is its whole world; any path that escapes it (absolute paths, ..
traversal, or symlinks pointing outside) is refused unless --allow-outside was
explicitly set.
"""

from __future__ import annotations

import os
from pathlib import Path


class SandboxError(Exception):
    """Raised when a path would escape the cwd boundary."""


class Sandbox:
    def __init__(self, root: "os.PathLike | str | None" = None, allow_outside: bool = False):
        self.root = Path(root or Path.cwd()).resolve()
        self.allow_outside = allow_outside

    def resolve(self, path: str) -> Path:
        """Resolve `path` against the sandbox root, or raise SandboxError.

        Uses realpath on both sides so a symlink inside the sandbox cannot be
        used to reach outside it. Works for paths that do not yet exist.
        """
        if path is None or str(path).strip() == "":
            raise SandboxError("empty path")

        p = Path(path)
        if p.is_absolute():
            if not self.allow_outside:
                raise SandboxError(
                    f"absolute path refused (outside the cwd boundary): {path}"
                )
            return Path(os.path.realpath(p))

        candidate = self.root / p
        real = Path(os.path.realpath(candidate))
        root_real = Path(os.path.realpath(self.root))

        if self.allow_outside:
            return real

        # Inside the boundary iff the realpath is the root or beneath it.
        if real != root_real and root_real not in real.parents:
            raise SandboxError(
                f"path escapes the cwd boundary: {path} (resolved to {real})"
            )
        return real

    def relative(self, resolved: Path) -> str:
        """Display helper: path relative to the root, or absolute if outside."""
        try:
            return str(resolved.relative_to(self.root))
        except ValueError:
            return str(resolved)
