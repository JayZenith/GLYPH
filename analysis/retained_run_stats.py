#!/usr/bin/env python3
"""Reproduces every headline (trace-retained) statistic in the README/blog.

Reads the retained eval JSONs from glyph_results/ (full per-rollout traces;
mirrored on the HF dataset JayZenith/Glyph-RLVR-Eval-Results) and prints
valid@8 per run plus the paired prompt-level sign-flip permutation tests.

Run:  python3 analysis/retained_run_stats.py
"""
from __future__ import annotations

import json
import random
from pathlib import Path

R = Path(__file__).resolve().parent.parent / "glyph_results"

RETAINED = {
    "SFT": [R / "SFT_HALF_A_V8/evals/passk8_heldout150.json"],
    "SPARSE": [R / f"RLVR_POOL_B_V8_STEP10/passk8_heldout150_run{i}.json" for i in (1, 2, 3)],
    "DENSE": [R / "RLVR_VFINAL_STEP10/evals/passk8_heldout150.json"],
    "COMPILER": [
        R / "RLVR_VFINAL2_STEP10/evals/passk8_heldout150.json",
        R / "RLVR_VFINAL2_STEP10/evals/seeds/step10_seedB.json",
        R / "RLVR_VFINAL2_STEP10/evals/seeds/step10_seedC.json",
    ],
}


def solved(path: Path) -> dict[str, int]:
    rows = json.load(open(path))
    assert all("rollouts" in r for r in rows), f"{path} is not trace-retained"
    return {r["name"]: (1 if r["valid_trace_solves"] > 0 else 0) for r in rows}


def paired_perm(a: dict, b: dict, iters: int = 20000) -> tuple[int, int, int, float]:
    names = sorted(a)
    diffs = [b[k] - a[k] for k in names]
    up, down = sum(d > 0 for d in diffs), sum(d < 0 for d in diffs)
    obs = sum(diffs)
    rng = random.Random(0)
    hits = sum(
        1 for _ in range(iters)
        if abs(sum(d if rng.random() < 0.5 else -d for d in diffs)) >= abs(obs) - 1e-12
    )
    return obs, up, down, hits / iters


def main() -> int:
    runs = {arm: [solved(p) for p in paths] for arm, paths in RETAINED.items()}
    print("=== valid@8 per trace-retained run (150 prompts) ===")
    for arm, rs in runs.items():
        print(f"  {arm:9} {[sum(r.values()) for r in rs]}")

    print("\n=== paired prompt-level sign-flip permutation (run 1 vs run 1) ===")
    for a, b in [("SFT", "DENSE"), ("SFT", "SPARSE"), ("SFT", "COMPILER"), ("DENSE", "COMPILER")]:
        obs, up, down, p = paired_perm(runs[a][0], runs[b][0])
        print(f"  {b} vs {a}: Δvalid@8 = {obs:+d}  ({up} prompts up / {down} down)  p = {p:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
