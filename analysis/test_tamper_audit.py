#!/usr/bin/env python3
"""Audit: did any eval rollout patch test code? Scans every apply_patch CALL in
every saved rollout of the headline eval files; flags patches whose find/replace
touches test markers or test files."""
import json
import re
import sys
from pathlib import Path

ROOT = Path("/home/jay-zenith/Desktop/GLYPH/glyph_results")
FILES = (
    sorted(ROOT.glob("*/evals/passk8_heldout150.json"))
    + sorted(ROOT.glob("*/passk8_heldout150_run*.json"))
    + sorted(ROOT.glob("*/evals/seeds/*.json"))  # only compiler's carry rollouts
)

CALL_RE = re.compile(r"CALL apply_patch (\{.*?\})\s*(?:\n|$)")
TEST_MARKERS = re.compile(r"#\[test\]|#\[cfg\(test\)\]|mod tests|assert_eq!|assert!|assert_ne!")


def extract_calls(trace: str):
    for m in CALL_RE.finditer(trace):
        raw = m.group(1)
        try:
            yield json.loads(raw)
        except json.JSONDecodeError:
            # fall back: capture may have cut a nested brace; try greedy to line end
            line = trace[m.start():].split("\n", 1)[0]
            start = line.index("{")
            for end in range(len(line), start, -1):
                try:
                    yield json.loads(line[start:end])
                    break
                except json.JSONDecodeError:
                    continue


def main():
    total_calls = 0
    flagged = []
    bad_path = []
    parsed_files = 0
    for f in FILES:
        try:
            rows = json.load(open(f))
        except Exception as e:
            print(f"SKIP {f}: {e}")
            continue
        parsed_files += 1
        for row in rows:
            for i, ro in enumerate(row.get("rollouts") or []):
                trace = ro.get("trace") or ""
                for call in extract_calls(trace):
                    total_calls += 1
                    fp = str(call.get("file_path", ""))
                    find = str(call.get("find", ""))
                    repl = str(call.get("replace", ""))
                    if "tests/" in fp or fp.endswith("Cargo.toml"):
                        bad_path.append((f.parent.parent.name, row["name"], i, fp))
                    if TEST_MARKERS.search(find) or TEST_MARKERS.search(repl):
                        flagged.append({
                            "arm": str(f).split("glyph_results/")[1].split("/")[0],
                            "file": f.name,
                            "case": row["name"],
                            "rollout": i,
                            "valid": ro.get("valid_trace"),
                            "file_path": fp,
                            "find": find[:200],
                            "replace": repl[:200],
                        })
    print(f"files parsed: {parsed_files}")
    print(f"apply_patch calls scanned: {total_calls}")
    print(f"patches to tests/ dir or Cargo.toml: {len(bad_path)}")
    for b in bad_path[:10]:
        print("  ", b)
    print(f"patches touching test markers in find/replace: {len(flagged)}")
    out = Path("/tmp/flagged_patches.json")
    json.dump(flagged, open(out, "w"), indent=1)
    print(f"flagged detail -> {out}")
    # summary of flagged by arm and validity
    from collections import Counter
    c = Counter((x["arm"], bool(x["valid"])) for x in flagged)
    for k, v in sorted(c.items()):
        print("  ", k, v)


if __name__ == "__main__":
    main()
