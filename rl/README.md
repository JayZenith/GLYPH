## RL

Current live path:

- [train.py](/home/jay-zenith/Desktop/TASK/rl/train.py:1): main launcher
- [task_trace.py](/home/jay-zenith/Desktop/TASK/rl/task_trace.py:1): PRIME-RL environment + reward wiring
- [configs/task_trace](/home/jay-zenith/Desktop/TASK/rl/configs/task_trace:1): trainer/orchestrator/inference defaults
- [rust](/home/jay-zenith/Desktop/TASK/rl/rust:1): Rust executor, reward, tool schema, case generation
- [../setup](/home/jay-zenith/Desktop/TASK/setup/setup.md:1): install + smoke + run scripts (see `setup/setup.md`)

Setup:

```bash
pip install -r requirements-train.txt
bash setup/install_prime_rl.sh
```

Prepare Rust tool-use cases (writes 8 sample Cargo projects + a prompt JSONL):

```bash
python3 -m rl.rust.prepare_cases \
  --root runs/rl1/rust_tool_cases \
  --output runs/rl1/rust_tool_prompts_8.jsonl
```

Each row carries `{prompt, expected_tool, expected_args}`; prompts are built via
`sft.evals.prompt_loader.build_prompt` so they share the exact TASK shape the
SFT model was trained against.

Train:

```bash
python3 rl/train.py \
  --adapter JayZenith/glyph-sft-v1-adapter \
  --teacher-model JayZenith/glyph-sft-v1 \
  --enable-teacher-inference \
  --data runs/rl1/rust_tool_prompts_8.jsonl \
  --output runs/rl1/rust_tool_run
```

Multi-turn execution: `RustToolEnv` in `task_trace.py` parses each `act { call ↦ … }`
the model emits, runs the real tool via `rl/rust/executor.py`, and injects a
`result {…}` block back into the rollout (up to `max_tool_rounds`, default 4).
RLVR reward sums `compute_tool_reward` across every call's verifiable outcome.
