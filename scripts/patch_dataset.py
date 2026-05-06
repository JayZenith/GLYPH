#!/usr/bin/env python3
"""Patch fixable bugs in the SFT dataset; drop unfixable ones.

Fixable:
  - missing result tag → inject `🏷 <call_id>` after the data string
  - garbage trailing `}` after response → strip
  - unclosed final response → append `」`

Drop:
  - unsatisfied todos (we can't invent satisfaction markers)
  - undefined ref (we don't know what the model meant)
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from validator import validate_trace, TaskValidator  # noqa: E402

CALL_BLOCK = re.compile(r'(act\s*\{[^{}]*?call\s*↦\s*\{[^{}]*?\bid\s*↦\s*([\w\-\"]+)[^{}]*?\}[^{}]*?\})', re.DOTALL)
RESULT_BLOCK = re.compile(r'result\s*\{(?P<inner>[^{}]*)\}', re.DOTALL)


def patch_missing_result_tags(trace: str) -> tuple[str, int]:
    """For each call ↦ { ... id ↦ X ... }, find the next result block and ensure it has 🏷 X."""
    patched = 0
    out = []
    cursor = 0
    for cm in CALL_BLOCK.finditer(trace):
        call_end = cm.end()
        call_id = cm.group(2).strip('"')
        # find the FIRST result block after this call
        rm = RESULT_BLOCK.search(trace, call_end)
        if not rm:
            continue
        inner = rm.group("inner")
        # Does it already have 🏷 call_id? (any occurrence)
        if re.search(r'🏷\s*"?' + re.escape(call_id) + r'"?', inner):
            continue
        # Find the data line; inject tag right after its closing 」 or "
        data_match = re.search(r'(data\s*↦\s*(?:「[^」]*」|"[^"]*"))', inner)
        if not data_match:
            continue
        new_inner = inner[:data_match.end()] + f' 🏷 {call_id}' + inner[data_match.end():]
        # write everything up to result block, then patched result block, then continue
        out.append(trace[cursor:rm.start()])
        out.append(f"result {{{new_inner}}}")
        cursor = rm.end()
        patched += 1
    out.append(trace[cursor:])
    return ''.join(out), patched


def patch_trailing_garbage(trace: str) -> tuple[str, int]:
    """Strip lone `}` (or similar junk) trailing the final response."""
    last_close = trace.rfind('」')
    if last_close < 0:
        return trace, 0
    head = trace[:last_close + 1]
    tail = trace[last_close + 1:]
    # strip chat template tokens for inspection
    tail_clean = TaskValidator.CHAT_TEMPLATE_TOKEN.sub('', tail).strip()
    if tail_clean and not TaskValidator.TAIL_OK_PATTERN.fullmatch(tail_clean):
        # remove only ASCII junk like trailing `}`, keep <|im_end|>
        new_tail = re.sub(r'[\}\)]+', '', tail)
        return head + new_tail, 1
    return trace, 0


def patch_unclosed_response(trace: str) -> tuple[str, int]:
    """If trace has `response「` without matching `」`, append `」`."""
    last_resp = trace.rfind('response「')
    if last_resp < 0:
        return trace, 0
    last_close = trace.rfind('」')
    if last_close > last_resp:
        return trace, 0
    # Insert 」 before <|im_end|> if present, else at end
    end_match = re.search(r'<\|im_end\|>', trace[last_resp:])
    if end_match:
        ins = last_resp + end_match.start()
        return trace[:ins].rstrip() + '」\n' + trace[ins:], 1
    return trace.rstrip() + '」', 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    n = patched_tag = patched_tail = patched_close = dropped = kept = 0
    with open(args.input) as fin, open(args.output, "w") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            n += 1
            obj = json.loads(line)
            trace = obj["trace"]

            trace, c1 = patch_missing_result_tags(trace)
            patched_tag += c1
            trace, c2 = patch_trailing_garbage(trace)
            patched_tail += c2
            trace, c3 = patch_unclosed_response(trace)
            patched_close += c3

            r = validate_trace(trace)
            if r.valid:
                obj["trace"] = trace
                fout.write(json.dumps(obj) + "\n")
                kept += 1
            else:
                dropped += 1

    print(f"Input: {n}")
    print(f"  patches applied — missing tag: {patched_tag}, trailing junk: {patched_tail}, unclosed resp: {patched_close}")
    print(f"  kept: {kept}")
    print(f"  dropped (still invalid): {dropped}")
    print(f"Output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
