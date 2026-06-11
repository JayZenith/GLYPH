# SFT Worked. RLVR Reshuffled, Not Improved. The Contract Was the Real Lesson.

This is where I am ending this round of Glyph.

Glyph is a Rust tool-use agent. The model emits `CALL tool(...)` blocks, tools
execute against real Rust crates, and then the model should stop with a clean
`FINAL`.

The contract is not just "make cargo pass." The contract is the whole trace:

```text
CALL read_file(...)
RESULT ...
CALL apply_patch(...)
RESULT ...
CALL cargo_test(...) or CALL cargo_run(...)
RESULT status: success
FINAL: ...
```

That is the core lesson:

```text
Verifier RL is only as real as the contract it is optimizing.
For tool-use agents, the contract is the whole trace, not just the verifier.
```

The experiment was simple: take a strong SFT model and ask whether verifier RL
can improve it on a held-out Rust tool-use eval.

The final result:

```text
SFT built the agent.
RLVR did not improve aggregate held-out reliability.
It changed the solved set: one strict solve gained, two lost.
Most apparent RL collapses turned out to be infrastructure, not policy.
```

It is not the clean RLVR result I wanted, but it is the result I trust.

## The Metric Had To Be the Whole Trace

Early scoring was too loose. A metric called `terminal_tool_success` could
credit a trace whose last successful tool was `read_file`. That is not a
coding-agent success.

The metric that mattered became strict `valid_trace`:

```text
valid_trace =
  terminal cargo_test or cargo_run success
  + clean FINAL after that verifier success
  + exact CALL syntax
  + no role-marker leakage
  + no repetition or gibberish
  + no extra tool use after successful verification
```

If the model passes tests but keeps patching, emits malformed calls, leaks
ChatML markers, or never finalizes, it is not a usable tool-use agent.

## SFT Was the Main Result

The first strong SFT model, `SFT_V1`, scored:

```text
SFT_V1 strict held-out-69: 52/69
```

That was the first real artifact: a 4B base model learned the
CALL/RESULT/FINAL protocol well enough to edit Rust projects, run cargo
verifiers, and solve most of the held-out set.

Then I tried deeper SFT data. `SFT_V2` added variable-depth recovery.
`SFT_V3` added deeper recovery plus oversampled clean PASS -> FINAL traces.

![Strict held-out-69 scores for SFT models](assets/final_sft_scores.svg)

```text
SFT_V1:     52/69
SFT_V2:     48/69
SFT_V3:     50/69
SFT_HALF_A: 51/69
```

The broad held-out score did not improve. But on the original 17 held-out
problems that `SFT_V1` failed:

```text
SFT_V1: 0/17
SFT_V2: 4/17
SFT_V3: 5/17
```

That was the first important tradeoff. Deeper recovery data added hard-tail
capability, but disturbed broad reliability. More difficult traces were not
automatically better. They shifted the policy.

The clean `SFT_HALF_A` run looked normal:

![SFT_HALF_A training curves](assets/final_sft_training_curves.svg)

So RLVR was starting from a competent SFT policy, not a broken baseline.

## The Clean Split

To make the RLVR experiment fair, I split `synthetic_data/signal_v3.jsonl` into
two deterministic halves:

```text
SFT_HALF_A: 1,042 rows, 762 unique case_ids
RL_POOL_B:  1,041 rows, 760 unique case_ids
```

The split preserved family, difficulty, expected tool-sequence length, and
run-vs-test balance as much as possible. It was grouped by `case_id`, so
oversampled traces for one case could not land on both sides.

Leakage checks:

```text
case_id overlap: 0
trace overlap:   0
```

`SFT_HALF_A` trained only on half A and scored:

```text
SFT_HALF_A strict held-out-69: 51/69
```

That became the baseline. RLVR needed to beat `51/69` on the same strict
held-out eval.

## The Harness Was the Experiment

Several RLVR attempts failed before the final clean readout.

Full-finetune RLVR was too destructive. Tiny target-set LoRA was basically
flat. Larger `RL_POOL_B` LoRA runs looked worth debugging, but the first scary
regressions were not all model failures. They were harness failures.

The same underlying lesson showed up three ways:

```text
RL reward must match held-out success.
RL rendering must match the SFT/eval tool protocol.
RL checkpoint export must match the policy actually served during training.
```

Reward first: cargo passing somewhere in the trace is not enough. Top reward
had to mean held-out-style success: terminal verifier pass, exact CALL syntax,
clean final, no role leakage, no repetition, and no extra tool use after
success.

Protocol next: the model was trained on literal ChatML-style tool turns:

```text
<|im_start|>assistant
CALL ...
<|im_end|>
<|im_start|>tool
RESULT ...
<|im_end|>
```

Any deviation is not formatting trivia. It changes the learned task.

Export was the nastiest one. Two checkpoints appeared to collapse to `0/69`,
but the traces were not random. They had one extra parenthesis:

```text
CALL read_file(id="c1", file_path="..."))
```

Strict eval rejected every malformed call, no tools ran, and the score went to
zero. That looked like RL destroyed the model. It had not. The bad repos came
from non-canonical full-weight exports. The served RL policy was base model plus
the broadcast LoRA adapter; `weights/step_N` was not the clean served policy.

The official path became:

```text
outputs/<RUN>/run_default/broadcasts/step_N/
```

exported as a PEFT adapter and evaluated as:

```bash
python -m sft.eval_formal \
  --sft-model JayZenith/SFT_HALF_A \
  --sft-adapter JayZenith/<RLVR_ADAPTER_REPO> \
  ...
```

Only after those fixes did the RLVR result become worth interpreting.

## One Gain, Two Losses

The cleanest case-level RLVR readout is `RLVR_V1000` step 25, evaluated through a
direct local merge of the broadcast adapter:

```text
SFT_HALF_A:                         51/69
RLVR_V1000 step25 direct merge:     50/69
```

So it did not improve overall.

But it did solve one held-out problem that `SFT_HALF_A` failed:

![V1000 case-level diff](assets/final_v1000_case_diff.svg)

This case matters because it is exactly the kind of recovery loop SFT still
struggled with: repeated plausible patches, real verifier feedback, and a
budget that disappears if the model does not converge.

The case:

```text
eval100_039_select_event_codes_partial_then_full_fix
kind: patch_test_recover
```

`SFT_HALF_A` got stuck in a repeated read -> patch -> test loop. It made 21
tool calls, never passed the tests, exhausted the budget, and emitted no clean
final.

`RLVR_V1000` made a better fourth patch, got `cargo_test` passing at call
`c12`, and emitted a clean one-line `FINAL`.

That is a real strict held-out solve. It is not lenient scoring or an export
artifact. But the same checkpoint regressed two cases that SFT solved:

```text
eval100_048_dispatch_action_match_branch_repair
eval100_085_log_window_filter_map_recover
```

The losses are the gain in reverse. On both, `SFT_HALF_A` converged in a few
patch cycles and finalized cleanly, while `RLVR_V1000` looped
read -> patch -> verify without converging, exhausted the 20-round budget, and
never emitted `FINAL`. No finalization drift, no protocol errors -- just
non-convergent patching. All three flipped cases are recovery-kind problems.

Two important caveats. First, each side is a single greedy sample per case.
One greedy sample cannot distinguish a new capability from sampling-path luck,
and I stopped spending compute before running the pass@k probe that would
settle it. If `SFT_HALF_A` solves `eval100_039` at pass@8, the gain was
variance, not capability. Second, the gain and the losses look like the same
phenomenon with opposite signs: a slightly perturbed policy whose greedy
trajectory diverges early on near-boundary recovery loops and either converges
or does not.

The honest claim is:

```text
RLVR changed which recovery loops converge under greedy decoding,
while aggregate reliability regressed by one.
```

That is movement, not a win, and the movement is unverified.

## The Final Clean RLVR Run Still Regressed

After fixing reward shape, protocol fidelity, strict parser behavior, and
adapter export, I ran the cleaner V3000-style LoRA path.

![RLVR held-out-69 did not beat SFT_HALF_A](assets/final_rlvr_scores.svg)

```text
SFT_HALF_A:            51/69
V3000 step 5 adapter:  44/69
V3000 step 10 adapter: 47/69
V3000 step 15 adapter: 43/69
```

Step 10 was the best checked V3000 checkpoint, but still below baseline.

The rollout logs say why, and it is not subtle: the run never learned its own
training pool. Measured from the per-step rollout files: in-distribution
success (positive reward) was flat across all 37 steps, 0.51 in the first half
versus 0.48 in the second. Each step saw only 6 unique prompts (batch 48 at 8
rollouts each). The pool was 56% recovery prompts, which the policy solved
33% of the time against 70% for everything else -- harder, but not hopeless,
and 86% of rollout groups did carry reward variance. The signal existed; the
policy did not move on it.

My best explanation for why is config-level inference, not measurement: the
learning rate was 2e-7, and the loss heavily weighted a distillation term
(teacher_tau 0.8) toward a teacher that was the base model itself, which by
construction anchors updates to the starting policy. I did not instrument the
loss breakdown to confirm the anchor dominated.

Either way, the measured outcome stands: flat in-distribution success means
the three checkpoints are best read as small random perturbations of the
baseline, and the step-10 "peak" is noise, not dynamics. Reward bounced
instead of showing clean improvement:

![RLVR rollout reward curves](assets/final_rlvr_reward_curves.svg)

Sequence length stayed volatile too:

![RLVR rollout length curves](assets/final_rlvr_length_curves.svg)

For this task, longer rollouts often mean recovery grind, not better behavior.
An RL reward spike only matters if it transfers to strict held-out
`valid_trace`. Here it did not.

## What I Think Happened

SFT gave the model a strong prior for the exact tool protocol and a decent
greedy repair strategy.

RLVR perturbed that policy enough to change recovery trajectories. Sometimes
that flipped a case in (V1000's one gain), more often out (its two losses, and
every V3000 checkpoint landing below baseline).

The model was not learning a broadly better repair policy; it was reshuffling
near-boundary greedy paths. The V3000 logs show it never improved on its own
training pool, and my best explanation -- tiny learning rate plus a
distillation anchor to the base model -- is inference from the run config, not
something I instrumented.

The best interpretation:

```text
RLVR produced case-level movement, not improvement.
Whether any of that movement is real capability is unverified.
```

## What I Would Do From Here

I am stopping here, so this is ordered by cost, cheapest first. The first two
cost almost nothing.

```text
1. Verify the one claim: run SFT_HALF_A pass@8 (temp 0.8) on the three
   flipped cases. If SFT solves eval100_039 at k=8, the V1000 gain was
   sampling variance and this writeup's caveat becomes its conclusion.
2. Filter RL_POOL_B using the rollout logs already on disk: keep only
   prompts where the policy had mixed pass/fail outcomes within the eval
   tool budget. Drop always-solved and always-failed prompts. No new
   compute needed to build the list.
3. Keep the training and eval contracts identical end to end -- budgets,
   prompts, stop behavior -- so checkpoint comparisons stay clean. (The
   official held-out evals here ran with a 20-round tool budget, above the
   15 used in training, so budget was not a confound in these results.)
4. Let the policy actually learn: higher learning rate, much weaker
   distillation anchor, more unique prompts per step.
5. Greedy canary eval every 5 steps on a small fixed held-out slice; stop
   the run the moment it drops below the best checkpoint twice.
```

The missing ingredient was not more compute. It was cleaner signal selection
and tighter regression control -- and verifying claims at the case level
before believing them.

## Where This Ends

The final readout:

```text
SFT is the main result.
Strict evals are non-negotiable.
RLVR moved one hard held-out case in and two out; net minus one.
Most apparent RL collapse was harness, reward, protocol, or export mismatch,
not the policy.
```

I wanted a simple RLVR result. The useful finding is sharper:

```text
Verifier RL is only as real as the contract it is optimizing.
For tool-use agents, the contract is the whole trace, not just the verifier.
```
