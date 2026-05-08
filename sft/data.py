"""Dataset loading + tokenization with assistant-only loss masking."""
import hashlib
import json
from pathlib import Path

from datasets import Dataset


def load_traces(data_path: str) -> list[dict]:
    """Load processed traces from JSONL into [{text: ...}, ...]."""
    traces = []
    with open(data_path) as f:
        for line in f:
            try:
                item = json.loads(line)
                traces.append({"text": item["trace"]})
            except Exception:
                pass
    print(f"Loaded {len(traces)} traces from {data_path}")
    return traces


def create_dataset(traces: list[dict], tokenizer, max_seq_length: int, cache_dir: str = ".cache") -> Dataset:
    """Tokenize traces with assistant-only loss masking; cache the result.

    Labels are -100 everywhere except inside `<|im_start|>assistant\\n` ... `<|im_end|>`.
    The assistant span includes the trailing `<|im_end|>` so the model is trained
    to actually emit the stop token.
    """
    cache_key = hashlib.md5(
        f"v2_assistant_mask_{len(traces)}_{tokenizer.name_or_path}_{max_seq_length}".encode()
    ).hexdigest()[:12]
    cache_path = Path(cache_dir) / f"tokenized_{cache_key}"

    if cache_path.exists():
        print(f"✓ Loading tokenized dataset from cache: {cache_path}")
        dataset = Dataset.load_from_disk(str(cache_path))
        print(f"  Loaded {len(dataset)} samples")
        return dataset

    print(f"Tokenizing dataset (will cache to {cache_path})...")

    true_lengths = []
    for trace in traces:
        tokens = tokenizer(trace["text"], truncation=False, add_special_tokens=True)
        true_lengths.append(len(tokens["input_ids"]))

    truncated = sum(1 for l in true_lengths if l > max_seq_length)
    if truncated > 0:
        over_lengths = [l for l in true_lengths if l > max_seq_length]
        print("\n⚠️  Truncation warning:")
        print(f"   {truncated}/{len(traces)} traces exceed max_seq_length ({max_seq_length})")
        print(f"   Max length: {max(true_lengths)}, Median: {sorted(true_lengths)[len(true_lengths) // 2]}")
        print(f"   Truncated lengths: min={min(over_lengths)}, max={max(over_lengths)}, avg={sum(over_lengths) // len(over_lengths)}")
    else:
        print(f"✓ No truncation needed (max trace: {max(true_lengths)} tokens)")

    asst_header_ids = tokenizer.encode("<|im_start|>assistant\n", add_special_tokens=False)
    im_end_id = tokenizer.convert_tokens_to_ids("<|im_end|>")
    H = len(asst_header_ids)

    def make_labels(ids):
        labels = [-100] * len(ids)
        i = 0
        while i <= len(ids) - H:
            if ids[i:i + H] == asst_header_ids:
                j = i + H
                while j < len(ids) and ids[j] != im_end_id:
                    labels[j] = ids[j]
                    j += 1
                if j < len(ids):
                    labels[j] = ids[j]
                    i = j + 1
                else:
                    break
            else:
                i += 1
        return labels

    def tokenize(examples):
        tokenized = tokenizer(
            examples["text"],
            truncation=True,
            max_length=max_seq_length,
            padding=False,
            return_attention_mask=True,
        )
        tokenized["labels"] = [make_labels(ids) for ids in tokenized["input_ids"]]
        return tokenized

    dataset = Dataset.from_list(traces)
    dataset = dataset.map(
        tokenize,
        batched=True,
        remove_columns=["text"],
        num_proc=4,
        desc="Tokenizing",
    )

    original_len = len(dataset)
    dataset = dataset.filter(lambda x: len(x["input_ids"]) > 100)
    print(f"Filtered {original_len - len(dataset)} short sequences")

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    dataset.save_to_disk(str(cache_path))
    print(f"✓ Cached tokenized dataset to {cache_path}")

    return dataset
