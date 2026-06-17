"""web_fetch — fetch the readable text of an http(s) URL with w3m.

Read-only: a GET rendered to plain text by w3m, no JavaScript, no filesystem
writes. Network egress is a capability axis of its own, separate from the cwd
boundary — a URL is not a path, so the sandbox does not apply to it. Only http
and https schemes are accepted, so this can never be turned into a way to read
local files (e.g. file://) and slip past the sandbox.

Gating lives in the agent loop: web_fetch is advertised to the API only when
`web_fetch_enabled` is set (consented during `loci onboard`), and the loop prints
the URL before each fetch. Like the read tools, it does not ask y/N per call.
"""

from __future__ import annotations

import subprocess
from urllib.parse import urlparse

from .base import ToolContext, ToolError

FETCH_TIMEOUT = 30           # seconds
OUTPUT_LIMIT = 40_000        # characters of rendered text returned to the model


def web_fetch(ctx: ToolContext, url: str) -> str:
    url = (url or "").strip()
    if not url:
        raise ToolError("empty url")
    if urlparse(url).scheme.lower() not in ("http", "https"):
        raise ToolError("web_fetch only accepts http:// or https:// URLs")
    try:
        proc = subprocess.run(
            ["w3m", "-dump", "-cols", "100", url],
            capture_output=True,
            text=True,
            timeout=FETCH_TIMEOUT,
        )
    except FileNotFoundError:
        raise ToolError("w3m is not installed — install it (e.g. `brew install w3m`) "
                        "to use web_fetch.")
    except subprocess.TimeoutExpired:
        raise ToolError(f"fetch timed out after {FETCH_TIMEOUT}s")
    text = (proc.stdout or "").strip()
    if not text:
        err = (proc.stderr or "").strip() or f"w3m exited {proc.returncode}"
        raise ToolError(f"could not fetch {url}: {err}")
    if len(text) > OUTPUT_LIMIT:
        text = text[:OUTPUT_LIMIT] + f"\n... [truncated at {OUTPUT_LIMIT} chars]"
    return text
