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
ssh -p 47282 -N -L 18080:127.0.0.1:8000 root@173.239.95.142

# On the laptop, in another terminal pane:
CASE=eval100_013_patch_test_pass_014_dispatch_policy_match_order
python3 -m demo_tui \
  --base-url http://127.0.0.1:18080/v1 \
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
