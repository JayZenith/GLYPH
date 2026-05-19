# Clean Tool-Turn SFT Runbook

Use this path for the re-SFT run.

## Train

```bash
git clone https://github.com/JayZenith/glyph.git
cd glyph
bash sft/setup/install_sft_env.sh
source .venv/bin/activate
hf auth login

python -m sft.train --model Qwen/Qwen3-4B-Base --data synthetic_data/glyph_dataset.jsonl --output runs/sft_toolturn_v1
```

The setup script creates a project-local `.venv`, prefers `python3.11`, auto-installs a managed `python3.11` via `uv` when the image only has `python3.12`, installs a pinned `torch` build, installs the pinned SFT Python deps, and installs `flash-attn` as a prebuilt wheel only.

On Vast.ai, use a CUDA 12.4 image unless you plan to override:

```text
PYTHON_BIN
TORCH_VERSION
CUDA_WHL_TAG
TORCH_INDEX_URL
FLASH_ATTN_WHEEL_URL
```

Keep these defaults:

```text
masking_mode = assistant_only
modules_to_save = lm_head
lora_r = 64
lora_alpha = 64
learning_rate = 2e-5
lm_head_lr = 2e-5
max_seq_length = 8192
epochs = 3
```

Do not run generation eval during training. Use validation loss during training, then run formal eval after saving the adapter.

## Pull Artifacts

```bash
scp -P <PORT> -r root@<HOST>:/workspace/glyph/runs/sft_toolturn_v1/{final,test_set} sft_artifacts/glyph_sft_toolturn_v1/
```

## Merge

```bash
python -m sft.merge_adapter --base Qwen/Qwen3-4B-Base --adapter sft_artifacts/glyph_sft_toolturn_v1/final --output sft_artifacts/glyph_sft_toolturn_v1/merged
```

## Eval

Held-out test loss:

```bash
python -m sft.eval_test_loss --base Qwen/Qwen3-4B-Base --sft sft_artifacts/glyph_sft_toolturn_v1/merged --test-set sft_artifacts/glyph_sft_toolturn_v1/test_set --output runs/sft_toolturn_v1/eval_test_loss.json
```

Generation format:

```bash
python -m sft.eval_formal --sft-model sft_artifacts/glyph_sft_toolturn_v1/merged --output runs/sft_toolturn_v1/eval_formal.json --max-new-tokens 6000 --max-tool-rounds 4
```

## Pass Bar

```text
test loss improves over base
no repetition / no truncation
tool tasks produce assistant act-call turns
tool results are injected as tool turns
assistant does not write result blocks
final answers appear as response「...」
```
