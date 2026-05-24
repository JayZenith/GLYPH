# Dataset Lineage

Canonical broad clean training file:

- `final_glyph_sft_dataset.jsonl`

Recommended RL-oriented retrain file:

- `final_glyph_sft_dataset_rlvr_curated_v1.jsonl`

Build chain:

1. `build_gold50.py`
2. `build_gold300.py`
3. `build_gold3000.py`
   - grows the base corpus
4. `build_gold_rust_tooluse.py`
   - appends the Rust/tool-use expansion into `gold_glyph_3000.jsonl`
   - introduces the main RL-shaped traces:
     - `read_file -> apply_patch -> cargo_test -> response`
     - `read_file -> apply_patch -> cargo_run -> response`
5. `build_rlvr_seed_final_v1.py`
   - adds the `137`-trace corrective top-up
   - produces `gold_glyph_3141_plus_rlvr_seed_final_v1.jsonl`
6. `build_rlvr_seed_microfix_v1.py`
   - adds the final `7`-trace micro-fix
   - produces `gold_glyph_3148_plus_rlvr_seed_microfix_v1.jsonl`
7. exact dedupe pass
   - removes repeated rows from `gold_glyph_3148_plus_rlvr_seed_microfix_v1.jsonl`
   - produces `final_glyph_sft_dataset.jsonl`
8. `build_rlvr_termination_hardening_v1.py`
   - adds an `808`-trace termination-hardening top-up
   - aggressively reinforces `read -> patch -> verify -> response -> stop`
   - produces `final_glyph_sft_dataset_rlvr_term_v1.jsonl`
9. `build_rlvr_single_tool_hardening_v1.py`
   - adds a `96`-trace single-tool sufficiency top-up
   - rebalances toward `tool -> response -> stop` for one-tool tasks
   - produces `final_glyph_sft_dataset_rlvr_term_v2.jsonl`
10. `build_rlvr_single_tool_hardening_v2.py`
   - adds a stronger `192`-trace single-tool sufficiency top-up
   - further pressures exact minimal tool use for `read_file`, `cargo_*`, and `rustc`
   - produces `final_glyph_sft_dataset_rlvr_term_v3.jsonl`
11. `build_rlvr_user_unique_dataset_v1.py`
   - removes duplicate user prompts from `final_glyph_sft_dataset_rlvr_term_v3.jsonl`
   - preserves one row per unique user prompt
   - produces `final_glyph_sft_dataset_rlvr_term_v4_useruniq.jsonl`
12. `build_rlvr_curated_dataset_v1.py`
   - discards the broad mixed corpus for RL retraining
   - keeps only the clean RL-specific seed/top-up files:
     - termination hardening
     - single-tool hardening v1
     - single-tool hardening v2
   - exact-dedupes and user-dedupes those RL-only traces
   - produces `final_glyph_sft_dataset_rlvr_curated_v1.jsonl`

Files that matter now:

- `gold_glyph_3000.jsonl`
- `rlvr_seed_final_v1.jsonl`
- `gold_glyph_3141_plus_rlvr_seed_final_v1.jsonl`
- `rlvr_seed_microfix_v1.jsonl`
- `gold_glyph_3148_plus_rlvr_seed_microfix_v1.jsonl`
- `final_glyph_sft_dataset.jsonl`
- `rlvr_seed_termination_hardening_v1.jsonl`
- `final_glyph_sft_dataset_rlvr_term_v1.jsonl`
- `rlvr_seed_single_tool_hardening_v1.jsonl`
- `final_glyph_sft_dataset_rlvr_term_v2.jsonl`
- `rlvr_seed_single_tool_hardening_v2.jsonl`
- `final_glyph_sft_dataset_rlvr_term_v3.jsonl`
- `final_glyph_sft_dataset_rlvr_term_v4_useruniq.jsonl`
- `final_glyph_sft_dataset_rlvr_curated_v1.jsonl`

Repro facts:

- `gold_glyph_3000.jsonl` has `3004` rows on disk
- `gold_glyph_3141_plus_rlvr_seed_final_v1.jsonl` has `3141` rows
- `gold_glyph_3148_plus_rlvr_seed_microfix_v1.jsonl` has `3148` rows
- `final_glyph_sft_dataset.jsonl` has `3039` rows
- `rlvr_seed_termination_hardening_v1.jsonl` has `808` rows
- `final_glyph_sft_dataset_rlvr_term_v1.jsonl` has `3847` rows
- `rlvr_seed_single_tool_hardening_v1.jsonl` has `96` rows
- `final_glyph_sft_dataset_rlvr_term_v2.jsonl` has `3943` rows
- `rlvr_seed_single_tool_hardening_v2.jsonl` has `192` rows
- `final_glyph_sft_dataset_rlvr_term_v3.jsonl` has `4135` rows
- `final_glyph_sft_dataset_rlvr_term_v4_useruniq.jsonl` has `3963` rows
- `final_glyph_sft_dataset_rlvr_term_v4_useruniq.jsonl` has `0` exact duplicate rows
- `final_glyph_sft_dataset_rlvr_term_v4_useruniq.jsonl` removed `172` duplicate user-prompt rows from `v3`
- `final_glyph_sft_dataset_rlvr_curated_v1.jsonl` has `1004` rows
- `final_glyph_sft_dataset_rlvr_curated_v1.jsonl` has `0` exact duplicate rows
- `final_glyph_sft_dataset_rlvr_curated_v1.jsonl` removed `92` duplicate user-prompt rows from its RL-only sources
- `final_glyph_sft_dataset_rlvr_curated_v1.jsonl` has `0` exact user overlap with `formal_eval_rl`
- `final_glyph_sft_dataset_rlvr_curated_v1.jsonl` tool mix:
  - `read_file -> apply_patch -> cargo_test`: `488`
  - `read_file -> apply_patch -> cargo_run`: `320`
  - `read_file`: `36`
  - `cargo_build`: `32`
  - `cargo_check`: `32`
  - `cargo_run`: `32`
  - `cargo_test`: `32`
  - `rustc`: `32`
- all `137` seed traces are in the final `3148` file
- all `7` micro-fix traces are in the final `3148` file
- `final_glyph_sft_dataset.jsonl` remains the older broad clean set
- `final_glyph_sft_dataset_rlvr_curated_v1.jsonl` is the current file to use for RL-oriented SFT retrain
