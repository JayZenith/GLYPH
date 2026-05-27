1. Reset

I previously had a DSL that was too overloaded for a 4B model:
- custom role wrappers
- plans
- thoughts
- satisfation bookkeeping
- tags
- refs
- proof markers
- extra Unicode operators

This new reset schema keeps only behavior that we should care about:
- assistant emits `CALL ...`
- tool emits `RESULT ...`
- assistant emits exactly one `FINAL: ...`
- model stops immediately `<|im_end|>`

## Canonical Format

```bash
<|im_start|>system
You are a Rust coding agent. Use tools when needed. After FINAL, stop immediately.
<|im_end|>

<|im_start|>user
User task here.
<|im_end|>

<|im_start|>assistant
CALL tool_name(id="c1", arg1="...", arg2="...")
<|im_end|>

<|im_start|>tool
RESULT c1:
tool output here
<|im_end|>

<|im_start|>assistant
FINAL: brief final answer.
<|im_end|>
```
* We will also keep assistant-only masking and have the environment feed the system prompt, tools available, and tool results. 

2. Simplifed Tool Scope

Keep the tool set narrow to avoid tool-choice confusion:
- `read_file`
- `apply_patch`
- `cargo_test`
- `cargo_run`

3. Synthetic Families

Preferred 1200 trace dataset mix and train on only these families:
320 patch_test_pass- `read_file -> apply_patch -> cargo_test -> FINAL`
180 patch_run_pass- `read_file -> apply_patch -> cargo_run -> FINAL`
340 patch_test_recover- `read_file -> apply_patch -> cargo_test_fail -> ... -> cargo_test_pass -> FINAL`
260 patch_run_recover- `read_file -> apply_patch -> cargo_run_fail -> ... -> cargo_run_pass -> FINAL`
60 test_only- `cargo_test -> FINAL`
30 run_only- `cargo_run -> FINAL`


* Preferred percentage mix:
  * pass families = `500 / 1200 = 41.7%`
  * recover families = `600 / 1200 = 50.0%`
  * single-tool families = `90 / 1200 = 7.5%`
* REMINDER: NEED TO MAKE SURE I GENERATE HARDER CASES WITHIN THE FAMILIES TO ENCOURAGE MULTI TURN USE. 

*This complete set includes multi turn chat capabilities along with recovery behavior. We don't teach the model "failing answers are okay" but that failed tool results are feedback, and it should continue instead of giving up or hallucinating success. 

* This is preferred over a more pass-heavy mix because it reduces dominance of easy one-shot repair and gives the model much more recovery practice before RL.

 * For scaling, i will keep one source file per family and merge into one train file at end. This allows me to scale easier as i can raise one family without touching others while auditing quality per family. 
 - synthetic_data/families/patch_test_pass.jsonl
 - synthetic_data/families/patch_run_pass.jsonl
 - synthetic_data/families/patch_test_recover.jsonl
 - synthetic_data/families/patch_run_recover.jsonl
 - synthetic_data/families/test_only.jsonl
 - synthetic_data/families/run_only.jsonl

 The model should invent:
 
   - Rust bug
   - intended repair path
   - patch strings
   - user prompt
   - final message
 
   Local code should own:
 
   - file creation
   - tool execution
   - RESULT blocks
   - status pass/fail truth
   - final JSONL trace assembly
   - rejection of bad cases
 
   That gives you diversity from gpt-5.4, but correctness from execution. It also
   means bad generations are cheap to reject instead of silently poisoning SFT.


4. Evals
I wont include a random train/val/test split for this current run due to compute limits in generating a larger dataset, thus I will train on all curated traces but then will use a held-out post-eval that checks exact schemas, clean stopping, real tool success, and no extra tokens. 

With scaling up, validation loss is useful for generalization/overfit monitorinng but here its weak as it does not mean "stops corectly" or "uses tool correctly"

The post-eval test will overweight the hard cases. I started with 8 held-out real tool-executed prompts to prove the loop works, and with scaling should push this much higher before wasting RL money.

Post-eval will follow this held-out curation mix:
40 `patch_test_pass` - `read_file -> apply_patch -> cargo_test -> FINAL`
30 `patch_run_pass` - `read_file -> apply_patch -> cargo_run -> FINAL`
60 `patch_test_recover` - `read_file -> apply_patch -> cargo_test_fail -> ... -> cargo_test_pass -> FINAL`
45 `patch_run_recover` - `read_file -> apply_patch -> cargo_run_fail -> ... -> cargo_run_pass -> FINAL`
10 `test_only` - `cargo_test -> FINAL`
5 `run_only` - `cargo_run -> FINAL`


# Prevoiusly i used mock tool calling, thats a cheap format gate. I will be implementing real tool calling in the post-sft eval to care about real patching, real recovery, and real verifier success. 

# Real Example with real tool call eval suggestion
SFT eval can still be multi-turn with real tool execution as RL is about reward optimization, policy, updates, while this is just inference + execution + scoring. 

  1. Start from the prompt.
  2. Let the model generate the next assistant block.
  3. If it emits a valid CALL ..., execute that tool for real.
  4. Insert the real RESULT cN: block.
  5. Let the model continue from there.
  6. Repeat until:
      - it emits FINAL: ...
      - or it hits max_tool_rounds
      - or it emits invalid structure

```bash
<|im_start|>system
You are a Rust coding agent. Use tools when needed. After FINAL, stop immediately.
<|im_end|>

<|im_start|>user
Fix the failing crate at runs/rlvr1/rust_cases/addlib_bug. Read src/lib.rs, patch the bug, run cargo_test, then answer once.
<|im_end|>

<|im_start|>assistant
CALL read_file(id=\"c1\", file_path=\"runs/rlvr1/rust_cases/addlib_bug/src/lib.rs\")
<|im_end|>

<|im_start|>tool
RESULT c1:\npub fn add(a: i32, b: i32) -> i32 { a - b }
<|im_end|>
```

``` bash
<|im_start|>assistant
CALL apply_patch(id=\"c2\", file_path=\"runs/rlvr1/rust_cases/addlib_bug/src/lib.rs\", find=\"a - b\", replace=\"a + b\")\n<|im_end|>

<|im_start|>tool
RESULT c2:\nstatus: success\n<|im_end|>

<|im_start|>assistant
CALL cargo_test(id=\"c3\", project_path=\"runs/rlvr1/rust_cases/addlib_bug\")\n<|im_end|>

<|im_start|>tool
RESULT c3:\nstatus: success\nstdout: test result: ok\n<|im_end|>

<|im_start|>assistant
FINAL: Fixed the bug by changing subtraction to addition and verified it with cargo_test.
<|im_end|>
```
* My concern here is choosing a correct max_tool_rounds cap. 


# OK THE STORY NOW

I started by simplifying the trace format down to the only behavior I actually care about:
- assistant emits `CALL ...`
- tool emits `RESULT ...`
- assistant emits exactly one `FINAL: ...`

Then I narrowed tool scope to:
- `read_file`
- `apply_patch`
- `cargo_test`
- `cargo_run`

The next big step was making synthetic data real instead of fake. GPT only generates compact case specs, while local code owns:
- Rust file creation
- tool execution
- real `RESULT` blocks
- pass/fail truth
- final JSONL assembly
- rejection of bad generations

That gave me a real data pipeline instead of hallucinated tool traces.

I also aligned the runtime across synthetic data, SFT evals, and RL-facing code by using the same path style, same tool protocol, and shared runtime helpers. The eval loop is now real:
- model emits `CALL`
- tool executes for real
- real `RESULT` is injected
- model continues until `FINAL` or a hard cap

Validation became a required part of the workflow too. `synthetic_data/validate_dataset.py` now does both:
- static protocol checks
- replay execution against disposable copied Rust cases

On the data side I started with many brittle family splits, but simplified them into the ones that matter:
- `patch_test_pass`
- `patch_run_pass`
- `patch_test_recover`
- `patch_run_recover`
- `test_only`
- `run_only`

That simplification mattered a lot because exact recovery-count bookkeeping was creating noise without teaching the behavior I actually care about.

For dataset generation, I ran small pilot batches first, rejected bad generations, and only kept traces that survived real execution. From that process I assembled the current signal dataset:
- `synthetic_data/signal_259.jsonl`

Current signal dataset counts:
- `patch_test_pass`: `105`
- `patch_run_pass`: `49`
- `patch_test_recover`: `95`
- `test_only`: `5`
- `run_only`: `5`

Then I built a held-out formal eval with real Rust cases and real tool execution. I also added contamination guards:
- exact prompt overlap hard fail via `--train-data`
- prompt similarity hard fail via `--max-prompt-similarity`

The first train/eval runs exposed real issues:
- old mock-eval assumptions
- missing Rust toolchain on the eval machine
- stale eval naming and scoring around `recover_once` / `recover_twice`
- some held-out case path bugs

Those are now fixed.

The best current SFT run on the 259 dataset is:
- `3` epochs
- `lr=2e-5`
- `max_seq_length=4096`

That run now gets real held-out passes on the formal eval with actual tool execution. It is not finished, but it is enough proof that:
- the runtime works
- the dataset is teaching something real
- the eval is testing something real
- RLVR is now a credible next step rather than a random gamble

So the story at this point is pretty simple:
- the pipeline is real now
- the eval loop is real now
- the current dataset is enough to prove signal

Now it is time to scale the dataset and eval set up properly, because we have proof that the loop is working.
