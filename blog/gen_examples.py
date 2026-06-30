"""Regenerates the Examples section of blog/index.html from the same trace
data as the portfolio's trace viewer (~/Desktop/portfolio/src/traces.json +
crateSources.js), so the two surfaces show identical real rollouts. Splices
the generated HTML between the EXAMPLES_START/EXAMPLES_END markers in
index.html. Rerun: python3 blog/gen_examples.py
"""
from __future__ import annotations

import html
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORTFOLIO = ROOT.parent / "portfolio"

SYSTEM_PROMPT = "You are a Rust coding agent. Use tools when needed. After FINAL, stop immediately."

EXAMPLE_DESCRIPTIONS = {
    "clean-solve": (
        "An RLVR-trained agent reads a small Rust config-merge crate, follows "
        "failed-test feedback, patches the merge precedence, and confirms the tests pass."
    ),
    "recovery": (
        "An RLVR-trained agent fixes sorting first, then uses failed-test output to "
        "notice the missing shared-rank behavior and patch the ranking logic."
    ),
    "long-recovery": (
        "A longer RLVR rollout where the agent recovers from bad edits and uses "
        "repeated test feedback to fix trimming and signed-number parsing."
    ),
}

EXAMPLE_NOTES = {
    "clean-solve": (
        "Verifier gap, not a clean win: the patch also flips tls from direct-first to "
        "profile-first, the opposite of the stated precedence rule. No test sets "
        'conflicting direct/profile tls values, so cargo_test still passes 3/3, and the '
        'FINAL message ("tls, which was already correct") is true of the original code but '
        "glosses over the regression its own edit just introduced. A strict cargo-pass + "
        "clean-FINAL reward does not catch this — the test suite would need to."
    ),
}

ORDER = ["clean-solve", "recovery", "long-recovery"]


def load_traces():
    traces = json.loads((PORTFOLIO / "src/traces.json").read_text())
    return {t["id"]: t for t in traces}


def load_crate_sources():
    out = subprocess.run(
        ["node", "-e",
         "const c=require('./src/crateSources.js').default||require('./src/crateSources.js');"
         "process.stdout.write(JSON.stringify(c))"],
        cwd=PORTFOLIO, capture_output=True, text=True, check=True,
    )
    return json.loads(out.stdout)


def esc(s: str) -> str:
    return html.escape(s, quote=False)


def render_block(content: str, role: str) -> str:
    text = esc(content)
    if role == "assistant" and content.lstrip().startswith("CALL"):
        return f'<span class="call">{text}</span>'
    if role == "assistant" and content.lstrip().startswith("FINAL:"):
        return f'<span class="final">{text}</span>'
    if role == "tool":
        return f'<span class="result">{text}</span>'
    return text


def render_trace(trace: dict) -> str:
    parts = [f'<span class="role">SYSTEM</span> {esc(SYSTEM_PROMPT)}']
    parts.append(f'<span class="role">USER</span> {esc(trace["task"])}')
    for turn in trace["turns"]:
        label = turn["role"].upper()
        parts.append(f'<span class="role">{label}</span> {render_block(turn["content"].strip(), turn["role"])}')
    return "\n\n".join(parts)


def render_example(trace_id: str, trace: dict, crate_src: str | None) -> str:
    label = esc(trace["label"])
    model = trace["model"]
    desc = esc(EXAMPLE_DESCRIPTIONS[trace_id])
    note = EXAMPLE_NOTES.get(trace_id)
    note_html = (
        f'\n  <div class="panel note"><p>{esc(note)}</p></div>' if note else ""
    )
    src_html = ""
    if crate_src:
        src_html = (
            f'\n  <div class="panel"><pre>{esc(crate_src.strip())}</pre></div>'
        )
    trace_html = render_trace(trace)
    return f"""<h3>{label}</h3>
  <p class="meta">{model} &middot; RL reward {trace["reward"]} &middot; {len(trace["turns"])} trace turns</p>
  <p>{desc}</p>{note_html}{src_html}
  <div class="panel trace scroll"><pre>{trace_html}</pre></div>
"""


def main():
    traces = load_traces()
    crate_sources = load_crate_sources()
    sections = [render_example(tid, traces[tid], crate_sources.get(tid)) for tid in ORDER]
    body = "\n".join(sections)

    index = ROOT / "blog/index.html"
    text = index.read_text()
    new_text = re.sub(
        r"<!-- EXAMPLES_START -->.*?<!-- EXAMPLES_END -->",
        f"<!-- EXAMPLES_START -->\n  <h2>Examples: real rollouts</h2>\n{body}\n  <!-- EXAMPLES_END -->",
        text,
        flags=re.DOTALL,
    )
    if new_text == text:
        raise SystemExit("EXAMPLES_START/EXAMPLES_END markers not found in blog/index.html")
    index.write_text(new_text)
    print(f"wrote {index}")


if __name__ == "__main__":
    main()
