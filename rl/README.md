## RL
- [train.py]
  - builds PRIME-RL configs from TOML + CLI flags and starts rollout vLLM
  - should enforce frozen teacher vLLM for KL anchoring, then calls prime_rl.rl_local(config) to start training
  - PRIME-RL compares rollout rewards within batches/rollouts, updates model with RL, and with teacher uses `teacher_tau` to stop policy from drifting. 
- [synthetic_data/rl_prompmts_1062.jsonl]: 
  - loaded into prompts, filtered by length? and packed into dataset wit prompt plus info fields like expected tool, expected args, exptected tool sequence, blueprint crate, and expected output
- [task_trace.py]: PRIME-RL environment + reward wiring
- Rollout FLow:
SFT model generates emits CALL ..., `RustToolEnv` xectutes real Rust tool against sandbox copy, appends `RESULT`, and lets model continue until no new calls or max tool rounds 
- Reward Flow:
it scores structure validity, clean final termination, correct tool choice/args, expected tool sequence, actual Rust execution success, cargo test/run results, and penalizes missing calls, unmatched results, repetition, role leakage, and garbage after final response.
- [configs/task_trace]: trainer/orchestrator/inference defaults
- [../agent_runtime/rust]: shared Rust executor, reward, runtime, and tool schema
- [../setup]: install + smoke + run scripts (see `setup/setup.md`)

Setup:

```bash
pip install -r requirements-train.txt
bash setup/install_prime_rl.sh
```

Build the RL prompt JSONL from the validated SFT_V1 traces:

```bash
python3 synthetic_data/build_rl_prompts.py \
  --data synthetic_data/signal_1062.jsonl \
  --blueprint-root synthetic_data/blueprints \
  --output synthetic_data/rl_prompts_1062.jsonl
```

Each row carries `{prompt, expected_tool, expected_args, expected_tool_sequence,
blueprint_root, trace_prefix, expected_output}`. `blueprint_root` points at the
durable crate under `synthetic_data/blueprints`; `trace_prefix` preserves the
model-facing `runs/rlvr1/rust_cases/CASE_ID` path so runtime can rewrite tool
calls into a sandbox copy.

Train:

```bash
python3 rl/train.py \
  --model JayZenith/SFT_V1 \
  --teacher-model JayZenith/SFT_V1 \
  --data synthetic_data/rl_prompts_1062.jsonl \
  --output outputs/rlvr1
```

Canary eval during training:

```bash
python3 rl/scripts/canary_eval.py \
  --weights-root outputs/rlvr1/weights \
  --train-data synthetic_data/signal_1062.jsonl \
  --prompt-file sft/evals/eval_prompts_heldout_69.yaml \
  --prompt-section post_eval_heldout_69 \
  --output outputs/rlvr1/canary_eval/latest.json \
  --cases-root runs/rlvr1/rust_cases/eval_canary
```

This runs six fixed held-out prompts: common missing-`FINAL` failures, one
SFT-only fixed case, one RLVR-regressed case, and one normal passing case. It is
not part of the PPO reward; it is a small external monitor for whether checkpoint
behavior is actually changing.

Multi-turn execution: `RustToolEnv` in `task_trace.py` parses each `CALL ...`
the model emits, runs the real tool via `agent_runtime/rust`, and injects a
`RESULT cN:` block back into the rollout (up to `max_tool_rounds`, default 15).
The live tool set is intentionally narrow:
- `read_file`
- `apply_patch`
- `cargo_test`
- `cargo_run`
