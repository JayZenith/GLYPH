#!/usr/bin/env python3
"""EXPLORATORY pooled analysis: does any RLVR arm beat SFT, and where does
movement live?

CAVEAT: this pools three eval repetitions per arm, but for SFT and dense the
2nd/3rd repetitions exist only as per-prompt aggregate counts (raw rollout
traces not retained) — count-auditable, not trace-auditable. Sparse and
compiler-aware repetitions are fully trace-retained. Treat every number below
as exploratory; headline claims rest only on the trace-retained runs (README).

  1. Arm-level: paired sign-flip permutation on per-prompt solve fractions.
  2. Band-level: split prompts by SFT difficulty (bands from SFT run A only;
     deltas vs SFT runs B+C, so regression-to-the-mean cannot manufacture the
     pattern) with a bootstrap 95% CI per band. Bands group held-out EVAL
     prompts; they do not measure RL training groups, so any link to the GRPO
     zero-advantage mechanism is a hypothesis, not evidence.

Run:  python3 analysis/pooled_band_analysis.py   (downloads via huggingface_hub)
"""
from __future__ import annotations

import json
import random

from huggingface_hub import hf_hub_download

REPO = "JayZenith/Glyph-RLVR-Eval-Results"
ARMS = {
    "SFT": [
        "SFT_HALF_A_V8/evals/passk8_heldout150.json",
        "SFT_HALF_A_V8/evals/seeds/sft_seed1.json",
        "SFT_HALF_A_V8/evals/seeds/sft_seedB.json",
    ],
    "SPARSE": [
        "RLVR_POOL_B_V8_STEP10/evals/passk8_heldout150_run1.json",
        "RLVR_POOL_B_V8_STEP10/evals/passk8_heldout150_run2.json",
        "RLVR_POOL_B_V8_STEP10/evals/passk8_heldout150_run3.json",
    ],
    "DENSE": [
        "RLVR_VFINAL_STEP10/evals/passk8_heldout150.json",
        "RLVR_VFINAL_STEP10/evals/seeds/step10_seedB.json",
        "RLVR_VFINAL_STEP10/evals/seeds/step10_seedC.json",
    ],
    "COMPILER": [
        "RLVR_VFINAL2_STEP10/evals/passk8_heldout150.json",
        "RLVR_VFINAL2_STEP10/evals/seeds/step10_seedB.json",
        "RLVR_VFINAL2_STEP10/evals/seeds/step10_seedC.json",
    ],
}
K = 8  # rollouts per prompt per run


def solves(remote_path: str) -> dict[str, int]:
    local = hf_hub_download(REPO, remote_path, repo_type="dataset")
    return {r["name"]: r["valid_trace_solves"] for r in json.load(open(local))}


def paired_perm(a: dict, b: dict, names: list[str], n_roll: int, iters: int = 20000) -> tuple[float, float]:
    diffs = [(b[k] - a[k]) / n_roll for k in names]
    obs = sum(diffs) / len(diffs)
    rng = random.Random(0)
    hits = sum(
        1
        for _ in range(iters)
        if abs(sum(d if rng.random() < 0.5 else -d for d in diffs) / len(diffs)) >= abs(obs) - 1e-12
    )
    return obs, hits / iters


def main() -> int:
    runs = {arm: [solves(p) for p in paths] for arm, paths in ARMS.items()}
    pooled = {
        arm: {k: sum(r[k] for r in rs) for k in rs[0]}  # solves out of 24
        for arm, rs in runs.items()
    }
    names = sorted(pooled["SFT"])
    n = len(names)

    print(f"=== pooled over 3 runs x {K} rollouts = 24 rollouts/prompt, n={n} prompts ===")
    for arm in ARMS:
        per_run = [sum(1 for v in r.values() if v > 0) for r in runs[arm]]
        p1 = sum(pooled[arm].values()) / (3 * K * n)
        print(f"  {arm:9} valid@8 per run {per_run}   pooled pass@1 = {p1:.4f}")

    print("\n=== arm vs SFT: paired sign-flip permutation on per-prompt pass@1 ===")
    for arm in ["SPARSE", "DENSE", "COMPILER"]:
        obs, p = paired_perm(pooled["SFT"], pooled[arm], names, 3 * K)
        print(f"  {arm:9} Δpass@1 = {obs:+.4f}   p = {p:.3f}")
    obs, p = paired_perm(pooled["DENSE"], pooled["COMPILER"], names, 3 * K)
    print(f"  COMPILER vs DENSE: Δpass@1 = {obs:+.4f}   p = {p:.3f}")

    band_ref = runs["SFT"][0]
    sft_bc = {k: runs["SFT"][1][k] + runs["SFT"][2][k] for k in names}  # /16
    rng = random.Random(0)
    for arm in ["SPARSE", "DENSE", "COMPILER"]:
        print(f"\n=== EXPLORATORY: {arm} by band (bands from SFT run A; deltas vs SFT runs B+C) ===")
        for lo, hi, label in [(0, 0, "never-solved 0/8"), (1, 3, "frontier-low 1-3"),
                              (4, 6, "frontier-mid 4-6"), (7, 8, "high 7-8")]:
            ks = [k for k in names if lo <= band_ref[k] <= hi]
            deltas = [pooled[arm][k] / 24 - sft_bc[k] / 16 for k in ks]
            d = sum(deltas) / len(deltas)
            # bootstrap 95% CI over prompts within the band
            boots = sorted(
                sum(deltas[rng.randrange(len(deltas))] for _ in deltas) / len(deltas)
                for _ in range(10000)
            )
            lo95, hi95 = boots[249], boots[9749]
            print(f"  {label:18} n={len(ks):3}   Δpass@1 = {d:+.4f}   95% CI [{lo95:+.4f}, {hi95:+.4f}]")
    print("\nNOTE: exploratory subgroup analysis on partially trace-unauditable data;")
    print("band-mechanism link is a hypothesis. Headline claims: trace-retained runs only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
