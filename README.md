<p align="center">
  <img src="docs/banner.svg?v=2" alt="loci — the genius of the place · summon with //" width="420">
</p>

# loci

**loci** is an ambient AI agent that lives in your normal zsh shell, summoned
with `//`, powered by Claude via the Anthropic API. It is *not* a REPL you launch
and leave — it is a presence you address from your own prompt, in whatever
directory you're standing in. The current working directory is its world: loci is
the genius of the place you summon it.

> [!WARNING]
> **Use at your own risk.** loci can read, modify, move, and delete files — and,
> if you enable it, run arbitrary shell commands — in the directories you point
> it at. An LLM can make mistakes. **You** are responsible for what you let it do.
> It is provided "AS IS", with no warranty and no liability on the authors; see
> the [Disclaimer](#disclaimer) and [LICENSE](LICENSE). Keep version control or
> backups, and review what it proposes before approving.

## The `//` UX

```sh
# one ambient turn — works in the cwd, reports what it did, hands you back the shell
// rename every .jpeg in here to .jpg

# bare //  then Enter — a sustained back-and-forth for when one line isn't enough
//
loci ‹ summarize what this repo does
loci ‹ now draft a README section for the installer
loci ‹ //                       # leave (or Ctrl-D)
```

Both forms share one session thread per terminal window.

```sh
// :new      # start a fresh session
// :forget   # wipe this session's transcript
```

## Cheatsheet

Summon it any time with **`// help`** (instant, no API call). It prints:

```text
── summon ──
  // <request>      one ambient turn in the current directory
  //  (then Enter)  a sustained chat — leave with // or Ctrl-D
── session ──
  // :new           start a fresh conversation
  // :forget        wipe this terminal's transcript
  // help           show this
── what it can do  (asks before anything destructive) ──
  read    list_files · read_file · find_files · search_text
  write   write_file · edit_file · make_dir · rename/move/delete_file
  shell   run_shell — off until you enable it in `loci onboard`
  web     web_fetch — read a URL with w3m; off until you enable it
  memory  reads & writes OKF knowledge in ./.loci and the global bundle
── safety ──
  • acts only inside the current directory (cwd boundary)
  • one y/N per destructive action; a shown plan + one y/N for batches
  • run_shell shows the command first · web_fetch shows the URL first
  • --dry-run changes nothing
── config ──
  key     LOCI_ANTHROPIC_KEY  (or ANTHROPIC_API_KEY)
  setup   loci onboard   ·   ~/.config/loci/config.json
  flags   --dry-run · --allow-outside · --model NAME · --no-color · -q/-v
```

## Install

[pipx](https://pipx.pypa.io) is the recommended installer — it brings its own
modern Python, installs loci in an isolated environment, and puts it on your
PATH. (macOS note: do not rely on the system `/usr/bin/python3`; it ships an old
pip and a Python below loci's floor.)

```sh
brew install pipx && pipx ensurepath     # once; or: python3 -m pip install --user pipx
git clone <your-fork> loci && cd loci
./install.sh
```

The installer (TokyoNight, zero-dependency) detects pipx (or a Python ≥3.11),
installs `loci` onto your PATH, adds a small fenced hook to your `.zshrc`, and
checks for your API key. It honours `NO_COLOR` and non-interactive shells, and it
never writes your key anywhere. Without pipx it falls back to `pip install --user`
against a Python ≥3.11.

Then, in a new shell:

```sh
export LOCI_ANTHROPIC_KEY="sk-ant-..."  # loci's own var; read from the env only
loci onboard                            # consent, defaults, and a live key check
// say hello                            # your first turn
```

### Requirements

- zsh (the `//` hook is a zsh ZLE widget)
- pipx (recommended), or a Python 3.11+ on your PATH
- An Anthropic API key in `LOCI_ANTHROPIC_KEY` (or `ANTHROPIC_API_KEY` as a fallback)
- Optional: [`w3m`](https://w3m.sourceforge.net/) on your PATH, only if you enable
  `web_fetch` (e.g. `brew install w3m`)

## Configuration

`loci onboard` writes `~/.config/loci/config.json` (XDG-aware):

| key                  | default              | meaning                                  |
|----------------------|----------------------|------------------------------------------|
| `model`              | `claude-sonnet-4-6`  | overridable to a stronger model          |
| `run_shell_enabled`  | `false`              | the shell tool stays off until you opt in |
| `web_fetch_enabled`  | `false`              | the web_fetch tool (reads URLs via w3m) stays off until you opt in |
| `verbosity`          | `normal`             | `quiet` / `normal` / `verbose`           |

Per-run flags: `--dry-run`, `--allow-outside`, `--model NAME`, `--no-color`,
`-q`/`-v`. The key is **only** ever read from the environment —
`LOCI_ANTHROPIC_KEY` first (loci's own, isolated variable), then
`ANTHROPIC_API_KEY` as a fallback.

## Safety

loci touches real files and can run commands, so the safety model is explicit and
enforced — these are invariants, not suggestions:

- **The cwd is a hard boundary.** Every file tool resolves against the current
  directory; absolute paths, `..` traversal, and symlinks pointing outside are
  refused unless you pass `--allow-outside`.
- **Read before write.** An existing file must be read before it can be
  overwritten.
- **One destructive action → one inline `y/N`.**
- **A multi-file change → a SHOWN PLAN first** (the full source→target mapping),
  then a single `y/N` for the whole batch. No silent batch mutations.
- **`run_shell` always shows the exact command and waits.** It never
  auto-executes, and it is disabled until you consent during onboarding.
- **`web_fetch` reaches the network only after you opt in.** It is disabled until
  you consent during onboarding, only accepts `http`/`https` URLs (never
  `file://`, so it cannot bypass the cwd boundary to read local files), is
  read-only, and prints the URL before each fetch.
- **`--dry-run` mutates nothing** and only prints intended actions.
- **Confirms fail safe.** Anything but an explicit `yes` — including EOF — is a
  no.

## Memory — two layers, kept separate

1. **Session memory** — a lightweight rolling transcript on disk under an XDG
   state path, keyed to your terminal session so different windows hold different
   threads. Each `//` loads recent turns, appends, and trims to a token budget.
   Ephemeral and recency-shaped. *Not* OKF.

2. **Knowledge memory** — durable and structured, in
   [Open Knowledge Format (OKF) v0.1](https://github.com/GoogleCloudPlatform/knowledge-catalog/tree/main/okf):
   a directory of markdown files with YAML frontmatter, one concept per file, the
   path as its identity, concepts cross-linked into a graph, with `index.md` for
   progressive disclosure and `log.md` for history. loci both reads bundles for
   context and writes concept docs as it learns. Two scopes are active:
   a per-directory `.loci/` bundle that travels with the repo, and a global
   bundle under an XDG data path for what loci knows about you everywhere.
   Promotion is conservative and **always shown** — loci never writes memory
   silently, and memory writes obey the same cwd boundary as any file write.

## How it works (the ZLE hook)

`shell/loci.zsh` installs an `accept-line` ZLE widget. When a command line begins
with `//`, the widget captures the request **raw** — it quotes the text with
`${(q)...}` before zsh re-reads the line, so no globbing or word-splitting ever
touches what you typed — and routes it to `loci turn`. A bare `//` opens the
sustained chat. Everything else runs as a normal shell command, untouched. The
hook is idempotent and safe to source from `.zshrc` more than once.

Under the hood, loci runs the Anthropic Messages API tool-use loop: it sends the
conversation plus tool schemas; when Claude returns `tool_use` blocks, loci
validates them, runs them through the safety model, returns `tool_result` blocks,
and loops until the turn ends. Text is streamed as it arrives.

## Development

Install editable so your edits apply without reinstalling:

```sh
./install.sh --dev                       # pipx editable install + the zsh hook
# or directly:  pipx install --editable .
```

Run the tests (no SDK or network needed):

```sh
PYTHONPATH=src python3 -m unittest discover -s tests
```

The suite covers the cwd sandbox (path-escape rejection), the plan/confirm
gating, and an OKF bundle read/write round-trip.

## Disclaimer

loci is an autonomous agent. It can read, modify, move, and delete files, and —
when you enable `run_shell` — execute arbitrary shell commands in the directories
you point it at. It is driven by a large language model, which can misunderstand,
hallucinate, or take actions you did not intend. Its safety model (confirmations,
shown plans, the cwd boundary, `--dry-run`) reduces risk but does **not**
eliminate it.

**You use loci entirely at your own risk.** To the maximum extent permitted by
applicable law, the software is provided "AS IS", without warranty of any kind,
express or implied, and in no event shall the authors or contributors be liable
for any claim, damages, data loss, or other liability arising from the software
or its use — as set out in the [MIT LICENSE](LICENSE). By installing, running, or
otherwise using loci you accept these terms. Use version control or backups,
review proposed actions before approving them, and run it only where you accept
the consequences. Nothing here is legal advice.

## License

MIT — see [LICENSE](LICENSE).
