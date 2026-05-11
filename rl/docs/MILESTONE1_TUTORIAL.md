# Milestone 1 RL Setup

## Goal

Start GRPO from the SFT policy using:

- base: `Qwen/Qwen3-4B-Base`
- train policy: `JayZenith/glyph-sft-v1-adapter`
- teacher/reference: `JayZenith/glyph-sft-v1`
- reward: deterministic only

Trainables:

- LoRA
- `lm_head`

Not trainable:

- base model

## Hardware

Important:

- total VRAM is not pooled
- trainer VRAM is per GPU
- `4 x 24GB` still means the trainer only gets `24GB`

Practical minimum:

- trainer GPU: `48GB`
- inference GPU: `24GB+`
- teacher GPU: `24GB+`

`4 x 24GB` is enough to prove the loop works, but not a good long-run baseline.

## Manual Setup

```bash
git clone https://github.com/JayZenith/glyph.git
cd glyph
git pull --ff-only
pip install -r requirements-train.txt
git clone --depth 1 https://github.com/PrimeIntellect-ai/prime-rl.git /root/prime-rl-src
bash rl/setup_prime_rl.sh /root/prime-rl-src
```

Generate the 24-prompt smoke set:

```bash
/root/prime-rl-src/.venv/bin/python - <<'PY'
from pathlib import Path
import json
from sft.evals.prompt_loader import load_prompts, build_prompt
rows = []
for i, spec in enumerate(load_prompts("formal_eval")[:24]):
    rows.append({"prompt": build_prompt(spec["user"], spec.get("tools", [])), "task_id": f"smoke_{i:03d}"})
Path("runs/rl1").mkdir(parents=True, exist_ok=True)
out = Path("runs/rl1/smoke_prompts_24.jsonl")
with out.open("w", encoding="utf-8") as f:
    for row in rows:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
print(out)
PY
```

Audit adapter load:

```bash
python3 rl/audit_adapter_setup.py \
  --adapter JayZenith/glyph-sft-v1-adapter \
  --output runs/rl1/adapter_audit.json
```

## Smoke Launch

Use this shape first on a real box:

```bash
PYTHONPATH=$PWD /root/prime-rl-src/.venv/bin/python rl/run_api.py \
  --adapter JayZenith/glyph-sft-v1-adapter \
  --teacher-model JayZenith/glyph-sft-v1 \
  --enable-teacher-inference \
  --teacher-tau 0.01 \
  --data runs/rl1/smoke_prompts_24.jsonl \
  --output runs/rl1/smoke_run \
  --max-steps 20 \
  --batch-size 8 \
  --rollouts-per-example 2 \
  --seq-len 3072 \
  --max-model-len 3072 \
  --max-completion-tokens 768 \
  --learning-rate 1e-6 \
  --reward-mode smoke_deterministic \
  --gpu-memory-utilization 0.75
```

If trainer OOMs, cut to:

- `batch-size=2`
- `rollouts-per-example=2`
- `seq-len=1024`
- `max-completion-tokens=256`

## Reward

Smoke reward:

`struct_pass + section_credit - teacher_KL`

Where:

- `struct_pass` comes from `core/validator.py`
- `section_credit` comes from `rl/task_format/core.py`
- teacher KL is driven by `--teacher-tau 0.01`

## Files That Matter

Needed for milestone 1:

- `rl/run_api.py`
- `rl/setup_prime_rl.sh`
- `rl/patch_install.py`
- `rl/audit_adapter_setup.py`
- `rl/task_trace.py`
- `rl/task_format/core.py`
- `core/validator.py`
- `rl/docs/MILESTONE1_TUTORIAL.md`
- `rl/configs/task_trace/orchestrator.toml`
- `rl/configs/task_trace/trainer.toml`
- `rl/configs/task_trace/inference.toml`
- `sft/evals/prompt_loader.py`
- `sft/evals/prompts.yaml`

HF models needed:

- `JayZenith/glyph-sft-v1-adapter`
- `JayZenith/glyph-sft-v1`
- `Qwen/Qwen3-4B-Base`

Not needed for milestone 1:

- local merged checkpoints outside HF
- local adapter copies on the instance
- `sft/evals/llm_judge.py`
- tool execution additions not yet wired for RL, such as future registry work around `get_weather` / `search_web` / `fetch_page` / `run_python` / `get_time`
- human review dump/hook files, not yet added for milestone 1
- unrelated blog files like [blog/01_sft.md](/home/jay-zenith/Desktop/TASK/blog/01_sft.md:1)

## What Broke

In order:

1. Mixed local deps with PRIME-RL deps.
Fix: install PRIME-RL in its own `uv` env with `rl/setup_prime_rl.sh`.

2. `flash-attn` wanted to compile from source.
Fix: install a matching wheel first.

3. Teacher model access failed.
Fix: use public HF repo or authenticated HF access.

4. Bad GPU mapping put trainer and teacher on the same 24GB GPU.
Fix: map inference/trainer/teacher to separate GPUs.

5. vLLM startup was too slow and cache-starved on 24GB.
Fix: `enforce_eager=true` and `gpu_memory_utilization=0.75`.

6. PRIME-RL teacher logprob path broke on OpenAI client parsing.
Fix: patch teacher `/generate` client to parse raw JSON.

7. Trainer still OOMed after step 1.
Fix: shrink smoke config or use a `48GB+` trainer GPU.

## What To Check

- adapter audit says only LoRA + `lm_head` are trainable
- launcher log shows teacher model is `JayZenith/glyph-sft-v1`
- orchestrator log reaches `Step 0`
- rollouts appear under `runs/rl1/.../rollouts/step_*`
- outputs still end correctly and do not collapse

## Status

RL is set up.

More precisely:

- setup: yes
- adapter/teacher wiring: yes
- deterministic smoke loop: yes
- stable 20-step run on `24GB` trainer GPU: not yet
