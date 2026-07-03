# SFT'ing Qwen3-4B-Base
1. Reset after failure on teaching Qwen3-4B-Base the structured agent trace

I previously had an agent trace language that was either too complicated for a 4B model or I had poor training runs:
* custom role wrappers, todos, thoughts, satisfaction bookkeeping, tags, refs, extra Unicode operators

To reduce complexity I stripped it down to the vital behavior:
- env/system role emits prompt
- User emits their prompt
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
CALL tool_name {"id":"c1","arg1":"...","arg2":"..."}
<|im_end|>

<|im_start|>tool
RESULT c1:
tool output here
<|im_end|>

<|im_start|>assistant
FINAL: brief final answer.
<|im_end|>
```

The model will be trained on assistant-only masking as the environment is responsible for responding to its tool calls via tool results.

2. Simplifying the Tool Scope

Keep the tool set narrow to avoid tool-choice confusion and keep important behavior such as reading files, editing files, running tests, and running programs:
* `read_file`, `apply_patch`, `cargo_test`, `cargo_run`

3. Building the Synthetic Dataset Families

Here's the preferred trace dataset mix and these families cover the main behavior as well as promoting multi-turn assistant behavior for error recovery:
patch_test_pass- `read_file -> apply_patch -> cargo_test -> FINAL`
patch_run_pass- `read_file -> apply_patch -> cargo_run -> FINAL`
patch_test_recover- `read_file -> apply_patch -> cargo_test_fail -> ... -> cargo_test_pass -> FINAL`
patch_run_recover- `read_file -> apply_patch -> cargo_run_fail -> ... -> cargo_run_pass -> FINAL`
test_only- `cargo_test -> FINAL`
run_only- `cargo_run -> FINAL`

* This is preferred over a more pass-heavy mix because it reduces dominance of easy one-shot repair and gives the model much more recovery practice before RL.

<!--* Preferred percentage mix:
  * pass families = `500 / 1200 = 41.7%`
  * recover families = `600 / 1200 = 50.0%`
  * single-tool families = `90 / 1200 = 7.5%`
* REMINDER: NEED TO MAKE SURE I GENERATE HARDER CASES WITHIN THE FAMILIES TO ENCOURAGE MULTI TURN USE.-->



 <!--* For scaling, I will keep one source file per family and merge into one train file at end. This allows me to scale easier as I can raise one family without touching others while auditing quality per family.
 - synthetic_data/families/patch_test_pass.jsonl
 - synthetic_data/families/patch_run_pass.jsonl
 - synthetic_data/families/patch_test_recover.jsonl
 - synthetic_data/families/patch_run_recover.jsonl
 - synthetic_data/families/test_only.jsonl
 - synthetic_data/families/run_only.jsonl-->


4. Running Evals
I won't include a random train/val/test split for this current run due to compute limits in generating a larger dataset but I will use a held-out post-eval that checks exact schemas, clean stopping, and real tool success. This post-eval should really gauge whether RLVR is viable.
* This post-eval also hard fails on exact overlap with the training dataset prompts and similarity between the training set crates and eval crates to avoid `data contamination` and measure `generalization`.
* This post-eval test will also overweight the hard cases from the dataset families. 

# Example with real tool call just focusing on actual behavior
SFT eval can still be multi-turn with real tool execution as RL is about reward optimization

```bash
<|im_start|>user
Fix the failing crate at runs/rlvr1/rust_cases/addlib_bug. Read src/lib.rs, patch the bug, run cargo_test, then answer once.
<|im_end|>

<|im_start|>assistant
CALL read_file {"id":"c1","file_path":"runs/rlvr1/rust_cases/addlib_bug/src/lib.rs"}
<|im_end|>

<|im_start|>tool
RESULT c1:\npub fn add(a: i32, b: i32) -> i32 { a - b }
<|im_end|>

<|im_start|>assistant
CALL apply_patch {"id":"c2","file_path":"runs/rlvr1/rust_cases/addlib_bug/src/lib.rs","find":"a - b","replace":"a + b"}\n<|im_end|>

<|im_start|>tool
RESULT c2:\nstatus: success\n<|im_end|>

<|im_start|>assistant
CALL cargo_test {"id":"c3","project_path":"runs/rlvr1/rust_cases/addlib_bug"}\n<|im_end|>

<|im_start|>tool
RESULT c3:\nstatus: success\nstdout: test result: ok\n<|im_end|>

<|im_start|>assistant
FINAL: Fixed the bug by changing subtraction to addition and verified it with cargo_test.
<|im_end|>
```

# Now really starting from a strong basis...
The pipeline to validate GPT 5.4 generated case specs through local code execution to verify crates are generated as well as real tool call results and valid expected behavior 
1. GPT generates a case spec
2. `materialize_specs.py` writes clean crate under source root.
3. It copies crate to sandbox
4. It executes intended tools on sandbox
5. If real execution matches expected status/stdout, writes training trace with real `RESULT` blocks.
6. Final train JSONL is merged.
7. `validate_dataset.py` later replays traces from clean blueprints into fresh sandbox copies.
8. Eval uses held-out blueprints and `eval_formal.py` to let model produce its own tool calls.


## SFT/RL/Evals alignment
- Training traces use `runs/rlvr1/rust_cases/CASE_ID`. 
- Eval prompts use the same style.
- Runtime rewrites that path to sandbox internally.
- This keeps model path format simple while making execution safe.
- It helped isolate the main question: can the model emit real tool use and repair behavior? YES. 

I initially passed 6/8 valid traces from formal eval which showed enough proof that:
- the runtime works
- the dataset is teaching something real
- the eval is testing something real

Then scaled up the dataset and eval set up properly to create an official `SFT_V1` model that will be carried into RLVR. 


## Rust-source similarity:
On top of making sure exact prompts don't overlap between eval and training set, I created a preflight command before eval that checked held-out eval crates are `not copies/near-copied` from train crates.

## The successful `SFT_V1` training run
The vital training specs:
- Epochs: 3
- Effective batch size: 8
- LR: 2e-5
- Max sequence length: 4096 (No Truncation)
- Masking: assistant-only
- No train split: trained on all curated traces
- Scheduler/defaults: cosine, warmup 0.03, weight decay 0.01, bf16/tf32 enabled
HF model: JayZenith/SFT_V1
HF dataset: JayZenith/SFT_V1_DATASET

## Key SFT_V1 findings showing RLVR readiness and what RLVR will look to fix 
- `52/69` valid traces with most failing on model not emitting a closing `FINAL`
  - Will look to solve this via RL
- Tool execution works: `68/69` terminal tool success 
- Format mostly works: call/result IDs `100%`, no repetition/truncation `100%`
- Real recovery works: example below fixed a bad patch after compiler error.
- Main remaining issue is policy/termination. `17` traces succeeded or kept trying but failed to emit clean `FINAL`.
- RLVR target is clear: reward verifier success + clean stop, penalize extra rounds/max-round loops


# REAL EVAL TRACE from `SFT_V1`
it reads, patches, gets compiler error, rereads, patches dereference `*enabled`, runs successfully, then emits `FINAL`

```bash
<|im_start|>system
You are a Rust coding agent. Use tools when needed. After FINAL, stop immediately.
<|im_end|>

<|im_start|>user
In the Rust crate at runs/rlvr1/rust_cases/eval100_024_patch_run_pass_005_active_tags_filter_map_join, fix the iterator pipeline in src/main.rs so running the binary prints the expected list of active tags.
<|im_end|>

<|im_start|>assistant
CALL read_file {"id":"c1","file_path":"runs/rlvr1/rust_cases/eval100_024_patch_run_pass_005_active_tags_filter_map_join/src/main.rs"}
<|im_end|>

<|im_start|>tool
RESULT c1:
status: success
stdout:
fn main() {
    let items = [
        ("core", true),
        ("draft", false),
        ("fast", true),
        ("wip", false),
        ("safe", true),
    ];

    let output = items
        .iter()
        .filter_map(|(name, enabled)| if !enabled { Some(*name) } else { None })
        .collect::<Vec<_>>()
        .join(",");

    println!("{}", output);
}
<|im_end|>

<|im_start|>assistant
CALL apply_patch {"id":"c2","file_path":"runs/rlvr1/rust_cases/eval100_024_patch_run_pass_005_active_tags_filter_map_join/src/main.rs","find":".filter_map(|(name, enabled)| if !enabled { Some(*name) } else { None })","replace":".filter_map(|(name, enabled)| if enabled { Some(*name) } else { None })"}
<|im_end|>

<|im_start|>tool
RESULT c2:
status: success
stdout:
patch applied
<|im_end|>

<|im_start|>assistant
CALL cargo_run {"id":"c3","project_path":"runs/rlvr1/rust_cases/eval100_024_patch_run_pass_005_active_tags_filter_map_join"}
<|im_end|>

<|im_start|>tool
RESULT c3:
status: failed
stderr:
error[E0308]: mismatched types
  --> src/main.rs:12:42
   |
12 |         .filter_map(|(name, enabled)| if enabled { Some(*name) } else { None })
   |                                          ^^^^^^^ expected `bool`, found `&bool`
   |
help: consider dereferencing the borrow
   |
12 |         .filter_map(|(name, enabled)| if *enabled { Some(*name) } else { None })
   |                                          +

For more information about this error, try `rustc --explain E0308`.
error: could not compile `active_tags_filter_map_join` (bin "active_tags_filter_map_join") due to previous error
<|im_end|>

<|im_start|>assistant
CALL read_file {"id":"c4","file_path":"runs/rlvr1/rust_cases/eval100_024_patch_run_pass_005_active_tags_filter_map_join/src/main.rs"}
<|im_end|>

<|im_start|>tool
RESULT c4:
status: success
stdout:
fn main() {
    let items = [
        ("core", true),
        ("draft", false),
        ("fast", true),
        ("wip", false),
        ("safe", true),
    ];

    let output = items
        .iter()
        .filter_map(|(name, enabled)| if enabled { Some(*name) } else { None })
        .collect::<Vec<_>>()
        .join(",");

    println!("{}", output);
}
<|im_end|>

<|im_start|>assistant
CALL apply_patch {"id":"c5","file_path":"runs/rlvr1/rust_cases/eval100_024_patch_run_pass_005_active_tags_filter_map_join/src/main.rs","find":".filter_map(|(name, enabled)| if enabled { Some(*name) } else { None })","replace":".filter_map(|(name, enabled)| if *enabled { Some(*name) } else { None })"}
<|im_end|>

<|im_start|>tool
RESULT c5:
status: success
stdout:
patch applied
<|im_end|>

<|im_start|>assistant
CALL cargo_run {"id":"c6","project_path":"runs/rlvr1/rust_cases/eval100_024_patch_run_pass_005_active_tags_filter_map_join"}
<|im_end|>

<|im_start|>tool
RESULT c6:
status: success
stdout:
core,fast,safe
<|im_end|>

<|im_start|>assistant
FINAL: Fixed the iterator filter_map condition so it keeps active tags and dereferences the boolean flag, producing the expected stdout.
<|im_end|>

```


### cN used for tool call and result pairs
- CALL read_file {"id":"c1","file_path":"runs/rlvr1/rust_cases/CASE_ID/src/lib.rs"}
- CALL cargo_test {"id":"c3","project_path":"runs/rlvr1/rust_cases/CASE_ID"}

`cN` is different. It identifies the tool call/result pair:
` CALL read_file {"id":"c1",...}
  RESULT c1:
`

so:
- CASE_ID = which Rust project
- c1,c2,c3 = which tool call in the convo



# So now moving onto RLVR with PRIME-RL ...
PRIME-RL is the training stack as my code defines the `task environment + reward` then hands it to PRIME-RL

## 3 core PRIME-RL runtime pieces
1. Inference: holds current policy and generates rollouts 
2. Orchestrator: CPU-side, samples prompts, calls inference for rollouts, invokes verifier env, packs complete rollouts to send to trainer, and relays updated trainer weights back to infernce
3. Trainer: updates weights, receives rollout batches, rewards, logprobs, advantages, then does the RL gradient updates. Runds backprop/FSDP/optimizer. 

```text
GPU 0 = rollout inference vLLM
GPU 1 = frozen teacher vLLM
GPU 2-3 = trainer FSDP shards
```

# Teacher
Frozen base SFT model. Gives token-level logprobs so student policy stays close to SFT behavior while still learning from reward. PRIME-RL calls this on-policy distillation/teacher anchoring. 

My task_trace.py is the `custom environment` PRIME-RL calls into for Rust tool execution and reward scoring. train.py builds PRIME-RL configs, maps GPUs, starts teacher inference, validates config, then calls PRIME-RL's local RL entrypoint.

### Note
Current PRIME-RL docs say OPD can be done natively with `num_teacher_gpus` plus `teacher_tau > 0` and that automatically starts teacher inference. My repo intentionall pins older PRIME-RL, before the student/teacher inference-pool refactor.

My train.py proves that: it starts teacher inference as a separate subprocess, then points the orchestrator at http://127.0.0.1:{teacher_port}/v1

# The first main issue i ran into `(results/RLVR1/rollouts)`

## What happened
model never stops at <|im_end|> and dumps a whole fake multi-turn transcript (hallucinates fake user/assistant turns instead of halting) in turn 1. Reward still pays it (+1.83) as the verifier only grades the real CALL-RESULT-FINAL and ignores the garbage. SO RL is reinforcing non-termination. Env runs only the first real `CALL`, so multi-step tasks never cmoplete `(is_complete=0 everywhere)`. Stop fails as the boundary is emitted in `literal text`, not token `151645`, so `stop_token_ids` dosen't catch it.
* Model's only emit `token IDs` samples from vocab but the text `<|im_end|>` can be produced as the single special token id 151645, or as a sequence of ordinary tokens that decode to the same characters -- e.g. `<`, `|`, `im_end`, `|`, `>`.
* So model can still leak probability onto the look-alike spelling. 

### Real picture
- stop tokens are enforced via VLLM - `stop_token_ids: [151644, 151645]` is in every request.
- SFT masking is correct too - `sft/data.py` trains `<|im_end|>` token as a lable, so termination is learnable. 
- Yet msg[0] has text after <|im_end|>. An id-based stop can only fail to fire
  if the model isn't emitting token 151645 there — it's emitting the literal 
  string <|im_end|> as ordinary text tokens. Tells: it writes <|im_end|>user /
  <|im_end|>assistant (wrong — should be <|im_start|>), and turns 2–3 did stop
  cleanly, so the id-stop works when the real token is sampled. Turn 1 spells
  the boundary as text, so stop_token_ids never matches.
  - This shows the model is emitting the string and stop id versions as when the string version is emitted, inferenc is not stopped. 

## Attempted Fix
Add a string stop as backup + penalize post-boundary tokens.
```bash
  # alongside add_chat_boundary_stop_tokens
  extra_body  # keep stop_token_ids
  sampling["stop"] = ["<|im_end|>", "<|im_start|>"]  # catches the literal-text 
  spelling
```
Then keep reward penalty for content after first boundary and penalty fixes the gradient. 
* Note: to prove token-vs-string, token ids need to be saved and (`return_token_ids` needs to persist) and then log generated token ids for one step and check if `151645` appears mid-completion.

What's actually happening (confirmed across steps):
- Every rollout (12/12, every step) fails to stop after the first <|im_end|>.
- is_completed = 0 for all rows — no rollout ever finishes cleanly.

Why it cascades: the model dumps its entire imagined multi-turn solution
inside turn 1 (e.g. the -4.2 row emits read_file, then hallucinates
<|im_end|>user\nCALL apply_patch {...} etc.). But the env only executes the
first real CALL, returns one RESULT, and the rest of the model's "plan" is
never run — it's just text. So:
- Single-call tasks (test_only) → one CALL is enough → succeed → +1.8.
- Multi-step tasks (patch_test_recover) → need CALL→RESULT→patch→test loop,
but the loop never happens because turn 1 never yielded control → fail → -4.2.


# Curious
I only trained on the stop id (my traces tokenized <|im_end|> -> 151645) but it's a `base` model: pretraining saw the ltieral characters `<|im_end|>` as ordinary text so multi-token spelling already exists in its priors. SFT taught the id but didn't fully kill pretrained string pathway, thus is `leaks`. 


### Result from these issues
RL has no learning signal as with no clean completions, there's barely any positive signal, so reward drifts down (step_0 -2.21 -> step_38 -3.72). Fix stopping first -> the multi-turn tasks should start cmpleting -> RL gets real signal.



# SO moving onto the fix
Stopping on both the id and string, but then penalize post-boundary tokens in reward / fix SFT, so it learns to emit the real stop token 151645.

  Teaching only comes from training signal:
  - SFT already trains 151645 as a label (right direction, just not winning).
  - RL: penalize tokens after the first boundary → gradient pushes mass onto the
  real stop. That's what teaches it.


# SO NEW ROADBLOCK, model found that bailing early caps the downside instead of gaming the upside. `(results/RLVR1/rollouts2)`
- classic when per-step/length penalites outweight the complegtion bonus
Model now stops too early. It patches, then quits — no cargo_test, no FINAL, sometimes an empty <|im_end|> turn. Fixed the "never stops" bug, created "stops before finishing" bug. Reward lets early-quit be cheaper than completing, so it bails.


## Attempted Fix
● Reward shaping. Make a verified FINAL the only path to positive reward, and
  penalize ending without it:
  - No FINAL reached → strongly negative (worse than continuing).
  - Empty/no-op turn (no CALL, no FINAL) → penalize.
  - Task verified (cargo_test/cargo_run passes) and clean FINAL → positive.



# SIDE NOTES 
● Whoever told you "averaging at the end" is wrong. Look at
  rl/task_trace.py:248-320 (_rust_tool_reward): the episode reward is a single
  sum over the whole transcript — alignment + per-call tool rewards summed over
  every executed call + terminal bonus/penalty + structure. One terminal scalar.
  No per-turn penalty, no averaging, no discounting.


# POTENTIAL ISSUE: Avoidance mechanism -> reward avoidance
- terminal_success_bonus: +3.0, clean_final_after_success:+2.0 - prize for not finishing. 
- failed_terminal_penalty: -2.0 - what you eat if you run cargo_test/cargo_run and it fails 
- missing_final_after_success_penalty: -1.0 - only fires inside terminal_success branch
- TRAP: terinal bonuses/penalties only apply if a terminal verifier actually ran. If model patches and quits before running cargo_test, then terminal_success=False AND saw_terminal=False → it hits
  neither branch. No −2.0, no missing-FINAL penalty, nothing.


SO RUNNING TEST RISKS -2.0 AND NOT RUNNING IT RISKS 0. not testing is the safe move. 

Fix: penalize "patched but never reached a terminal verifier" at least as hard as a failed terminal (e.g. an unconditional "no clean FINAL → big negative"), so quitting early is worse than trying and failing.
- The empty <|im_end|> turn (row #1 step_11) — the −2.5 should kill it
indirectly, but confirm those vanish.
- CALLTYPE — already self-corrects, ignore.



# NOW THE ISSUE (results/RLVR1/rollouts3)

  1. zero_advantage 6/6 = your real blocker. GRPO computes advantage = reward − group_mean, where a group is multiple rollouts of the same prompt. Your groups are size 2, and the two rollouts are identical every time (both −3.72, both 2.08). Identical reward → advantage 0 for the whole group → zero gradient. 6/6 means the entire step taught the model nothing. This is why reward shaping alone won't move it — if both samples behave the same, no shaping creates contrast.

  Fix: get variance within each group.
  - Bump rollouts-per-prompt from 2 to 8–16 (2 is far too small for GRPO).
  - Raise sampling temp (0.4 is too low — samples collapse to the same
  trajectory, no exploration).

  Without this, nothing else matters.

  2. CALLTYPE — you're right, it's not self-correcting here (rows #2/#3,
  step_18, −3.72). Malformed keyword → parser finds no valid CALL → no tool runs → tanks. Happy to add an explicit penalty + ideally a sampling constraint so it can't be emitted.

  3. bare <|im_end|> (rows #4/#5) — the empty-turn quit. My
  no_terminal_verifier_penalty already targets this, but it's moot until
  advantage is nonzero.

  4. Also noticed: even the good rollout (ex850, reward 2.08, has FINAL +
  terminal tool) shows is_completed=False. The env isn't marking successful
  episodes complete — worth checking the stop-condition logic; it may be
  undercounting real successes.



  ```bash
  HF_HOME=/workspace/.hf_home \
    CARGO_HOME=$HOME/.cargo \
    RUSTUP_HOME=$HOME/.rustup \   
    PATH=/workspace/prime-rl-src/.venv/bin:$HOME/.cargo/bin:$PATH \
    PYTHONPATH=/workspace/glyph:/workspace/glyph/rl \
    /workspace/prime-rl-src/.venv/bin/python rl/train.py \
      --model JayZenith/SFT_V1 \
      --teacher-model JayZenith/SFT_V1 \
      --teacher-device 0 \
      --teacher-tau 0.01 \
      --prime-rl-gpu-ids 2,3 \
      --num-infer-gpus 1 \
      --num-train-gpus 1 \
      --gpus-per-node 2 \
      --data synthetic_data/rl_prompts_1062.jsonl \
      --output outputs/rlvr_penalty_runpod \
      --max-steps 200 \
      --batch-size 24 \ 
      --rollouts-per-example 8 \
      --seq-len 5120 \
      --max-model-len 12288 \
      --teacher-max-model-len 12288 \
      --max-completion-tokens 1536 \
      --learning-rate 5e-7 \
      --weight-decay 0.01 \
      --checkpoint-interval 1000 \
      --temperature 0.8 \
      --gpu-memory-utilization 0.70 \
      --teacher-gpu-memory-utilization 0.50 \
      --max-tool-rounds 15 \
      --tool-timeout 30 \
      --port 8010 \
      --teacher-port 8011
  ```

  *  Three changes: rollouts-per-example 2→8 (group size; 2 can't produce
  contrast), batch-size 6→24 (keeps 3 prompts × 8 samples — your data showed
  batch_size = total rollouts, prompts = batch/rollouts), temperature 0.4→0.8
  (0.4 made the 2 samples collapse identical). If the infer GPU OOMs at 24, drop batch-size to 16 (2 prompts × 8) — keep rollouts-per-example at 8 regardless, that's the one that matters.

  Your sampling-constraint question — you're right. A sampling constraint
  (logit_bias, grammar-forced decoding) does not teach the model. It's a pure
  inference guardrail, exactly like the stop token: no gradient, it just blocks the bad token at generation time. The reward penalty is what actually teaches. So I only added the penalty for CALLTYPE (task_trace.py) — that produces the gradient. A constraint would also be clumsy here since CALLTYPE = CALL+TYPE (two tokens), not a single bannable id. Penalty is the correct lever.


# The REAL ISSUE
The RL prompt prefix matches SFT eval format: 
- system/user blocks
- ends with <|im_start|>assistant\n 
- examples in synthetic_data/rl_prompts_1062.jsonl look correct

HOWEVER, the RL continuation after tool result differs from SFT eval
- SFT eval explicitly injects:
  - <|im_start|>tool
  - RESULT ...
  - <|im_end}>
  - <|im_start|>assistant
- RL env returns only a message dict:
  - {"role": "tool", "content": "RESULT ..."}
- With `message_type="completion"`, this may not be rendered back into the exact ChatML continuation the SFT model was trained/eval on

Rollouts were however showing the failures as:
- assistant turn 1: valid CALL read_file {...} <|im_end|>
- tool result: valid RESULT c1...
- assistant turn 2: only <|im_end|>
- Then env sees no pending call and stops.

Symptom in RL rollout:

  assistant: CALL read_file {...} <|im_end|>
  tool: RESULT c1: ...
  assistant: <|im_end|>

  That second assistant turn means the model is being asked to continue from a bad boundary/context. It emits/closes the assistant block immediately, env sees no new call, rollout ends.


* FIXED by making RL env continuation match SFT eval exactly
Implemented in rl/task_trace.py.

  Change:

  - RustToolEnv.env_response() now returns tool results as raw ChatML:

  <|im_start|>tool
  RESULT ...
  <|im_end|>

  <|im_start|>assistant

  - It also keeps raw_chatml_transcript in state and parses against that, so
    subsequent calls are read from the same transcript shape as SFT eval.


# Issue now is zero_advantage=24/24 and so inspected Step 5/6 rewards/components
Are the 8 within-group rollouts identical trajectories, or different trajectories the ladder maps to the same score? This determines whether my additive-rewards instict is the fix compared to the current monolothic structure reward system that was constructed previous to the SFT/RT eval fix.

Found that within-group trajectories are differnt (4/8, 7/8, 3/8 unique) but the ladder maps them all to the `same scalar`, so advantage = 0 -> no gradient. 


# What's actually happening 
zero_advantage is not an exploration problem here - it's a `reward resolution` problem. GRPO advntage = reward - group_mean. If all 8 rollouts of a prompt get identical reward, advantage is 0 for entire group regardless of how different the trajectories are. 


Look at step_5 ex376: 8 rollouts, 4 distinct trajectories, all scored −3.17. The model tried genuinely different recovery attempts after the test failed — and the ladder said "all equally worthless." No signal to prefer the better attempt.


# WHy the ladder causes it
Ladder is `max`-style. It credits only the `deepest` rung reached, then collapses everything else. Two rollouts that both "patched, ran test, test failed, didn't recover" land on `staged_failed_terminal` (+0.5) identically -- even if one made the tests 0-pass-1-pass and other made them worse. The reward thows away exaclty the partial-progress information GRPO needs to rank siblings. 

  Evidence it's resolution, not depth: step_5/6 rollouts reach term=24/24
  (everyone runs the verifier). They're all at the same rung. The ladder has
  nothing left to differentiate them. Compare step_7 (za=8/24) — variance
  survives there only because rollouts happened to land on different rungs.


# So now is additive component rewards the final lever to get things really working?
Replace "credit the deepest rung" with "sum independent partial-credit signals," so two trajecroeis at same rung still separate on finer-grained progress. 


# REGROUP 
based on SFT, tools are wroking - terminal_tool_success_rate 0.875, result_id_match 1.0,no_repetition 1.0, not_truncated 1.0. Those are solved; don't reward them.


The failures are really all about FINAL:
- missing_final: 2
- dirty_final: 2
- final_before_tool_completion: 2
- (task_failure: 1 — the only non-FINAL one)


So single thing RL must fix = emit `one clean FINAL, after the last tool result, then stop.` This is the right v1 as "reward FINAL or penalize"


`Minimal additive reward plan (scrap ladder)`
Three independent terms, sumned:
+1.0   has exactly one valid FINAL
+1.0   FINAL comes after the last tool result (placement) — only if has_final
-1.0   no FINAL at all
-0.5   dirty FINAL (text/garbage after it, not clean stop)


Additive really is just "basic rewards/penalties -> less zero_advantage" Latter collapsed distinct trajectoreis to one scalar. WIth additive terms, a rollout that emits a clean FINAL and one taht dosent differ by ~2 points even if everything else matches -> nonzero advantage -> gradient.
