#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _step_number(path: Path) -> int:
    return int(path.name.removeprefix("step_"))


def _ready_steps(weights_root: Path) -> list[Path]:
    steps = []
    for path in weights_root.glob("step_*"):
        if not path.is_dir():
            continue
        if not (path / "config.json").exists():
            continue
        if not (path / "model.safetensors.index.json").exists():
            continue
        steps.append(path)
    return sorted(steps, key=_step_number)


def _run_canary(args: argparse.Namespace, step_dir: Path, output_path: Path) -> int:
    cmd = [
        sys.executable,
        str(ROOT / "rl" / "scripts" / "canary_eval.py"),
        "--model",
        str(step_dir),
        "--train-data",
        args.train_data,
        "--prompt-file",
        args.prompt_file,
        "--prompt-section",
        args.prompt_section,
        "--output",
        str(output_path),
        "--max-new-tokens",
        str(args.max_new_tokens),
        "--max-tool-rounds",
        str(args.max_tool_rounds),
        "--cases-root",
        args.cases_root,
    ]
    if args.nsjail_path:
        cmd.extend(["--nsjail-path", args.nsjail_path])
    if args.names:
        cmd.append("--names")
        cmd.extend(args.names)
    print(f"Running canary for {step_dir} -> {output_path}", flush=True)
    return subprocess.call(cmd, cwd=ROOT)


def main() -> int:
    parser = argparse.ArgumentParser(description="Watch RL weights and run heldout canary eval per checkpoint.")
    parser.add_argument("--weights-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--interval-seconds", type=int, default=60)
    parser.add_argument("--once", action="store_true", help="Scan once, run missing canaries, then exit.")
    parser.add_argument("--train-data", default="synthetic_data/signal_1062.jsonl")
    parser.add_argument("--prompt-file", default="sft/evals/eval_prompts_heldout_69.yaml")
    parser.add_argument("--prompt-section", default="post_eval_heldout_69")
    parser.add_argument("--names", nargs="*", default=None)
    parser.add_argument("--max-new-tokens", type=int, default=4000)
    parser.add_argument("--max-tool-rounds", type=int, default=15)
    parser.add_argument("--cases-root", default="runs/rlvr1/rust_cases/eval_canary")
    parser.add_argument("--nsjail-path", default=None)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    while True:
        for step_dir in _ready_steps(args.weights_root):
            step = step_dir.name
            output_path = args.output_dir / f"{step}.json"
            running_marker = args.output_dir / f"{step}.running"
            failed_marker = args.output_dir / f"{step}.failed"
            if output_path.exists() or running_marker.exists():
                continue
            running_marker.write_text(str(time.time()))
            rc = _run_canary(args, step_dir, output_path)
            running_marker.unlink(missing_ok=True)
            if rc == 0:
                failed_marker.unlink(missing_ok=True)
            else:
                failed_marker.write_text(str(rc))
                print(f"Canary failed for {step_dir} with exit code {rc}", file=sys.stderr, flush=True)
        if args.once:
            return 0
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
