# Eval Notes

This repo has two eval styles that answer different questions:

- **HF/Transformers formal eval** (`sft.eval_formal`): one rollout per prompt, scored as a valid trace only if the model solves the task and ends cleanly with `FINAL`.
- **vLLM pass@k scan** (`sft/passk_scan_vllm.py`): `k` sampled rollouts per prompt, primarily counted by terminal verifier success (`cargo_run` expected stdout or passing `cargo_test`).

## Failure Buckets

Buckets are not mutually exclusive: one trace can be `missing_final`, `dirty_final`, and `final_before_tool_completion` at the same time.

| eval | valid traces | terminal tool successes | clean end | dirty/final/missing | task failure | truncated | repetition |
|---|---:|---:|---:|---:|---:|---:|---:|
| `SFT_V1` HF formal heldout-69 | 52/69 | 68/69 | 0.754 | 17 | 1 | 0 | 0 |
| `RLVR_V1` HF formal heldout-69 | 20/69 | 48/69 | 0.333 | 46 | 21 | 5 | 0 |
| `RLVR_B` HF formal heldout-69 | 19/69 | 46/69 | 0.275 | 50 | 23 | 7 | 3 |
| `RLVR_HELDOUT69_PASSK_STEP25` HF formal heldout-69 | 19/69 | 47/69 | 0.304 | 48 | 22 | 7 | 0 |

Primary artifacts:

```text
results/SFT_V1/eval_formal_heldout_69.json
results/RLVR_V1/eval_formal_heldout_69.json
results/RLVR_B/heldout_69/eval_heldout_69.json
results/RLVR_HELDOUT69_FORMAL_STEP25/eval_formal_heldout_69_step25.json
```

## Sample Rollout

One clean SFT_V1 recovery trace from `eval100_024_patch_run_pass_005_active_tags_filter_map_join`:

```text
CALL read_file(id="c1", file_path=".../src/main.rs")
RESULT c1: status: success
stdout:
    .filter_map(|(name, enabled)| if !enabled { Some(*name) } else { None })

CALL apply_patch(id="c2", ..., replace=".filter_map(|(name, enabled)| if enabled { Some(*name) } else { None })")
RESULT c2: status: success
stdout: patch applied

CALL cargo_run(id="c3", project_path="...")
RESULT c3: status: failed
stderr:
error[E0308]: mismatched types
help: consider dereferencing the borrow

CALL read_file(id="c4", file_path=".../src/main.rs")
RESULT c4: status: success

CALL apply_patch(id="c5", ..., replace=".filter_map(|(name, enabled)| if *enabled { Some(*name) } else { None })")
RESULT c5: status: success
stdout: patch applied

CALL cargo_run(id="c6", project_path="...")
RESULT c6: status: success
stdout: core,fast,safe

FINAL: Fixed the iterator filter_map condition so it keeps active tags and dereferences the boolean flag, producing the expected stdout.
```

## pass@k Table

All pass@k rows below use vLLM sampling at `k=8`, `T=0.8`.

| scan | prompts | solve histogram | total solves | mean pass@8 | use |
|---|---:|---|---:|---:|---|
| train depth>=3 SFT_V1 scan | 134 | `{4:1, 5:4, 6:7, 7:27, 8:95}` | 1015/1072 | 0.947 | found 39 train rlvr-target prompts |
| original SFT_V1 formal failures rescanned | 17 | `{1:1, 6:3, 7:4, 8:9}` | 119/136 | 0.875 | showed heldout failures had latent verifier capability |
| final 8 heldout-failure targets, SFT_V1 | 8 | selected mixed band | 47/64 | 0.734 | before for narrow RLVR run |
| final 8 heldout-failure targets, step 25 | 8 | selected mixed band | 54/64 | 0.844 | narrow matched vLLM win |

Primary artifacts:

```text
synthetic_data/passk_train134.json
results/SFT_V1/passk_heldout69_fail17.json
results/RLVR_HELDOUT69_PASSK_STEP25/passk8_step25_comparison.csv
```

## HF vs vLLM Harness Mismatch

The heldout-69 "failures" were not all Rust capability failures. In the original HF/Transformers formal eval, most SFT_V1 failures had already reached terminal verifier success but did not produce a clean final trace. The later vLLM pass@8 scan used the same prompts/cases and the same CALL/RESULT tool protocol, but sampled multiple rollouts and counted terminal verifier success for the pass@8 banding. So the mismatch was not "protocol eval versus no protocol eval." It was single-sample valid-trace scoring versus sampled terminal-success banding. The narrow RLVR artifact is therefore only valid as a matched vLLM-vs-vLLM pass@8 improvement; the same checkpoint still failed the broader HF formal robustness check.
