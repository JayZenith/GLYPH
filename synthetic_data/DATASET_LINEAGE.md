# Dataset Lineage

This directory now has one recommended RLVR seed path and a small number of source builders.

## Recommended Files

- `gold_glyph_3000.jsonl`
  - Baseline SFT dataset used for `GLYPH_SFT_V3`.
  - Important: despite the filename, it currently contains `3004` rows on disk.
- `build_rlvr_seed_final_v1.py`
  - Final RLVR-focused augmentation builder.
- `rlvr_seed_final_v1.jsonl`
  - Final RLVR-focused top-up dataset.
- `gold_glyph_3141_plus_rlvr_seed_final_v1.jsonl`
  - Recommended combined dataset for the last pre-RLVR SFT pass.
- `rlvr_seed_final_v1_report.json`
  - Count summary and contamination check result for the final RLVR top-up.

## Build Chain

1. `build_gold50.py`
   - Defines the base trace format helpers and the first hand-authored seed pool.
2. `build_gold300.py`
   - Extends the `gold_glyph_50` style traces into a broader `gold_glyph_300.jsonl`.
3. `build_gold3000.py`
   - Expands the `gold_glyph_300` pool with prompt/system variations and writes `gold_glyph_3000.jsonl`.
4. `build_gold_rust_tooluse.py`
   - Adds the RL-relevant Rust tool schema and reusable trace constructors.
   - Source of the main `read_file -> apply_patch -> cargo_test/cargo_run -> response` trace families.
5. `build_rlvr_seed_final_v1.py`
   - Final corrective builder for RLVR readiness.
   - Uses the Rust tool-use builders plus extra closure-focused traces.
   - Also checks for exact user-prompt overlap against `sft/evals/prompts_125.yaml`.

## Final RLVR Top-Up Contents

`rlvr_seed_final_v1.jsonl` contains `137` traces:

- `61` lib bug-fix traces
  - `read_file -> apply_patch -> cargo_test -> response`
- `40` bin bug-fix traces
  - `read_file -> apply_patch -> cargo_run -> response`
- `8` single-tool traces
  - `cargo_build`, `cargo_run`, `cargo_check`, `rustc`, `read_file`
- `8` read-and-answer traces
  - clean `read_file -> response` closure
- `8` cargo diagnostic traces
  - clean `cargo_check -> response` closure
- `6` stronger bin bug-fix traces
  - extra emphasis on not stopping after patch
- `6` stronger lib bug-fix traces
  - extra emphasis on verifier-before-response completion

## Why This Is the Final Recommended Dataset

This final augmentation is explicitly optimized for:

- correct RL tool arg schema
  - `project_path`, `file_path`, `find`, `replace`
- full patch-and-verify loops
- no stopping after `apply_patch`
- clean final closure
- correct todo satisfaction
- zero exact prompt overlap with `prompts_125.yaml`

## Files Removed From The Main Path

These older top-ups are not part of the recommended path anymore:

- `build_rlvr_seed_topup.py`
- `rlvr_seed_topup_v1.jsonl`
- `rlvr_seed_topup_v1.md`
- `build_rlvr_micro_topup_v1.py`
- `rlvr_micro_topup_v1.jsonl`
- `gold_glyph_3023_plus_rlvr_topup_v1.jsonl`
- `gold_glyph_3027_plus_rlvr_topup_v1_clean.jsonl`
- `gold_glyph_3016_plus_rlvr_micro_topup_v1.jsonl`

They were intermediate experiments and should not be used for the final RLVR seed.
