# RLVR Latent Capability Target Selection

This directory captures the pass@8 scan used to separate true capability gaps from latent-capability reliability targets among the 17 prompts that SFT_V1 failed in the original single-sample heldout-69 eval.

Run settings:
- Model: JayZenith/SFT_V1
- Prompt source: sft/evals/eval_prompts_heldout_69.yaml, section post_eval_heldout_69
- Prompt subset: original 17 SFT_V1 single-sample failures
- Samples: k=8
- Temperature: 0.8
- Max tool rounds: 15
- Harness: sft/passk_scan_vllm.py with real tool execution

Result:
- 9/17 were solved 8/8 under pass@8
- 8/17 were mixed RLVR targets
- 0/17 were 0/8 capability gaps

Interpretation:
The original SFT_V1 failures were not pure missing capability. They were mostly reliability failures under single-sample decoding. The 8 mixed prompts are the clean RLVR target set: SFT_V1 can solve them, but unreliably.
