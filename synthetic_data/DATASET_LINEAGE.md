# Dataset Lineage

Canonical clean training file:

- `final_glyph_sft_dataset.jsonl`

Recommended RL-oriented retrain file:

- `final_glyph_sft_dataset_rlvr_term_v1.jsonl`

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

Files that matter now:

- `gold_glyph_3000.jsonl`
- `rlvr_seed_final_v1.jsonl`
- `gold_glyph_3141_plus_rlvr_seed_final_v1.jsonl`
- `rlvr_seed_microfix_v1.jsonl`
- `gold_glyph_3148_plus_rlvr_seed_microfix_v1.jsonl`
- `final_glyph_sft_dataset.jsonl`
- `rlvr_seed_termination_hardening_v1.jsonl`
- `final_glyph_sft_dataset_rlvr_term_v1.jsonl`

Repro facts:

- `gold_glyph_3000.jsonl` has `3004` rows on disk
- `gold_glyph_3141_plus_rlvr_seed_final_v1.jsonl` has `3141` rows
- `gold_glyph_3148_plus_rlvr_seed_microfix_v1.jsonl` has `3148` rows
- `final_glyph_sft_dataset.jsonl` has `3039` rows
- `rlvr_seed_termination_hardening_v1.jsonl` has `808` rows
- `final_glyph_sft_dataset_rlvr_term_v1.jsonl` has `3847` rows
- all `137` seed traces are in the final `3148` file
- all `7` micro-fix traces are in the final `3148` file
- `final_glyph_sft_dataset.jsonl` remains the older broad clean set
- `final_glyph_sft_dataset_rlvr_term_v1.jsonl` is the file to use for the next RL-oriented SFT retrain
