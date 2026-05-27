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
220 patch_test_recover_once- `read_file -> apply_patch -> cargo_test_fail -> read_file -> apply_patch -> cargo_test_pass -> FINAL`
150 patch_run_recover_once- `read_file -> apply_patch -> cargo_run_fail -> read_file -> apply_patch -> cargo_run_pass -> FINAL`
120 patch_test_recover_twice- `read_file -> apply_patch -> cargo_test_fail -> read_file -> apply_patch -> cargo_test_fail -> read_file -> apply_patch -> cargo_test_pass -> FINAL`
80 patch_run_recover_twice- `read_file -> apply_patch -> cargo_run_fail -> read_file -> apply_patch -> cargo_run_fail -> read_file -> apply_patch -> cargo_run_pass -> FINAL`
60 test_only- `cargo_test -> FINAL`
30 run_only- `cargo_run -> FINAL`
40 read_only- `read_file -> FINAL`


* Preferred percentage mix:
  * 1-turn repair families = `500 / 1200 = 41.7%`
  * 2-turn recovery families = `370 / 1200 = 30.8%`
  * 3-turn recovery families = `200 / 1200 = 16.7%`
  * single-tool families = `130 / 1200 = 10.8%`
* REMINDER: NEED TO MAKE SURE I GENERATE HARDER CASES WITHIN THE FAMILIES TO ENCOURAGE MULTI TURN USE. 

*This complete set includes multi turn chat capabilities along with recovery behavior. We don't teach the model "failing answers are okay" but that failed tool results are feedback, and it should continue instead of giving up or hallucinating success. 

* This is preferred over a more pass-heavy mix because it reduces dominance of easy one-shot repair and gives the model much more recovery practice before RL.

* For scaling, i will keep one source file per family and merge into one train file at end. This allows me to scale easier as i can raise one family without touching others while auditing quality per family. 
 - synthetic_data/families/patch_test_pass.jsonl
 - synthetic_data/families/patch_run_pass.jsonl
 - synthetic_data/families/patch_test_recover_once.jsonl
 - synthetic_data/families/patch_run_recover_once.jsonl
 - synthetic_data/families/patch_test_recover_twice.jsonl
 - synthetic_data/families/patch_run_recover_twice.jsonl
 - synthetic_data/families/test_only.jsonl
 - synthetic_data/families/run_only.jsonl
 - synthetic_data/families/read_only.jsonl

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
I wont include a random train/val/test split for this current run due to compute limits in generating a larger dataset, thus I will train on all curated traces but then will use a held-out post-eval that checks exact schemas, clean stopping, tool order, recovery behavior, and no extra tokens. 

With scaling up, validation loss is useful for generalization/overfit monitorinng but here its weak as it does not mean "stops corectly" or "uses tool correctly"

The post-eval test will overweight the hard cases. 200 prompts shall give enough hard recovery cases to trust the result before wasting RL money!

Post-eval will follow this 9-family curation mix:
40 `patch_test_pass` - `read_file -> apply_patch -> cargo_test -> FINAL`
30 `patch_run_pass` - `read_file -> apply_patch -> cargo_run -> FINAL`
40 `patch_test_recover_once` - `read_file -> apply_patch -> cargo_test_fail -> read_file -> apply_patch -> cargo_test_pass -> FINAL`
30 `patch_run_recover_once` - `read_file -> apply_patch -> cargo_run_fail -> read_file -> apply_patch -> cargo_run_pass -> FINAL`
25 `patch_test_recover_twice` - `read_file -> apply_patch -> cargo_test_fail -> read_file -> apply_patch -> cargo_test_fail -> read_file -> apply_patch -> cargo_test_pass -> FINAL`
20 `patch_run_recover_twice` - `read_file -> apply_patch -> cargo_run_fail -> read_file -> apply_patch -> cargo_run_fail -> read_file -> apply_patch -> cargo_run_pass -> FINAL`
10 `test_only` - `cargo_test -> FINAL`
5 `run_only` - `cargo_run -> FINAL`
5 `read_only` - `read_file -> FINAL`


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


# So setting tool execution for sft plan
1. Replace SFT's mock injection with real call parsing, execution, result formatting, and sandbox path-rewriting RL already uses
2. Make eval prompts materialize real held-out cases from names/blueprints instead of carrying fake mock_results
3. Tighten scoring so eval_formal.py checks actual verifier success for cargo_test/cargo_run and not just tool order 
  * Before scoring was structured gate + expected-sequence check. 
    * Did not verify real success as sft/evals/generation.py was injecting `mock_results`, a model could pass format/sequence checks w/o fixing code or surviving real recovery loops. 
    * Real execution in post-SFT eval is standard serious practice to decide if RL is worth it. 

# SFT eval tool execution now wired via RL runtime pieces
- `eval_formal.py` creates held out rust projects on disk via `--cases-root` before running eval, materializing cases like `runs/sft_eval_cases/<prompt_name>/<cache_dir>` and writes prompt with this real prompt. 
  * SO MUST CREATE THE `synthetic_data` dataset to use similar file paths. 
- `sft/evals/generation.py` runs the loop:
  - model emites `CALL ...`, parse pending call, execute tool for real, inject real `RESULT ...`, continue generation until `FINAL` or round limit. 
- `scoring.py` not declares success by requiring both protocol correctness and `real termial tool success`. Concretely
  - exact expected tool sequence
  - matching `CALL`/`RESULT` ids
  - one clean `FINAL`
  - final comes after last tool
  - last tool result has `status: success`
  - if last tool is `cargo_run`, its `stdout` must exactly match `expecgted output`
- Moved into `rl/rust/runtime.py` in which `sft/evals/generation.py` which is passed config from `eval_formal.py` now imports from the following
  - execute_rust_tool(...)
  - ensure_sandbox_copy(..) 
    - makes private copied workspace for one rollout/eval case so edits/tests don't touch original blueprint files
  - rewrite_path(..)
    - if a path points at original blueprint case, swap that prefix to the sandbox copy path
  - rewrite_params_for_sandbox(...) 
    - apply path rewrite across all string params in a tool call, like file_path or project_path. 




6. SFT & RL & Evals sharing the same world
* Some key notes here on SFT/RL/Eval alignment 
  * I will be using the same file path's that the RL env will provide such as `runs/rlvr1/rust_cases/...` as this is curcial so model sees same style in: 
    * SFT seed traces
    * RL prompts
    * eval prompts 
  * Also will make sure all three surfaces use the same trace families so we dont have SFT teaching one behavior while RL/eval test another.
    * Here are the 9 families:
      * patch_test_pass
      * patch_run_pass
      * patch_test_recover_once
      * patch_run_recover_once
      * patch_test_recover_twice
      * patch_run_recover_twice
      * test_only
      * run_only
      * read_only
  * Same protocol everywhere so all teach same trace format:
    * CALL tool(id="cN", ..,)
    * RESULT cN:
    * FINAL: ... 
  * Same tool invventory everywhere so model is not trained/eval'd on tools RL does not want.

* Key notes on data contamination
  * Training traces and eval prompts (`sft/evals/eval_prompts.yaml`) should not match overlap or else your eval will be contaminated as you will be testing the model's memorization. Rewording the prompts for eval is a way to avoid exact copies. 
    * `eval_formal.py` supports `--train-data` which calls the overlap check.


# SFT grading 
- exact protocol validity 
- valid `CALL` syntax
- valid `RESULT` linkage by id 
- clean stopping after `FINAL`
- tool sequence appropriateness
- whether patch cases actually end in passing `cargo_test` / correct `cargo_run`
- whether recovery cases improve after failures
- whether model avoids useless extra calls


# Lastly before data generation
One-off check read each trace, executed its CALLs for real, compared real tool results to the trace shape, and confirms recover cases fail first and pass at end
* Before generating more traces, should make this into a saved script so after generation, can run a command and know dataset is executable and not poisoned.

Extended synthetic_data/validate_dataset.py:1.

  It now always does both:

  - static validation: protocol, ids, family sequence, metadata, fail/pass
    recovery shape
  - replay validation: copies each Rust case into --cases-root, rewrites tool
    paths there, executes every CALL, and checks the trace result statuses/
    stdout are semantically right

  Important mental model:

  - --source-root: clean blueprint Rust cases, read-only during validation
  - --cases-root: disposable workspace where validation mutates files and runs
    cargo
  Do not mutate --source-root. Delete --cases-root whenever.

  I would run validate_dataset.py before every training run, but not inside sft/
   train.py by default. Better pattern:
 
   python3 synthetic_data/validate_dataset.py synthetic_data/train.jsonl \
     --source-root runs/rlvr1/rust_cases \
     --cases-root runs/validate_dataset_cases \
     --require-metadata \
     --summary
 
   python3 -m sft.train --data synthetic_data/train.jsonl ...
 
   Reason: replay validation can be slow for 1200 traces because it runs cargo
   many times. Make it a required preflight step in your run script, not hidden
   inside training.
