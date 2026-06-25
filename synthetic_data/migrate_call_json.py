#!/usr/bin/env python3
"""Migrate legacy Glyph CALL lines to JSON CALL payloads.

Runtime accepts only the current protocol:

    CALL tool_name {"id":"c1","arg":"value"}

This script exists only to convert historical synthetic traces that used the
legacy parenthesized argument form.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


CALL_PREFIX_RE = re.compile(r"^(\s*)CALL\s+([A-Za-z_]\w*)\(")


def _parse_legacy_args(blob: str) -> dict[str, str]:
    params: dict[str, str] = {}
    pos = 0
    first = True
    while pos < len(blob):
        while pos < len(blob) and blob[pos].isspace():
            pos += 1
        if pos >= len(blob):
            break
        if not first:
            if blob[pos] != ",":
                raise ValueError("expected comma between CALL arguments")
            pos += 1
            while pos < len(blob) and blob[pos].isspace():
                pos += 1
        first = False

        key_match = re.match(r"[A-Za-z_]\w*", blob[pos:])
        if not key_match:
            raise ValueError("expected CALL argument name")
        key = key_match.group(0)
        pos += key_match.end()
        while pos < len(blob) and blob[pos].isspace():
            pos += 1
        if pos >= len(blob) or blob[pos] != "=":
            raise ValueError(f"expected '=' after CALL argument {key}")
        pos += 1
        while pos < len(blob) and blob[pos].isspace():
            pos += 1
        if pos >= len(blob) or blob[pos] != '"':
            raise ValueError(f"expected JSON string for CALL argument {key}")

        start = pos
        pos += 1
        escaped = False
        while pos < len(blob):
            ch = blob[pos]
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                pos += 1
                break
            pos += 1
        else:
            raise ValueError(f"unterminated string for CALL argument {key}")

        if key in params:
            raise ValueError(f"duplicate CALL argument {key}")
        params[key] = json.loads(blob[start:pos])
    return params


def _find_legacy_call_end(line: str, open_paren: int) -> int:
    pos = open_paren + 1
    escaped = False
    in_string = False
    while pos < len(line):
        ch = line[pos]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
        elif ch == ")":
            return pos
        pos += 1
    raise ValueError("unterminated legacy CALL")


def migrate_line(line: str) -> str:
    match = CALL_PREFIX_RE.match(line)
    if not match:
        return line
    indent, tool = match.groups()
    open_paren = match.end() - 1
    close_paren = _find_legacy_call_end(line, open_paren)
    params = _parse_legacy_args(line[open_paren + 1:close_paren])
    payload = json.dumps(params, ensure_ascii=False, separators=(",", ":"))
    return f"{indent}CALL {tool} {payload}{line[close_paren + 1:]}"


def migrate_text(text: str) -> str:
    return "".join(migrate_line(line) for line in text.splitlines(keepends=True))


def migrate_value(value: Any) -> Any:
    if isinstance(value, str):
        return migrate_text(value)
    if isinstance(value, list):
        return [migrate_value(item) for item in value]
    if isinstance(value, dict):
        return {key: migrate_value(item) for key, item in value.items()}
    return value


def migrate_jsonl(path: Path) -> bool:
    changed = False
    out_lines: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw:
            out_lines.append(raw)
            continue
        row = json.loads(raw)
        migrated = migrate_value(row)
        changed = changed or migrated != row
        out_lines.append(json.dumps(migrated, ensure_ascii=False, separators=(",", ":")))
    if changed:
        path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    return changed


def migrate_json(path: Path) -> bool:
    original = json.loads(path.read_text(encoding="utf-8"))
    migrated = migrate_value(original)
    if migrated == original:
        return False
    path.write_text(json.dumps(migrated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True


def migrate_plain(path: Path) -> bool:
    original = path.read_text(encoding="utf-8")
    migrated = migrate_text(original)
    if migrated == original:
        return False
    path.write_text(migrated, encoding="utf-8")
    return True


def iter_files(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_dir():
            files.extend(
                child
                for child in path.rglob("*")
                if child.is_file()
                and child.suffix in {".jsonl", ".json", ".md", ".py", ".yaml", ".yml", ".txt"}
            )
        elif path.is_file():
            files.append(path)
    return files


def migrate_file(path: Path) -> bool:
    if path.name == "migrate_call_json.py":
        return False
    if path.suffix == ".jsonl":
        return migrate_jsonl(path)
    if path.suffix == ".json":
        return migrate_json(path)
    return migrate_plain(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()

    changed: list[Path] = []
    for path in iter_files(args.paths):
        if migrate_file(path):
            changed.append(path)
    for path in changed:
        print(path)
    print(f"migrated {len(changed)} files")


if __name__ == "__main__":
    main()
