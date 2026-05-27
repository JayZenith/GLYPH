# Data Lineage

Current signal SFT dataset:
- `synthetic_data/signal_259.jsonl`
- per-family source files in `synthetic_data/signal_259_families/`

How it was built:
- Generate compact case specs with GPT batch jobs.
- Materialize specs locally into real Rust crates.
- Execute real tools locally:
  - `read_file`
  - `apply_patch`
  - `cargo_test`
  - `cargo_run`
- Write traces with real `RESULT` blocks.
- Reject bad generations instead of repairing them by hand.

Main accepted batch sources that fed this dataset:
- `synthetic_data/batch_general_30/`
- `synthetic_data/batch_general_50/`
- `synthetic_data/batch_stable_50/`
- `synthetic_data/batch_scale_200/`

Family policy used for `signal_259`:
- keep:
  - `patch_test_pass`
  - `patch_run_pass`
  - `patch_test_recover`
  - `test_only`
  - `run_only`
- exclude:
  - `patch_run_recover`
  - `read_only`

Assembly flow:
- accepted family rows were copied into `synthetic_data/signal_259_families/`
- merged into `synthetic_data/signal_259.jsonl`
- replay-validated with `synthetic_data/validate_dataset.py`

Final counts:
- `patch_test_pass`: `105`
- `patch_run_pass`: `49`
- `patch_test_recover`: `95`
- `test_only`: `5`
- `run_only`: `5`
- total: `259`
