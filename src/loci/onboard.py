"""`loci onboard` — first-run setup.

Runs where Python is guaranteed (after install.sh). Styled ANSI, zero-dep. Three
things, on purpose:
  1. A real SAFETY CONSENT checkpoint — loci can read, modify, and run shell in
     directories you point it at — requiring a typed "yes" before run_shell is
     enabled.
  2. Offer to set defaults: model, run_shell on/off, verbosity.
  3. Verify the key with a tiny live // turn ("say hello") so you see it work.
"""

from __future__ import annotations

from . import config
from .client import MissingKeyError, get_api_key
from .ui import UI


def _ask(ui: UI, prompt: str, default: str = "") -> str:
    ui.prompt(prompt)
    try:
        return input().strip()
    except (EOFError, KeyboardInterrupt):
        ui.line("")
        return default


def run_onboard(cfg: dict, opts: dict) -> int:
    ui = UI(color=(False if opts.get("no_color") else None))
    ui.banner()
    ui.line("")
    ui.rule("welcome")
    ui.line("loci lives in your shell and acts in whatever directory you summon it from.")
    ui.line("")

    # 1. Safety consent --------------------------------------------------- #
    ui.panel("safety", [
        "loci can READ files, MODIFY files, and (if you allow it) RUN shell",
        "commands in the directory you point it at. It always asks before any",
        "destructive action, and shows every command before running it.",
        "",
        "run_shell has the largest blast radius and stays OFF until you opt in.",
    ])
    ans = _ask(ui, 'Type "yes" to acknowledge and enable run_shell (anything else keeps it off): ')
    cfg["consented"] = True
    cfg["run_shell_enabled"] = (ans.strip().lower() == "yes")
    if cfg["run_shell_enabled"]:
        ui.ok("run_shell enabled. You will still confirm every command.")
    else:
        ui.info("run_shell left disabled. Re-run `loci onboard` to change this.")

    # 2. Defaults --------------------------------------------------------- #
    ui.line("")
    ui.rule("defaults")
    model = _ask(ui, f"Model [{cfg.get('model', config.DEFAULT_MODEL)}]: ")
    if model:
        cfg["model"] = model
    verbosity = _ask(ui, f"Verbosity quiet/normal/verbose [{cfg.get('verbosity','normal')}]: ")
    if verbosity in ("quiet", "normal", "verbose"):
        cfg["verbosity"] = verbosity

    saved = config.save_config(cfg)
    ui.ok(f"saved {saved}")

    # 3. Live key check --------------------------------------------------- #
    ui.line("")
    ui.rule("verify")
    try:
        get_api_key()
    except MissingKeyError as e:
        ui.fail(str(e))
        ui.info("Set the key, then run a first turn:  // say hello")
        return 1

    ui.info("running a tiny live turn to verify your key…")
    try:
        from .agent import Agent
        from .memory.session import Session
        from .sandbox import Sandbox
        agent = Agent(cfg, ui, Sandbox(), Session(), model=cfg.get("model"))
        agent.run_turn("Say hello in one short sentence to confirm you are working.")
        ui.line("")
        ui.ok("your key works. loci is ready.")
    except MissingKeyError as e:
        ui.fail(str(e))
        return 1
    except Exception as e:  # network/SDK error — report, don't crash onboarding
        ui.fail(f"could not reach the API: {e}")
        return 1

    ui.line("")
    ui.panel("try it", ["// list what's in this directory and suggest a .gitignore"])
    return 0
