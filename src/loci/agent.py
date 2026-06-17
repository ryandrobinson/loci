"""The tool-use loop against the Anthropic Messages API.

Send conversation + tool schemas; when Claude returns tool_use blocks, gate them
through the safety model, execute, return tool_result blocks, and loop until the
model ends its turn. Text is streamed for responsiveness.
"""

from __future__ import annotations

from datetime import datetime
from typing import List

from . import client as client_mod
from . import config, safety
from .memory.okf import Bundle
from .memory.session import Session
from .sandbox import Sandbox
from .tools import DESTRUCTIVE, EXEC, READ, BENIGN, NET, get, schemas
from .tools.base import ToolContext, ToolError
from .ui import UI

SYSTEM_TEMPLATE = """\
You are loci — "the genius of the place" — an ambient assistant summoned from the \
user's shell with //. You act in the current working directory and report what you \
did concisely.

VOICE:
- Talk like a competent colleague at a terminal: plain, direct, a little warm. \
Short sentences. No theatrics.
- You are not a character. Drop the ominous-AI register — no portentous \
narration, no "I'm afraid I can't do that," no roleplayed reluctance.
- When you decline or hit a boundary, say so plainly and briefly, and say why. \
A refusal is one line, not a scene.

Working directory (your whole world): {cwd}
Current local time: {now}
Outside-cwd access: {outside}

TOOLS & JUDGMENT:
- Answer from what you already know. You are given the current date/time and the \
working directory above — do not run a command or any tool just to learn the date, \
do arithmetic, or recall general knowledge. Just answer.
- Reach for tools only when you need the live system or filesystem: reading or \
changing files in this directory, or a command whose result you genuinely cannot \
know. run_shell is the last resort, not the first.
{web}
DIRECTORY (read carefully):
- Each // turn runs in the directory shown above and tagged on the latest user \
message as "[cwd: …]". This can DIFFER from earlier turns in the same conversation: \
the user moves between folders and you move with them. The latest turn's directory \
is the only one that matters now.
- If the current directory differs from a previous turn's, the user has moved — act \
in the NEW directory and acknowledge it. Never claim you are "anchored" to an old \
folder or tell them to relaunch you; a // turn already runs where they are.
- When asked about "this directory" (its files, counts, contents), inspect it NOW \
with list_files/find_files. Do not reuse a listing or count from a different \
directory or an earlier turn.

SAFETY (enforced by the harness around you; honour its spirit):
- The directory above is a hard boundary. File tools refuse paths that escape it.
- Read a file before overwriting it.
- Destructive actions (write/edit/rename/move/delete, knowledge promotion) and \
run_shell are confirmed by the user out of band — propose them; do not assume they \
ran until you see the tool_result.
- Prefer the smallest action that satisfies the request.

MEMORY:
- Session memory is the recent transcript and is automatic.
- Knowledge is durable OKF. Two bundles: `local` (./.loci — this place) and \
`global` (the user across everywhere). Navigate via knowledge_index before reading \
whole concepts. Promote a fact with knowledge_write only when it is genuinely \
durable and useful later; promotion is shown to the user. Be conservative and \
transparent. Concept types: project, preference, directory, person, fact.

{knowledge}
"""


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _row_text(row) -> str:
    action, source, target = row
    return f"{action} {source} -> {target}" if target else f"{action} {source}"


class Agent:
    def __init__(self, cfg: dict, ui: UI, sandbox: Sandbox, session: Session,
                 dry_run: bool = False, model: str = None, confirm=None):
        self.cfg = cfg
        self.ui = ui
        self.sandbox = sandbox
        self.session = session
        self.dry_run = dry_run
        self.model = model or cfg.get("model", config.DEFAULT_MODEL)
        # Injectable for tests; defaults to the fail-safe tty confirm.
        self.confirm = confirm or (lambda: safety.confirm(""))
        self.ctx = ToolContext(
            sandbox=sandbox,
            read_cache=safety.ReadCache(),
            ui=ui,
            local_bundle=Bundle(sandbox.root / ".loci"),
            global_bundle=Bundle(config.global_bundle_dir()),
            now=_now_iso,
            dry_run=dry_run,
        )
        self._client = None

    # -- system prompt ------------------------------------------------------ #

    def _knowledge_context(self) -> str:
        parts = []
        for scope, bundle in (("local", self.ctx.local_bundle),
                              ("global", self.ctx.global_bundle)):
            if bundle.exists():
                index = bundle.read_index()
                if index:
                    parts.append(f"Available {scope} knowledge index:\n{index}")
        return "\n\n".join(parts) if parts else "(No knowledge bundles yet.)"

    def _system(self) -> str:
        web = ("- web_fetch returns the readable plain text of an http/https page "
               "(rendered by w3m, no JavaScript). Reach for it when the user gives a "
               "URL or asks you to read or summarise a web page; it is read-only."
               if self.cfg.get("web_fetch_enabled", False) else "")
        return SYSTEM_TEMPLATE.format(
            cwd=self.sandbox.root,
            now=self.ctx.now(),
            outside="allowed (--allow-outside)" if self.sandbox.allow_outside else "refused",
            web=web,
            knowledge=self._knowledge_context(),
        )

    # -- the loop ----------------------------------------------------------- #

    def run_turn(self, request: str) -> None:
        if self._client is None:
            self._client = client_mod.make_client()

        messages = self.session.load()
        # Stamp the turn with its directory so the thread is self-describing across
        # folder changes — otherwise the model conflates "this directory" across
        # turns that ran in different places.
        messages.append({"role": "user", "content": f"[cwd: {self.sandbox.root}]\n{request}"})
        tools = schemas(self.cfg.get("run_shell_enabled", False),
                        self.cfg.get("web_fetch_enabled", False))

        while True:
            blocks = client_mod.stream_assistant(
                self._client, self.model, self._system(), messages, tools, self.ui
            )
            messages.append({"role": "assistant", "content": blocks})
            tool_uses = [b for b in blocks if b.get("type") == "tool_use"]
            if not tool_uses:
                break  # end_turn

            results = self._run_tools(tool_uses)
            messages.append({"role": "user", "content": results})

        self.session.save(messages)

    def _run_tools(self, tool_uses: List[dict]) -> List[dict]:
        # Decide batch approval for destructive actions up front.
        destructive = [t for t in tool_uses if get(t["name"]).klass == DESTRUCTIVE]
        batch_approved = None
        if not self.dry_run and len(destructive) >= 2:
            rows = [get(t["name"]).plan_row(t.get("input", {})) for t in destructive]
            self.ui.line("")
            self.ui.line(safety.render_plan(rows))
            self.ui.prompt(f"Apply all {len(rows)} changes? [y/N] ")
            batch_approved = self.confirm()

        results = []
        for tu in tool_uses:
            results.append(self._execute_one(tu, batch_approved))
        return results

    def _execute_one(self, tu: dict, batch_approved) -> dict:
        tool = get(tu["name"])
        inp = tu.get("input", {}) or {}

        # web_fetch: gated by consent, shown before each call, but never y/N'd
        # (read-only). The refusal applies even under --dry-run.
        if tool.klass == NET:
            if not self.cfg.get("web_fetch_enabled", False):
                return self._result(tu, "web_fetch is disabled. Enable it with "
                                        "`loci onboard`.", is_error=True)
            self.ui.line("")
            self.ui.info(f"→ fetching {inp.get('url','')}")

        # Confirmation gating (skipped entirely under --dry-run).
        if not self.dry_run:
            if tool.klass == EXEC:
                if not self.cfg.get("run_shell_enabled", False):
                    return self._result(tu, "run_shell is disabled. Enable it with "
                                            "`loci onboard`.", is_error=True)
                self.ui.line("")
                self.ui.warn(f"run_shell: {inp.get('command','')}")
                self.ui.prompt("Run this command? [y/N] ")
                if not self.confirm():
                    return self._result(tu, "declined by user", is_error=True)
            elif tool.klass == DESTRUCTIVE:
                if batch_approved is True:
                    pass  # covered by the shown batch plan
                elif batch_approved is False:
                    return self._result(tu, "declined by user (batch)", is_error=True)
                else:
                    row = tool.plan_row(inp)
                    self.ui.line("")
                    self.ui.info(_row_text(row))
                    self.ui.prompt("Apply this change? [y/N] ")
                    if not self.confirm():
                        return self._result(tu, "declined by user", is_error=True)

        # Execute.
        try:
            output = tool.handler(self.ctx, **inp)
            if tool.klass == NET:
                self.ui.ok(f"fetched ({len(output)} chars)")
            elif tool.klass in (DESTRUCTIVE, BENIGN, EXEC):
                self.ui.ok(output.splitlines()[0])
            return self._result(tu, output, is_error=False)
        except ToolError as e:
            return self._result(tu, str(e), is_error=True)
        except TypeError as e:
            return self._result(tu, f"bad tool arguments: {e}", is_error=True)

    @staticmethod
    def _result(tu: dict, content: str, is_error: bool) -> dict:
        return {
            "type": "tool_result",
            "tool_use_id": tu["id"],
            "content": content,
            "is_error": is_error,
        }
