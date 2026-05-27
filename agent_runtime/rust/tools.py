from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Tool:
    name: str
    description: str
    params: dict[str, dict]


RUST_TOOLS = [
    Tool(
        name="cargo_test",
        description="Runs the test suite for a Cargo project",
        params={
            "project_path": {
                "type": "string",
                "description": "Path to the Cargo project directory",
            },
        },
    ),
    Tool(
        name="cargo_run",
        description="Builds and runs the binary of a Cargo project, returning its stdout",
        params={
            "project_path": {
                "type": "string",
                "description": "Path to the Cargo project directory",
            },
        },
    ),
    Tool(
        name="read_file",
        description="Reads a file from disk and returns its contents (truncated if very large).",
        params={
            "file_path": {
                "type": "string",
                "description": "Path to the file to read",
            },
        },
    ),
    Tool(
        name="apply_patch",
        description="Applies a textual find/replace edit to a single file. The 'find' text must occur exactly once.",
        params={
            "file_path": {
                "type": "string",
                "description": "Path to the file to edit",
            },
            "find": {
                "type": "string",
                "description": "Exact text snippet to locate (must occur exactly once in the file)",
            },
            "replace": {
                "type": "string",
                "description": "Replacement text",
            },
        },
    ),
]
