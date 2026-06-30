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
        "Specification gaming, not a clean win: the patch satisfies the verifier "
        "(cargo_test, 3/3) while violating the user's actual spec — it flips tls from "
        "direct-first to profile-first, the opposite of the stated 'direct values take "
        "precedence' rule. No test sets conflicting direct/profile tls values, so the "
        'verifier can\'t see the violation, and the FINAL message ("tls, which was already '
        'correct") doesn\'t disclose it. One observed instance from reading this trace, not '
        "a measured systemic exploit — but it's exactly the proxy-vs-true-objective gap "
        "verifiable reward is supposed to close."
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


def render_example(trace_id: str, trace: dict, crate_src: str | None, active: bool) -> str:
    label = esc(trace["label"])
    model = trace["model"]
    desc = esc(EXAMPLE_DESCRIPTIONS[trace_id])
    note = EXAMPLE_NOTES.get(trace_id)
    note_html = (
        f'\n    <div class="panel note"><p>{esc(note)}</p></div>' if note else ""
    )
    src_html = ""
    if crate_src:
        src_html = (
            f'\n    <div class="panel"><pre>{esc(crate_src.strip())}</pre></div>'
        )
    trace_html = render_trace(trace)
    hidden = "" if active else " hidden"
    return f"""  <div class="example-panel" id="example-{trace_id}"{hidden}>
    <p class="meta">{model} &middot; RL reward {trace["reward"]} &middot; {len(trace["turns"])} trace turns</p>
    <p>{desc}</p>{note_html}{src_html}
    <div class="panel trace scroll"><pre>{trace_html}</pre></div>
  </div>
"""


def render_tabs(traces: dict) -> str:
    buttons = []
    for i, tid in enumerate(ORDER):
        cls = "example-tab active" if i == 0 else "example-tab"
        buttons.append(
            f'<button class="{cls}" data-target="example-{tid}" '
            f'onclick="showExample(this)">{esc(tid)}</button>'
        )
    return '  <div class="example-tabs">' + "".join(buttons) + "</div>\n"


def main():
    traces = load_traces()
    crate_sources = load_crate_sources()
    tabs = render_tabs(traces)
    sections = [
        render_example(tid, traces[tid], crate_sources.get(tid), active=(i == 0))
        for i, tid in enumerate(ORDER)
    ]
    script = """  <script>
    function showExample(btn) {
      var target = btn.getAttribute('data-target');
      document.querySelectorAll('.example-panel').forEach(function (el) {
        el.hidden = el.id !== target;
      });
      document.querySelectorAll('.example-tab').forEach(function (el) {
        el.classList.toggle('active', el === btn);
      });
    }
  </script>
"""
    body = tabs + "\n".join(sections) + script

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
