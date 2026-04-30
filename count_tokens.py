#!/usr/bin/env python3
"""
Count tokens in TASK traces JSONL file using the target model tokenizer.
"""

import argparse
import json
from pathlib import Path

from transformers import AutoTokenizer


def estimate_tokens_simple(text: str) -> int:
    """Simple estimation: ~4 chars per token."""
    return len(text) // 4


def percentile(values: list[int], pct: float) -> int:
    """Return an integer percentile using nearest-rank semantics."""
    if not values:
        return 0
    sorted_values = sorted(values)
    index = int((len(sorted_values) - 1) * pct)
    return sorted_values[index]


def analyze_traces(file_path: Path, model_name: str, use_simple: bool = False):
    """Analyze token counts in traces JSONL."""
    if not file_path.exists():
        print(f"Error: {file_path} not found")
        return
    
    print(f"Analyzing {file_path}...")

    tokenizer = None
    if not use_simple:
        print(f"Loading tokenizer: {model_name}")
        tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    
    traces = []
    total_tokens = 0
    
    with open(file_path) as f:
        for i, line in enumerate(f):
            try:
                item = json.loads(line)
                trace_text = item.get("trace", "")
                
                if use_simple:
                    tokens = estimate_tokens_simple(trace_text)
                else:
                    tokens = len(
                        tokenizer(
                            trace_text,
                            truncation=False,
                            add_special_tokens=True,
                        )["input_ids"]
                    )
                
                traces.append({
                    "index": i,
                    "tokens": tokens,
                    "chars": len(trace_text)
                })
                total_tokens += tokens
            except Exception as e:
                print(f"  Error on line {i + 1}: {e}")
    
    if not traces:
        print("No traces found")
        return
    
    # Stats
    trace_tokens = [t["tokens"] for t in traces]
    min_tokens = min(trace_tokens)
    max_tokens = max(trace_tokens)
    avg_tokens = sum(trace_tokens) // len(trace_tokens)
    median_tokens = percentile(trace_tokens, 0.50)
    p95_tokens = percentile(trace_tokens, 0.95)
    p99_tokens = percentile(trace_tokens, 0.99)
    
    print(f"\n{'='*60}")
    print(f"Total traces: {len(traces):,}")
    print(f"Total tokens: {total_tokens:,}")
    print(f"Total chars:  {sum(t['chars'] for t in traces):,}")
    print(f"\nPer-trace stats:")
    print(f"  Min:     {min_tokens:,} tokens")
    print(f"  Max:     {max_tokens:,} tokens")
    print(f"  Average: {avg_tokens:,} tokens")
    print(f"  Median:  {median_tokens:,} tokens")
    print(f"  P95:     {p95_tokens:,} tokens")
    print(f"  P99:     {p99_tokens:,} tokens")
    
    # Training estimates (rough)
    print(f"\n{'='*60}")
    print("Training estimates (very rough):")
    print(f"  Base model SFT (1 epoch):     ~{total_tokens:,} tokens")
    
    # Distribution
    print(f"\n{'='*60}")
    print("Token distribution:")
    buckets = [0, 100, 500, 1000, 5000, 10000, 50000, float('inf')]
    bucket_names = ["0-100", "100-500", "500-1K", "1K-5K", "5K-10K", "10K-50K", "50K+"]
    counts = [0] * len(bucket_names)
    
    for t in trace_tokens:
        for i, (low, high) in enumerate(zip(buckets[:-1], buckets[1:])):
            if low <= t < high:
                counts[i] += 1
                break
    
    for name, count in zip(bucket_names, counts):
        pct = 100 * count / len(traces)
        bar = "█" * int(pct / 2)
        print(f"  {name:>10}: {count:4} ({pct:5.1f}%) {bar}")
    
    print(f"{'='*60}\n")
    
    # Largest traces
    print("Top 10 largest traces:")
    largest = sorted(traces, key=lambda x: x["tokens"], reverse=True)[:10]
    for t in largest:
        print(f"  trace_{t['index']:04d}: {t['tokens']:,} tokens ({t['chars']:,} chars)")


def main():
    parser = argparse.ArgumentParser(description="Count tokens in TASK traces")
    parser.add_argument(
        "file",
        nargs="?",
        default="traces.jsonl",
        help="Path to traces JSONL file (default: traces.jsonl)"
    )
    parser.add_argument(
        "--simple",
        action="store_true",
        help="Use simple character-based estimation instead of the HF tokenizer"
    )
    parser.add_argument(
        "--model",
        default="Qwen/Qwen3-4B-Base",
        help="HF tokenizer/model name to use for token counting"
    )
    
    args = parser.parse_args()
    file_path = Path(args.file)
    
    analyze_traces(file_path, model_name=args.model, use_simple=args.simple)


if __name__ == "__main__":
    main()
