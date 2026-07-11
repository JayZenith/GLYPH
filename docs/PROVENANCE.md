# Eval provenance manifest (forensic, 2026-07-10)

Scope: the trace-retained evaluations behind every headline claim. Each field
is marked **recovered** (found in a contemporaneous artifact), **inferred**
(follows from artifacts but not directly recorded), or **unknown**.
Evidence sources: `glyph_results/RLVR_POOL_B_V8_STEP10/passk8_heldout150_metadata/`
(command files, environment.txt, run logs), `glyph_results/RLVR_VFINAL2_STEP10/evals/eval2.log`
(full vLLM engine-config dump), `glyph_results/SFT_HALF_A_V8/MANIFEST.md`,
wandb `requirements.txt`, setup logs, git history, HF API.

## Trace-retained runs and their status

| arm | runs | valid@8 | provenance grade |
| --- | --- | --- | --- |
| SFT_HALF_A_V8 | 1 | 95 | partial (no run log; command inferred) |
| sparse RLVR_POOL_B_V8_STEP10 | 3 | 98, 96, 98 | **full** (commands, commit, env, revisions recorded at run time) |
| dense RLVR_VFINAL_STEP10 | 1 | 102 | partial (exact command recovered from a contemporaneous record; no run log) |
| compiler RLVR_VFINAL2_STEP10 | 3 | 95, 96, 94 | strong (full console log incl. engine config; repo commit inferred) |

Aggregate-only (per-prompt counts, no traces, excluded from claims):
SFT 97, 100 (`seeds/sft_seed1.json`, `sft_seedB.json`); dense 102, 99
(`seeds/step10_seed{B,C}.json`). **Correction to the earlier audit:** the
compiler arm's `seeds/step10_seed{B,C}.json` DO contain full rollouts — the
compiler arm is trace-retained ×3.

## Shared, recovered facts (all runs)

- Harness: `sft/passk_scan_vllm.py`, byte-identical from 2026-06-26 (commit
  4901fd8) through the eval window — **recovered** (git history; blob
  `e0db7d7d` at eval commit = blob at every candidate eval date).
- Chat template `agent_runtime/chatml.py` and dataset
  `sft/evals/eval_prompts_heldout_150.yaml` (150 prompts, section
  `post_eval_heldout_150`): byte-identical from 2026-06-26 through today —
  **recovered** (git blob comparison at eval commit `abed10cc`).
- Sampling: T=0.8, top_p=1.0, n=1 per turn, k=8, max 4000 new tokens, max 20
  tool rounds, stop on `<|im_end|>`/`<|im_start|>`/eos — **recovered**
  (command files + harness source + engine log).
- **Seed: vLLM default `seed=0`, identical for every repetition** —
  **recovered** (explicit `seed=0` in eval2.log engine config; no seed flag in
  harness). Repetitions are NOT independent seeded samples; variation comes
  from runtime nondeterminism (async scheduling, chunked prefill, prefix
  caching, batching — all enabled per engine config, plus tool timing).
- Eval dtype: bfloat16, enforce_eager off (VLLM_COMPILE), FlashAttention 2,
  FlashInfer top-p sampling, max_model_len 24576, gpu_mem_util 0.90,
  enable_lora max_lora_rank 64 — **recovered** (eval2.log engine config).
- Library stack: Python 3.12.13, torch 2.11.0+cu128, transformers 4.57.5,
  **vllm 0.23.0**, peft 0.17.1, accelerate 1.10.1, datasets 4.0.0,
  huggingface_hub 0.36.2 — **recovered** (environment.txt 2026-07-01; vllm
  0.23.0 independently confirmed in eval2.log 2026-06-30; same instance and
  venv per setup log).
- Hardware: vast.ai, Blackwell-class GPU (NVIDIA RTX PRO 6000, 96 GB), 1 GPU —
  **recovered** (setup log "Detected Blackwell-class GPU", README-recorded
  rig; exact GPU string not in logs → that detail **inferred**).
- Model/tokenizer HF revisions — **recovered** (environment.txt + HF API +
  SFT MANIFEST):
  - `Qwen/Qwen3-4B-Base` @ `906bfd4b4dc7f14ee4320094d8b41684abff8539`
  - `JayZenith/SFT_HALF_A_V8` @ `1b76c5fb8bcafc92574f62ff3c418eb179abc66f` (pushed 2026-06-27)
  - `JayZenith/RLVR_POOL_B_V8_STEP10` @ `b401ec0b94e81026bf1093e358eee9669f3540f5` (r=64, α=128, base=SFT_HALF_A_V8 — from cached adapter_config)
  - `JayZenith/RLVR_VFINAL_STEP10` @ `4fdce4481e70e09002576804a0bd2099a4c8c650`
  - `JayZenith/RLVR_VFINAL2_STEP10` @ `ed1cbec132f0` (pushed 2026-06-30 01:20 UTC, 8 min before its eval began — the only revision with weights)

## Per-run specifics

**Sparse runs 1–3** — everything recorded at run time in
`passk8_heldout150_metadata/`: exact commands (`command_run{1,2,3}.txt`),
timestamp 2026-07-01T23:27Z, repo commit `abed10cc` with **clean worktree**
(empty `git status` captured), environment.txt, per-run console logs, per-run
summaries matching the JSONs (98/96/98). Nothing unknown.

**Compiler runs 1–3 (labeled "SEED a/b/c")** — full console log
(`evals/eval2.log`): all three ran back-to-back starting 2026-06-30 01:28 UTC,
engine config dumped (source of `seed=0`, dtype, scheduler facts above).
Command **inferred** from the log's non-default-args + output paths (matches
the README command pattern). Repo commit: **inferred** — between `6acec17`
(before) and `abed10cc`; harness/template/dataset provably identical in that
range, so the ambiguity is immaterial to reproduction.

**Dense run 1** — command **recovered verbatim** from
`parity_source_command.txt` (written 2026-07-01 as the command the sparse runs
mirrored). Date **inferred**: after adapter push 2026-06-27 19:22 UTC, before
the 2026-06-28 18:53 README commit citing its result. No console log retained.

**SFT run 1** — no command file or log. Command **inferred**: the documented
README base-model command (harness identical, output path matches). MANIFEST
records "repo commit used for eval: `3b4d8937`" for the *greedy* eval; the
pass@8 date is **inferred** ~2026-06-27/28. Weakest provenance of the four,
but harness/dataset/template/model revision are all pinned by the shared
facts above.

## Reproducibility verdicts

- **Sparse:** reproducible in the strict re-run sense — exact command, commit,
  clean tree, library pins, model revisions all recorded. (Bitwise-identical
  outputs are still not guaranteed: vLLM async scheduling is nondeterministic
  even at fixed seed.)
- **Compiler:** reproducible — command reconstructed from engine log; all
  inputs pinned; commit ambiguity provably immaterial.
- **Dense:** reproducible — verbatim command + pinned inputs; run date and
  console output unrecoverable.
- **SFT:** reproducible with one inference (the command); all inputs pinned.
- All four: *statistical* reproduction is the right expectation, not bitwise
  equality. Observed count spans were 2 prompts for sparse and 5/3 for the
  aggregate-only SFT/dense repetitions.

## Training runs (context)

One training run per arm. Training env recovered from wandb
`requirements.txt`: prime-rl 0.4.0, verifiers 0.1.15.dev7, prime 0.6.6,
torch 2.11.0+cu128. Orchestrator/trainer/inference TOMLs retained per arm
(`glyph_results/*/configs/`). Orchestrator seed 42 (config); trainer/sampling
unseeded. Training-seed variance across runs: never measured.

## Still unknown

- SFT and dense run-1 console logs (deleted with the instance).
- Exact eval dates for SFT/dense run 1 (bounded, not pinned).
- Exact repo commit for compiler and SFT/dense evals (bounded to a range in
  which all relevant files are byte-identical).
- CUDA driver version; exact GPU device string.
