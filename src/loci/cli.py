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

HELP_TOKENS = {"help", ":help", "?", "--help", "-h"}


def render_help(ui: UI) -> None:
    """A local, instant cheatsheet — printed by `// help` and `loci help`."""
    ui.rule("summon")
    ui.line("  // <request>      one ambient turn in the current directory")
    ui.line("  //  (then Enter)  a sustained chat — leave with // or Ctrl-D")
    ui.rule("session")
    ui.line("  // :new           start a fresh conversation")
    ui.line("  // :forget        wipe this terminal's transcript")
    ui.line("  // help           show this")
    ui.rule("what it can do  (asks before anything destructive)")
    ui.line("  read    list_files · read_file · find_files · search_text")
    ui.line("  write   write_file · edit_file · make_dir · rename/move/delete_file")
    ui.line("  shell   run_shell — off until you enable it in `loci onboard`")
    ui.line("  web     web_fetch — read a URL with w3m; off until you enable it")
    ui.line("  memory  reads & writes OKF knowledge in ./.loci and the global bundle")
    ui.rule("safety")
    ui.line("  • acts only inside the current directory (cwd boundary)")
    ui.line("  • one y/N per destructive action; a shown plan + one y/N for batches")
    ui.line("  • run_shell shows the command first · web_fetch shows the URL first")
    ui.line("  • --dry-run changes nothing")
    ui.rule("config")
    ui.line("  key     LOCI_ANTHROPIC_KEY  (or ANTHROPIC_API_KEY)")
    ui.line("  setup   loci onboard   ·   ~/.config/loci/config.json")
    ui.line("  flags   --dry-run · --allow-outside · --model NAME · --no-color · -q/-v")
    ui.line("")
    ui.info("use at your own risk — see the README Disclaimer.")


def _build(cfg, opts):
    ui = UI(color=(False if opts["no_color"] else None), verbosity=opts["verbosity"])
    sandbox = Sandbox(allow_outside=opts["allow_outside"])
    session = Session(budget=cfg.get("session_token_budget"))
    return ui, sandbox, session


def _handle_control(token: str, session: Session, ui: UI) -> bool:
    """Handle help / :new / :forget locally. Returns True if it was a control
    command (so no API turn is made)."""
    if token in HELP_TOKENS:
        render_help(ui)
        return True
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
        render_help(UI(color=(False if opts["no_color"] else None)))
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
