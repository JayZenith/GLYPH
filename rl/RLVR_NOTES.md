# RLVR — what failed and the corrected recipe

RLVR_V1 (run v7, from SFT_V1) **regressed** the base model on the held-out 69:

| metric | SFT_V1 | RLVR_V1 |
|---|---|---|
| valid_traces | 52/69 | **20/69** |
| clean_end_rate | 0.75 | 0.33 |
| terminal_tool_success | 0.99 | 0.70 |
| task_failure (buckets) | 1 | 21 |

It got *worse at everything*, including behaviors the reward never touched → this was a capability **collapse**, not a finalization bug.

## Root causes (ranked)
1. **Depth-1-only recovery data.** All 507 recover traces in signal_1062 were exactly 1 fail → 1 fix → pass. The model learned a fixed 2-patch template; on cases needing 2–5 attempts it can't progress, never reaches the terminal state, loops, never FINALs. → Fixed in **signal_v2** (depth 1–5, diagnosis per attempt).
2. **Reward had no positive path on unsolved tasks.** Clean FINAL was only rewarded after a passing verifier, so every option on an unsolvable case scored negative → optimizer pushed the policy away from the SFT behaviors that worked.
3. **Huge, stacked, asymmetric penalties.** no-FINAL stacked to **-13…-23** vs +12…+17 for solve+FINAL. Under GRPO one bad rollout = ~-10…-20 advantage = brutal high-variance gradient.
4. **Penalties punished the shape of recovery** (long, multi-turn, no-FINAL-yet) — exactly what in-progress recovery looks like.
5. **SFT anchor off** (`teacher-tau 0.01` ≈ no KL) → nothing stopped drift/collapse.
6. **56% zero-advantage groups** (all-identical rollouts) → no gradient where it mattered; signal dominated by the giant penalties.
7. **Hyperparams moved backwards** (v6/v7: temp 0.8→0.6, rollouts 8→4, lr 5e-7→1e-6) → less exploration, less variance, faster sharpening.
8. **Eval was noisy and expensive** — a 6-prompt canary steered decisions (noise), and the 69-prompt eval ran on the multi-GPU RL box (~30 min, blocking).

## Fixes implemented
- **Reward** (`rl/task_trace.py`, `DEFAULT_REWARD_CONFIG`): bounded, outcome-first. Best ≈ +13, worst ≈ -5 (no stacking). Finalization **decoupled** from solving — a clean FINAL is rewarded even on an unsolved task (graceful exit > looping). Big signal = real verifier success (+8). Removed: `empty_after_result_no_final` (-8), `verifier_success_no_final` (-10), `verifier_success_more_tools` (-6), and the hand-shaped `_recovery_reward` block (recovery is taught by data now). Properties locked by `reward_golden_tests.py`.
- **SFT anchor** (`rl/train.py`): `teacher-tau` default 0.01 → **0.2**.
- **Hyperparams** (`rl/configs/task_trace/orchestrator.toml`): `rollouts_per_example` 4 → **8**, `zero_advantage` filter **enforced**, data → `rl_prompts_v2_1323`, model → `SFT_V2`. Keep temp 0.8, lr 5e-7.
- **Data**: `signal_v2_1323` (variable-depth recovery) → SFT_V2; `rl_prompts_v2_1323` for RL.
- **Eval**: `sft/evals/eval_prompts_smoke_12.yaml` (recover-weighted, 12 prompts, includes the prior failures) for fast per-checkpoint gating; run the full 69 only on final candidates, on a **separate 1-GPU box** so the RL box never blocks.

## Procedure for the next run
1. SFT_V2 on `signal_v2_1323` (README recipe).
2. Eval SFT_V2 on the 69 — **must beat 52/69 before any RL**. If not, fix data first; RL won't help.
3. RLVR from SFT_V2 with the corrected config (`rl/scripts/launch_rlvr_v2.sh`).
4. Gate every checkpoint on the 12-prompt smoke set; full 69 on the 2–3 best.
5. **Early-stop on held-out**; expect the winner early (prior best was step ~25).

## Kill conditions
- clean_end or terminal_tool_success drops below the SFT_V2 baseline for 2 consecutive checkpoints → stop, you're collapsing again.
- **Success bar:** beat SFT_V2's held-out valid-trace rate. If a run can't, don't ship it.

## Still open / to verify
- `max_completion_tokens=1536` did not hard-cap prior rollouts (they hit ~4500 tokens / 16 turns); confirm whether it's per-turn vs per-rollout, and that deep (depth-5) recovery fits `seq_len=5120`.
