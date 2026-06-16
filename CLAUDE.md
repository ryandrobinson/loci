# CLAUDE.md — conventions for contributors and for Claude Code

This repo is **public from commit one**. No secrets, no personal paths, no
machine-specific config. Write code people will read.

## What loci is

An ambient agent summoned from zsh with `//`, running the Anthropic Messages API
tool-use loop against the current working directory. Two parts: the zsh ZLE hook
(`shell/loci.zsh`) and the Python agent core (`src/loci/`).

## Dependencies

Standard library plus the official `anthropic` SDK. **No framework, no TUI
library.** The Anthropic import is local to `client.py` functions so the rest of
the package (and the test suite) imports without the SDK present.

## Style

- Python 3.11+ floor; the code is kept simple and broadly compatible.
- Clear names, real comments where intent isn't obvious, small modules.
- ANSI styling is hand-rolled in `ui.py`; honour `NO_COLOR` and non-tty.

## Safety invariants (NEVER weaken these)

These are enforced in code and documented in the README. Changing them is a
breaking change to the project's promise:

1. **cwd is a hard boundary.** All file paths resolve through `sandbox.Sandbox`,
   which rejects absolute paths, `..` traversal, and symlink escapes unless
   `--allow-outside` is set. Use real-path checks; never trust a string compare.
2. **Read before write.** `write_file` refuses to overwrite a file that wasn't
   read this session (`safety.ReadCache`).
3. **Single destructive action → one inline `y/N`.**
4. **Multi-file change → a shown plan, then one `y/N`** for the whole batch
   (`safety.render_plan` + the batch logic in `agent.Agent._run_tools`). No silent
   batch mutations.
5. **`run_shell` always shows the command and waits**, and is gated by
   `config.run_shell_enabled` (off until consent).
6. **`--dry-run` mutates nothing.**
7. **Confirms fail safe.** `safety.confirm` returns `True` only for an explicit
   `y`/`yes`; EOF and everything else is `False`.

The API key is read from `ANTHROPIC_API_KEY` only, at runtime. Never log it, never
write it to disk, never add it to the repo.

## How tools are registered

Each tool is a `Tool` in `src/loci/tools/__init__.py` with: a `name`, a safety
`klass` (`read` / `benign` / `destructive` / `exec`), a `handler(ctx, **input)`,
a JSON `schema` advertised to the API, and — for destructive/exec tools — a
`plan_row(input)` used to render batch/confirm lines.

- Handlers assume confirmation already happened; the agent loop owns gating.
- Handlers enforce tool-level preconditions (sandbox resolve, read-before-write)
  and honour `ctx.dry_run`, returning a one-line summary string. Raise `ToolError`
  for failures that should return to the model as an error `tool_result`.
- `run_shell` schema is hidden from the API entirely when `run_shell_enabled` is
  false.

To add a tool: write the handler, add a `Tool(...)` entry with its schema and
class, and (if it mutates) a `plan_row`. That's it — the loop and gating pick it
up.

## How memory promotion works

Two layers, never conflated (`src/loci/memory/`):

- `session.py` — ephemeral rolling transcript, per terminal (`LOCI_SESSION`),
  trimmed to a token budget. `:new` resets, `:forget` wipes.
- `okf.py` — durable **OKF v0.1** bundles. Required frontmatter is a non-empty
  `type`; recommended keys are `title`, `description`, `resource`, `tags`,
  `timestamp`. Reserved filenames are only `index.md` and `log.md`. A concept's id
  is its path minus `.md`. Unknown frontmatter keys are preserved. This module
  never reads the clock — callers pass an ISO timestamp.

Promotion is the `knowledge_write` tool (a destructive action): it goes through
the same confirm gating, is always shown to the user, and stays inside the cwd
boundary for the `local` scope. Keep promotion conservative — durable, reusable
facts only. loci's concept types: `project`, `preference`, `directory`, `person`,
`fact`.

## Tests

```sh
PYTHONPATH=src python3 -m unittest discover -s tests
```

Cover, at minimum: the sandbox path-escape rejection, the plan/confirm gating,
and an OKF read/write round-trip. Tests must not require the Anthropic SDK or a
network connection.
