# GLYPH interactive demo

A local TUI for a GLYPH model served remotely through vLLM. The model generates
on the GPU instance; the TUI renders GLYPH ChatML, executes Rust tools against a
fresh local crate copy, and displays every assistant/tool turn.

## Serve the model

On the GPU instance, serve the SFT model with the dense RLVR adapter:

```bash
vllm serve JayZenith/SFT_HALF_A_V8 \
  --enable-lora \
  --lora-modules glyph=JayZenith/RLVR_VFINAL_STEP10 \
  --max-lora-rank 64 \
  --max-model-len 24576
```

Expose port 8000 only through an authenticated network or an SSH tunnel.

On Vast.ai, the SSH host and SSH port change per instance. Keep them in shell
variables instead of hardcoding old instance details:

```bash
export GLYPH_SSH_HOST=<instance-ip>
export GLYPH_SSH_PORT=<instance-ssh-port>
export GLYPH_REMOTE_VLLM_PORT=8000
export GLYPH_LOCAL_VLLM_PORT=18082

ssh -p "$GLYPH_SSH_PORT" -N \
  -L "$GLYPH_LOCAL_VLLM_PORT:127.0.0.1:$GLYPH_REMOTE_VLLM_PORT" \
  "root@$GLYPH_SSH_HOST"
```

In another local terminal, verify that the tunnel reaches vLLM:

```bash
curl "http://127.0.0.1:$GLYPH_LOCAL_VLLM_PORT/v1/models"
```

If this hangs or returns non-JSON, check the remote vLLM port from inside the
instance:

```bash
curl http://127.0.0.1:8000/v1/models
curl http://127.0.0.1:8080/v1/models
```

Vast.ai often uses port 8080 for Jupyter/portal services, not vLLM.

## Run the TUI

```bash
python -m pip install -r requirements-demo.txt

python -m demo_tui \
  --base-url http://127.0.0.1:8000/v1 \
  --model glyph \
  --project synthetic_data/blueprints/<case_id>
```

Enter the task in the prompt bar. Each submission creates a new disposable copy
under `runs/demo_tui/sandboxes/`; the source blueprint is never edited. Complete
ChatML transcripts are saved under `runs/demo_tui/transcripts/`.

If the task text names a different model-visible crate path, map that prefix to
the disposable copy:

```bash
python -m demo_tui ... \
  --project synthetic_data/blueprints/<case_id> \
  --trace-prefix runs/rlvr1/rust_cases/<case_id>
```

By default, Cargo fails closed into Bubblewrap. If the TUI itself is already
inside a disposable external container, host execution requires both explicit
flags:

```bash
python -m demo_tui ... \
  --sandbox-backend host \
  --allow-unsafe-host-execution
```

Do not use those flags directly on a workstation: model-edited Rust is arbitrary
code.

## OOD smoke test

`demo_tui/ood_cases/score_summary` is a tiny Rust crate kept in this repository
for an out-of-distribution TUI smoke test. It is not an eval blueprint. The bug
is simple numeric/vector logic: ignore invalid negative scores, cap scores above
100, and compute the summary from normalized scores.

With the SSH tunnel above running:

```bash
source .venv/bin/activate

python3 -m demo_tui \
  --base-url "http://127.0.0.1:$GLYPH_LOCAL_VLLM_PORT/v1" \
  --model glyph \
  --project demo_tui/ood_cases/score_summary \
  --trace-prefix demo_tui/ood_cases/score_summary \
  --sandbox-backend host \
  --allow-unsafe-host-execution \
  --max-tool-rounds 8 \
  --max-tokens 2200
```

Prompt:

```text
In the Rust crate at demo_tui/ood_cases/score_summary, fix the failing tests. Read demo_tui/ood_cases/score_summary/src/lib.rs first. Identify the score summary bugs, make a minimal implementation change, run cargo test, and stop with FINAL when tests pass. Do not modify tests or Cargo.toml.
```

One successful local run produced this trace shape:

1. `read_file` on `src/lib.rs`
2. first `apply_patch`
3. `cargo_test` showing remaining failures
4. second `apply_patch`
5. `cargo_test` with `4 passed; 0 failed`
6. `FINAL`

This demonstrates the interactive tool loop on a small unseen Rust crate. It is
not a broad Rust-generalization benchmark.

## Offline scripted mode

Use this when you want to inspect the TUI without a vLLM instance or SSH tunnel.
It emits a deterministic GLYPH-style assistant trace for
`eval100_013_patch_test_pass_014_dispatch_policy_match_order`:

```bash
CASE=eval100_013_patch_test_pass_014_dispatch_policy_match_order
python3 -m demo_tui \
  --backend scripted \
  --project synthetic_data/eval_blueprints/$CASE \
  --trace-prefix runs/rlvr1/rust_cases/$CASE \
  --sandbox-backend host \
  --allow-unsafe-host-execution
```

You can also omit `--project` and `--trace-prefix`; scripted mode defaults to
that same case. The scripted backend does not call the network, but it still
runs the real local tool loop against a disposable crate copy: `read_file`,
`apply_patch`, then `cargo_test`, followed by a red `FINAL` assistant box.
If Bubblewrap works on your machine, omit the two host-execution flags.

## Why raw completions

The client calls vLLM's `/v1/completions` endpoint with ChatML rendered locally
by `agent_runtime.chatml.render_messages`. This preserves the byte-identical
SFT/RLVR/eval transcript format and avoids server-side chat-template drift.
The `glyph` request model is the name assigned by `--lora-modules`; verify that
it appears in `curl http://127.0.0.1:8000/v1/models` before launching the TUI.

## Held-out smoke test

One local smoke test used the original prompt for held-out eval case
`eval100_013_patch_test_pass_014_dispatch_policy_match_order`. I cloned the repo,
installed the SFT environment, served the SFT model plus dense RLVR adapter on a
Vast.ai GPU box, forwarded vLLM over SSH, then ran the TUI locally:

```bash
git clone https://github.com/JayZenith/GLYPH.git
cd GLYPH
bash sft/setup/install_sft_env.sh
source .venv/bin/activate

# On the GPU instance:
vllm serve JayZenith/SFT_HALF_A_V8 \
  --enable-lora \
  --lora-modules glyph=JayZenith/RLVR_VFINAL_STEP10 \
  --max-lora-rank 64 \
  --max-model-len 24576

# On the laptop, in one terminal pane:
export GLYPH_SSH_HOST=<instance-ip>
export GLYPH_SSH_PORT=<instance-ssh-port>
export GLYPH_LOCAL_VLLM_PORT=18080
ssh -p "$GLYPH_SSH_PORT" -N \
  -L "$GLYPH_LOCAL_VLLM_PORT:127.0.0.1:8000" \
  "root@$GLYPH_SSH_HOST"

# On the laptop, in another terminal pane:
CASE=eval100_013_patch_test_pass_014_dispatch_policy_match_order
python3 -m demo_tui \
  --base-url "http://127.0.0.1:$GLYPH_LOCAL_VLLM_PORT/v1" \
  --model glyph \
  --project synthetic_data/eval_blueprints/$CASE \
  --trace-prefix runs/rlvr1/rust_cases/$CASE \
  --sandbox-backend host \
  --allow-unsafe-host-execution
```

Prompt entered in the TUI:

```text
In the Rust crate at runs/rlvr1/rust_cases/eval100_013_patch_test_pass_014_dispatch_policy_match_order, fix the enum branch logic in src/lib.rs so the tests pass. Keep the implementation compact and only change the bug.
```

On my laptop Bubblewrap could not create a namespace (`bwrap: Creating new
namespace failed: Resource temporarily unavailable`), so this live demo opted out
with `--sandbox-backend host --allow-unsafe-host-execution`. Use that only for a
disposable demo copy: model-edited Rust is arbitrary code. Without the opt-out,
the runtime fails closed.
