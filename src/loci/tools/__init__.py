"""Tool registry.

Each tool has a JSON schema (sent to the Messages API), a handler, a class that
determines its safety gating, and — for destructive/exec tools — a plan_row used
to render batch plans.

Safety classes:
  read       — no confirmation (list_files, read_file)
  benign     — mutates only by creating dirs; no confirmation (make_dir)
  destructive— inline y/N, or one y/N for a shown batch (write/rename/move,
               knowledge_write)
  exec       — always shown, always waits; off until consented (run_shell)
  net        — read-only network fetch; shown before each call, no y/N; off until
               consented (web_fetch)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from . import fs, knowledge, shell, web
from .base import ToolContext, ToolError

READ, BENIGN, DESTRUCTIVE, EXEC, NET = "read", "benign", "destructive", "exec", "net"


@dataclass
class Tool:
    name: str
    klass: str
    handler: Callable
    schema: dict
    plan_row: Optional[Callable] = None     # (input) -> (action, source, target)


_SCOPE = {
    "type": "string",
    "enum": ["local", "global"],
    "description": "local = ./.loci bundle (this place); global = the user-wide bundle.",
}

REGISTRY = {t.name: t for t in [
    Tool("list_files", READ, fs.list_files, {
        "name": "list_files",
        "description": "List entries in a directory within the working directory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "subdir": {"type": "string", "description": "Subdirectory, default '.'"},
            },
        },
    }),
    Tool("read_file", READ, fs.read_file, {
        "name": "read_file",
        "description": "Read a UTF-8 text file within the working directory.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    }),
    Tool("find_files", READ, fs.find_files, {
        "name": "find_files",
        "description": "Find files by name glob (e.g. '*.py') recursively within the "
                       "working directory. Skips .git/__pycache__/node_modules/etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Filename glob, e.g. '*.py'. Default '*'."},
                "subdir": {"type": "string", "description": "Subdirectory to search, default '.'"},
            },
        },
    }),
    Tool("search_text", READ, fs.search_text, {
        "name": "search_text",
        "description": "Search file contents with a regex (grep-style) within the "
                       "working directory. Returns path:line: text. Read-only.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Python regular expression."},
                "subdir": {"type": "string", "description": "Subdirectory to search, default '.'"},
                "glob": {"type": "string", "description": "Optional filename glob filter, e.g. '*.py'."},
                "ignore_case": {"type": "boolean"},
            },
            "required": ["pattern"],
        },
    }),
    Tool("make_dir", BENIGN, fs.make_dir, {
        "name": "make_dir",
        "description": "Create a directory (and parents) within the working directory.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    }),
    Tool("write_file", DESTRUCTIVE, fs.write_file, {
        "name": "write_file",
        "description": "Write a file within the working directory. Existing files "
                       "must be read first (read-before-write).",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    }, plan_row=fs.plan_write),
    Tool("edit_file", DESTRUCTIVE, fs.edit_file, {
        "name": "edit_file",
        "description": "Replace text in an existing file (read it first). `old` must "
                       "be unique unless replace_all is set. Prefer this over "
                       "write_file for surgical changes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old": {"type": "string", "description": "Exact text to replace."},
                "new": {"type": "string", "description": "Replacement text."},
                "replace_all": {"type": "boolean", "description": "Replace every occurrence."},
            },
            "required": ["path", "old", "new"],
        },
    }, plan_row=fs.plan_edit),
    Tool("rename_file", DESTRUCTIVE, fs.rename_file, {
        "name": "rename_file",
        "description": "Rename a file within the working directory.",
        "input_schema": {
            "type": "object",
            "properties": {"src": {"type": "string"}, "dst": {"type": "string"}},
            "required": ["src", "dst"],
        },
    }, plan_row=fs.plan_rename),
    Tool("move_file", DESTRUCTIVE, fs.move_file, {
        "name": "move_file",
        "description": "Move a file to a new location within the working directory.",
        "input_schema": {
            "type": "object",
            "properties": {"src": {"type": "string"}, "dst": {"type": "string"}},
            "required": ["src", "dst"],
        },
    }, plan_row=fs.plan_move),
    Tool("delete_file", DESTRUCTIVE, fs.delete_file, {
        "name": "delete_file",
        "description": "Delete a file within the working directory. Irreversible; "
                       "gated like any destructive action.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    }, plan_row=fs.plan_delete),
    Tool("run_shell", EXEC, shell.run_shell, {
        "name": "run_shell",
        "description": "Run a shell command in the working directory. The exact "
                       "command is shown and must be approved every time.",
        "input_schema": {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
    }, plan_row=shell.plan_shell),
    Tool("web_fetch", NET, web.web_fetch, {
        "name": "web_fetch",
        "description": "Fetch the readable text of an http(s) web page, rendered to "
                       "plain text with w3m (no JavaScript). Use this when the user "
                       "gives you a URL or asks you to read/summarise a page. "
                       "Read-only — it never changes anything.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "An http:// or https:// URL."},
            },
            "required": ["url"],
        },
    }),
    Tool("knowledge_index", READ, knowledge.knowledge_index, {
        "name": "knowledge_index",
        "description": "Read the index of an OKF knowledge bundle (progressive "
                       "disclosure). Navigate this before reading whole concepts.",
        "input_schema": {
            "type": "object",
            "properties": {"scope": _SCOPE},
        },
    }),
    Tool("knowledge_read", READ, knowledge.knowledge_read, {
        "name": "knowledge_read",
        "description": "Read one concept document from an OKF knowledge bundle.",
        "input_schema": {
            "type": "object",
            "properties": {
                "scope": _SCOPE,
                "concept_id": {"type": "string", "description": "Path-style id, e.g. 'people/sam'."},
            },
            "required": ["scope", "concept_id"],
        },
    }),
    Tool("knowledge_write", DESTRUCTIVE, knowledge.knowledge_write, {
        "name": "knowledge_write",
        "description": "Promote a durable fact into an OKF knowledge bundle. Use "
                       "conservatively for things worth remembering across turns. "
                       "Concept types: project, preference, directory, person, fact.",
        "input_schema": {
            "type": "object",
            "properties": {
                "scope": _SCOPE,
                "concept_id": {"type": "string"},
                "type": {"type": "string", "description": "project|preference|directory|person|fact"},
                "title": {"type": "string"},
                "description": {"type": "string"},
                "body": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["scope", "concept_id", "type"],
        },
    }, plan_row=knowledge.plan_knowledge_write),
]}


def schemas(run_shell_enabled: bool, web_fetch_enabled: bool = False):
    """The tool schemas to advertise to the API. run_shell and web_fetch are each
    hidden unless their capability is enabled in config."""
    out = []
    for tool in REGISTRY.values():
        if tool.klass == EXEC and not run_shell_enabled:
            continue
        if tool.klass == NET and not web_fetch_enabled:
            continue
        out.append(tool.schema)
    return out


def get(name: str) -> Tool:
    if name not in REGISTRY:
        raise ToolError(f"unknown tool: {name}")
    return REGISTRY[name]
