"""Knowledge tools — loci reading and writing its own OKF bundles.

Two scopes, both active:
  local  — the ./.loci bundle: the genius of THIS place; travels with the repo.
  global — the XDG-data bundle: what loci knows about the user everywhere.

Reads are free. Writes are promotion: durable, shown to the user, and gated like
any other destructive action by the agent loop. Local writes stay inside the cwd
boundary (the bundle lives under ./.loci); global writes go to loci's own data
dir.
"""

from __future__ import annotations

from ..memory.okf import Concept, OKFError
from .base import ToolContext, ToolError


def knowledge_index(ctx: ToolContext, scope: str = "local") -> str:
    bundle = ctx.bundle(scope)
    if not bundle.exists():
        return f"({scope} bundle is empty — no concepts yet)"
    index = bundle.read_index()
    if index:
        return index
    ids = bundle.list_concepts()
    if not ids:
        return f"({scope} bundle is empty — no concepts yet)"
    return "Concepts:\n" + "\n".join(f"- {cid}" for cid in ids)


def knowledge_read(ctx: ToolContext, scope: str, concept_id: str) -> str:
    bundle = ctx.bundle(scope)
    try:
        concept = bundle.read_concept(concept_id)
    except OKFError as e:
        raise ToolError(str(e))
    return concept.to_text()


def knowledge_write(ctx: ToolContext, scope: str, concept_id: str, type: str,
                   title: str = None, description: str = None, body: str = "",
                   tags=None) -> str:
    bundle = ctx.bundle(scope)
    if not type or not str(type).strip():
        raise ToolError("OKF requires a non-empty 'type'")
    concept = Concept(
        concept_id=concept_id,
        type=type,
        title=title,
        description=description,
        body=body or "",
        tags=list(tags) if tags else [],
    )
    rel = f"{scope}:/{concept.concept_id}"
    if ctx.dry_run:
        return f"[dry-run] would promote concept {rel} (type={type})"
    try:
        bundle.write_concept(concept, timestamp=ctx.now(),
                             log_note="promoted by loci")
    except OKFError as e:
        raise ToolError(str(e))
    return f"promoted concept {rel} (type={type})"


def plan_knowledge_write(inp):
    scope = inp.get("scope", "local")
    return ("remember", f"{scope}:/{inp.get('concept_id')}", None)
