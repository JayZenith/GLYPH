#!/usr/bin/env python3
"""Render finalized_blogv3.md to a standalone, readable HTML article."""
from __future__ import annotations

from pathlib import Path

import markdown


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "finalized_blogv3.md"
TARGET = ROOT / "index.html"


CSS = r"""
:root {
  --bg: #e8edf3;
  --paper: #ffffff;
  --ink: #14171c;
  --muted: #596271;
  --line: #d7dde6;
  --soft: #f6f8fb;
  --code-bg: #0f1722;
  --code-ink: #f5f8fc;
  --link: #174ea6;
  --accent: #246a73;
  --accent-soft: #edf7f8;
  --warn-soft: #fff6e6;
  --shadow: rgba(17, 24, 39, 0.10);
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  line-height: 1.68;
}
a {
  color: var(--link);
  text-decoration-thickness: 1px;
  text-underline-offset: 3px;
}
.shell {
  max-width: 1140px;
  margin: 28px auto;
  background: var(--paper);
  border-radius: 14px;
  overflow: hidden;
  box-shadow: 0 0 0 1px rgba(17, 24, 39, 0.06), 0 32px 90px var(--shadow);
}
.top {
  padding: 70px 86px 40px;
  border-bottom: 1px solid var(--line);
  background:
    linear-gradient(180deg, rgba(255,255,255,0.96) 0%, rgba(248,250,252,0.98) 100%),
    radial-gradient(circle at 90% 10%, rgba(36,106,115,0.14), transparent 34%);
}
.kicker {
  margin: 0 0 14px;
  color: var(--accent);
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.top h1 {
  max-width: 940px;
  margin: 0;
  font-size: clamp(42px, 5.8vw, 72px);
  line-height: 1.02;
  letter-spacing: 0;
}
.article {
  padding: 46px 86px 84px;
}
.article > h1 { display: none; }
.article h2 {
  max-width: 880px;
  margin: 68px 0 22px;
  padding-top: 18px;
  border-top: 1px solid var(--line);
  font-size: 32px;
  line-height: 1.18;
  letter-spacing: 0;
}
.article h2:first-of-type {
  margin-top: 24px;
}
.article p,
.article ul,
.article ol {
  max-width: 830px;
  font-size: 18.5px;
}
.article p {
  margin: 18px 0;
}
.article strong {
  font-weight: 780;
}
.article code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
  font-size: 0.91em;
  background: #eef1f5;
  border: 1px solid #dde3eb;
  border-radius: 5px;
  padding: 0.08em 0.28em;
}
.article pre {
  max-width: 960px;
  margin: 24px 0;
  padding: 20px 22px;
  overflow-x: auto;
  color: var(--code-ink);
  background: var(--code-bg);
  border-radius: 10px;
  line-height: 1.55;
  font-size: 15.5px;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.07), 0 12px 30px rgba(15, 23, 34, 0.10);
}
.article pre code {
  background: transparent;
  border: 0;
  padding: 0;
  color: inherit;
  font-size: inherit;
}
.article blockquote {
  max-width: 900px;
  margin: 28px 0;
  padding: 18px 22px;
  border-left: 5px solid var(--accent);
  background: var(--accent-soft);
  border-radius: 0 8px 8px 0;
}
.article img {
  display: block;
  width: min(100%, 980px);
  height: auto;
  margin: 30px 0 12px;
  padding: 16px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 14px 36px rgba(17, 24, 39, 0.08);
}
.article table {
  width: min(100%, 960px);
  margin: 26px 0;
  border-collapse: collapse;
  font-size: 16px;
  border: 1px solid var(--line);
  border-radius: 10px;
  overflow: hidden;
  display: block;
}
.article th,
.article td {
  padding: 13px 15px;
  border-bottom: 1px solid var(--line);
  vertical-align: top;
  text-align: left;
}
.article th {
  color: #3d4652;
  background: #eef2f6;
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.article tbody tr:nth-child(even) {
  background: #fbfcfd;
}
.article tbody tr:last-child td {
  border-bottom: 0;
}
.article hr {
  max-width: 960px;
  border: 0;
  border-top: 1px solid var(--line);
  margin: 48px 0;
}
.footer {
  padding: 30px 86px 50px;
  border-top: 1px solid var(--line);
  color: var(--muted);
  background: #fafbfc;
  font-size: 15px;
}
@media (max-width: 760px) {
  .shell {
    margin: 0;
    border-radius: 0;
  }
  .top, .article, .footer {
    padding-left: 22px;
    padding-right: 22px;
  }
  .top {
    padding-top: 36px;
  }
  .top h1 {
    font-size: 40px;
  }
  .article p,
  .article ul,
  .article ol {
    font-size: 17px;
  }
  .article h2 {
    font-size: 26px;
  }
  .article pre {
    font-size: 14px;
  }
}
"""


def render() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    md = markdown.Markdown(extensions=["extra", "sane_lists"])
    body = md.convert(source)
    title = source.splitlines()[0].lstrip("# ").strip()

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <meta name="description" content="A postmortem on Glyph, a Rust tool-use agent experiment built around SFT and PRIME-RL RLVR.">
  <style>{CSS}</style>
</head>
<body>
  <div class="shell">
    <header class="top">
      <p class="kicker">Glyph postmortem</p>
      <h1>{title}</h1>
    </header>
    <main class="article">
{body}
    </main>
    <footer class="footer">
      Code and artifacts: <a href="https://github.com/JayZenith/glyph">github.com/JayZenith/glyph</a>.
    </footer>
  </div>
</body>
</html>
"""
    TARGET.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    render()
