#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path


def read_ids(path: Path) -> list[str]:
    ids: list[str] = []
    with path.open(encoding="utf-8") as handle:
        for line_no, raw in enumerate(handle, 1):
            raw = raw.strip()
            if not raw:
                continue
            row = json.loads(raw)
            case_id = row.get("case_id")
            if not isinstance(case_id, str):
                raise SystemExit(f"{path}:{line_no}: missing string case_id")
            ids.append(case_id)
    return ids


def source_file(root: Path, case_id: str) -> Path:
    # the 150-case eval set spans two blueprint roots (eval100_* under
    # eval_blueprints/, heldoutfail* under blueprints/)
    for r in (root, root.parent / "blueprints"):
        case_root = r / case_id
        for name in ("lib.rs", "main.rs"):
            p = case_root / "src" / name
            if p.exists():
                return p
    raise FileNotFoundError(f"missing Rust source for {case_id} under {root}")


def normalize_source(text: str) -> str:
    """Strip comments and whitespace AND normalize literals: every string
    literal becomes "S" and every numeric literal becomes 0, so two crates
    that differ only in field values/sample data hash identically."""
    text = re.sub(r"//.*", "", text)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r'"(?:\\.|[^"\\])*"', '"S"', text)
    text = re.sub(r"\b\d+(?:\.\d+)?(?:_?[iuf]\d+|_?usize|_?isize)?\b", "0", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _self_test() -> None:
    a = 'fn f() { let x = 42u32; let s = "hello"; } // c'
    b = 'fn f() { let x = 7u32;  let s = "world"; } /* d */'
    assert normalize_source(a) == normalize_source(b), "literal normalization broken"
    c = 'fn f() { let x = 42u32; let s = "hello"; return; }'
    assert normalize_source(a) != normalize_source(c), "over-normalization"


def load_sources(data: Path, root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for case_id in read_ids(data):
        out[case_id] = normalize_source(source_file(root, case_id).read_text(encoding="utf-8"))
    return out


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def tokens(text: str) -> set[str]:
    return set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+|==|!=|<=|>=", text))


def main() -> int:
    parser = argparse.ArgumentParser(description="Hard-fail eval/train Rust blueprint source overlap.")
    parser.add_argument("--train-data", type=Path, required=True)
    parser.add_argument("--train-blueprints", type=Path, required=True)
    parser.add_argument("--eval-data", type=Path, required=True)
    parser.add_argument("--eval-blueprints", type=Path, required=True)
    parser.add_argument("--max-source-similarity", type=float, default=0.92)
    parser.add_argument("--top-k", type=int, default=10)
    args = parser.parse_args()
    _self_test()

    train = load_sources(args.train_data, args.train_blueprints)
    evals = load_sources(args.eval_data, args.eval_blueprints)
    train_by_hash: dict[str, list[str]] = {}
    train_tokens: dict[str, set[str]] = {}
    inverted: dict[str, set[str]] = defaultdict(set)
    for case_id, src in train.items():
        train_by_hash.setdefault(digest(src), []).append(case_id)
        src_tokens = tokens(src)
        train_tokens[case_id] = src_tokens
        for tok in src_tokens:
            inverted[tok].add(case_id)

    exact: list[dict] = []
    near: list[dict] = []
    for eval_id, eval_src in evals.items():
        eval_hash = digest(eval_src)
        if eval_hash in train_by_hash:
            exact.append({"eval": eval_id, "train": train_by_hash[eval_hash]})
            continue
        eval_tokens = tokens(eval_src)
        candidates: set[str] = set()
        for tok in eval_tokens:
            candidates.update(inverted.get(tok, ()))
        if not candidates:
            candidates = set(train)
        best_score = 0.0
        best_train = ""
        candidate_scores = []
        for train_id in candidates:
            train_tok = train_tokens[train_id]
            union = len(eval_tokens | train_tok)
            jaccard = len(eval_tokens & train_tok) / union if union else 0.0
            if jaccard >= 0.35:
                candidate_scores.append((jaccard, train_id))
        candidate_scores.sort(reverse=True)
        for _, train_id in candidate_scores[:75]:
            train_src = train[train_id]
            score = SequenceMatcher(None, eval_src, train_src).ratio()
            if score > best_score:
                best_score = score
                best_train = train_id
        if best_score >= args.max_source_similarity:
            near.append({"eval": eval_id, "train": best_train, "score": round(best_score, 4)})

    summary = {
        "train_cases": len(train),
        "eval_cases": len(evals),
        "exact_duplicates": len(exact),
        "near_duplicates": len(near),
        "threshold": args.max_source_similarity,
        "exact_sample": exact[: args.top_k],
        "near_sample": sorted(near, key=lambda row: row["score"], reverse=True)[: args.top_k],
    }
    print(json.dumps(summary, indent=2))
    return 1 if exact or near else 0


if __name__ == "__main__":
    raise SystemExit(main())
