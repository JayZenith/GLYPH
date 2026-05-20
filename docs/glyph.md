# GLYPH Trace Language

This document describes the **rigid target format** used by the hand-built gold set that was later expanded into [gold_glyph_2500.jsonl](/home/jay-zenith/Desktop/TASK/synthetic_data/gold_glyph_2500.jsonl).

It is intentionally narrower than older experimental traces.

The goal is not “any valid-looking glyph.”  
The goal is a **small, semantically consistent agent trace language** that is easy to learn, validate, and evaluate.

## Core Principles

- Every trace is a single-user-task interaction.
- The trace is always a sequence of Qwen chat segments using:
  - `<|im_start|>system`
  - `<|im_start|>user`
  - `<|im_start|>assistant`
  - optional `<|im_start|>tool`
  - `<|im_end|>`
- Tool results live in `tool` turns only.
- The assistant never writes `result {}`.
- `think` blocks are **supporting reasoning only**.
- `think` blocks do **not** satisfy todos.
- Todos are satisfied only by:
  - `call` blocks
  - the final `response`
- The final trace always ends in a final assistant `response「...」`.

## Required Segment Shape

A trace is joined by exactly one blank line between segments:

```text
<|im_start|>system
...
<|im_end|>

<|im_start|>user
...
<|im_end|>

<|im_start|>assistant
...
<|im_end|>
```

If tools are used, the shape alternates:

```text
assistant -> tool -> assistant -> tool -> assistant
```

The final segment is always `assistant`.

## Per-Role Format

### `system`

Format:

```text
system「...」
```

Rules:
- no `🏷` tag
- plain text only
- if tools are available, tool schemas appear below the `system「...」` line in the same segment

Example:

```text
<|im_start|>system
system「You are a Rust documentation assistant who answers briefly and precisely.」
tool {
    name ↦ rustdoc_lookup •
    description ↦ "Returns concise documentation for a Rust symbol." •
    params ↦ {
        symbol ↦ { type ↦ string • description ↦ "Rust symbol" }
    }
}
<|im_end|>
```

### `user`

Format:

```text
user「...」🏷 usr1
```

Rules:
- exactly one user turn
- always tagged `usr1`

### `assistant`

An assistant turn may contain:
- one `plan { ... }`
- one or more `act { ... }`
- the final assistant turn contains `response「...」`

The common shapes are:

#### No-tool trace

```text
plan { ... }

act {
    think ↦ [
        「...」 𝑝 0.9 🏷 note1 ※ [ usr1 ]
    ]
}

response「...」
※ [ note1 ]
⊨ 1
```

#### Single-tool trace

```text
plan { ... }

act {
    call ↦ {
        tool ↦ some_tool •
        ...args...
        id ↦ res1
    } ⊨ 1
}
```

then a `tool` turn, then:

```text
act {
    think ↦ [
        「...」 𝑝 0.9 🏷 note1 ※ [ res1 ]
    ]
}

response「...」
※ [ res1 • note1 ]
⊨ 2
```

#### Multi-tool trace

```text
plan { ... }

act { call ↦ { ... id ↦ step1 } ⊨ 1 }
```

then:

```text
act {
    think ↦ [
        「...」 𝑝 0.9 🏷 note1 ※ [ step1 ]
    ]
}

act { call ↦ { ... id ↦ step2 } ⊨ 2 }
```

then:

```text
act {
    think ↦ [
        「...」 𝑝 0.9 🏷 note2 ※ [ step1 • step2 ]
    ]
}

response「...」
※ [ step1 • step2 • note2 ]
⊨ 3
```

### `tool`

Format:

```text
result {
    data ↦ "..." 🏷 some_id
}
```

Rules:
- only in `tool` turns
- the tag must match the preceding call `id`
- the assistant must stop after the call and wait for the tool turn

## Operators

| Glyph | Meaning |
|------|---------|
| `↦` | maps key to value |
| `•` | separates items |
| `🏷` | assigns a tag to an expression |
| `※` | references earlier tags |
| `⊨` | marks a todo as satisfied |
| `𝑝` | confidence on a thought |

## Semantic Rules

These are the important rules.

### 1. `plan.todo` defines the work items

Example:

```text
plan {
    todo ↦ {
        1 ↦ "Look up std::mem::take in the docs tool." ※ usr1 •
        2 ↦ "Explain what it does briefly." ※ usr1
    } •
    rationale ↦ "Use one tool call, then summarize the behavior and Default requirement."
}
```

Rules:
- todos are numbered `1..N`
- every todo must be satisfied exactly by later trace actions
- every todo text may reference `usr1`

### 2. `⊨` belongs on `call` or final `response`

This is the most important rule.

Allowed:

```text
act {
    call ↦ { ... } ⊨ 1
}
```

```text
response「...」
※ [ ... ]
⊨ 2
```

Not part of the target format:

```text
act {
    think ↦ [
        「...」 𝑝 0.9 🏷 note1 ※ [ res1 ] ⊨ 2
    ]
}
```

`think` supports the response or next step.  
It does not itself resolve the todo.

### 3. `think` is optional support, not completion

`think` exists to:
- explain the next step briefly
- connect tool evidence to the final answer
- keep the reasoning trace legible

`think` should:
- be short
- usually have one tagged note
- usually reference the relevant prior evidence with `※ [...]`

`think` should not:
- claim todo completion with `⊨`
- restate the entire answer
- become a long chain-of-thought dump

### 4. Tool calls satisfy retrieval/action todos

Examples:
- “Look up X in docs” -> satisfied by the docs `call`
- “Run cargo check” -> satisfied by the `cargo_check` `call`
- “Query total signups” -> satisfied by the SQL `call`

The tool result itself is evidence, but the completion marker goes on the `call`.

### 5. Final `response` satisfies answer/summarize/recommend todos

Examples:
- “Explain what it does briefly”
- “Provide a concise diagnosis”
- “Report the percentage”
- “Summarize the top findings”

The final user-facing answer is what resolves those todos.

### 6. Final `response` always carries references

Format:

```text
response「...」
※ [ tag1 • tag2 ]
⊨ N
```

Rules:
- the final response always has a ref block
- refs should point to:
  - tool-result tags
  - or supporting `think` note tags

### 7. Assistant stops after tool call

After:

```text
act {
    call ↦ { ... } ⊨ 1
}
```

the assistant turn ends.

The next segment is a `tool` result.

The assistant does not continue writing speculative results or fake tool outputs.

## Canonical Blocks

### `plan`

```text
plan {
    todo ↦ {
        1 ↦ "..." ※ usr1 •
        2 ↦ "..." ※ usr1
    } •
    rationale ↦ "..."
}
```

### `act` with `think`

```text
act {
    think ↦ [
        「...」 𝑝 0.9 🏷 note1 ※ [ res1 ]
    ]
}
```

### `act` with `call`

```text
act {
    call ↦ {
        tool ↦ rustdoc_lookup •
        symbol ↦ "std::mem::take" •
        id ↦ res1
    } ⊨ 1
}
```

### `result`

```text
result {
    data ↦ "..." 🏷 res1
}
```

### Final `response`

```text
response「...」
※ [ res1 • note1 ]
⊨ 2
```

## Exact Example

```text
<|im_start|>system
system「You are a Rust documentation assistant who answers briefly and precisely.」
tool {
    name ↦ rustdoc_lookup •
    description ↦ "Returns concise documentation for a Rust symbol." •
    params ↦ {
        symbol ↦ { type ↦ string • description ↦ "Rust symbol" }
    }
}
<|im_end|>

<|im_start|>user
user「In Rust, what does std::mem::take do? Use the docs tool.」🏷 usr1
<|im_end|>

<|im_start|>assistant
plan {
    todo ↦ {
        1 ↦ "Look up std::mem::take in the docs tool." ※ usr1 •
        2 ↦ "Explain what it does briefly." ※ usr1
    } •
    rationale ↦ "Use one tool call, then summarize the behavior and Default requirement."
}

act {
    call ↦ {
        tool ↦ rustdoc_lookup •
        symbol ↦ "std::mem::take" •
        id ↦ res1
    } ⊨ 1
}
<|im_end|>

<|im_start|>tool
result {
    data ↦ "Replaces a value behind a mutable reference with Default::default() and returns the previous value." 🏷 res1
}
<|im_end|>

<|im_start|>assistant
act {
    think ↦ [
        「Use the doc wording directly and mention the Default requirement.」 𝑝 0.9 🏷 note1 ※ [ res1 ]
    ]
}

response「std::mem::take replaces the value behind a mutable reference with Default::default() and returns the old value, so the type must implement Default.」
※ [ res1 • note1 ]
⊨ 2
<|im_end|>
```

## Non-Goals

The gold-set format does **not** try to support every historical glyph variant.

Specifically, this gold set does not rely on:
- multiple user turns
- `reply ↦ 「...」`
- `think` lines with `⊨`
- assistant-written `result {}`
- vague placeholder args like `"requested crate"` or `"target date"`
- generic filler thoughts

Those may have appeared in earlier experiments, but they are not part of the current target language.
