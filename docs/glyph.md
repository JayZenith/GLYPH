# GLYPH Trace Language

Structured trace format used in `synthetic_data/glyph_dataset.jsonl`. Describes how an assistant plans, calls tools, receives results, and responds.

A trace is a sequence of Qwen chat segments (`<|im_start|>role\n...\n<|im_end|>`) joined by `\n\n`. Inside each segment the body uses the glyph notation below.

## Chat Structure

Every trace is a multi-turn chat with four possible roles:

```
<|im_start|>system
…system body…
<|im_end|>

<|im_start|>user
…user body…
<|im_end|>

<|im_start|>assistant
…plan + act{call}…
<|im_end|>

<|im_start|>tool
…result{}…
<|im_end|>

<|im_start|>assistant
…plan/act/think/response…
<|im_end|>
```

The pattern repeats `assistant → tool → assistant → tool → …` until a final assistant turn ends with `response「…」` or `reply ↦ 「…」`.

Important structural rules (as actually appears in the dataset):

- `result{…}` blocks live in `tool` segments only. Assistant turns never contain `result{}` — they end after `act{call↦{…}}` so the model learns to stop on its own.
- Segments are separated by exactly one blank line (`\n\n`).
- The final segment is always `assistant`.

## Per-Role Body Format

### system

```
system「You are a helpful math assistant…」
```

No `🏷` tag. The literal token `system` is followed by `「…」`, nothing else.

### user

```
user「Find the dimensions…」🏷 usr1
```

Always tagged `🏷 usrN` (1-indexed). Multiple user turns get `usr1`, `usr2`, …

### assistant

One or more glyph blocks, in this order when present:

```
plan { todo ↦ {…}, rationale ↦ "…" }

act { call ↦ {…} ⊨ N }
```

or for a reasoning-only step:

```
act { think ↦ [ 「…」 𝑝 0.9 🏷 stepK ⊨ K • … ] }
```

The final assistant turn ends with one of:

```
response「…」 ※ [tagA • tagB] ⊨ N
```

or

```
reply ↦ 「…」 ※ […] ⊨ N
```

### tool

```
result { data ↦ "…" 🏷 sol1 }
```

The `🏷` id matches the `id ↦ …` field from the preceding `act{call↦{… id ↦ sol1 …}}`. Tool bodies are produced by the environment, not the model.

## Primitive Types

| Form | Meaning |
|------|---------|
| `123`, `3.14`, `0xFF` | Number |
| `hello` | Bare string (no spaces) |
| `"hello world"` | Quoted string |
| `「multi-line text」` | Long-text string (CJK corner brackets) |
| `[ a • b • c ]` | Array |
| `{ a ↦ b • c ↦ d }` | Object |

## Operators

| Glyph | Name | Example | Meaning |
|-------|------|---------|---------|
| `↦` | Maps to | `tool ↦ get_weather` | Key/value pair inside `{}` |
| `•` | Separator | `a • b` | Separates items in `{}` / `[]` |
| `🏷` | Tag | `"…" 🏷 step1` | Assigns a semantic id to an expression |
| `※` | Reference | `※ [step1 • step2]` | Refers to previously tagged ids |
| `⊨` | Satisfies | `act{…} ⊨ 2` | Marks completion of todo item N |
| `𝑝` | Confidence | `"…" 𝑝 0.92` | Confidence 0.0–1.0 on a thought |

Tags attach to *expressions*, not blocks. `result{} 🏷 weather_result` tags the result expression, not the role segment.

## Block Vocabulary

### plan

```
plan {
    todo ↦ {
        1 ↦ "Step one." ※ usr1 •
        2 ↦ "Step two."
    } •
    rationale ↦ "Why this plan."
}
```

### act — tool call

```
act {
    call ↦ {
        tool ↦ solve_symbolic •
        expression ↦ "(x^3 - 2*x)/(x^2 + 1)" •
        operation ↦ integrate •
        variable ↦ "x" •
        id ↦ sol1
    } ⊨ 1
}
```

The assistant segment ends immediately after this. The next segment is `tool` carrying the matching `result{}`.

### act — think

```
act {
    think ↦ [
        「Restating the problem.」 𝑝 0.92 🏷 step1 ⊨ 1 •
        「Substitute h = V/(π r^2).」 𝑝 0.92 🏷 step2 ⊨ 2
    ]
}
```

### result (tool role only)

```
result {
    data ↦ "68F and cloudy."
} 🏷 weather_result
```

### response / reply (final assistant)

```
response「Wear a light sweater.」
※ [weather_result • rationale]
⊨ 3
```

## Full Example

```
<|im_start|>system
system「You are a helpful math assistant.」
<|im_end|>

<|im_start|>user
user「Integrate (x^3 - 2x)/(x^2 + 1).」🏷 usr1
<|im_end|>

<|im_start|>assistant
plan {
    todo ↦ {
        1 ↦ "Compute antiderivative." ※ usr1 •
        2 ↦ "Verify by differentiation."
    } •
    rationale ↦ "Integrate symbolically, then verify."
}

act {
    call ↦ {
        tool ↦ solve_symbolic •
        expression ↦ "(x^3 - 2*x)/(x^2 + 1)" •
        operation ↦ integrate •
        variable ↦ "x" •
        id ↦ sol1
    } ⊨ 1
}
<|im_end|>

<|im_start|>tool
result {
    data ↦ "(1/2)*x^2 - (3/2)*ln(x^2 + 1) + C" 🏷 sol1
}
<|im_end|>

<|im_start|>assistant
response「Antiderivative: (x^2 - 3 ln(x^2 + 1))/2 + C.」
※ [sol1] ⊨ 2
<|im_end|>
```
