# GLYPH

An end-to-end post-training stack for a 4B Rust coding agent: verified
synthetic traces, full SFT, verifier RL, pass@8 evaluation, and a live TUI.

The model works on real Cargo crates through a strict ChatML tool loop:

```text
ASSISTANT  CALL read_file {...}
TOOL       RESULT src/lib.rs
ASSISTANT  CALL apply_patch {...}
ASSISTANT  CALL cargo_test {...}
TOOL       RESULT 4 passed
ASSISTANT  FINAL: fixed and tested
```

[Write-up](https://jayzenith.github.io/GLYPH/) ·
[Environment Hub](https://app.primeintellect.ai/dashboard/environments/jayzenith/glyph) ·
[SFT model](https://huggingface.co/JayZenith/SFT_HALF_A_V8) ·
[Dense RLVR adapter](https://huggingface.co/JayZenith/RLVR_VFINAL_STEP10) ·
[Raw evaluations](https://huggingface.co/datasets/JayZenith/Glyph-RLVR-Eval-Results)

## What GLYPH contains

```text
generated task specs
        ↓ real Cargo execution
verified agent traces
        ↓ full fine-tuning
SFT_HALF_A_V8
        ↓ sparse / dense / compiler-aware RLVR
pass@8 evaluation + retained rollouts
```

- `verifiers` defines the Rust environment, tools, and rewards.
- PRIME-RL orchestrates rollouts and policy updates.
- One runtime renders SFT data, RL trajectories, evaluation, and TUI traces.
- Every rollout edits its own disposable crate copy.

The generator proposes structured Rust tasks. A deterministic materializer
executes every planned step and rejects cases whose real compiler/test outcome
does not match the spec. The full system/user/assistant/tool conversation—not
an isolated patch—is the SFT training unit.

## Results

`valid@8` counts a crate when at least one of eight sampled rollouts reaches
Cargo success and ends with one clean `FINAL`.

| Model | Trace-retained valid@8 / 150 | Counts only |
| --- | ---: | ---: |
| SFT control | **95** | 97 / 100 |
| Sparse RLVR | **98 / 96 / 98** | — |
| Dense RLVR | **102** | 102 / 99 |
| Compiler-aware RLVR | **95 / 96 / 94** | — |

No RL arm reliably improved over SFT. Dense versus SFT was +7 prompts on the
retained evaluation, but p≈0.12 when pairing the same prompts and p≈0.15 after
grouping recognizable task families. Each reward arm is one training run, so
the experiment does not establish causal reward-shape effects.

Count-only SFT/dense repetitions remain visible for context but are excluded
from headline claims because their per-rollout traces were not saved.

### Working explanation

- **Protocol saturation:** SFT already learned the ChatML/tool interface.
- **Capability boundary:** 74 of sparse RLVR's 76 greedy failures also failed
  for SFT under the same pass@1 setup.
- **Weak failure resolution:** at sparse step 0, 64 of 96 rollouts belonged to
  tied zero-advantage groups and were filtered.
- **Curriculum limit:** the synthetic data likely taught recurring patterns
  better than diverse intermediate Rust capability.

The last point is a hypothesis. Denser rewards exposed partial progress but
could not reliably improve the held-out result.

## Try the environment

Requirements: Python 3.10+, `cargo`, and `rustc`.

```bash
git clone https://github.com/JayZenith/GLYPH.git
cd GLYPH
python -m venv .venv
source .venv/bin/activate
pip install -e environments/glyph
```

```python
import verifiers as vf

env = vf.load_environment("glyph")
```

```bash
uv run vf-eval glyph -m <your-model> -n 20 -r 5
```

The repository package is v0.2.0. Check the Hub package version before
assuming it is identical to the current source.

## Interactive TUI

`demo_tui/` renders the exact ChatML conversation while a remotely served model
reads, patches, and tests a disposable local crate. It includes an easy OOD
Rust case and a compact trace explorer.

See [`demo_tui/README.md`](demo_tui/README.md) for the vLLM command, SSH tunnel,
OOD prompt, offline scripted mode, and safety notes.

## Safety

Model-edited Rust is arbitrary code. Run GLYPH only inside a disposable VM,
container, or isolated job environment.

Current source:

- confines tool paths to the copied rollout crate;
- blocks edits to tests and build-control files;
- runs Cargo on the host by default for hosted-container compatibility;
- supports stricter Bubblewrap execution as an explicit opt-in.

```python
env = vf.load_environment("glyph", sandbox_backend="bwrap")
```

The published evaluations predate the current runtime hardening. See the audit
for the exact historical boundary.

## Repository map

| Path | Purpose |
| --- | --- |
| `agent_runtime/` | Shared ChatML and Rust tool runtime |
| `synthetic_data/` | Task generation, materialization, and split audits |
| `sft/` | Full fine-tuning and pass@8 evaluation |
| `rl/` | PRIME-RL training and reward implementations |
| `environments/glyph/` | Standalone Hub environment |
| `demo_tui/` | Interactive local trace viewer |
| `analysis/` | Reproducible result and audit scripts |
| `glyph_results/` | Retained configs, logs, rollouts, and evaluations |
| `blog/` | Concise research write-up and trace explorer |

## Reproduce and audit

- [Training and evaluation commands](docs/REPRODUCTION.md)
- [Per-run provenance](docs/PROVENANCE.md)
- [Experiment history](docs/EXPERIMENT_HISTORY.md)
- [Adversarial audit](docs/AUDIT_2026-07.md)
- [Historical claims audit](docs/CLAIMS_AUDIT.md)

The companion crate dataset is
[`JayZenith/glyph-crates`](https://huggingface.co/datasets/JayZenith/glyph-crates).
