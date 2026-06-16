"""Configuration and XDG paths.

Nothing secret lives here. The API key is read from the environment at runtime
(see client.py) and is never persisted by loci.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

# Default model. Overridable in config.json or with --model. The spec calls for a
# capable default that can be pointed at a stronger model.
DEFAULT_MODEL = "claude-sonnet-4-6"

# Rolling session transcript budget, in (estimated) tokens.
DEFAULT_SESSION_TOKEN_BUDGET = 24_000


def _xdg(env_var: str, default_rel: str) -> Path:
    """Resolve an XDG base dir, honouring the env var, with a ~ fallback."""
    base = os.environ.get(env_var)
    root = Path(base) if base else Path.home() / default_rel
    return root / "loci"


def config_dir() -> Path:
    return _xdg("XDG_CONFIG_HOME", ".config")


def state_dir() -> Path:
    # Ephemeral, recency-shaped session transcripts live here.
    return _xdg("XDG_STATE_HOME", ".local/state")


def data_dir() -> Path:
    # Durable knowledge (the global OKF bundle) lives here.
    return _xdg("XDG_DATA_HOME", ".local/share")


def global_bundle_dir() -> Path:
    return data_dir() / "knowledge"


def sessions_dir() -> Path:
    return state_dir() / "sessions"


def config_path() -> Path:
    return config_dir() / "config.json"


# Defaults are intentionally conservative: run_shell is OFF until the user
# consents during onboarding.
DEFAULTS = {
    "model": DEFAULT_MODEL,
    "run_shell_enabled": False,
    "verbosity": "normal",          # "quiet" | "normal" | "verbose"
    "consented": False,             # safety acknowledgement recorded
    "session_token_budget": DEFAULT_SESSION_TOKEN_BUDGET,
}


def load_config() -> dict:
    """Load config.json merged over defaults. Never throws on a missing file."""
    cfg = dict(DEFAULTS)
    path = config_path()
    if path.exists():
        try:
            cfg.update(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            # A corrupt config should not brick the agent — fall back to defaults.
            pass
    return cfg


def save_config(cfg: dict) -> Path:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    return path
