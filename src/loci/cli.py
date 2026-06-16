"""loci command-line entry point.

The zsh hook routes:
  // <request>     -> `loci turn -- <request>`   (one ambient turn)
  //  (bare)       -> `loci chat`                 (sustained back-and-forth)

You can also call these directly. Control tokens `:new` and `:forget` manage the
session transcript.
"""

from __future__ import annotations

import sys

from . import config
from .client import MissingKeyError
from .memory.session import Session
from .sandbox import Sandbox
from .ui import UI

USAGE = """\
loci — the genius of the place

  // <request>     one ambient turn in the current directory
  //  (then Enter) a sustained chat; exit with Ctrl-D or //

Commands:
  loci turn -- <request>   run a single turn (what the // hook calls)
  loci chat                start a sustained session
  loci onboard             first-run setup (consent, defaults, key check)
  loci version             print version
  loci help                this message

Global flags:
  --dry-run         mutate nothing; only print intended actions
  --allow-outside   permit paths outside the current directory
  --model NAME      override the model for this run
  --no-color        disable ANSI styling
  -q | -v           quieter / more verbose
"""


def _build(cfg, opts):
    ui = UI(color=(False if opts["no_color"] else None), verbosity=opts["verbosity"])
    sandbox = Sandbox(allow_outside=opts["allow_outside"])
    session = Session(budget=cfg.get("session_token_budget"))
    return ui, sandbox, session


def _handle_control(token: str, session: Session, ui: UI) -> bool:
    """Handle :new / :forget. Returns True if the token was a control command."""
    if token == ":new":
        session.reset()
        ui.info("started a fresh session.")
        return True
    if token == ":forget":
        session.forget()
        ui.info("wiped this session's transcript.")
        return True
    return False


def _turn(request: str, cfg, opts) -> int:
    ui, sandbox, session = _build(cfg, opts)
    request = request.strip()
    if not request:
        ui.info("nothing to do.")
        return 0
    if _handle_control(request, session, ui):
        return 0

    from .agent import Agent  # lazy: avoids importing the SDK for :new/:forget
    agent = Agent(cfg, ui, sandbox, session, dry_run=opts["dry_run"], model=opts["model"])
    try:
        agent.run_turn(request)
    except MissingKeyError as e:
        ui.fail(str(e))
        return 1
    except KeyboardInterrupt:
        ui.line("")
        ui.info("interrupted.")
        return 130
    return 0


def _chat(cfg, opts) -> int:
    ui, sandbox, session = _build(cfg, opts)
    ui.banner()
    ui.info("sustained session — Ctrl-D or // to leave.")
    from .agent import Agent
    agent = Agent(cfg, ui, sandbox, session, dry_run=opts["dry_run"], model=opts["model"])
    while True:
        try:
            ui.prompt("\nloci ‹ ")
            line = input()
        except (EOFError, KeyboardInterrupt):
            ui.line("")
            ui.info("until next time.")
            return 0
        text = line.strip()
        if text in ("", "//"):
            if text == "//":
                ui.info("until next time.")
                return 0
            continue
        if _handle_control(text, session, ui):
            continue
        try:
            agent.run_turn(text)
        except MissingKeyError as e:
            ui.fail(str(e))
            return 1
        except KeyboardInterrupt:
            ui.line("")
            ui.info("interrupted.")
    # unreachable


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    opts = {"dry_run": False, "allow_outside": False, "model": None,
            "no_color": False, "verbosity": "normal"}
    positional = []
    literal = []          # everything after `--`
    i = 0
    seen_ddash = False
    while i < len(argv):
        tok = argv[i]
        if seen_ddash:
            literal.append(tok)
        elif tok == "--":
            seen_ddash = True
        elif tok == "--dry-run":
            opts["dry_run"] = True
        elif tok == "--allow-outside":
            opts["allow_outside"] = True
        elif tok == "--no-color":
            opts["no_color"] = True
        elif tok in ("-q", "--quiet"):
            opts["verbosity"] = "quiet"
        elif tok in ("-v", "--verbose"):
            opts["verbosity"] = "verbose"
        elif tok == "--model":
            i += 1
            opts["model"] = argv[i] if i < len(argv) else None
        else:
            positional.append(tok)
        i += 1

    cmd = positional[0] if positional else None
    cfg = config.load_config()

    if cmd in ("help", "-h", "--help") or (cmd is None and not literal):
        sys.stdout.write(USAGE)
        return 0
    if cmd == "version":
        from . import __version__
        sys.stdout.write(f"loci {__version__}\n")
        return 0
    if cmd == "onboard":
        from .onboard import run_onboard
        return run_onboard(cfg, opts)
    if cmd == "chat":
        return _chat(cfg, opts)
    if cmd == "turn":
        request = " ".join(literal) if literal else " ".join(positional[1:])
        return _turn(request, cfg, opts)

    # Bare `loci <words...>` is treated as a turn request.
    request = " ".join(literal) if literal else " ".join(positional)
    return _turn(request, cfg, opts)


if __name__ == "__main__":
    raise SystemExit(main())
