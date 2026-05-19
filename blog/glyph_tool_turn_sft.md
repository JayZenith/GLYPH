# Glyph SFT: Tool-Turn Repair

Glyph teaches a base model to write structured task traces:

```text
plan { ... }
act { call ↦ { tool ↦ ... id ↦ ... } }
<tool result turn>
response「...」
```

The first SFT run learned the surface format, but it also learned a bad prior: after an assistant `act { call ... }`, it often wrote its own `result { ... }`. That breaks RL, because the environment is supposed to provide tool results.

The repair is simple: train on traces where tool outputs are separate `tool` turns.

```text
<|im_start|>assistant
act {
    call ↦ {
        tool ↦ get_weather •
        location ↦ "Boston" •
        id ↦ weather1
    }
}
<|im_end|>

<|im_start|>tool
result {
    data ↦ "Cold and rainy." 🏷 weather1
}
<|im_end|>
```

During SFT, labels are masked everywhere except assistant turns. That means:

- system/user/tool turns are context only
- assistant turns are training targets
- the model learns to stop with `<|im_end|>` after a call
- the model reads tool results later, but does not learn to generate them as assistant text

The important training choices stay the same:

- Base: `Qwen/Qwen3-4B-Base`
- LoRA rank/alpha: `64/64`
- `modules_to_save=["lm_head"]`
- assistant-only loss masking
- `lm_head_lr=2e-5`

`lm_head` remains load-bearing because Qwen3-Base needs direct pressure to emit the chat stop token reliably.

Expected SFT success criteria:

- validation loss improves cleanly
- held-out test loss beats base
- generation emits `act { call ... }` then `<|im_end|>`
- mocked/tool results appear only in `tool` turns
- final `response「...」` appears after tool context

Full format spec: [`docs/glyph.md`](../docs/glyph.md).
