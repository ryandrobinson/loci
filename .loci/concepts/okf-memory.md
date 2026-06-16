---
type: fact
title: Knowledge memory (OKF)
description: loci's durable memory layer, an Open Knowledge Format v0.1 bundle.
resource: "https://github.com/GoogleCloudPlatform/knowledge-catalog/tree/main/okf"
tags:
  - memory
  - okf
timestamp: "2026-06-16T12:00:00-05:00"
---

Durable knowledge lives in OKF v0.1 bundles: a directory of markdown files
with YAML frontmatter, one concept per file, the path as its identity,
concepts cross-linked into a graph. Reserved filenames are only `index.md`
(progressive disclosure) and `log.md` (history); required frontmatter is a
non-empty `type`.

Two scopes are active: this per-directory `.loci/` bundle, and a global
bundle under an XDG data path. Promotion is conservative and always shown
to the user. Concept types loci uses: project, preference, directory,
person, fact. This is distinct from the ephemeral session transcript —
see [the project](/projects/loci).
