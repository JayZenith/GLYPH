# GLYPH Claims Audit — README.md + blog/index.html (published state)

Forensic audit, 2026-07-01. Every empirical claim traced to artifacts. Verdicts:
**V** verified · **U** unsupported (no artifact proves it) · **C** contradicted ·
**A** ambiguous (artifact exists but metadata/method/attribution unclear).
"Repl. type": T = training replication, I = inference-only replication, — = n/a.
"Seeded": whether randomness was explicitly seeded for the claim's runs.

Standardized names: `SFT_HALF_A_V8` (SFT base) · `RLVR_POOL_B_V8_STEP10` (sparse baseline)
· `RLVR_VFINAL_STEP10` (dense, headline) · `RLVR_VFINAL2_STEP10` (compiler-aware).

| # | Claim (as published) | Model/ckpt | Source artifact | Command/args provenance | Repl. | Seeded | Metric def | Stat unit | Verdict | Corrected wording |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | "sparse **binary** reward (+10 only for a clean pass)" (README); "The reward was binary" (blog lede) | RLVR_POOL_B_V8 | `glyph_results/RLVR_POOL_B_V8_STEP10/configs/orchestrator.toml` (no progress flags) + `rl/reward.py` DEFAULT_REWARD_CONFIG | `rl/train.py` launch, no reward flags → default table (−5/−4/−3/−1 penalties active) | T (n=1) | orch seed=42; trainer/sampling unseeded | reward table | — | **C** | "sparse: +10 clean success, fixed failure penalties otherwise — not binary" |
| 2 | "step 0 … filtered the **entire batch — 96 rollouts**" (blog lede+bullet); "0/96 for sparse" (README) | RLVR_POOL_B_V8 step 0 | `…STEP10/logs/orchestrator.log:42` = `Detected 64/96 (zero_advantage=64)`; `trainer.log` Step 0 loss 0.3445 | full-run log coverage (31 lines/30 steps) | T | — | rollouts dropped by zero-advantage filter | rollout/group | **C** — and no 96/96 or 48/48 event exists in ANY of 427 log files + trashed May-17 log; global max 80/96 (`new_results/RLVR_V999*`) | "step 0 filtered 64/96 (32 retained); 25–83% per batch across the run" |
| 3 | SFT "greedy strict pass@1: **74/150**" | SFT_HALF_A_V8 | provably-greedy `eval_formal_heldout_150.json` (embedded args, commit 3b4d893) = **72**; metadata-less `passk1_heldout150.json` = **74** (temp/args unrecorded; harness defaults T=0.8) | eval_formal: `python -m sft.eval_formal --max-tool-rounds 20 …` (recorded in file); passk1: unrecorded | I | eval_formal greedy=deterministic-ish; passk1 unknown | strict valid_trace, 1 attempt | prompt | **A** | "72 (HF-generate greedy) / 74 (vLLM k=1, sampling params unrecorded)" |
| 4 | sparse "74 → **72**/150. Flat-to-down" | RLVR_POOL_B_V8 STEP10 vs STEP20 | STEP10 `eval_formal` = **74** (greedy, recorded); STEP20 `passk1` = **72** (unrecorded params, different checkpoint) | as row 3 | I | mixed | strict valid_trace | prompt | **C** as stated — the provably-greedy pair is SFT 72 vs sparse-step10 74 (+2, opposite direction) | "greedy direction not established; sparse ≈ flat within noise across harnesses/checkpoints" |
| 5 | "**3-seed replication**" / "Welch's t-test (**independent seeds**)" | all three pass@8 arms | `…VFINAL2_STEP10/evals/eval2.log`: `===== SEED a/b/c =====`, identical args ×3, vLLM `seed=0` (default) every time; `sft/passk_scan_vllm.py` has **no seed parameter** | assistant-authored `run_eval_vfinal2.sh` (transcript 2026-06-30T01:28Z): `run_seed a/b/c` tags label filenames only | I (same adapter ×3) | **NO** | — | run | **C** as "seed replication" | "three independent reruns of the same nondeterministic eval (no seed control); variance = vLLM scheduling + tool-timing nondeterminism" |
| 6 | valid@8 table: SFT 95/97/100 (97.3); dense 102/102/99 (101.0); compiler 95/96/94 (95.0) | all three | 9 JSONs under `glyph_results/{SFT_HALF_A_V8,RLVR_VFINAL_STEP10,RLVR_VFINAL2_STEP10}/evals/` | passk8: k=8, T=0.8, max-tool-rounds 20, max-model-len 24576 (from eval2.log) | I | no | # prompts of 150 with ≥1 rollout: valid_trace ∧ any-cargo-success | prompt→run aggregate | **V** (all 9 recomputed exactly) | keep numbers; fix "seed" labels |
| 7 | "+3.7 valid@8 … p ≈ 0.115" | dense vs SFT | scipy reproduces exactly (t=2.079, df=3.55, p=0.11502) | Welch on [102,102,99] vs [95,97,100] | I | no | Welch t, n=3 aggregates | run (wrong unit: prompts are paired, family-clustered) | **V** as computation, **A** as method | add 95% CI ≈ [−0.9, +8.2]; prompt-level paired test preferable |
| 8 | "small but **reproducible**" | dense | 3 reruns of ONE adapter | — | I only | no | — | — | **U** | "consistent across three reruns of one trained adapter; training not replicated" |
| 9 | "The sparse run was flat, so the lift is **attributable to the reward change**" (blog) | sparse vs dense | **no pass@8 artifact exists for RLVR_POOL_B_V8** (only eval_formal + passk1); 1 training run/arm | — | — | — | — | — | **U** | delete; requires sparse pass@8 ×3 + training replication |
| 10 | "−6.0 valid@8 vs dense (p ≈ 0.012)" | compiler vs dense | scipy: t=−5.196, p=0.0118 | Welch on [95,96,94] vs [102,102,99] | I | no | as row 7 | run | **V** computation; direction consistent in all 3 runs; method caveats as row 7 | keep with caveat |
| 11 | "step 0 retained 32/96 … vs 0/96 for sparse" (README) | VFINAL2 vs POOL_B_V8 | VFINAL2 log: 65/96 detected (64 zero-adv +1 gibberish) → ~31; POOL_B_V8: 64/96 → 32; VFINAL: 79/96 → 17 | orchestrator logs | T | — | step-0 filter counts | rollout | **C** — sparse retained the same ~32; dense retained 17 | "step-0 filtering: sparse 64/96, dense 78/96, compiler 64/96 — retention doesn't separate arms" |
| 12 | "Likely Goodhart … churning on borrow-checker errors" | VFINAL2 | no trace-analysis artifact; alternative (ladder saturation: blueprints compile at start → stage 4 on first call, verified `cargo build` exit 0 on `scale200_063…`) unexamined | — | — | — | — | — | **U** (hypothesis) | label as untested hypothesis; note ladder-saturation alternative |
| 13 | "Structure is 100% SFT-saturated … 150/150" (blog) | RLVR_POOL_B_V8_STEP10 greedy | eval_formal: syntax/ids/paths 150/150/150 for the sparse arm; SFT itself = **149**/150 syntax | recorded in file | I | greedy | per-prompt structural checks | prompt | **V** for sparse arm; **A** attribution | attribute to the sparse-arm eval; SFT is 149/150 |
| 14 | "75 of 76 failures never reach a terminal cargo success" | RLVR_POOL_B_V8_STEP10 greedy | eval_formal: 76 strict fails, 75 without terminal success — recomputed exact | recorded | I | greedy | terminal_tool_success on strict failures | prompt | **V** | keep, name the artifact |
| 15 | "72/150 fail in both SFT and RLVR" | SFT + POOL_B_V8_**STEP20** | passk1 pair: 76∩78 = 72 exact; but eval_formal pair (used by rows 13–14) gives 74 | passk1 params unrecorded | I | unknown | valid_trace=0 intersection | prompt | **A** — number verified against passk1 pair, but adjacent bullets use the other harness/checkpoint | state harness; eval_formal overlap = 74 |
| 16 | "of the 75 cargo-failures, 52% compile and 44% pass ≥1 test (median 50%)" | RLVR_POOL_B_V8_STEP10 greedy | recomputed exact: 39/75 compile (strict cargo-RESULT), 33/75 ≥1 test, median 0.5 | recorded | I | greedy | per-prompt best over trace | prompt | **V** | keep, name artifact |
| 17 | "48 cases never a clean cargo success in 8 tries; 0 / 20 (41.7%) / 28 (58.3%)" | RLVR_VFINAL_STEP10, primary pass@8 run | recomputed exact (48 = cargo_solves==0; classification 0/20/28 with runs-count-as-compiled) | passk8 run 1 | I | no | cargo_solves==0 + trace classification | prompt | **V** (single run; SFT primary gives 55) | note it's the dense arm, one run |
| 18 | "cargo vs valid_trace differ by 0.3% (SFT), 0.2% (dense), 0.8% (compiler)" | all three | primary runs only: 0.33/0.25/0.83% ✓; all-3-runs: 0.61/0.47/0.81% | passk8 | I | no | per-rollout rate difference | rollout | **V** vs primary runs; **A** wording ("across the pass@8 eval") | "first run: 0.3/0.2/0.8%; all runs: 0.6/0.5/0.8%" |
| 19 | compiler-aware 0/8-valid-but-1/8-cargo truncation case | RLVR_VFINAL2_STEP10 | `heldoutfailplus150_015_patch_run_pass_016_enum_dispatch_priority_summary_labels`, rollout 7: cargo success, no FINAL, trace ends on reopened assistant turn — verified | passk8 run 1 | I | no | — | rollout | **V** | keep |
| 20 | "Stability (8/8) is flat" | SFT vs dense | per-file 8/8 counts: SFT [31,36,36] vs dense [37,36,33] — means 34.3 vs 35.3 (flat); primary-only 31 vs 37 (not flat) | passk8 | I | no | prompts with 8/8 valid | prompt | **A** (definition/source unrecorded) | "mean 8/8-stable prompts ≈ flat (34.3 vs 35.3)" |
| 21 | "~18% config-merge, ~17% enum-dispatch, ~11% leaderboard … roughly half in 3 families" | eval set | case-name clustering, method unrecorded (assistant-computed Jul 1); independent re-clustering gives 23/24/9% — 3-family total 56% | — | — | — | keyword buckets | case | **A** numerically, **V** qualitatively | "keyword-dependent; ~half the set in 3 recognizable families" |
| 22 | "zero exact case_id/blueprint_root overlap; zero source match after normalizing numbers/strings (703 vs 150)" | train vs eval | re-ran the exact normalized-hash check today: path overlap 0, normalized-hash overlap 0, no missing sources | transcript 2026-07-01T02:29Z (assistant), re-verified | — | deterministic | SHA1 of normalized src equality | file | **V** | keep (note: equality check, not similarity) |
| 23 | "703 training crates" | RL manifest | 703 unique case_ids in `rl_prompts_signal_v3_pool_b_mixed_oversampled.jsonl` — but the manifest is **923 rows** (44 test_only/run_only cases ×6 oversampled), undocumented | — | — | — | — | case | **V** count; **A** omission | disclose the 6× *_only oversampling |
| 24 | "a single run showed +7 … seed noise" | dense vs SFT | first-run pair 102 vs 95 = +7 ✓ | passk8 run 1 | I | no | — | run | **V** arithmetic; "seed noise" mislabel (row 5) | "rerun-to-rerun sampling noise" |
| 25 | "held-out 150 **unseen** crates" | eval set | unseen at ID/source level ✓ (row 22); composition: 81/150 from `heldout_fail_like*` batches, 99/150 hard, same GPT-5.4 generator (`synthetic_data/batch_specs.py`) as training | — | — | — | — | case | **V** "unseen"; **A** "held-out" framing | "unseen crates from the same generator, deliberately skewed hard/fail-like" |
| 26 | "only the reward shape changed" (A/B config parity) | dense vs compiler | archived orchestrator/trainer/inference TOMLs differ only in progress flags + output paths; orchestrator seed=42 both | recorded configs | T | partial (orch only) | — | — | **V** (config parity); training-run variance still unsampled | keep + note n=1/arm |
| 27 | ladder "monotone … isn't gamed by churning error counts" | reward code | `rl/tests/test_reward_progress.py` exists; per-call monotone by construction; as a training-dynamics claim untested; stage-4 saturation for compiles-at-start crates unmentioned | — | — | — | — | — | **A** | "monotone per call; behavior under optimization untested; saturates when the crate already compiles" |
| 28 | dense credit "fixed by the task (**unhackable**)" (blog) | env design | tests live in model-editable `src/lib.rs`; verified attempted assertion flip in SFT_HALF_A_V8 passk8 trace (`heldoutfail48_027`, call c11: `assert!(!cfg.use_tls)`→`assert!(cfg.use_tls)`), blocked only by find-uniqueness | passk8 artifacts | — | — | — | — | **C** | "not model-editable-proof: the model can patch test code; one blocked attempt on record" |
| 29 | "1 confirmed instance out of 29 traces (~3%)" spec-gaming | RLVR trace audit | tls-flip case documented (blog diff, portfolio note); the 28-trace random sample has **no artifact** (no trace-ID list); only 12 of 29 had checkable specs → 1/12 ≈ 8% of checkable | — | — | — | — | trace | **A**/**U** (sample unrecorded; denominator framing) | "1 violation among 12 traces with checkable specs (~8%); audit sample not archived" |
| 30 | Hardware/disk (~20 GB per pass@8 run; 200 GB filled) | — | no recorded measurements | — | — | — | — | — | **U** (benign) | keep as anecdote or measure |
| 31 | GRPO story: "A_i=(r−mean)/std; all-fail ⇒ identical ⇒ filtered ⇒ no gradient" | trainer | zero_advantage group filter behavior **V** (logs); exact normalization formula **U** locally (PRIME-RL pinned `97872d3e0`, not vendored); published story omits the OPD loss: `training_mode="opd"`, `teacher_tau=0.2`, `kl_tau=0.001`, `dppo_mask=0.2` (trainer.toml) — "no gradient" is true only of dropped groups; retained rollouts also carry teacher/KL terms | archived trainer.toml | T | — | — | — | **A** (incomplete) | "identical-reward groups are dropped (no signal at all); retained rollouts train on advantage + teacher-anchor + KL terms" |

## New evidence (2026-07-02): sparse pass@8 reruns + paired analysis

**Parity verification of the sparse eval** (`glyph_results/RLVR_POOL_B_V8_STEP10/`):
- Runner `passk8_heldout150_metadata/run_sparse_passk8.sh` + per-run `command_run{1,2,3}.txt`:
  flag-for-flag identical to the dense/compiler commands (`parity_source_command.txt` and
  `eval2.log`) — only `--sft-adapter` and paths differ. k=8, T=0.8, max-new-tokens 4000,
  max-tool-rounds 20, max-model-len 24576, prompt-batch-size 8, save-rollouts. No seed
  (matching the other arms' non-design). **[V]**
- `environment.txt`: vllm 0.23.0 (same as June-30 arms), clean git tree at `abed10c`,
  adapter rev `b401ec0` r=64 α=128 base=`SFT_HALF_A_V8` rev `1b76c5f` (matches MANIFEST),
  150 prompts from the same YAML/section. Prompt set verified identical to the
  `RLVR_VFINAL_STEP10` eval. **[V]**
- Raw JSONs recomputed: run1 98, run2 96, run3 98 valid@8 (cargo@8 98/97/99); 150 unique
  prompts × k=8 × 1200 rollouts each. Summaries match. **[V]**
- Provenance note: run1 was interrupted at 80/150 and resumed (fresh vLLM engine for the
  last 70 prompts; `nohup_resume_20260701T232700Z.log`). Same args/adapter — composite run,
  not a parity break. **[A→noted]**

**valid@8, all four arms (3 unseeded reruns each):**

| arm | runs | mean |
|---|---|---|
| SFT_HALF_A_V8 | 95, 97, 100 | 97.3 |
| RLVR_POOL_B_V8_STEP10 (sparse) | 98, 96, 98 | 97.3 |
| RLVR_VFINAL_STEP10 (dense) | 102, 102, 99 | 101.0 |
| RLVR_VFINAL2_STEP10 (compiler) | 95, 96, 94 | 95.0 |

**Prompt-level paired analysis** (primary test: sign-flip permutation on per-prompt
mean-solve differences, 150 paired prompts, 100k permutations; sensitivity: family-block
sign-flip over 4 keyword clusters; discordant = pooled-ever-solved over 24 rollouts):

| comparison | Δ valid@8 | p (paired sign-flip) | p (family-block) | discordant |
|---|---:|---:|---:|---|
| dense vs SFT | +3.7 | 0.136 | 0.25 | +4/−2 |
| dense vs sparse | +3.7 | 0.162 | 0.38 | +5/−4 |
| sparse vs SFT | −0.0 | 1.000 | 1.00 | +6/−5 |
| compiler vs dense | −6.0 | **0.014** | 0.50 | +3/−8 |
| compiler vs SFT | −2.3 | 0.298 | 0.50 | +4/−7 |

**Claims now defensible / still not:**
1. **"Sparse RLVR was flat at pass@8" — now DEFENSIBLE** (measured: Δ vs SFT = 0.0,
   identical means). Amends audit row 9's premise; previously only greedy evidence existed.
2. **"Dense sits above both SFT and sparse by +3.7"** — defensible as a *point estimate
   with consistent direction* (dense ≥ 99 in all runs; SFT/sparse ≤ 100 in all runs);
   **not statistically significant** under the paired prompt-level test (p≈0.14/0.16).
3. **"The dense reward caused the lift" — still NOT established.** One training run per
   arm; run-to-run training variance unsampled. What changed: the comparison is now
   apples-to-apples at the headline metric, and the sparse control is flat.
4. **"Compiler-aware < dense (−6.0)" — defensible at p≈0.014** treating prompts as
   exchangeable (matches Welch's 0.012); the family-block sensitivity (only 4 blocks,
   very low power) cannot confirm it — report both. Mechanism (Goodhart/borrow-churn)
   remains an untested hypothesis (audit row 12).
5. Welch-on-3-aggregates is hereby demoted to a secondary consistency check everywhere.

## The "3-seed" question, resolved

What actually ran (verified from `eval2.log` + this session's transcript, 2026-06-30T01:28Z):
an assistant-authored script `run_eval_vfinal2.sh` with `run_seed a/b/c` — three **sequential,
argument-identical** invocations of `sft.passk_scan_vllm`. The `tag` is used only in the echo
header, `--cases-root` name, and output filename. The harness has no seed flag; vLLM initialized
with default `seed=0` all three times; per-request sampling seeds were never set. Run-to-run
variation comes from vLLM async-scheduling/batching nondeterminism and tool-execution timing.
"3-seed replication" and "independent seeds" were the assistant's labels for this. The user's
only related instruction (2026-06-30, verbatim: "identical data, steps, and base model and
seeds") *requested* seed control — the docs asserted it instead of implementing it.

## Where the GRPO narrative entered

- `ccce448` (2026-06-04, **no agent trailer**): first A_i formula + "std=0 ⇒ no gradient" in the
  heldout-69 blog draft. Correct as far as it goes; already omits loss composition.
- `4d37d20`/`8e4989a` (2026-06-28, **Claude Opus 4.8** co-authored): the oversimplification —
  "binary reward", "filtered the entire first batch", "3-seed replication" all first appear.
- `6acec17`/`d165491` (2026-06-30, **Claude Sonnet 5** co-authored): "all 96", "0/96 vs 32/96",
  lede rewrite, "independent seeds".
- Possible source of "96/96": user recollection (stated in review 2026-07-01) codified by the
  agent without artifact verification; no surviving artifact shows it.

## Ownership attribution (user's work vs agent-generated/overstated)

Grounded in commit trailers + transcript; commits without Co-Authored-By are taken as user-authored.

**User's experiments/decisions (real, defensible):** SFT pipeline and masking design (May);
protocol design (CALL/RESULT/FINAL); the RLVR runs themselves; heldout-69→150 promotion; the
decision to A/B reward shapes; the instruction to replicate evals and match configs; the Jun-4
GRPO/zero-advantage diagnosis in its original, narrower form; the V999 postmortem discipline
(ARCHIVE_README, no agent trailer on `ccce448`/`d74120b`).

**Agent-implemented but numerically verified (safe to own with attribution):** dense +
compiler reward code (`caf2dbb`, `a945723`, Opus 4.8); chat-template parity fix (`d21fe5b`,
Fable 5); the eval numbers themselves — valid@8 table, p-values, 44%/52%/median-0.5, 48-set
0/20/28, leakage 0/0, truncation case — all recomputed exactly in this audit.

**Agent-generated and overstated (the audit's fixes):** "binary reward"; "entire batch/96-96
filtered"; "0/96 vs 32/96"; "3-seed replication"/"independent seeds"; "reproducible";
"attributable to the reward change"; "unhackable"; "~3%" denominator framing; family-%
precision; Goodhart-borrow-churn stated as likely cause.

## Addendum (2026-07-02): advantage formula verified from rollout artifacts

`glyph_results/RLVR_POOL_B_V8_STEP10/rollouts_step_10/train_rollouts.jsonl` (96 rows,
12 groups of 8, fields incl. `reward`, `advantage`, `is_filtered`): **advantage =
reward − group mean, with NO std normalization** (`mean-only=True, std-normalized=False`
on every checked group). Consequences: (1) the A_i=(r−mean)/std formula committed in the
blog drafts (`ccce448`) is wrong in detail for this PRIME-RL pin; (2) reward *scale*
directly sets gradient weight — penalty gaps (−3 vs −5) and progress bonuses (+0.5/+2.0
vs the ±10..−12 range) matter absolutely, not relative to group std. Also observed: an
all-10.0 group (adv all 0) and a mixed-success group [10×5, 9×3] with adv ±0.375 —
within-success variance from failed-verifier penalties is real, so all-success groups do
NOT always tie. Corrections/doc-push: commit `1715d28`.

## Oral exam results (2026-07-02)

Q1 reward mechanics: strong→exceptional (a,b exceptional — mean-only advantage claim
artifact-verified; c aside on success-gating was shaky; d missed OPD terms).
Q2 loss/trainer: exceptional — reconstruction matched pinned prime-rl loss.py exactly
(DPPO prob-space mask, teacher term detached into advantage, kl to inference policy);
missed mask-sign-before-teacher-add subtlety and filtered-groups-lose-distillation corollary.
Q3 SFT masking: strong — all token classes right; missed the <|im_start|>-stop append-back
leniency loophole (harness converts attempted continuation into clean stop).
Q4 data/leakage: strong — HELDOUT_FAILURE_TARGETS citation verified (batch_specs.py:69,291,
"similar in shape to SFT_V1 held-out failures"); reskin pair given was eval–eval instead of
train–eval (real channel confirmed: 103 ranking-family train cases).
Q5 stats: strong — pass@k estimator, gate asymmetry (valid⇒cargo redundancy direction),
independence violations, per-prompt vs family-block reconciliation all correct.
Q6 verifier: strong — read-only hidden test copy fix; correct intent-irrelevance;
minor conflation of the two config-merge cases (tls direct-vs-profile ≠ env-fills case).
Q7 systems: strong — loop, staleness bounds, weights-vs-broadcasts, teacher-alias
failure mode all correct.
Q8 history: strong — correct invalidation split (RL-side template mismatch compromised
pre-fix RL checkpoints; SFT eval harness never affected — could have been more decisive).
Q9 benchmark: strong — internal-eval verdict; hand-authored-50 pick well defended;
family-holdout design correct.
Q10 defense: strong — 30s version, four-failure account, ownership statements match audit.

Overall: exam passed; no re-drills required. Readiness assessment delivered in session.

## Status
- Doc corrections from earlier today: reverted; preserved at `review/pending_doc_corrections.patch`.
- Nothing committed or published. Hub env untouched (still carries its own README — audit later).
