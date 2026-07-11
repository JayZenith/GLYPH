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

## Why raw completions

The client calls vLLM's `/v1/completions` endpoint with ChatML rendered locally
by `agent_runtime.chatml.render_messages`. This preserves the byte-identical
SFT/RLVR/eval transcript format and avoids server-side chat-template drift.
The `glyph` request model is the name assigned by `--lora-modules`; verify that
it appears in `curl http://127.0.0.1:8000/v1/models` before launching the TUI.
