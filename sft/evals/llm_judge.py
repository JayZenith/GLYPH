"""LM judge for SFT outputs (OpenAI-backed).

Validator scores STRUCTURE (well-formed trace, terminates, todos satisfied).
This judges QUALITY (does the plan solve the task; does the response answer
the user; are claims plausible; would a real user be satisfied).

Both signals are reported separately. Judge augments, not replaces.

Default: gpt-5-mini (~$0.25/1M input, ~$2/1M output — cheap, strong reasoning).
Switch to gpt-4o or gpt-5 for the RL reward path or paper-quality numbers.
"""
import json
import os
import re
from typing import Optional

from openai import OpenAI


JUDGE_SYSTEM = """You are an evaluator for an AI assistant that emits structured task traces.

A trace has these phases (in order):
  - plan { todo ↦ {1 ↦ "...", 2 ↦ "..."}, rationale ↦ "..." }
  - act { call ↦ {tool, params, id} } (calling tools)
  - result { data ↦ "..." 🏷 <id> } (tool results)
  - act { think ↦ "..." } (reasoning between tool calls)
  - response「Final answer to the user.」※ [refs] ⊨ N

You will be given a USER REQUEST and the assistant's full TRACE.

Score on a 1-5 scale on each dimension. Be calibrated, not lenient.
- 1 = unusable / wrong / off-topic
- 2 = bad but recoverable
- 3 = mediocre / partial
- 4 = good
- 5 = excellent / can't reasonably do better

Return ONLY a JSON object — no prose, no markdown fences."""


JUDGE_USER_TEMPLATE = """USER REQUEST:
{user}

ASSISTANT TRACE:
{trace}

Return JSON of this exact shape:
{{
  "plan_quality": <1-5 int>,
  "response_relevance": <1-5 int>,
  "factual_correctness": <1-5 int>,
  "helpfulness": <1-5 int>,
  "comments": "<one short sentence>"
}}"""


_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(text: str) -> dict:
    """Tolerant JSON extractor: takes the largest {...} block."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
    m = _JSON_OBJECT.search(text)
    if not m:
        raise ValueError(f"No JSON object found in:\n{text[:500]}")
    return json.loads(m.group(0))


def judge(
    user: str,
    trace: str,
    *,
    client: Optional[OpenAI] = None,
    model: str = "gpt-5-mini",
    max_tokens: int = 2000,
) -> dict:
    """Judge a single (user, trace) pair. Returns dict with 4 numeric dims + comments."""
    client = client or OpenAI()
    # GPT-5 family uses max_completion_tokens and disallows temperature override.
    is_gpt5 = model.startswith("gpt-5")
    kwargs: dict = {
        "model": model,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": JUDGE_SYSTEM},
            {"role": "user", "content": JUDGE_USER_TEMPLATE.format(user=user, trace=trace)},
        ],
    }
    if is_gpt5:
        kwargs["max_completion_tokens"] = max_tokens
    else:
        kwargs["max_tokens"] = max_tokens
        kwargs["temperature"] = 0
    resp = client.chat.completions.create(**kwargs)
    text = resp.choices[0].message.content or ""
    parsed = _extract_json(text)
    for k in ("plan_quality", "response_relevance", "factual_correctness", "helpfulness"):
        if k not in parsed:
            raise ValueError(f"Judge response missing {k!r}: {parsed}")
        v = parsed[k]
        if not isinstance(v, int) or not 1 <= v <= 5:
            raise ValueError(f"Judge {k}={v!r} must be int in [1,5]")
    parsed["judge_mean"] = sum(parsed[k] for k in (
        "plan_quality", "response_relevance", "factual_correctness", "helpfulness"
    )) / 4.0
    parsed["judge_model"] = model
    return parsed


def judge_eval_file(input_path: str, output_path: str, *, model: str = "gpt-5-mini") -> dict:
    """Read an eval_formal.json, judge every sft output, write augmented JSON."""
    with open(input_path) as f:
        eval_data = json.load(f)

    client = OpenAI()
    sft_results = eval_data["results"]["sft"]
    print(f"Judging {len(sft_results)} sft outputs with {model}...")

    judgments = []
    for i, row in enumerate(sft_results, 1):
        user = row["prompt"]
        trace = row["output"]
        if not trace.strip():
            print(f"  [{i}/{len(sft_results)}] {row['name']}: SKIP (empty output)")
            row["judge"] = None
            continue
        try:
            j = judge(user, trace, client=client, model=model)
            row["judge"] = j
            judgments.append(j)
            print(f"  [{i}/{len(sft_results)}] {row['name']}: mean={j['judge_mean']:.2f}  "
                  f"plan={j['plan_quality']} resp={j['response_relevance']} "
                  f"fact={j['factual_correctness']} help={j['helpfulness']}")
        except Exception as e:
            print(f"  [{i}/{len(sft_results)}] {row['name']}: FAILED ({e})")
            row["judge"] = {"error": str(e)}

    if judgments:
        dims = ("plan_quality", "response_relevance", "factual_correctness", "helpfulness")
        summary = {
            "n_judged": len(judgments),
            "model": model,
            **{f"{d}_mean": sum(j[d] for j in judgments) / len(judgments) for d in dims},
            "judge_mean_overall": sum(j["judge_mean"] for j in judgments) / len(judgments),
        }
        eval_data.setdefault("summary", {})["judge"] = summary
        print("\nJudge summary:")
        print(json.dumps(summary, indent=2))

    with open(output_path, "w") as f:
        json.dump(eval_data, f, indent=2)
    print(f"\nWrote {output_path}")
    return eval_data.get("summary", {}).get("judge", {})


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Run LM judge over an eval_formal JSON.")
    ap.add_argument("input", help="Path to eval_formal.json")
    ap.add_argument("output", help="Where to write the judged JSON")
    ap.add_argument("--model", default="gpt-5-mini",
                    help="Judge model (default: gpt-5-mini; use gpt-4o or gpt-5 for paper-quality)")
    args = ap.parse_args()
    judge_eval_file(args.input, args.output, model=args.model)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
