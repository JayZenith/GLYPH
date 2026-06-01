#!/usr/bin/env python3
"""Assemble results/RLVR_V1 plotting artifacts from the rlvr_final_penaltyv7 run."""
import json, re, os, shutil, glob, csv

RUN = "outputs/rlvr_final_penaltyv7"
DST = "results/RLVR_V1"
os.makedirs(f"{DST}/canary_eval", exist_ok=True)
os.makedirs(f"{DST}/wandb", exist_ok=True)

# 1) copy canary jsons
for f in sorted(glob.glob(f"{RUN}/canary_eval/step_*.json")):
    shutil.copy(f, f"{DST}/canary_eval/{os.path.basename(f)}")

# 2) training_metrics.csv from launcher.log
log = open(f"{RUN}/logs/launcher.log").read()
rows = re.findall(r"Step (\d+) \| Time: ([\d.]+)s \| Reward: ([\d.-]+) \| Seq\. Length: ([\d.]+)", log)
with open(f"{DST}/training_metrics.csv", "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["step", "time_s", "reward", "seq_len_tokens"])
    seen=set()
    for s, t, r, sl in rows:
        if s in seen: continue
        seen.add(s); w.writerow([s, t, r, sl])

# 3) canary_summary.csv (per-step heldout canary metrics)
with open(f"{DST}/canary_summary.csv", "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["step", "num_prompts", "valid_traces", "clean_end_rate",
                "final_after_last_tool_rate", "avg_score",
                "fb_missing_final", "fb_dirty_final", "fb_final_before_tool_completion"])
    for f in sorted(glob.glob(f"{DST}/canary_eval/step_*.json"),
                    key=lambda p: int(re.search(r"step_(\d+)", p).group(1))):
        s = json.load(open(f))["summary"]["formal"]
        fb = s.get("failure_buckets", {})
        step = int(re.search(r"step_(\d+)", f).group(1))
        w.writerow([step, s["num_prompts"], s["valid_traces"], round(s["clean_end_rate"], 4),
                    round(s["final_after_last_tool_rate"], 4), round(s["avg_score"], 4),
                    fb.get("missing_final", 0), fb.get("dirty_final", 0),
                    fb.get("final_before_tool_completion", 0)])

# 4) wandb raw (full history for interactive plotting)
W = glob.glob(f"{RUN}/wandb/offline-run-*")[0]
for f in glob.glob(f"{W}/run-*.wandb") + [f"{W}/files/requirements.txt"]:
    if os.path.exists(f):
        shutil.copy(f, f"{DST}/wandb/{os.path.basename(f)}")

# 5) provenance README
canary = {int(re.search(r"step_(\d+)", f).group(1)):
          json.load(open(f))["summary"]["formal"]["valid_traces"]
          for f in glob.glob(f"{DST}/canary_eval/step_*.json")}
readme = f"""# RLVR_V1 results

Artifacts for plotting the RLVR_V1 run.

- **model**: JayZenith/RLVR_V1 (= rlvr_final_penaltyv7 weights/step_25)
- **base**: JayZenith/SFT_V1
- **data**: JayZenith/RLVR_V1_DATASET (rl_prompts_hard_recover.jsonl, 1042 rows)
- **git commit**: b194f7e
- **hyperparams**: lr 1e-6, temp 0.6, rollouts/example 4, batch 24, max_tool_rounds 15, max_completion_tokens 1536, max_steps 200

## Files
- `training_metrics.csv` — per-step reward / seq-length / wall-time (steps 0-{len(rows)-1})
- `canary_summary.csv` — per-checkpoint 6-prompt heldout canary metrics
- `canary_eval/step_*.json` — full per-case canary traces + metrics
- `wandb/run-*.wandb` — raw W&B offline history (full metric set)

## Checkpoint selection
Canary valid_traces: {dict(sorted(canary.items()))}. step_25 chosen (3/6 vs 2/6 at step_50;
25->50 regression consistent with prior runs) and published as JayZenith/RLVR_V1.
"""
open(f"{DST}/README.md", "w").write(readme)

print("assembled", DST)
for f in sorted(glob.glob(f"{DST}/**/*", recursive=True)):
    if os.path.isfile(f): print(f"  {os.path.getsize(f):>9} {f}")
