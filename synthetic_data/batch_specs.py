#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from openai import OpenAI

MODEL = "gpt-5.4"
DEFAULT_FAMILY_COUNTS = {
    "patch_test_pass": 27,
    "patch_run_pass": 15,
    "patch_test_recover": 29,
    "patch_run_recover": 19,
    "test_only": 5,
    "run_only": 2,
}
FAMILY_SEQUENCES = {
    "patch_test_pass": ["read_file", "apply_patch", "cargo_test"],
    "patch_run_pass": ["read_file", "apply_patch", "cargo_run"],
    "patch_test_recover": ["read_file", "apply_patch", "cargo_test", "read_file", "apply_patch", "cargo_test"],
    "patch_run_recover": ["read_file", "apply_patch", "cargo_run", "read_file", "apply_patch", "cargo_run"],
    "test_only": ["cargo_test"],
    "run_only": ["cargo_run"],
}
DEFAULT_DIFFICULTY_COUNTS = {
    "patch_test_pass": {"easy": 7, "medium": 15, "hard": 5},
    "patch_run_pass": {"easy": 4, "medium": 8, "hard": 3},
    "patch_test_recover": {"easy": 4, "medium": 16, "hard": 9},
    "patch_run_recover": {"easy": 3, "medium": 9, "hard": 7},
    "test_only": {"easy": 3, "medium": 2, "hard": 0},
    "run_only": {"easy": 1, "medium": 1, "hard": 0},
}
BANNED_PATTERNS = (
    "Do not use these seed patterns: add/subtract arithmetic, hello/greeting typo, inclusive range sum, "
    "integer parse trim/signed/default, simple counter loop formatting."
)
PROBLEM_ARCHETYPES = (
    "parsing_validation",
    "sorting_ranking_tiebreaks",
    "aggregation_reporting",
    "state_transitions",
    "iterator_filter_map_logic",
    "match_enum_branch_logic",
    "config_merge_precedence",
    "interval_overlap_booking",
)
STEP_EXAMPLES = """Step skeleton examples:
- patch_test_pass: [{"tool":"read_file","file_path":"src/lib.rs"},{"tool":"apply_patch","file_path":"src/lib.rs","find":"...","replace":"..."},{"tool":"cargo_test","expect_status":"success"}]
- patch_run_pass: [{"tool":"read_file","file_path":"src/main.rs"},{"tool":"apply_patch","file_path":"src/main.rs","find":"...","replace":"..."},{"tool":"cargo_run","expect_status":"success"}]
- patch_test_recover: one or more read_file, apply_patch, cargo_test cycles; every cargo_test before the last fails; the last succeeds.
- patch_run_recover: one or more read_file, apply_patch, cargo_run cycles; every cargo_run before the last fails; the last succeeds.
- test_only: [{"tool":"cargo_test","expect_status":"success"}]
- run_only: [{"tool":"cargo_run","expect_status":"success"}]
"""

PROMPT = """You generate one Rust tool-use SFT dataset case spec.

Return valid JSON only. No markdown. No comments.

The final training trace will be built locally by executing tools. Do not include RESULT blocks. Do not invent tool outputs.

Target family: {family}
Case index: {case_index}
Difficulty target: {difficulty}
Target archetype: {archetype}

Difficulty definition:
- easy: one clear bug or straightforward already-correct single-tool task.
- medium: at least one nontrivial condition, branch, formatting rule, or edge case.
- hard: multiple independent behavioral requirements; for recovery families, failed verifier output should reveal useful next steps.

Archetype definitions:
- parsing_validation: parse structured text or records and validate rules.
- sorting_ranking_tiebreaks: ordering, ranking, deduping, or tie rules.
- aggregation_reporting: grouped totals, summaries, counters, filtered reports.
- state_transitions: event-driven status/state updates with invariants.
- iterator_filter_map_logic: iterator pipelines, filtering, mapping, accumulation.
- match_enum_branch_logic: branch coverage, enum handling, dispatch logic.
- config_merge_precedence: layered config/default/override merge behavior.
- interval_overlap_booking: ranges, overlaps, containment, booking conflicts.

{banned_patterns}

Protocol sequence required for this family:
{sequence}

Family meanings:
- patch_test_pass: one read, one patch, cargo_test succeeds.
- patch_run_pass: one read, one patch, cargo_run stdout exactly equals expected_output.
- patch_test_recover: one or more incomplete repair attempts fail cargo_test; the final patch makes tests pass.
- patch_run_recover: one or more incomplete repair attempts fail exact cargo_run stdout; the final patch makes stdout exactly equal expected_output.
- test_only: crate is already correct; only cargo_test is needed.
- run_only: crate is already correct; only cargo_run is needed and expected_output must match exactly.

{step_examples}

Hard constraints:
- Rust edition 2021.
- One tiny Cargo crate.
- No external dependencies.
- File paths are relative only: Cargo.toml, src/lib.rs, src/main.rs.
- Use lib.rs for cargo_test crates; use main.rs for cargo_run crates.
- Each apply_patch step must have exact find/replace strings.
- Each find string must occur exactly once in the file at that step.
- Steps must be executable exactly in order.
- expected_tool_sequence must exactly match the step tool order.
- expected_output must be null except cargo_run families, where it must be exact stdout without trailing newline.
- final must start with "FINAL: ".
- User prompt must contain "{{project_root}}" as the crate path placeholder.
- Keep code compact but realistic.
- Prefer small real utility logic over toy string cleanup.
- Do not center the task on whitespace normalization, slugify, title casing, label cleanup, or punctuation formatting unless the archetype is explicitly parsing_validation and that formatting is only a small part of the task.
- Before returning, mentally apply every patch and verify each expected_status is true.
- For apply_patch, prefer the smallest exact unique snippet needed; do not use a huge function body unless necessary.
- Do not make two apply_patch steps identical or semantically no-op.

Recovery constraints:
- For patch_test_recover and patch_run_recover, include one or more failed verifier turns before the final success.
- Every verifier turn before the last must fail because the patch is incomplete, not because code does not compile.
- Use tests/output expectations with separate requirements, so partial fixes really fail and the final fix really passes.

Return exactly this schema:
{{
  "family": "{family}",
  "case_id": "snake_case_unique_name",
  "bug_category": "{archetype}",
  "difficulty": "{difficulty}",
  "user": "natural user instruction using {{project_root}}",
  "expected_tool_sequence": {sequence_json},
  "expected_output": {expected_output_json},
  "files": {{
    "Cargo.toml": "...",
    "{source_file}": "..."
  }},
  "steps": [
    {{ "tool": "..." }}
  ],
  "final": "FINAL: ..."
}}

Step object shapes:
- read_file: {{"tool": "read_file", "file_path": "{source_file}"}}
- apply_patch: {{"tool": "apply_patch", "file_path": "{source_file}", "find": "...", "replace": "..."}}
- cargo_test: {{"tool": "cargo_test", "expect_status": "failed|success"}}
- cargo_run: {{"tool": "cargo_run", "expect_status": "failed|success"}}

For patch families, the first step must read the file being patched.
For cargo_run families, expected_output is the exact final stdout.
For cargo_test families, expected_output is null.
For this request, expected_output must be {expected_output_rule}.
"""


def _difficulty_mix_for_total(total: int, family: str) -> dict[str, int]:
    base = DEFAULT_DIFFICULTY_COUNTS[family]
    base_total = DEFAULT_FAMILY_COUNTS[family]
    scaled = {
        key: int(round(total * value / base_total))
        for key, value in base.items()
    }
    diff = total - sum(scaled.values())
    order = ["medium", "hard", "easy"] if "recover" in family else ["medium", "easy", "hard"]
    while diff != 0:
        for key in order:
            if diff == 0:
                break
            if diff > 0:
                scaled[key] += 1
                diff -= 1
            elif scaled[key] > 0:
                scaled[key] -= 1
                diff += 1
    return scaled


def difficulty_for(family: str, case_index: int, family_counts: dict[str, int]) -> str:
    counts = _difficulty_mix_for_total(family_counts[family], family)
    if sum(counts.values()) != family_counts[family]:
        raise ValueError(f"difficulty counts do not match family count for {family}")
    remaining = counts.copy()
    cycle = ["easy", "medium", "medium", "hard"]
    if "recover" in family:
        cycle = ["medium", "hard", "medium", "easy"]
    if family in {"test_only", "run_only"}:
        cycle = ["easy", "medium"]
    schedule: list[str] = []
    while len(schedule) < family_counts[family]:
        for difficulty in cycle:
            if remaining.get(difficulty, 0) > 0:
                schedule.append(difficulty)
                remaining[difficulty] -= 1
            if len(schedule) == family_counts[family]:
                break
    return schedule[case_index - 1]


def archetype_for(case_index: int) -> str:
    return PROBLEM_ARCHETYPES[(case_index - 1) % len(PROBLEM_ARCHETYPES)]


def build_prompt(family: str, case_index: int, difficulty: str) -> str:
    sequence = FAMILY_SEQUENCES[family]
    expected_output_rule = "a JSON string" if "run" in family else "JSON null"
    expected_output_json = '"exact final stdout"' if "run" in family else "null"
    source_file = "src/main.rs" if "run" in family else "src/lib.rs"
    archetype = archetype_for(case_index)
    return PROMPT.format(
        family=family,
        case_index=case_index,
        difficulty=difficulty,
        archetype=archetype,
        banned_patterns=BANNED_PATTERNS,
        step_examples=STEP_EXAMPLES,
        sequence=" -> ".join(sequence),
        sequence_json=json.dumps(sequence),
        expected_output_rule=expected_output_rule,
        expected_output_json=expected_output_json,
        source_file=source_file,
    )


def iter_requests(family_counts: dict[str, int], custom_prefix: str) -> list[dict]:
    rows = []
    global_idx = 0
    for family, count in family_counts.items():
        for i in range(count):
            difficulty = difficulty_for(family, i + 1, family_counts)
            prompt = build_prompt(family, i + 1, difficulty)
            rows.append({
                "custom_id": f"{custom_prefix}-{global_idx:03d}-{family}-{i+1:03d}",
                "method": "POST",
                "url": "/v1/responses",
                "body": {
                    "model": MODEL,
                    "input": [
                        {"role": "system", "content": "You produce strict JSON specs for executable Rust SFT data generation."},
                        {"role": "user", "content": prompt},
                    ],
                    "text": {"format": {"type": "json_object"}},
                    "max_output_tokens": 2600,
                },
            })
            global_idx += 1
    return rows


def write_jsonl(path: Path, family_counts: dict[str, int], custom_prefix: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = iter_requests(family_counts, custom_prefix)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    families = Counter(row["custom_id"].split("-", 2)[2].rsplit("-", 1)[0] for row in rows)
    difficulties = Counter(
        row["body"]["input"][1]["content"].split("Difficulty target: ", 1)[1].splitlines()[0]
        for row in rows
    )
    print(json.dumps({
        "wrote": str(path),
        "requests": len(rows),
        "families": dict(sorted(families.items())),
        "difficulties": dict(sorted(difficulties.items())),
    }, indent=2))


def preview_prompt(family: str, case_index: int) -> None:
    if family not in DEFAULT_FAMILY_COUNTS:
        raise SystemExit(f"unknown family {family}")
    difficulty = difficulty_for(family, case_index, DEFAULT_FAMILY_COUNTS)
    print(build_prompt(family, case_index, difficulty))


def submit(path: Path, metadata: Path, task_name: str) -> None:
    client = OpenAI()
    uploaded = client.files.create(file=path.open("rb"), purpose="batch")
    batch = client.batches.create(
        input_file_id=uploaded.id,
        endpoint="/v1/responses",
        completion_window="24h",
        metadata={"task": task_name, "model": MODEL},
    )
    metadata.parent.mkdir(parents=True, exist_ok=True)
    metadata.write_text(json.dumps({"file_id": uploaded.id, "batch_id": batch.id}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"file_id": uploaded.id, "batch_id": batch.id, "status": batch.status}, indent=2))


def status(metadata: Path) -> None:
    client = OpenAI()
    meta = json.loads(metadata.read_text(encoding="utf-8"))
    batch = client.batches.retrieve(meta["batch_id"])
    print(batch.model_dump_json(indent=2))


def retrieve(metadata: Path, output: Path) -> None:
    client = OpenAI()
    meta = json.loads(metadata.read_text(encoding="utf-8"))
    batch = client.batches.retrieve(meta["batch_id"])
    if not batch.output_file_id:
        raise SystemExit(f"batch has no output_file_id; status={batch.status}")
    content = client.files.content(batch.output_file_id).read()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(content)
    print(f"wrote {output}")


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("build")
    p.add_argument("--output", type=Path, default=Path("synthetic_data/batch_pilot_100/requests.jsonl"))
    p.add_argument("--counts-json", type=Path, default=None)
    p.add_argument("--custom-prefix", default="pilot100")
    p = sub.add_parser("preview-prompt")
    p.add_argument("--family", choices=sorted(DEFAULT_FAMILY_COUNTS), default="patch_test_recover_twice")
    p.add_argument("--case-index", type=int, default=1)
    p = sub.add_parser("submit")
    p.add_argument("--input", type=Path, default=Path("synthetic_data/batch_pilot_100/requests.jsonl"))
    p.add_argument("--metadata", type=Path, default=Path("synthetic_data/batch_pilot_100/batch.json"))
    p.add_argument("--task-name", default="glyph_sft_pilot_100_specs")
    p = sub.add_parser("status")
    p.add_argument("--metadata", type=Path, default=Path("synthetic_data/batch_pilot_100/batch.json"))
    p = sub.add_parser("retrieve")
    p.add_argument("--metadata", type=Path, default=Path("synthetic_data/batch_pilot_100/batch.json"))
    p.add_argument("--output", type=Path, default=Path("synthetic_data/batch_pilot_100/results.jsonl"))
    args = parser.parse_args()

    if args.cmd == "build":
        family_counts = DEFAULT_FAMILY_COUNTS
        if args.counts_json is not None:
            family_counts = json.loads(args.counts_json.read_text(encoding="utf-8"))
        write_jsonl(args.output, family_counts, args.custom_prefix)
    elif args.cmd == "preview-prompt":
        preview_prompt(args.family, args.case_index)
    elif args.cmd == "submit":
        submit(args.input, args.metadata, args.task_name)
    elif args.cmd == "status":
        status(args.metadata)
    elif args.cmd == "retrieve":
        retrieve(args.metadata, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
