---
type: project
title: loci
description: An ambient AI agent summoned from zsh with // and powered by Claude.
resource: "https://github.com/vajramatt/loci"
tags:
  - cli
  - agent
  - anthropic
  - zsh
  - okf
timestamp: "2026-06-16T12:00:00-05:00"
---

loci is *the genius of the place* — a presence you address from your own
zsh prompt, acting in whatever directory you're standing in. It is not a
REPL you launch and leave.

## Shape

- `shell/loci.zsh` — an accept-line ZLE widget. A line starting with `//`
  is captured raw (quoted with `${(q)...}` before re-parse) and routed to
  the agent; bare `//` opens a sustained chat.
- `src/loci/` — a Python core (stdlib + the `anthropic` SDK) running the
  Messages API tool-use loop against the current working directory.

## Invariants

The cwd is a hard boundary; reads happen before writes; destructive and
shell actions are confirmed (a single `y/N`, or one `y/N` over a shown
plan for batches); `--dry-run` mutates nothing; confirms fail safe. See
[the safety model](/concepts/safety-model) and the project conventions in
`CLAUDE.md`.

## Memory

Two layers, never conflated: an ephemeral rolling session transcript, and
durable knowledge in [Open Knowledge Format](/concepts/okf-memory) — the
bundle you are reading now. This `.loci/` bundle travels with the repo and
is the genius of *this* place specifically.
