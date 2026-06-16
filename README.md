<p align="center">
  <img src="docs/banner.svg" alt="loci — the genius of the place · summon with //" width="420">
</p>

# loci

**loci** is an ambient AI agent that lives in your normal zsh shell, summoned
with `//`, powered by Claude via the Anthropic API. It is *not* a REPL you launch
and leave — it is a presence you address from your own prompt, in whatever
directory you're standing in. The current working directory is its world: loci is
the genius of the place you summon it.

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

## Install

```sh
git clone <your-fork> loci && cd loci
./install.sh
```

The installer (TokyoNight, zero-dependency) detects zsh and Python ≥3.11,
installs `loci` onto your PATH, adds a small fenced hook to your `.zshrc`, and
checks for your API key. It honours `NO_COLOR` and non-interactive shells, and it
never writes your key anywhere.

Then, in a new shell:

```sh
export ANTHROPIC_API_KEY="sk-ant-..."   # loci reads this from the env, only
loci onboard                            # consent, defaults, and a live key check
// say hello                            # your first turn
```

### Requirements

- zsh (the `//` hook is a zsh ZLE widget)
- Python 3.11+
- An Anthropic API key in `ANTHROPIC_API_KEY`

## Configuration

`loci onboard` writes `~/.config/loci/config.json` (XDG-aware):

| key                  | default              | meaning                                  |
|----------------------|----------------------|------------------------------------------|
| `model`              | `claude-sonnet-4-6`  | overridable to a stronger model          |
| `run_shell_enabled`  | `false`              | the shell tool stays off until you opt in |
| `verbosity`          | `normal`             | `quiet` / `normal` / `verbose`           |

Per-run flags: `--dry-run`, `--allow-outside`, `--model NAME`, `--no-color`,
`-q`/`-v`. The key is **only** ever read from the environment.

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

```sh
PYTHONPATH=src python3 -m unittest discover -s tests
```

The suite covers the cwd sandbox (path-escape rejection), the plan/confirm
gating, and an OKF bundle read/write round-trip.

## License

MIT — see [LICENSE](LICENSE).
