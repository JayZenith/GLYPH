"""Regenerates blog/training_curves.svg: per-step reward and zero-advantage
filter rate for the dense vs compiler-aware RLVR runs, parsed straight from
the pulled orchestrator logs in glyph_results/. Hand-rolled SVG to match the
blog's CSS theme. Rerun: python3 blog/gen_training_curves.py
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
R = ROOT / "glyph_results"

STEP_RE = re.compile(r"Step (\d+) \| Time: [\d.]+s \| Reward: (-?[\d.]+)")
FILTER_RE = re.compile(r"Detected (\d+)/96 rollouts")

RUNS = [
    ("Dense reward", R / "RLVR_VFINAL_STEP10/logs/orchestrator.log", "#3ddc84"),
    ("Compiler-aware", R / "RLVR_VFINAL2_STEP10/arm_b.log", "#ffce6a"),
]


def parse(path: Path):
    text = path.read_text()
    rewards = [(int(s), float(r)) for s, r in STEP_RE.findall(text)]
    kept = [int(k) for k in FILTER_RE.findall(text)]  # rollouts retained after filtering, per step
    return rewards, kept


def line_path(points, x_of, y_of):
    return "M " + " L ".join(f"{x_of(x):.1f},{y_of(y):.1f}" for x, y in points)


W, H = 640, 460
PAD_L, PAD_R, PAD_T, PAD_B = 50, 16, 26, 34
GAP = 38
PLOT_W = W - PAD_L - PAD_R
PANEL_H = (H - PAD_T - PAD_B - GAP) / 2

MAX_STEP = 11

svg = [
    f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
    f'font-family="ui-monospace, SFMono-Regular, Menlo, monospace">',
    f'<rect x="0" y="0" width="{W}" height="{H}" fill="#0c1712" rx="8"/>',
]


def x_of(step):
    return PAD_L + PLOT_W * (step / MAX_STEP)


# --- Panel 1: reward per step ---
p1_top = PAD_T
r_min, r_max = -4, 10


def y1_of(r):
    frac = (r - r_min) / (r_max - r_min)
    return p1_top + PANEL_H * (1 - frac)


svg.append(f'<text x="{PAD_L}" y="{p1_top - 8:.1f}" font-size="11" fill="#82998d">'
           f'mean batch reward per orchestrator step</text>')
for gv in (r_min, 0, r_max):
    y = y1_of(gv)
    svg.append(f'<line x1="{PAD_L}" y1="{y:.1f}" x2="{W - PAD_R}" y2="{y:.1f}" '
               f'stroke="#1c2b24" stroke-width="1"/>')
    svg.append(f'<text x="{PAD_L - 6}" y="{y + 3:.1f}" text-anchor="end" '
               f'font-size="9.5" fill="#4d6358">{gv:g}</text>')

for name, path, color in RUNS:
    rewards, _ = parse(path)
    rewards = [(s, r) for s, r in rewards if s <= MAX_STEP]
    d = line_path(rewards, x_of, y1_of)
    svg.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2"/>')
    for s, r in rewards:
        svg.append(f'<circle cx="{x_of(s):.1f}" cy="{y1_of(r):.1f}" r="2.4" fill="{color}"/>')

# --- Panel 2: rollouts retained after zero-advantage filtering ---
p2_top = PAD_T + PANEL_H + GAP


def y2_of(kept_frac):
    return p2_top + PANEL_H * (1 - kept_frac)


svg.append(f'<text x="{PAD_L}" y="{p2_top - 8:.1f}" font-size="11" fill="#82998d">'
           f'rollouts retained after zero-advantage filtering (of 96)</text>')
for gv in (0, 50, 100):
    y = y2_of(gv / 100)
    svg.append(f'<line x1="{PAD_L}" y1="{y:.1f}" x2="{W - PAD_R}" y2="{y:.1f}" '
               f'stroke="#1c2b24" stroke-width="1"/>')
    svg.append(f'<text x="{PAD_L - 6}" y="{y + 3:.1f}" text-anchor="end" '
               f'font-size="9.5" fill="#4d6358">{gv}%</text>')

for name, path, color in RUNS:
    _, kept = parse(path)
    kept = kept[: MAX_STEP + 1]
    pts = [(i, k / 96) for i, k in enumerate(kept)]
    d = line_path(pts, x_of, y2_of)
    svg.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2"/>')
    for s, k in pts:
        svg.append(f'<circle cx="{x_of(s):.1f}" cy="{y2_of(k):.1f}" r="2.4" fill="{color}"/>')

# x-axis labels (shared)
for s in range(0, MAX_STEP + 1):
    svg.append(f'<text x="{x_of(s):.1f}" y="{H - PAD_B + 14:.1f}" text-anchor="middle" '
               f'font-size="9" fill="#4d6358">{s}</text>')
svg.append(f'<text x="{W / 2:.1f}" y="{H - 6:.1f}" text-anchor="middle" '
           f'font-size="10" fill="#82998d">orchestrator step</text>')

# legend
lx = W - PAD_R - 150
ly = PAD_T + 4
for i, (name, _, color) in enumerate(RUNS):
    yy = ly + i * 14
    svg.append(f'<rect x="{lx}" y="{yy - 8}" width="10" height="10" fill="{color}"/>')
    svg.append(f'<text x="{lx + 14}" y="{yy + 1}" font-size="10" fill="#bcd6c5">{name}</text>')

svg.append("</svg>")

out = ROOT / "blog" / "training_curves.svg"
out.write_text("\n".join(svg))
print(f"wrote {out}")
