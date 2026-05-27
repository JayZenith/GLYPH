#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from synthetic_data.validate_dataset import CANONICAL_FAMILIES


def _read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as handle:
        for line_no, raw in enumerate(handle, 1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                rows.append(json.loads(raw))
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{line_no}: invalid json: {exc}") from exc
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge per-family synthetic trace files into one training JSONL.")
    parser.add_argument("--families-dir", type=Path, default=Path("synthetic_data/families"))
    parser.add_argument("--output", type=Path, default=Path("synthetic_data/train.jsonl"))
    parser.add_argument("--shuffle-seed", type=int, default=1337)
    parser.add_argument("--no-shuffle", action="store_true")
    parser.add_argument("--expected-total", type=int, default=None)
    args = parser.parse_args()

    rows: list[dict] = []
    missing: list[str] = []
    for family in CANONICAL_FAMILIES:
        path = args.families_dir / f"{family}.jsonl"
        if not path.exists():
            missing.append(str(path))
            continue
        rows.extend(_read_jsonl(path))
    if missing:
        raise SystemExit("missing family files:\n" + "\n".join(missing))
    if args.expected_total is not None and len(rows) != args.expected_total:
        raise SystemExit(f"row count {len(rows)} != expected_total {args.expected_total}")

    if not args.no_shuffle:
        random.Random(args.shuffle_seed).shuffle(rows)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    counts = Counter(str(row.get("family")) for row in rows)
    print(json.dumps({"wrote": str(args.output), "rows": len(rows), "families": dict(sorted(counts.items()))}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
