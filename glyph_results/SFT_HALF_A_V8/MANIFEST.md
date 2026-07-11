# SFT_HALF_A_V8

Hugging Face model repo: `JayZenith/SFT_HALF_A_V8`

Uploaded model revision: `1b76c5fb8bcafc92574f62ff3c418eb179abc66f`

Source training artifact on instance: `runs/SIGNAL_v3_HALF_A_SFT_E3_LR2E5/final`

Repo commit used for eval: `3b4d8937e14ad16dcd7004a0bacb4313322f8d72`

Local contents:

- `evals/eval_formal_heldout_150.json`: strict pass@1 heldout-150 eval.
- `training_run/runs/.../events.out.tfevents...`: TensorBoard event file.
- `training_run/checkpoint-288/trainer_state.json`: Trainer state metadata.
- `training_run/**`: non-weight config/tokenizer/training metadata copied from the run.
- `logs/sft_setup_vllm.*`: environment setup log and exit code from the instance.

Model weights were intentionally not copied locally. This directory excludes `*.safetensors` and `model.safetensors.index.json`; the full model lives on Hugging Face.

Eval summary:

- prompts: 150
- strict valid traces: 72
- terminal cargo success rate: 0.4866666666666667
- clean end rate: 0.48
- average score: 9.286666666666667
