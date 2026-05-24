# RL Dataset

Canonical RL prompt set:
- `runs/rlvr1/prompts.jsonl`

Materialized Rust cases:
- `runs/rlvr1/rust_cases/`

Generator:
- `python3 -m rl.rust.prepare_cases --root runs/rlvr1/rust_cases --output runs/rlvr1/prompts.jsonl --phrasings 2 --gold-count 12`

Source files:
- `rl/rust/prepare_cases.py`
- `synthetic_data/final_glyph_sft_dataset_rlvr_term_v1.jsonl`
- `sft/evals/prompts_125.yaml`

Composition:
- total rows: `95`
- Rust execution rows: `83`
- targeted structure rows: `12`
- Rust fraction: `87.4%`

Structure rows are mined from the final SFT dataset and target:
- clean final `response` ending
- correct todo closure
- patch-then-verify completion

Rust rows are generated from `49` materialized verifier cases:
- `24` lib bug-fix cases
- `10` bin bug-fix cases
- `5` `cargo_check` cases
- `5` `cargo_build` cases
- `5` `rustc` cases

Surface-form setting:
- `phrasings=2`
- this yields two prompt wordings per bug-fix Rust case

Held-out eval hygiene:
- exact overlap with `sft/evals/prompts_125.yaml`: `0`

Notes:
- regenerate this dataset on a fresh box; `runs/` is not intended as a permanent source-of-truth artifact
- the generator, RL-oriented SFT dataset, and held-out eval prompt file are the reproducible sources
