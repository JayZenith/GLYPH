"""Generate the compact browser-side trace data used by blog/index.html."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROLLOUTS = ROOT / "glyph_results" / "RLVR_VFINAL_STEP10" / "rollouts_step_10" / "train_rollouts.jsonl"
OUT = ROOT / "blog" / "traces.js"

ORDER = ["clean-solve", "recovery", "long-recovery"]

SELECTORS = {
    "clean-solve": (663, "FINAL: Updated merge precedence so direct values now override profile values for all fields except tls"),
    "recovery": (113, "FINAL: Updated leaderboard sorting to use score desc, wins desc, then name asc"),
    "long-recovery": (436, "FINAL: The iterator pipeline now trims each part"),
}

LABELS = {
    "clean-solve": "RLVR step 10 - config merge recovery",
    "recovery": "RLVR step 10 - ranking recovery",
    "long-recovery": "RLVR step 10 - token parser recovery",
}

DESCRIPTIONS = {
    "clean-solve": "Passes every test but changes TLS precedence against the written specification.",
    "recovery": "Uses failed-test output to repair sorting and shared-rank behavior.",
    "long-recovery": "Recovers through repeated feedback and fixes trimming and signed-number parsing.",
}

NOTES = {
    "clean-solve": (
        "One auditable verifier-gap example, not a prevalence estimate or evidence "
        "of a material effect on aggregate results."
    ),
}


def main() -> None:
    rows = [json.loads(line) for line in ROLLOUTS.read_text().splitlines()]
    output = []

    for trace_id in ORDER:
        example_id, final_prefix = SELECTORS[trace_id]
        matches = [
            row for row in rows
            if row["example_id"] == example_id
            and row["completion"]
            and row["completion"][-1]["content"].startswith(final_prefix)
        ]
        if len(matches) != 1:
            raise RuntimeError(f"expected one {trace_id} rollout, found {len(matches)}")
        row = matches[0]
        turns = []
        for turn in [*row["prompt"], *row["completion"]]:
            turns.append({
                "role": turn["role"],
                "content": turn["content"].removesuffix("\n<|im_end|>"),
            })
        output.append({
            "id": trace_id,
            "label": LABELS[trace_id],
            "model": "JayZenith/RLVR_VFINAL_STEP10",
            "reward": row["reward"],
            "description": DESCRIPTIONS[trace_id],
            "note": NOTES.get(trace_id),
            "turns": turns,
        })

    OUT.write_text("window.GLYPH_TRACES = " + json.dumps(output, indent=2) + ";\n")
    print(f"wrote {OUT} ({len(output)} traces)")


if __name__ == "__main__":
    main()
