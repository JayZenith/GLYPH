# Evaluation provenance

This is the verification index for GLYPH's reported evaluation results. It
records what ran, where the evidence lives, and what remains unknown.

- Recompute reported statistics: `python3 analysis/retained_run_stats.py`
- Review claim corrections: [`CLAIMS_AUDIT.md`](CLAIMS_AUDIT.md)
- Reproduce the pipeline: [`REPRODUCTION.md`](REPRODUCTION.md)
- Review experiment chronology: [`EXPERIMENT_HISTORY.md`](EXPERIMENT_HISTORY.md)

## Reported runs

`valid@8` means at least one of eight sampled rollouts both reaches Cargo
success and ends with one clean `FINAL`.

| Model | Trace-retained valid@8 / 150 | Provenance |
| --- | ---: | --- |
| `SFT_HALF_A_V8` | 95 | Partial: no console log; command inferred |
| `RLVR_POOL_B_V8_STEP10` (sparse) | 98, 96, 98 | Full |
| `RLVR_VFINAL_STEP10` (dense) | 102 | Partial: command recovered; no console log |
| `RLVR_VFINAL2_STEP10` (compiler-aware) | 95, 96, 94 | Strong: full console log; repo commit bounded |

Aggregate-only repetitions are excluded from headline claims because their
rollouts were not saved: SFT 97/100 and dense 102/99. The compiler-aware
repetitions do contain full rollouts.

## Shared evaluation inputs

| Input | Pinned value | Evidence |
| --- | --- | --- |
| Prompts | `sft/evals/eval_prompts_heldout_150.yaml`, section `post_eval_heldout_150`, 150 crates | Git blob comparison |
| Harness | `sft/passk_scan_vllm.py` | Byte-identical from commit `4901fd8` through the evaluation window |
| ChatML | `agent_runtime/chatml.py` | Byte-identical through the evaluation window |
| Sampling | `k=8`, T=0.8, top_p=1.0, 4000 new tokens, 20 tool rounds | Commands, harness, engine log |
| Runtime | Python 3.12.13, vLLM 0.23.0, torch 2.11.0+cu128, transformers 4.57.5 | `environment.txt`, `eval2.log` |
| Engine | bf16, max model length 24576, LoRA rank limit 64 | `eval2.log` |

The prompt set, harness, and ChatML renderer were byte-identical across the
relevant commit ranges. Exact repo-commit uncertainty therefore does not
change those evaluation inputs.

## Model revisions

- `Qwen/Qwen3-4B-Base` — `906bfd4b4dc7f14ee4320094d8b41684abff8539`
- `JayZenith/SFT_HALF_A_V8` — `1b76c5fb8bcafc92574f62ff3c418eb179abc66f`
- `JayZenith/RLVR_POOL_B_V8_STEP10` — `b401ec0b94e81026bf1093e358eee9669f3540f5`
- `JayZenith/RLVR_VFINAL_STEP10` — `4fdce4481e70e09002576804a0bd2099a4c8c650`
- `JayZenith/RLVR_VFINAL2_STEP10` — `ed1cbec132f0`

## Evidence by arm

| Arm | Primary evidence | Missing or inferred |
| --- | --- | --- |
| Sparse | `glyph_results/RLVR_POOL_B_V8_STEP10/passk8_heldout150_metadata/`: three commands, clean commit `abed10cc`, environment, logs, summaries | Nothing material |
| Compiler-aware | `glyph_results/RLVR_VFINAL2_STEP10/evals/eval2.log` plus three rollout JSONs | Exact repo commit inferred within a byte-identical range |
| Dense | `parity_source_command.txt`, adapter revision, retained rollout JSON | Run date and console log |
| SFT | Manifest, model revision, retained rollout JSON, documented harness command | Exact pass@8 command, date, and console log |

## Limits that affect interpretation

- The three repetitions were not independent seeds. The harness exposed no
  seed flag; vLLM used `seed=0`. Variation came from asynchronous runtime and
  tool-execution nondeterminism.
- Each RL reward arm has one training run. Training-seed variance was never
  measured.
- Training and evaluation used the same generator and semantic families. The
  holdout tests new crates from known archetypes, not broad Rust OOD transfer.
- No matched base-model evaluation was run, so the results cannot separate
  base-model capacity, SFT coverage, or post-training regression.
- Expect statistical reproduction, not bitwise-identical generations.

## Still unavailable

- SFT and dense run-one console logs and exact evaluation timestamps
- Exact evaluation repo commit for SFT, dense, and compiler-aware runs
- CUDA driver version and exact GPU device string

These gaps are bounded by retained artifacts but cannot be reconstructed. Do
not promote inferred fields to recorded facts.
