"""Thin wrapper around the official Anthropic SDK.

The API key comes from ANTHROPIC_API_KEY in the environment ONLY. It is read at
runtime, never written to disk, never logged. The `anthropic` import is local to
the functions so the rest of loci (and the test suite) does not require the SDK.
"""

from __future__ import annotations

import os
from typing import List, Optional

MAX_TOKENS = 4096


class MissingKeyError(Exception):
    pass


def get_api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise MissingKeyError(
            "ANTHROPIC_API_KEY is not set.\n"
            "  Set it in your shell, e.g.:\n"
            '    export ANTHROPIC_API_KEY="sk-ant-..."\n'
            "  loci reads it from the environment and never stores it."
        )
    return key


def make_client():
    import anthropic  # local import: keeps the SDK optional for non-API code paths
    return anthropic.Anthropic(api_key=get_api_key())


def stream_assistant(client, model: str, system: str, messages: List[dict],
                     tools: List[dict], ui, max_tokens: int = MAX_TOKENS) -> List[dict]:
    """Stream one assistant message; print its text; return its content blocks
    as plain JSON-serializable dicts (text and tool_use)."""
    blocks: List[dict] = []
    with client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=messages,
        tools=tools,
    ) as stream:
        for text in stream.text_stream:
            ui.agent(text)
        final = stream.get_final_message()

    printed_text = False
    for block in final.content:
        if block.type == "text":
            blocks.append({"type": "text", "text": block.text})
            printed_text = True
        elif block.type == "tool_use":
            blocks.append({
                "type": "tool_use",
                "id": block.id,
                "name": block.name,
                "input": block.input,
            })
    if printed_text:
        ui.line("")  # newline after streamed speech
    return blocks
