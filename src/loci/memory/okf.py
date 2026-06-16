"""Open Knowledge Format (OKF) v0.1 bundles.

Conforms to OKF v0.1
(github.com/GoogleCloudPlatform/knowledge-catalog/tree/main/okf):

  - Reserved filenames: only `index.md` (progressive-disclosure listing) and
    `log.md` (chronological history). Every other .md file is a concept document.
  - Required frontmatter: a non-empty `type`.
  - Recommended frontmatter, in priority order: `title`, `description`,
    `resource`, `tags`, `timestamp` (ISO 8601).
  - A concept's identity is its file path within the bundle, minus the .md suffix
    (e.g. tables/users.md -> "tables/users").
  - Cross-links are markdown links; bundle-absolute links begin with "/".
  - Producers may add arbitrary extra keys; consumers must preserve unknown
    fields and tolerate unknown `type` values and broken links.

We depend only on the standard library, so frontmatter is handled by a small,
deliberately limited YAML reader/writer covering the subset OKF needs: scalars
and simple string lists (for `tags`). Unknown scalar keys are preserved verbatim.

loci's own concept types: project | preference | directory | person | fact
(OKF does not centrally register types; these are just descriptive strings).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

RESERVED = {"index.md", "log.md"}

# loci's concept vocabulary. Not enforced — OKF requires only a non-empty type —
# but used to guide promotion and documented for readers.
CONCEPT_TYPES = ("project", "preference", "directory", "person", "fact")


class OKFError(Exception):
    pass


# --------------------------------------------------------------------------- #
# Minimal frontmatter (a small, well-defined YAML subset)
# --------------------------------------------------------------------------- #

def _parse_scalar(raw: str):
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ("'", '"'):
        return raw[1:-1]
    return raw


def parse_frontmatter(text: str):
    """Split a document into (frontmatter dict, body str).

    Accepts documents with or without a leading `---` block. Tags may be written
    inline (`tags: [a, b]`) or as a block list of `- item` lines.
    """
    if not text.startswith("---"):
        return {}, text

    lines = text.splitlines()
    # First line is the opening '---'; find the closing one.
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        raise OKFError("unterminated frontmatter block")

    meta: Dict = {}
    pending_list_key: Optional[str] = None
    for line in lines[1:end]:
        if not line.strip():
            continue
        stripped = line.strip()
        if stripped.startswith("- ") and pending_list_key:
            meta[pending_list_key].append(_parse_scalar(stripped[2:]))
            continue
        if ":" not in line:
            raise OKFError(f"unparseable frontmatter line: {line!r}")
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if value == "":
            # Could be the head of a block list; start collecting.
            meta[key] = []
            pending_list_key = key
        elif value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            meta[key] = [_parse_scalar(v) for v in inner.split(",")] if inner else []
            pending_list_key = None
        else:
            meta[key] = _parse_scalar(value)
            pending_list_key = None

    body = "\n".join(lines[end + 1:])
    if body.startswith("\n"):
        body = body[1:]
    return meta, body


def _dump_scalar(value) -> str:
    s = str(value)
    # Quote when characters would confuse the limited reader.
    if s == "" or s[0] in ("'", '"', "[", "-", " ") or ":" in s or s.strip() != s:
        return '"' + s.replace('"', '\\"') + '"'
    return s


def dump_frontmatter(meta: Dict) -> str:
    """Serialize a frontmatter dict deterministically (recommended keys first)."""
    order = ["type", "title", "description", "resource", "tags", "timestamp"]
    keys = [k for k in order if k in meta] + [k for k in meta if k not in order]
    out = ["---"]
    for key in keys:
        value = meta[key]
        if isinstance(value, list):
            if value:
                out.append(f"{key}:")
                out.extend(f"  - {_dump_scalar(v)}" for v in value)
            else:
                out.append(f"{key}: []")
        else:
            out.append(f"{key}: {_dump_scalar(value)}")
    out.append("---")
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# Concept documents
# --------------------------------------------------------------------------- #

@dataclass
class Concept:
    concept_id: str                 # bundle-relative path, no .md suffix
    type: str                       # required by OKF; must be non-empty
    title: Optional[str] = None
    description: Optional[str] = None
    resource: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    timestamp: Optional[str] = None
    extra: Dict = field(default_factory=dict)   # preserved unknown frontmatter
    body: str = ""

    def to_text(self) -> str:
        if not self.type or not str(self.type).strip():
            raise OKFError("OKF concept requires a non-empty 'type'")
        meta: Dict = {"type": self.type}
        if self.title:
            meta["title"] = self.title
        if self.description:
            meta["description"] = self.description
        if self.resource:
            meta["resource"] = self.resource
        if self.tags:
            meta["tags"] = list(self.tags)
        if self.timestamp:
            meta["timestamp"] = self.timestamp
        meta.update(self.extra)
        return dump_frontmatter(meta) + "\n\n" + (self.body.rstrip() + "\n" if self.body else "")

    @classmethod
    def from_text(cls, concept_id: str, text: str) -> "Concept":
        meta, body = parse_frontmatter(text)
        ctype = meta.get("type")
        if not ctype or not str(ctype).strip():
            raise OKFError(f"concept {concept_id!r} is missing a non-empty 'type'")
        known = {"type", "title", "description", "resource", "tags", "timestamp"}
        tags = meta.get("tags", [])
        if isinstance(tags, str):
            tags = [tags]
        return cls(
            concept_id=concept_id,
            type=ctype,
            title=meta.get("title"),
            description=meta.get("description"),
            resource=meta.get("resource"),
            tags=list(tags),
            timestamp=meta.get("timestamp"),
            extra={k: v for k, v in meta.items() if k not in known},
            body=body,
        )


# --------------------------------------------------------------------------- #
# Bundles
# --------------------------------------------------------------------------- #

class Bundle:
    """A directory of OKF concept documents."""

    def __init__(self, root: "Path | str"):
        self.root = Path(root)

    # -- reading ----------------------------------------------------------- #

    def exists(self) -> bool:
        return self.root.is_dir()

    def _path_for(self, concept_id: str) -> Path:
        cid = concept_id.strip().lstrip("/")
        if cid.endswith(".md"):
            cid = cid[:-3]
        if not cid or ".." in Path(cid).parts:
            raise OKFError(f"invalid concept id: {concept_id!r}")
        return self.root / (cid + ".md")

    def read_concept(self, concept_id: str) -> Concept:
        path = self._path_for(concept_id)
        if not path.exists():
            raise OKFError(f"no such concept: {concept_id!r}")
        cid = concept_id.strip().lstrip("/")
        if cid.endswith(".md"):
            cid = cid[:-3]
        return Concept.from_text(cid, path.read_text(encoding="utf-8"))

    def list_concepts(self) -> List[str]:
        if not self.exists():
            return []
        ids: List[str] = []
        for path in sorted(self.root.rglob("*.md")):
            if path.name in RESERVED:
                continue
            ids.append(str(path.relative_to(self.root).with_suffix("")))
        return ids

    def read_index(self) -> Optional[str]:
        index = self.root / "index.md"
        return index.read_text(encoding="utf-8") if index.exists() else None

    # -- writing ----------------------------------------------------------- #

    def write_concept(self, concept: Concept, timestamp: Optional[str] = None,
                      log_note: Optional[str] = None) -> Path:
        """Write a concept document, then refresh index.md and append to log.md.

        `timestamp` (ISO 8601) is supplied by the caller — this module does not
        read the clock — and stamps both the concept and the log entry.
        """
        if timestamp and not concept.timestamp:
            concept.timestamp = timestamp
        path = self._path_for(concept.concept_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(concept.to_text(), encoding="utf-8")
        self._refresh_index()
        self._append_log(concept, timestamp, log_note)
        return path

    def _refresh_index(self) -> None:
        """Regenerate index.md as a progressive-disclosure listing of concepts."""
        lines = ["---", "type: index", "title: Knowledge index", "---", ""]
        lines.append("Concepts in this bundle:\n")
        for cid in self.list_concepts():
            try:
                c = self.read_concept(cid)
                desc = f" — {c.description}" if c.description else ""
                label = c.title or cid
                lines.append(f"- [{label}](/{cid}) `{c.type}`{desc}")
            except OKFError:
                lines.append(f"- [/{cid}](/{cid})")
        (self.root / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _append_log(self, concept: Concept, timestamp: Optional[str],
                   note: Optional[str]) -> None:
        log = self.root / "log.md"
        if not log.exists():
            log.write_text("---\ntype: log\ntitle: Update history\n---\n\n",
                           encoding="utf-8")
        stamp = timestamp or ""
        entry = f"- {stamp} wrote [/{concept.concept_id}](/{concept.concept_id})"
        if note:
            entry += f" — {note}"
        with log.open("a", encoding="utf-8") as fh:
            fh.write(entry + "\n")
