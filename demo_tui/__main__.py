from __future__ import annotations

import argparse
import os
from pathlib import Path

from .app import GlyphDemoApp
from .client import ScriptedCompletionClient, VLLMCompletionClient
from .session import DemoConfig


DEFAULT_SCRIPTED_CASE = "eval100_013_patch_test_pass_014_dispatch_policy_match_order"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Interactive GLYPH TUI backed by vLLM or an offline script.")
    parser.add_argument(
        "--backend",
        choices=("vllm", "scripted"),
        default=os.getenv("GLYPH_DEMO_BACKEND", "vllm"),
        help="Completion backend. Use scripted to inspect the TUI without vLLM.",
    )
    parser.add_argument("--base-url", default=os.getenv("GLYPH_VLLM_URL", "http://127.0.0.1:8000/v1"))
    parser.add_argument("--model", default=os.getenv("GLYPH_VLLM_MODEL", "glyph"))
    parser.add_argument("--api-key", default=os.getenv("GLYPH_VLLM_API_KEY", "EMPTY"))
    parser.add_argument("--project", type=Path, help="Pristine Rust crate to copy per prompt.")
    parser.add_argument(
        "--trace-prefix",
        help="Optional crate path written in the user prompt; tool calls using it map to the disposable copy.",
    )
    parser.add_argument("--sandbox-root", type=Path, default=Path("runs/demo_tui/sandboxes"))
    parser.add_argument("--transcript-root", type=Path, default=Path("runs/demo_tui/transcripts"))
    parser.add_argument("--expected-output", help="Exact stdout required for cargo_run tasks.")
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--max-tokens", type=int, default=4000)
    parser.add_argument("--max-tool-rounds", type=int, default=20)
    parser.add_argument("--tool-timeout", type=int, default=30)
    parser.add_argument(
        "--sandbox-backend",
        choices=("host", "bwrap", "auto"),
        default="host",
        help="Rust execution backend. The TUI defaults to host execution in a disposable crate copy; use bwrap to opt into Bubblewrap.",
    )
    parser.add_argument(
        "--allow-unsafe-host-execution",
        action="store_true",
        default=True,
        help=argparse.SUPPRESS,
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.project is None:
        if args.backend == "scripted":
            args.project = Path("synthetic_data/eval_blueprints") / DEFAULT_SCRIPTED_CASE
        else:
            raise SystemExit("--project is required when --backend vllm")
    if args.trace_prefix is None and args.backend == "scripted":
        args.trace_prefix = f"runs/rlvr1/rust_cases/{args.project.name}"

    if args.backend == "scripted":
        client = ScriptedCompletionClient(trace_prefix=args.trace_prefix)
        endpoint_label = "scripted://local"
        model_label = "scripted-eval100-013"
    else:
        client = VLLMCompletionClient(
            base_url=args.base_url,
            model=args.model,
            api_key=args.api_key,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
        )
        endpoint_label = args.base_url
        model_label = args.model
    config = DemoConfig(
        project=args.project,
        trace_prefix=args.trace_prefix,
        sandbox_root=args.sandbox_root,
        transcript_root=args.transcript_root,
        expected_output=args.expected_output,
        max_tool_rounds=args.max_tool_rounds,
        tool_timeout=args.tool_timeout,
        sandbox_backend=args.sandbox_backend,
        allow_unsafe_host_execution=args.allow_unsafe_host_execution,
    )
    GlyphDemoApp(client, config, endpoint_label, model_label).run()


if __name__ == "__main__":
    main()
