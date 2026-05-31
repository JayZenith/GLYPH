# SFT to RLVR: Teaching a 4B Model to Use Rust Tools

This project is about teaching `Qwen3-4B-Base` a narrow coding-agent protocol:

```text
assistant -> CALL ...
tool      -> RESULT ...
assistant -> FINAL: ...
```

The model does not get to fake tool results. During eval and RL rollout, the environment executes real Rust tools against sandboxed crates and appends the real `RESULT` back into the transcript.

## The Format

I stripped the trace language down after earlier versions had too much bookkeeping. The current protocol is intentionally small:

```text
<|im_start|>assistant
CALL read_file(id="c1", file_path="runs/rlvr1/rust_cases/example/src/lib.rs")
<|im_end|>

<|im_start|>tool
RESULT c1:
status: success
stdout:
...
<|im_end|>

<|im_start|>assistant
FINAL: Fixed the bug and verified it with cargo_test.
<|im_end|>
```

The tool set is also small:

- `read_file`
- `apply_patch`
- `cargo_test`
- `cargo_run`

The dataset families mirror the workflows I care about:

- `patch_test_pass`: read -> patch -> test pass -> final
- `patch_run_pass`: read -> patch -> run pass -> final
- `patch_test_recover`: patch -> test fail -> read again -> patch again -> test pass -> final
- `patch_run_recover`: same idea, but with program output
- `test_only` / `run_only`: call verifier directly -> final

## Building the Data

The training traces are not just text templates. The pipeline materializes real Rust crates, runs the intended tools, and records real outputs:

1. Generate a case spec.
2. Materialize a clean Rust crate.
3. Copy it into a sandbox.
4. Execute the trace tools for real.
5. Keep the example only if the expected result actually happens.
6. Later, replay traces from clean blueprints to validate them.

The path format is kept stable for the model:

```text
runs/rlvr1/rust_cases/CASE_ID/...
```

The runtime rewrites that path to a sandbox internally. That keeps the prompt simple while preserving safe execution.

## SFT_V1

The successful SFT run became:

- model: `JayZenith/SFT_V1`
- dataset: `JayZenith/SFT_V1_DATASET`
- train data: `synthetic_data/signal_1062.jsonl`
- epochs: 3
- LR: `2e-5`
- assistant-only masking
- max sequence length: 4096

Held-out eval used 69 real Rust/tool prompts from `sft/evals/eval_prompts_heldout_69.yaml`, with overlap checks against the training prompts.

SFT_V1 result:

```text
valid traces:          52/69
terminal tool success: 68/69
result id match:       69/69
not truncated:         69/69
```

That was enough to show the core behavior worked. The model could read files, patch code, run tests, recover from failures, and often stop cleanly.

Here is a shortened real success trace. The first patch is wrong because `enabled` is a `&bool`; the model reads the compiler error, fixes the dereference, runs again, and then emits `FINAL`.

```text
CALL read_file(id="c1", file_path=".../active_tags_filter_map_join/src/main.rs")

RESULT c1:
status: success
stdout:
let output = items
    .iter()
    .filter_map(|(name, enabled)| if !enabled { Some(*name) } else { None })
    .collect::<Vec<_>>()
    .join(",");

CALL apply_patch(id="c2", ..., replace=".filter_map(|(name, enabled)| if enabled { Some(*name) } else { None })")

RESULT c2:
status: success
stdout:
patch applied

CALL cargo_run(id="c3", project_path="...")

RESULT c3:
status: failed
stderr:
error[E0308]: mismatched types
expected `bool`, found `&bool`
help: consider dereferencing the borrow

CALL read_file(id="c4", file_path=".../src/main.rs")

RESULT c4:
status: success

CALL apply_patch(id="c5", ..., replace=".filter_map(|(name, enabled)| if *enabled { Some(*name) } else { None })")

RESULT c5:
status: success

CALL cargo_run(id="c6", project_path="...")

RESULT c6:
status: success
stdout:
core,fast,safe

FINAL: Fixed the filter_map predicate to dereference enabled and keep active tags.
```

## The First RLVR Problem Was Plumbing

Early RL rollouts looked much worse than SFT eval. That did not make sense because the starting model was SFT_V1.

The cause was an SFT/RL transcript mismatch. SFT eval used raw ChatML-style tool turns:

```text
<|im_start|>tool
RESULT c3:
...
<|im_end|>

<|im_start|>assistant
```

The RL environment was not resending the exact same raw transcript shape after tool results. After fixing `RustToolEnv` to accumulate and resend the same ChatML format, tool behavior came back: the model reached `apply_patch` and verifier calls again.

That was the first major RLVR milestone: the rollout environment finally matched the SFT eval environment.

## RLVR_V1 Did Not Improve Held-Out Eval

I trained `RLVR_V1` from `SFT_V1` and pushed:

- model: `JayZenith/RLVR_V1`
- RL prompt dataset: `JayZenith/RLVR_V1_DATASET`

Then I ran the same held-out formal eval against `JayZenith/RLVR_V1`.

The comparison was sobering:

```text
SFT_V1:
valid traces:          52/69
terminal tool success: 68/69
missing FINAL:         17

RLVR_V1:
valid traces:          51/69
terminal tool success: 68/69
missing FINAL:         18
```

So RLVR preserved the ability to solve tool tasks, but it did not improve the behavior we cared about. It was effectively flat, and slightly worse by one valid trace.

## The Real Failure Is Not Dirty FINAL

At first I thought the issue might be one of:

- multiple `FINAL`s
- `FINAL` before tool completion
- text after `FINAL`
- role leakage after `FINAL`

But inspecting the outputs showed something much cleaner and more specific.

SFT_V1:

```text
missing FINAL: 17
multiple FINAL: 0
dirty FINAL with text after it: 0
ends with empty assistant turn after tool result: 17
```

RLVR_V1:

```text
missing FINAL: 18
multiple FINAL: 0
dirty FINAL with text after it: 0
ends with empty assistant turn after tool result: 18
```

The failed traces usually end like this:

```text
<|im_start|>tool
RESULT c16:
status: success
stdout:
...
<|im_end|>

<|im_start|>assistant
```

Then nothing.

That is the current key failure. The model enters the next assistant turn after a tool result and emits no `FINAL`.

## Even More Specific: It Keeps Using Tools After Success

The repeated failures are not random. SFT and RLVR fail on almost the same problems:

```text
SFT missing FINAL:  17
RLVR missing FINAL: 18
overlap:            16
```

The common failures mostly have 16 tool calls and hit the tool-round boundary. Many have already reached a successful verifier earlier, but instead of stopping, the model continues with more `read_file` / `apply_patch` / verifier loops.

Typical failed shape:

```text
CALL cargo_test(id="c13", project_path="...")

RESULT c13:
status: success
stdout:
test result: ok

CALL read_file(id="c14", file_path=".../src/lib.rs")

RESULT c14:
status: success
stdout:
...

CALL apply_patch(id="c15", ...)

RESULT c15:
status: success
stdout:
patch applied

CALL read_file(id="c16", file_path=".../src/lib.rs")

RESULT c16:
status: success
stdout:
...

<|im_start|>assistant
```

No `FINAL`.

This means the reward problem is not just "add more FINAL reward." The policy needs to learn:

```text
successful verifier -> stop with FINAL
successful verifier -> more tools is bad
last RESULT -> empty assistant turn is bad
```

## Current Reward Fix

The reward is now being changed to distinguish those cases directly:

- big bonus: last tool `RESULT` followed by assistant turn containing `FINAL`
- big penalty: last tool `RESULT` followed by empty assistant / no `FINAL`
- big bonus: successful `cargo_test` or `cargo_run` followed by exactly one clean `FINAL`
- penalty: successful verifier followed by more tool calls
- penalty: successful verifier with no `FINAL`
- recovery shaping remains: failed verifier -> read again -> second patch -> pass -> `FINAL`

The intended behavior is:

```text
RESULT c3:
status: success
...

FINAL: Tests pass after the patch.
```

Not:

```text
RESULT c3:
status: success
...

CALL read_file(...)
```

And not:

```text
RESULT c16:
status: success
...

<|im_start|>assistant
```

This is the next major milestone: the SFT and RLVR held-out failures still look the same, which means the first RL reward did not actually target the model's stable bad attractor. The next run should tell us whether explicitly penalizing "success then keep tooling" and "empty assistant after RESULT" changes that behavior.
