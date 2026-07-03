# GLYPH exam cheat sheet (condensed from review/CLAIMS_AUDIT.md exam log)

One line per point. Corrections from grading are folded in — this is the *right* answer, not my first draft.

## Q1 — reward mechanics (sparse arm)
- (a) A = **−3** (3 failed verifiers × −1, capped at −4). B = **−5** (no-CALL early return — skips missing-FINAL/no-verifier penalties → *doing nothing can outscore trying*).
- (b) **advantage = reward − group mean, NO std** (verified in `rollouts_step_10`). So reward *scale* = gradient weight; +0.5/+2.0 dense bonuses are small vs ±10 by design, not normalization.
- (c) 64/96 = 8 of 12 groups tied, 4 survived (inferred from divisibility — **step-0 per-rollout data doesn't exist**; only steps 10/20/29 saved). All-success groups also filter (saw a real all-10.0 group).
- (d) Honest mechanism: identical-failure-profile groups drop; survivors learn *failure taxonomy*, not solution proximity. Strongest alternative: **one training run per arm** (lucky adapter).
- ★ Correction to own: filtered groups also lose the **teacher-anchor gradient** — the filter is an orchestrator policy choice, not math necessity.

## Q2 — the loss (PRIME-RL pin 97872d3e0)
- loss = −keep·(A + 0.2·(logp_teacher − logp_θ).detach())·exp(logp_θ − logp_inf) + 0.001·(log-ratio)², /loss_scale.
- DPPO mask: **probability-space** ±0.2, drops PG only (KL keeps full mask). ★ Mask sign uses **raw** A, *before* teacher term — trust region and update direction can disagree.
- Teacher = init model, frozen → functionally **KL-to-init via the advantage channel**; sampled-token MC estimate, not full-vocab KL. τ=0.01 → drift/collapse (clean_end 0.75→0.33).
- [10×5, 9×3] → adv +0.375/−0.625. 10-vs-9 = one fewer failed verifier = *efficiency* signal. Keep separate from the all-fail "surface taxonomy" claim.

## Q3 — SFT masking (`sft/data.py`)
- Header masked · body + closing `<|im_end|>` labeled · everything after masked · tool turns never match header → all −100.
- Failure modes: literal `<|im_end|>` inside CALL JSON truncates labeling (HF tokenizers parse specials in raw text); header-tokenization merge → whole turn silently masked; unterminated last turn trains body with no stop token.
- Stop on `<|im_start|>` catches role-hallucination (fabricated RESULTs, V1-era). ★ Append-back loophole: cut-off hallucination ≡ clean stop in valid_trace — **the sampler enforces part of the metric**.
- Hard-fail > truncate: silent cut = syntactically-plausible corrupted protocol examples.

## Q4 — data / "held-out"
- Eval = same GPT-5.4 generator; 54% built from `HELDOUT_FAILURE_TARGETS` ("similar in shape to SFT_V1 held-out failures"); 99/150 hard → 97.3/150 is on a **failure-enriched, same-generator** set.
- ★ Reskin pair must be **train-vs-eval**: train `scale200_041_leaderboard_rank_tiebreak_order` (103 ranking-family train cases) vs eval `..._dense_rank_merge_tiebreak_repair`. Hash check can't see it; AST/template similarity could (but over-flags boilerplate).
- case_id grouping closes duplicate-case leakage only — not generator-template or reference-trace-pattern leakage.
- Surviving claim: **generalizes across re-skins of covered templates**. Discriminator: ~50 hand-authored out-of-archetype tasks (ownership/lifetimes/traits), same harness.

## Q5 — metrics / stats
- valid@8 = prompt has ≥1 of 8 rollouts with `valid_trace ∧ cargo_success`. Equals Chen pass@k at k=n; pass@2 needs the combinatorial estimator, not subsampling.
- Gates are **one-way redundant**: valid ⇒ cargo (wrong-stdout runs already marked failed). Cargo-not-valid: success then extra tool call / dirty FINAL.
- Welch violations: (1) 3 reruns of ONE adapter — no training seeds; (2) prompts paired + family-correlated. Sign-flip fixes pairing only. Power for +4: inadequate.
- p≈0.014 vs p≈0.5 both true: 150 "exchangeable" prompts vs ~4 effective families. Family-block for broad claims; per-prompt = within-benchmark only.

## Q6 — verifier
- tls case: spec = direct>profile precedence; proxy = 3 tests; gap = no conflicting-tls test; valid_trace checks protocol+cargo only. **Intent irrelevant** — proxy failed either way.
- Fix: execute tests from **read-only hidden copy** (task format unchanged). Doesn't fix weak/incomplete specs or stdout proxies.
- Rank: hidden holdout tests > differential-vs-reference > property > mutation > LLM judge.
- 12/29 auditable → generator specs aren't machine-checkable; require a `spec_invariants` field per case.
- Real exhibit: SFT rollout attempted `assert!(!cfg.use_tls)→assert!(cfg.use_tls)` — blocked only by find-uniqueness. (Different crate than the tls-precedence case — don't merge them.)

## Q7 — systems
- Loop: vLLM (broadcast LoRA) → orchestrator (tools, rewards/advantages/filters, teacher logprobs) → trainer → new broadcast. `max_async_level=1`, `max_off_policy_steps=8` bound staleness; step N trains on latest-broadcast-at-sampling rollouts.
- `weights/step_N` = trainer checkpoint; `broadcasts/step_N` = served adapter. Wrong one still *loads* → looks like degradation, never errors.
- Logprob mismatch: kernel/precision differences + staleness. `mismatch_kl` monitors, `kl_tau` penalizes, DPPO mask cuts runaway PG tokens.
- Teacher alias bug: teacher serving student adapter under same name → anchors student to itself; metrics still look healthy. Sharpest answer of the exam.

## Q8 — history / invalidation
- Qwen default template renders role=tool as **user `<tool_response>`**; SFT trained on literal `<|im_start|>tool`. Pre-fix RL saw alien bytes mid-rollout → CALL syntax + stopping degraded.
- ★ Be decisive: mismatch was **RL-rollout-side only** — SFT/eval_formal always used literal ChatML → SFT rows in ARCHIVE table clean, period; pre-fix RL checkpoints unusable.
- Oversampling-fix evidence: per-kind run_only clean_end/valid_trace restored vs V999 (refuted if run_only cargo-succeeds but FINAL still drops).
- Stake most: protocol/reward/verifier/eval details dominate small RL results. Retract first: +3.7 as causal.

## Q9 — benchmark verdict
- heldout-150 = internal eval / protocol regression suite. Not a benchmark (same generator, fail-like construction, family skew).
- Budget pick: 50 hand-authored tasks + hidden property tests (external validity + verifier strength beat more-of-same or seeds-on-synthetic).
- Should-have-had: family-level holdout *before generation* → licenses "transfers to unseen task families".
- Say: "In a controlled synthetic Rust tool-use env, reward/serialization/verifier choices measurably change RL behavior; general coding-lift evidence is weak." Never: "GLYPH proves RLVR improves coding agents."

## Q10 — defense
- 30s: Rust tool-use agent, SFT→RLVR on real execution; durable finding = serialization/reward/verifier/eval choices dominate apparent RL gains, mapped with artifacts.
- Four failures: format mismatch (protocol bytes are part of the model) · export trap (evaluate the served artifact) · seed-that-wasn't (label variance honestly) · filtering myth (inspect rollouts before explaining mechanisms).
- Ownership: reward designed+verified · trainer loss consumed+audited · harness/generator agent-built+verified · stats descriptive-defensible, causal-not.
- Skeptic answer: "a mapped failure surface, not a benchmark win" — every clause artifact-backed.
