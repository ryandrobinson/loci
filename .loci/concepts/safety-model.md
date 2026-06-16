---
type: fact
title: loci's safety model
description: The enforced invariants for touching real files and running commands.
tags:
  - safety
  - invariants
timestamp: "2026-06-16T12:00:00-05:00"
---

loci touches real files and can run shell, so its safety model is explicit
and enforced (never to be weakened — see `CLAUDE.md`):

- **cwd is a hard boundary** — absolute paths, `..`, and symlink escapes
  are refused unless `--allow-outside` is set.
- **read before write** — an existing file must be read before overwrite.
- **one destructive action → one inline `y/N`.**
- **a multi-file change → a shown plan, then one `y/N`** for the batch.
- **`run_shell` always shows the command and waits**, and is off until
  consent during onboarding.
- **`--dry-run` mutates nothing.**
- **confirms fail safe** — anything but an explicit yes (incl. EOF) is no.

These guard the work described in [the project](/projects/loci).
