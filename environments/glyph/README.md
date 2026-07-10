# glyph

A verifiable-reward RL environment for a **Rust tool-use coding agent**. Each
task hands the model a real Rust crate and a job: patch until `cargo_test`
passes, patch until `cargo_run` prints exact stdout, or confirm an
already-correct crate. The model emits `CALL tool {...}` blocks, tools execute
against real `cargo`, and the episode must end with a clean `FINAL`.

Reward is verifiable — cargo actually compiles and runs, not an LLM judge.
Strict success (`valid_trace`) requires terminal cargo success + one clean
`FINAL` after it + exact `CALL` syntax + no tool use after success.

Full write-up — diagnosis of a flat sparse-reward RLVR run and a dense
partial-credit reward that measured a small (not statistically significant)
pass@8 lift over both SFT and the sparse control:
<https://jayzenith.github.io/GLYPH/>. Source: <https://github.com/JayZenith/GLYPH>.

## Requirements

A Rust toolchain on `PATH` (`cargo`, `rustc`) — install via <https://rustup.rs>
if `rustc --version` fails. Crate templates (~30MB) download automatically
from the companion [`JayZenith/glyph-crates`](https://huggingface.co/datasets/JayZenith/glyph-crates)
dataset on first use and are cached locally.

## Usage

```python
import verifiers as vf

env = vf.load_environment("glyph")
```

```bash
uv run vf-eval glyph -m <your-model> -n 20 -r 5
```

Dense partial-credit reward shaping (see the write-up for why this matters —
a sparse reward silently discards the identically-failing part of the hard
tail via zero-advantage filtering):

```python
env = vf.load_environment(
    "glyph",
    progress_compile_bonus=0.5,
    progress_test_frac_bonus=2.0,
)
```

## Honest caveats

The held-out eval behind the write-up's numbers is 150 cases that cluster
into a handful of template families (config-merge precedence, enum-dispatch,
leaderboard-ranking cover roughly half the set) — treat it as a smaller
effective sample than n=150 suggests. Headline comparisons use trace-retained
pass@8 evaluations (no sampling seed — repetitions differ only through runtime
nondeterminism): dense reward +7 valid@8 over SFT (p ≈ 0.12, not significant),
sparse flat, compiler-aware level with SFT; each reward arm is one training
run, so nothing is causally attributed to reward shape. Two known verifier
limits, both audited: per-rollout isolation is path rewriting, not a security
containment boundary; and grading tests are model-editable (one baseline
rollout in ~41k audited patch calls flipped a test assertion — no published
count affected). Full methodology and raw per-rollout eval data:
[`JayZenith/Glyph-RLVR-Eval-Results`](https://huggingface.co/datasets/JayZenith/Glyph-RLVR-Eval-Results).
