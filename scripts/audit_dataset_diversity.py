#!/usr/bin/env python3
"""Cheap diversity audit for SFT trace dataset.

Flags template collapse: 1008/1137 traces from one model is the failure mode
where a small set of phrases dominate, the model overfits to template tokens,
and generation collapses.

Outputs:
  - length distribution
  - top repeated n-grams across traces (template fingerprints)
  - pairwise Jaccard similarity sample (avg + max + p95)
  - "near-duplicate" pairs above a threshold
"""
import argparse
import json
import random
from collections import Counter
from pathlib import Path
from statistics import mean, median


def char_ngrams(text: str, n: int) -> set[str]:
    return {text[i:i + n] for i in range(len(text) - n + 1)}


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / max(1, len(a | b))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--ngram", type=int, default=12, help="char n-gram size for similarity")
    ap.add_argument("--top-ngram", type=int, default=24, help="char n-gram size for fingerprint search")
    ap.add_argument("--sample", type=int, default=300, help="pairs to sample for similarity")
    ap.add_argument("--near-dup-threshold", type=float, default=0.6)
    ap.add_argument("--top-k", type=int, default=20)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    traces = []
    with open(args.data) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                traces.append(json.loads(line)["trace"])
            except (json.JSONDecodeError, KeyError):
                pass
    n = len(traces)
    if n < 2:
        print(f"Not enough traces ({n}).")
        return 1

    # length distribution (chars — fast proxy for tokens)
    lens = [len(t) for t in traces]
    lens_sorted = sorted(lens)
    print(f"\n=== Length (chars) — n={n} ===")
    print(f"  min={min(lens)}  median={median(lens):.0f}  mean={mean(lens):.0f}")
    print(f"  p90={lens_sorted[int(0.9 * n)]}  p99={lens_sorted[int(0.99 * n)]}  max={max(lens)}")

    # top repeated n-grams (template fingerprints)
    print(f"\n=== Top {args.top_k} {args.top_ngram}-char n-grams across traces ===")
    counter: Counter = Counter()
    for t in traces:
        # only count each n-gram ONCE per trace, so we measure cross-trace presence
        counter.update(set(t[i:i + args.top_ngram] for i in range(len(t) - args.top_ngram + 1)))
    for ngram, count in counter.most_common(args.top_k):
        pct = count / n * 100
        snippet = ngram.replace("\n", "\\n")
        print(f"  {count:5d} ({pct:5.1f}%)  {snippet!r}")

    # pairwise Jaccard sample
    print(f"\n=== Pairwise Jaccard ({args.ngram}-char n-grams, {args.sample} random pairs) ===")
    sets = [char_ngrams(t, args.ngram) for t in traces]
    pairs = [(rng.randrange(n), rng.randrange(n)) for _ in range(args.sample)]
    pairs = [(i, j) for i, j in pairs if i != j]
    sims = [jaccard(sets[i], sets[j]) for i, j in pairs]
    sims_sorted = sorted(sims)
    print(f"  mean={mean(sims):.3f}  median={median(sims):.3f}  max={max(sims):.3f}  p95={sims_sorted[int(0.95 * len(sims))]:.3f}")

    # near-duplicate pairs
    near_dups = sorted(
        ((s, i, j) for s, (i, j) in zip(sims, pairs) if s >= args.near_dup_threshold),
        reverse=True,
    )[:10]
    print(f"\n=== Near-duplicates (Jaccard >= {args.near_dup_threshold}, top 10 from sample) ===")
    if not near_dups:
        print("  none in sample")
    for s, i, j in near_dups:
        print(f"  sim={s:.3f}  trace[{i}] vs trace[{j}]")
        print(f"    A: {traces[i][:100]!r}")
        print(f"    B: {traces[j][:100]!r}")

    print("\n=== Heuristic flags ===")
    flags = []
    if mean(sims) > 0.4:
        flags.append(f"⚠ high avg pairwise similarity ({mean(sims):.3f}) — possible template collapse")
    template_fingerprints = [c for _, c in counter.most_common(args.top_k) if c > 0.8 * n]
    if template_fingerprints:
        flags.append(f"⚠ {len(template_fingerprints)} {args.top_ngram}-grams appear in >80% of traces — template signature")
    if not flags:
        print("  none — diversity looks healthy on these heuristics")
    for f in flags:
        print(f"  {f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
