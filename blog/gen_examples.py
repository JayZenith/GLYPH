"""Regenerates the Examples section of blog/index.html from the same trace
data as the portfolio's trace viewer (~/Desktop/portfolio/src/traces.json +
crateSources.js), so the two surfaces show identical real rollouts with the
same turn-card UI. Splices between EXAMPLES_START/EXAMPLES_END markers.
Rerun: python3 blog/gen_examples.py
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
        "Reads a config-merge crate, follows failed-test feedback, patches the "
        "merge precedence, confirms tests pass."
    ),
    "recovery": (
        "Fixes sorting first, then uses failed-test output to spot the missing "
        "shared-rank behavior and patch it."
    ),
    "long-recovery": (
        "A long rollout: recovers from bad edits via repeated test feedback, "
        "fixes trimming and signed-number parsing."
    ),
}

EXAMPLE_NOTES = {
    "clean-solve": (
        "Specification gaming: the patch passes the verifier (cargo_test 3/3) while "
        "flipping tls precedence — the opposite of the stated rule. No test covers "
        "conflicting tls values, so the verifier can't see it, and the FINAL doesn't "
        "disclose it. In this crate's own training group, 3 of 8 rollouts made the "
        "same flip — the reward reinforced gaming and correctness equally."
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


# Mirrors portfolio/src/MainPage.js rustTokenPattern.
RUST_TOKEN_RE = re.compile(
    r'("(?:\\.|[^"\\])*")'
    r"|\b(pub|struct|fn|let|mut|mod|use|super|impl|for|in|if|else|match|return|"
    r"true|false|None|Some|Option|Vec|String|usize|u32|u16|i32|bool|str)\b"
    r"|(\b\d+\b)"
    r"|(#\[[^\]]+\])"
)

# Mirrors portfolio/src/MainPage.js traceTokenPattern.
TRACE_TOKEN_RE = re.compile(
    r"\b(CALL|RESULT|FINAL|status:|success|failed|read_file|apply_patch|"
    r"cargo_test|stdout:|stderr:)\b"
)


def highlight_rust_line(line: str) -> str:
    out = []
    last = 0
    for m in RUST_TOKEN_RE.finditer(line):
        if m.start() > last:
            out.append(esc(line[last:m.start()]))
        string, keyword, number, attr = m.groups()
        cls = "rust-string" if string else "rust-keyword" if keyword else \
            "rust-number" if number else "rust-attr"
        out.append(f'<span class="{cls}">{esc(m.group(0))}</span>')
        last = m.end()
    out.append(esc(line[last:]))
    return "".join(out)


def render_rust(code: str) -> str:
    lines = []
    for i, line in enumerate(code.split("\n"), 1):
        lines.append(
            f'<span class="rust-line"><span class="rust-line-number">{i}</span>'
            f'<span class="rust-line-code">{highlight_rust_line(line)}</span></span>'
        )
    return "\n".join(lines)


def highlight_trace_tokens(content: str) -> str:
    out = []
    last = 0
    for m in TRACE_TOKEN_RE.finditer(content):
        if m.start() > last:
            out.append(esc(content[last:m.start()]))
        tok = m.group(0)
        if tok == "CALL":
            cls = "trace-call-token"
        elif tok == "RESULT":
            cls = "trace-result-token"
        elif tok == "FINAL":
            cls = "trace-final-token"
        elif tok == "success":
            cls = "trace-success-token"
        elif tok == "failed":
            cls = "trace-failed-token"
        elif tok.endswith(":"):
            cls = "trace-label-token"
        else:
            cls = "trace-tool-token"
        out.append(f'<span class="{cls}">{esc(tok)}</span>')
        last = m.end()
    out.append(esc(content[last:]))
    return "".join(out)


def render_turn(role: str, content: str) -> str:
    content = content.strip()
    body_cls = "turn-body"
    if content.startswith("FINAL:"):
        body_cls += " turn-final"
    elif content.startswith("CALL"):
        body_cls += " turn-call"
    elif role == "tool":
        body_cls += " turn-result"
    return (
        f'<div class="turn turn-{role}"><div class="turn-role">{role}</div>'
        f'<pre class="{body_cls}">{highlight_trace_tokens(content)}</pre></div>'
    )


def render_example(trace_id: str, trace: dict, crate_src: str | None, active: bool) -> str:
    desc = esc(EXAMPLE_DESCRIPTIONS[trace_id])
    note = EXAMPLE_NOTES.get(trace_id)
    note_html = f'\n      <p class="trace-note">{esc(note)}</p>' if note else ""
    src_html = ""
    if crate_src:
        src_html = f"""
    <div class="crate-source">
      <div class="crate-source-header"><strong>crate source</strong><span>src/lib.rs</span></div>
      <pre class="rust-code">{render_rust(crate_src.strip())}</pre>
    </div>"""
    turns = [render_turn("system", SYSTEM_PROMPT), render_turn("user", trace["task"])]
    turns += [render_turn(t["role"], t["content"]) for t in trace["turns"]]
    turns_html = "\n      ".join(turns)
    hidden = "" if active else " hidden"
    return f"""  <div class="example-panel" id="example-{trace_id}"{hidden}>
  <div class="trace-panel">
    <div class="trace-summary">
      <div>
        <span class="trace-label">{esc(trace["label"])}</span>
        <a class="model-label" href="https://huggingface.co/{trace["model"]}" target="_blank" rel="noreferrer">{esc(trace["model"])}</a>
        <p>{desc}</p>{note_html}
      </div>
      <div class="trace-metadata"><span>RL reward {trace["reward"]}</span><span>{len(trace["turns"])} trace turns</span></div>
    </div>{src_html}
    <div class="actions-panel">
      <div class="actions-header"><strong>full trace</strong><span>system, user, assistant, tool</span></div>
      <div class="trace-turns">
      {turns_html}
      </div>
    </div>
  </div>
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
    if "<!-- EXAMPLES_START -->" not in text:
        raise SystemExit("EXAMPLES_START/EXAMPLES_END markers not found in blog/index.html")
    if new_text == text:
        print("examples section already up to date")
        return
    index.write_text(new_text)
    print(f"wrote {index}")


if __name__ == "__main__":
    main()
