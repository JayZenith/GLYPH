from __future__ import annotations

import argparse
import os
from pathlib import Path

from .app import GlyphDemoApp
from .client import VLLMCompletionClient
from .session import DemoConfig


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Interactive GLYPH TUI backed by remote vLLM.")
    parser.add_argument("--base-url", default=os.getenv("GLYPH_VLLM_URL", "http://127.0.0.1:8000/v1"))
    parser.add_argument("--model", default=os.getenv("GLYPH_VLLM_MODEL", "glyph"))
    parser.add_argument("--api-key", default=os.getenv("GLYPH_VLLM_API_KEY", "EMPTY"))
    parser.add_argument("--project", type=Path, required=True, help="Pristine Rust crate to copy per prompt.")
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
    parser.add_argument("--sandbox-backend", choices=("auto", "bwrap", "host"), default="auto")
    parser.add_argument("--allow-unsafe-host-execution", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.sandbox_backend == "host" and not args.allow_unsafe_host_execution:
        raise SystemExit("--sandbox-backend host requires --allow-unsafe-host-execution")
    client = VLLMCompletionClient(
        base_url=args.base_url,
        model=args.model,
        api_key=args.api_key,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
    )
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
    GlyphDemoApp(client, config, args.base_url, args.model).run()


if __name__ == "__main__":
    main()
