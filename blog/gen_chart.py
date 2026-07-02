"""Regenerates blog/valid8_chart.svg from the pulled eval JSONs in glyph_results/.

Hand-rolled SVG (no plotting deps) so colors match the blog's CSS variables
exactly. Rerun after any new eval seed lands: python3 blog/gen_chart.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
R = ROOT / "glyph_results"


def valid_at_8(path: Path) -> int:
    rows = json.loads(path.read_text())
    return sum(1 for r in rows if r.get("valid_trace_solves", 0) > 0)


MODELS = [
    ("SFT base", [
        R / "SFT_HALF_A_V8/evals/passk8_heldout150.json",
        R / "SFT_HALF_A_V8/evals/seeds/sft_seed1.json",
        R / "SFT_HALF_A_V8/evals/seeds/sft_seedB.json",
    ], "#5fd0db"),  # cyan
    ("Sparse reward", [
        R / "RLVR_POOL_B_V8_STEP10/passk8_heldout150_run1.json",
        R / "RLVR_POOL_B_V8_STEP10/passk8_heldout150_run2.json",
        R / "RLVR_POOL_B_V8_STEP10/passk8_heldout150_run3.json",
    ], "#b48cff"),  # violet
    ("Dense reward", [
        R / "RLVR_VFINAL_STEP10/evals/passk8_heldout150.json",
        R / "RLVR_VFINAL_STEP10/evals/seeds/step10_seedB.json",
        R / "RLVR_VFINAL_STEP10/evals/seeds/step10_seedC.json",
    ], "#3ddc84"),  # green
    ("Compiler-aware", [
        R / "RLVR_VFINAL2_STEP10/evals/passk8_heldout150.json",
        R / "RLVR_VFINAL2_STEP10/evals/seeds/step10_seedB.json",
        R / "RLVR_VFINAL2_STEP10/evals/seeds/step10_seedC.json",
    ], "#ffce6a"),  # amber

]

W, H = 640, 340
PAD_L, PAD_R, PAD_T, PAD_B = 50, 20, 28, 46
PLOT_W, PLOT_H = W - PAD_L - PAD_R, H - PAD_T - PAD_B
Y_MIN, Y_MAX = 85, 105  # crop to where the data lives; axis says so explicitly
GROUP_GAP = 36
BAR_GAP = 8

groups = []
for name, paths, color in MODELS:
    vals = [valid_at_8(p) for p in paths]
    groups.append((name, vals, color))

n_groups = len(groups)
group_w = (PLOT_W - GROUP_GAP * (n_groups - 1)) / n_groups
bar_w = (group_w - BAR_GAP * 2) / 3


def y_px(v: float) -> float:
    frac = (v - Y_MIN) / (Y_MAX - Y_MIN)
    return PAD_T + PLOT_H * (1 - frac)


svg_parts = [
    f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
    f'font-family="ui-monospace, SFMono-Regular, Menlo, monospace">',
    f'<rect x="0" y="0" width="{W}" height="{H}" fill="#0c1712" rx="8"/>',
]

# gridlines + y labels
for gv in range(Y_MIN, Y_MAX + 1, 5):
    y = y_px(gv)
    svg_parts.append(
        f'<line x1="{PAD_L}" y1="{y:.1f}" x2="{W - PAD_R}" y2="{y:.1f}" '
        f'stroke="#1c2b24" stroke-width="1"/>'
    )
    svg_parts.append(
        f'<text x="{PAD_L - 8}" y="{y + 4:.1f}" text-anchor="end" '
        f'font-size="10" fill="#82998d">{gv}</text>'
    )

# bars
for gi, (name, vals, color) in enumerate(groups):
    gx0 = PAD_L + gi * (group_w + GROUP_GAP)
    for si, v in enumerate(vals):
        bx = gx0 + si * (bar_w + BAR_GAP)
        by = y_px(v)
        bh = PAD_T + PLOT_H - by
        svg_parts.append(
            f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" '
            f'fill="{color}" opacity="0.9" rx="2"/>'
        )
        svg_parts.append(
            f'<text x="{bx + bar_w / 2:.1f}" y="{by - 6:.1f}" text-anchor="middle" '
            f'font-size="10.5" fill="#e7f5ea">{v}</text>'
        )
    mean = sum(vals) / len(vals)
    svg_parts.append(
        f'<line x1="{gx0:.1f}" y1="{y_px(mean):.1f}" x2="{gx0 + group_w:.1f}" '
        f'y2="{y_px(mean):.1f}" stroke="#fff" stroke-width="1.4" stroke-dasharray="3,2"/>'
    )
    svg_parts.append(
        f'<text x="{gx0 + group_w / 2:.1f}" y="{H - PAD_B + 18:.1f}" text-anchor="middle" '
        f'font-size="11" fill="#bcd6c5">{name}</text>'
    )
    svg_parts.append(
        f'<text x="{gx0 + group_w / 2:.1f}" y="{H - PAD_B + 32:.1f}" text-anchor="middle" '
        f'font-size="9.5" fill="#4d6358">mean {mean:.1f}</text>'
    )

svg_parts.append(
    f'<text x="{PAD_L}" y="16" font-size="11" fill="#82998d">'
    f'valid@8 / 150 (pass@8, T=0.8, 3 unseeded runs each; dashed = mean)</text>'
)
svg_parts.append("</svg>")

out = ROOT / "blog" / "valid8_chart.svg"
out.write_text("\n".join(svg_parts))
print(f"wrote {out}")
for name, vals, _ in groups:
    print(f"  {name}: {vals} mean={sum(vals)/3:.1f}")
