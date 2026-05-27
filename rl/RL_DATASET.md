# RL Dataset

Canonical RL prompt set:
- `runs/rlvr1/prompts.jsonl`

Materialized Rust cases:
- `runs/rlvr1/rust_cases/`

Generator:
- `python3 -m rl.rust.prepare_cases --root runs/rlvr1/rust_cases --output runs/rlvr1/prompts.jsonl`

Scope:
- tools: `read_file`, `apply_patch`, `cargo_test`, `cargo_run`
- exactly 9 rows, one per active family

Families:
- `patch_test_pass`
- `patch_run_pass`
- `patch_test_recover_once`
- `patch_run_recover_once`
- `patch_test_recover_twice`
- `patch_run_recover_twice`
- `test_only`
- `run_only`
- `read_only`

Notes:
- the generator is now the source of truth for RL prompts
- there are no mined structure-only rows
- there is no broad verifier/tool pool anymore
