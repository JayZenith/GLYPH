# Data Lineage

## Current Reproducible Lineage

The README and final blog use the V3 split artifacts below. Treat these as the
active, reproducible path:

- `synthetic_data/signal_v3.jsonl`: full validated V3 trace pool, `2083` rows,
  `1522` unique cases.
- `synthetic_data/signal_v3_sft_half_a.jsonl`: SFT training half, `1042` rows,
  `762` unique cases.
- `synthetic_data/signal_v3_rl_pool_b.jsonl`: RL held-back trace pool, `1041`
  rows, `760` unique cases.
- `synthetic_data/rl_prompts_signal_v3_pool_b.jsonl`: RL prompt manifest built
  from pool B, `760` prompts.
- `synthetic_data/rl_prompts_signal_v3_pool_b_mixed.jsonl`: mixed-outcome RL
  prompt subset used by the final V999/V4000 RLVR run, `703` prompts.
- `synthetic_data/signal_v3_rl_pool_b_prompts.yaml`: pass@k-compatible prompt
  manifest for pool B, `760` prompts.
- `synthetic_data/signal_v3_split_summary.json` and
  `synthetic_data/signal_v3_split_summary.md`: deterministic split audit.

The split was grouped by `case_id` to prevent duplicate trace leakage. The
recorded audit reports `0` case-id overlap and `0` trace overlap between the
SFT half and RL pool.

Family counts:

| artifact | rows | patch_test_pass | patch_test_recover | patch_run_pass | patch_run_recover | test_only | run_only |
|---|---:|---:|---:|---:|---:|---:|---:|
| `signal_v3.jsonl` | 2083 | 728 | 561 | 394 | 298 | 71 | 31 |
| `signal_v3_sft_half_a.jsonl` | 1042 | 366 | 280 | 194 | 150 | 36 | 16 |
| `signal_v3_rl_pool_b.jsonl` | 1041 | 362 | 281 | 200 | 148 | 35 | 15 |
| `rl_prompts_signal_v3_pool_b.jsonl` | 760 | 181 | 281 | 100 | 148 | 35 | 15 |
| `rl_prompts_signal_v3_pool_b_mixed.jsonl` | 703 | 167 | 257 | 96 | 139 | 31 | 13 |

## Historical Signal Dataset

- `synthetic_data/signal_1062.jsonl`
- durable source blueprints in `synthetic_data/blueprints/`

This dataset was built by generating compact specs, materializing them into real Rust crates, executing tools locally, and only keeping traces whose real tool execution matched the requested family.

Main accepted batch sources that fed this dataset:
- `synthetic_data/batch_general_30/`
- `synthetic_data/batch_general_50/`
- `synthetic_data/batch_stable_50/`
- `synthetic_data/batch_scale_200/`

Validated counts:
- `patch_test_pass`: `300`
- `patch_run_pass`: `171`
- `patch_test_recover`: `310`
- `patch_run_recover`: `197`
- `test_only`: `59`
- `run_only`: `25`
- total: `1062`

The old `signal_259` dataset was used as a seed source, but 5 corrupted old rows containing literal `…[truncated]…` source text were excluded from `signal_1062`.

## Canonical Generation Pipeline

1. Write a per-family count file.

```bash
printf '%s\n' '{"patch_test_pass":85,"patch_run_pass":55,"patch_test_recover":100,"patch_run_recover":130,"test_only":20,"run_only":10}' \
  > synthetic_data/batch_NAME_counts.json
```

2. Build GPT batch requests for compact Rust case specs.

```bash
python3 synthetic_data/batch_specs.py build \
  --output synthetic_data/batch_NAME/requests.jsonl \
  --counts-json synthetic_data/batch_NAME_counts.json \
  --custom-prefix PREFIX
```

3. Submit the batch.

```bash
python3 synthetic_data/batch_specs.py submit \
  --input synthetic_data/batch_NAME/requests.jsonl \
  --metadata synthetic_data/batch_NAME/batch.json \
  --task-name glyph_sft_BATCH_NAME_specs
```

4. Poll until complete.

```bash
python3 synthetic_data/batch_specs.py status \
  --metadata synthetic_data/batch_NAME/batch.json
```

5. Retrieve results.

```bash
python3 synthetic_data/batch_specs.py retrieve \
  --metadata synthetic_data/batch_NAME/batch.json \
  --output synthetic_data/batch_NAME/results.jsonl
```

6. Materialize specs into Rust crates and execute real tools.

```bash
python3 synthetic_data/materialize_specs.py \
  synthetic_data/batch_NAME/results.jsonl \
  --source-root runs/rlvr1/rust_cases \
  --cases-root runs/materialize_BATCH_NAME_cases \
  --families-dir synthetic_data/BATCH_NAME_families \
  --rejects synthetic_data/batch_NAME/rejects.jsonl \
  --tool-timeout 30
```

This step creates source blueprints under `runs/rlvr1/rust_cases`, copies each case into a disposable `--cases-root`, executes `read_file`, `apply_patch`, `cargo_test`, and `cargo_run`, writes real `RESULT` blocks, and rejects specs whose execution does not match.

7. Merge accepted family files into one train file.

```bash
python3 synthetic_data/build_train_data.py \
  --families-dir synthetic_data/BATCH_NAME_families \
  --output synthetic_data/TRAIN_NAME.jsonl \
  --expected-total EXPECTED_ROWS
```

8. Replay-validate the final train file.

```bash
python3 synthetic_data/validate_dataset.py \
  synthetic_data/TRAIN_NAME.jsonl \
  --cases-root runs/validate_TRAIN_NAME_cases \
  --source-root runs/rlvr1/rust_cases \
  --require-metadata \
  --summary
```

9. Export durable blueprints out of gitignored `runs/`.

```bash
python3 synthetic_data/blueprint_store.py export \
  --data synthetic_data/TRAIN_NAME.jsonl \
  --source-root runs/rlvr1/rust_cases \
  --store-root synthetic_data/blueprints \
  --overwrite
```

10. Restore blueprints before replay/eval on a fresh checkout.

```bash
python3 synthetic_data/blueprint_store.py restore \
  --data synthetic_data/TRAIN_NAME.jsonl \
  --source-root runs/rlvr1/rust_cases \
  --store-root synthetic_data/blueprints \
  --overwrite
```

## Current Scale Run

The first attempted one-shot scale batch had `1230` requests and failed before execution because the org enqueued-token limit for `gpt-5.4` was `1,350,000`.

```bash
python3 synthetic_data/batch_specs.py build \
  --output synthetic_data/batch_scale_to_1200/requests.jsonl \
  --counts-json synthetic_data/batch_scale_to_1200_counts.json \
  --custom-prefix scale1200

python3 synthetic_data/batch_specs.py submit \
  --input synthetic_data/batch_scale_to_1200/requests.jsonl \
  --metadata synthetic_data/batch_scale_to_1200/batch.json \
  --task-name glyph_sft_scale_to_1200_specs
```

The active scale-up was split into two smaller batches:

```bash
python3 synthetic_data/batch_specs.py build \
  --output synthetic_data/batch_scale_a_400/requests.jsonl \
  --counts-json synthetic_data/batch_scale_a_400_counts.json \
  --custom-prefix scaleA400

python3 synthetic_data/batch_specs.py submit \
  --input synthetic_data/batch_scale_a_400/requests.jsonl \
  --metadata synthetic_data/batch_scale_a_400/batch.json \
  --task-name glyph_sft_scale_a_400_specs

python3 synthetic_data/batch_specs.py build \
  --output synthetic_data/batch_scale_b_350/requests.jsonl \
  --counts-json synthetic_data/batch_scale_b_350_counts.json \
  --custom-prefix scaleB350

python3 synthetic_data/batch_specs.py submit \
  --input synthetic_data/batch_scale_b_350/requests.jsonl \
  --metadata synthetic_data/batch_scale_b_350/batch.json \
  --task-name glyph_sft_scale_b_350_specs
```

Both completed with zero API request failures and were retrieved with:

```bash
python3 synthetic_data/batch_specs.py retrieve \
  --metadata synthetic_data/batch_scale_a_400/batch.json \
  --output synthetic_data/batch_scale_a_400/results.jsonl

python3 synthetic_data/batch_specs.py retrieve \
  --metadata synthetic_data/batch_scale_b_350/batch.json \
  --output synthetic_data/batch_scale_b_350/results.jsonl
```

Their materialization commands are:

```bash
python3 synthetic_data/materialize_specs.py \
  synthetic_data/batch_scale_a_400/results.jsonl \
  --source-root runs/rlvr1/rust_cases \
  --cases-root runs/materialize_scale_a_400_cases \
  --families-dir synthetic_data/scale_a_400_families \
  --rejects synthetic_data/batch_scale_a_400/rejects.jsonl \
  --tool-timeout 30

python3 synthetic_data/materialize_specs.py \
  synthetic_data/batch_scale_b_350/results.jsonl \
  --source-root runs/rlvr1/rust_cases \
  --cases-root runs/materialize_scale_b_350_cases \
  --families-dir synthetic_data/scale_b_350_families \
  --rejects synthetic_data/batch_scale_b_350/rejects.jsonl \
  --tool-timeout 30
```

Current materialization results:
- `batch_scale_a_400`: `257 / 400` accepted, `143` rejected
- `batch_scale_b_350`: `234 / 350` accepted, `116` rejected
- combined accepted: `491 / 750`

Accepted family counts:
- `patch_test_pass`: `149`
- `patch_run_pass`: `69`
- `patch_test_recover`: `126`
- `patch_run_recover`: `105`
- `test_only`: `34`
- `run_only`: `8`

The next 500-request scale batch favored weak recovery/run families:

```bash
python3 synthetic_data/batch_specs.py build \
  --output synthetic_data/batch_scale_c_500/requests.jsonl \
  --counts-json synthetic_data/batch_scale_c_500_counts.json \
  --custom-prefix scaleC500

python3 synthetic_data/batch_specs.py submit \
  --input synthetic_data/batch_scale_c_500/requests.jsonl \
  --metadata synthetic_data/batch_scale_c_500/batch.json \
  --task-name glyph_sft_scale_c_500_specs
```

It completed with zero API failures and materialized as:

```bash
python3 synthetic_data/batch_specs.py retrieve \
  --metadata synthetic_data/batch_scale_c_500/batch.json \
  --output synthetic_data/batch_scale_c_500/results.jsonl

python3 synthetic_data/materialize_specs.py \
  synthetic_data/batch_scale_c_500/results.jsonl \
  --source-root runs/rlvr1/rust_cases \
  --cases-root runs/materialize_scale_c_500_cases \
  --families-dir synthetic_data/scale_c_500_families \
  --rejects synthetic_data/batch_scale_c_500/rejects.jsonl \
  --tool-timeout 30
```

`batch_scale_c_500` accepted `317 / 500`:
- `patch_test_pass`: `50`
- `patch_run_pass`: `53`
- `patch_test_recover`: `90`
- `patch_run_recover`: `92`
- `test_only`: `20`
- `run_only`: `12`

Final validated artifact:

```bash
python3 synthetic_data/validate_dataset.py \
  synthetic_data/signal_1062.jsonl \
  --cases-root runs/validate_signal_1062_cases \
  --source-root runs/restored_signal_1062_blueprints \
  --require-metadata \
  --summary
```

Result: `ok: 1062 rows`.


Summary:
Files:

- synthetic_data/batch_specs.py: builds/submits/retrieves GPT-5.4 case-spec
  batches.
- synthetic_data/materialize_specs.py: turns specs into crates, executes
  intended tools, writes real traces, rejects bad specs.
- synthetic_data/build_train_data.py: merges accepted family JSONLs into final
  train JSONL.
- synthetic_data/validate_dataset.py: replays final traces from clean
  blueprints to verify they are still real.
- synthetic_data/blueprint_store.py: exports/restores durable blueprint
  crates.
- synthetic_data/audit_blueprint_similarity.py: train/eval Rust source
  contamination check.
- synthetic_data/build_eval_prompts.py: turns held-out validated eval traces/
  blueprints into eval YAML.
- sft/eval_formal.py: runs model inference with real tool execution.
- sft/evals/generation.py: loop that executes model CALLs and injects real
  RESULTs.
- agent_runtime/rust/runtime.py: shared tool execution/path rewrite helpers.
