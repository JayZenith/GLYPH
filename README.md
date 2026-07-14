# GLYPH

Post-training a 4B Rust coding agent with verified synthetic traces, full SFT,
verifier RL, pass@8 evaluation, and a live TUI.

```text
ASSISTANT  CALL read_file {...}
TOOL       RESULT src/lib.rs
ASSISTANT  CALL apply_patch {...}
ASSISTANT  CALL cargo_test {...}
TOOL       RESULT 4 passed
ASSISTANT  FINAL: fixed and tested
```

The full conversation is the training unit. Real Cargo execution verifies the
data and rewards. `verifiers` owns the environment; PRIME-RL runs RL.

[Write-up](https://jayzenith.github.io/GLYPH/) ·
[Environment](https://app.primeintellect.ai/dashboard/environments/jayzenith/glyph) ·
[SFT model](https://huggingface.co/JayZenith/SFT_HALF_A_V8) ·
[Dense RLVR](https://huggingface.co/JayZenith/RLVR_VFINAL_STEP10) ·
[Evaluation files](https://huggingface.co/datasets/JayZenith/Glyph-RLVR-Eval-Results)

## Results

`valid@8`: at least one of eight rollouts passes Cargo and ends with one clean
`FINAL`.

| Model | valid@8 / 150, retained runs |
| --- | ---: |
| SFT | 95 |
| Sparse RLVR | 98 / 96 / 98 |
| Dense RLVR | 102 |
| Compiler-aware RLVR | 95 / 96 / 94 |

No retained-run comparison reached `p < 0.05`.
[Methodology and interpretation](https://jayzenith.github.io/GLYPH/#methodology)

## Run the environment

Requires Python 3.10+, Cargo, and rustc.

```bash
git clone https://github.com/JayZenith/GLYPH.git
cd GLYPH
python3 -m venv .venv
source .venv/bin/activate
pip install -e environments/glyph
vf-eval glyph -m <your-model> -n 20 -r 5
```

## Interactive TUI smoke test

The TUI shows the exact ChatML system, user, assistant, and tool turns while
the model patches a disposable Rust crate.

[Run the live vLLM demo or offline preview](demo_tui/README.md)

## Safety

Model-edited Rust is arbitrary code. Use a disposable VM, container, or isolated
job. Host Cargo execution is the default; Bubblewrap is opt-in.

## Verify or reproduce

- [Commands](docs/REPRODUCTION.md)
- [Evaluation provenance](docs/PROVENANCE.md)
- [Claim audit](docs/CLAIMS_AUDIT.md)
- [Experiment history](docs/EXPERIMENT_HISTORY.md)

[Source layout](https://github.com/JayZenith/GLYPH) ·
[Companion Rust crates](https://huggingface.co/datasets/JayZenith/glyph-crates)
