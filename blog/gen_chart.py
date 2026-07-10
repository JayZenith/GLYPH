"""Regenerates blog/valid8_chart.svg from the pulled eval JSONs in glyph_results/.

Solid bars = trace-retained evaluations (full per-rollout traces saved,
auditable). Faded bars = aggregate-only repetitions (per-prompt counts only,
raw traces not retained — excluded from headline claims).
Rerun: python3 blog/gen_chart.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
R = ROOT / "glyph_results"


def valid_at_8(path: Path) -> int:
    rows = json.loads(path.read_text())
    return sum(1 for r in rows if r.get("valid_trace_solves", 0) > 0)


# (label, [(path, trace_retained)], color)
MODELS = [
    ("SFT base", [
        (R / "SFT_HALF_A_V8/evals/passk8_heldout150.json", True),
        (R / "SFT_HALF_A_V8/evals/seeds/sft_seed1.json", False),
        (R / "SFT_HALF_A_V8/evals/seeds/sft_seedB.json", False),
    ], "#5fd0db"),
    ("Sparse reward", [
        (R / "RLVR_POOL_B_V8_STEP10/passk8_heldout150_run1.json", True),
        (R / "RLVR_POOL_B_V8_STEP10/passk8_heldout150_run2.json", True),
        (R / "RLVR_POOL_B_V8_STEP10/passk8_heldout150_run3.json", True),
    ], "#b48cff"),
    ("Dense reward", [
        (R / "RLVR_VFINAL_STEP10/evals/passk8_heldout150.json", True),
        (R / "RLVR_VFINAL_STEP10/evals/seeds/step10_seedB.json", False),
        (R / "RLVR_VFINAL_STEP10/evals/seeds/step10_seedC.json", False),
    ], "#3ddc84"),
    ("Compiler-aware", [
        (R / "RLVR_VFINAL2_STEP10/evals/passk8_heldout150.json", True),
        (R / "RLVR_VFINAL2_STEP10/evals/seeds/step10_seedB.json", True),
        (R / "RLVR_VFINAL2_STEP10/evals/seeds/step10_seedC.json", True),
    ], "#ffce6a"),
]

W, H = 640, 340
PAD_L, PAD_R, PAD_T, PAD_B = 50, 20, 40, 46
PLOT_W, PLOT_H = W - PAD_L - PAD_R, H - PAD_T - PAD_B
Y_MIN, Y_MAX = 85, 105  # crop to where the data lives; axis says so explicitly
GROUP_GAP = 36
BAR_GAP = 8

groups = []
for name, specs, color in MODELS:
    vals = [(valid_at_8(p), retained) for p, retained in specs]
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
    f'<rect x="0" y="0" width="{W}" height="{H}" fill="#0a0a0c" rx="8"/>',
]

for gv in range(Y_MIN, Y_MAX + 1, 5):
    y = y_px(gv)
    svg_parts.append(
        f'<line x1="{PAD_L}" y1="{y:.1f}" x2="{W - PAD_R}" y2="{y:.1f}" '
        f'stroke="#1e1f24" stroke-width="1"/>'
    )
    svg_parts.append(
        f'<text x="{PAD_L - 8}" y="{y + 4:.1f}" text-anchor="end" '
        f'font-size="10" fill="#8b9198">{gv}</text>'
    )

for gi, (name, vals, color) in enumerate(groups):
    gx0 = PAD_L + gi * (group_w + GROUP_GAP)
    for si, (v, retained) in enumerate(vals):
        bx = gx0 + si * (bar_w + BAR_GAP)
        by = y_px(v)
        bh = PAD_T + PLOT_H - by
        opacity = "0.9" if retained else "0.28"
        dash = "" if retained else ' stroke="#8b9198" stroke-width="1" stroke-dasharray="3,2"'
        svg_parts.append(
            f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" '
            f'fill="{color}" opacity="{opacity}" rx="2"{dash}/>'
        )
        svg_parts.append(
            f'<text x="{bx + bar_w / 2:.1f}" y="{by - 6:.1f}" text-anchor="middle" '
            f'font-size="10.5" fill="{"#f2f3f5" if retained else "#8b9198"}">{v}</text>'
        )
    svg_parts.append(
        f'<text x="{gx0 + group_w / 2:.1f}" y="{H - PAD_B + 18:.1f}" text-anchor="middle" '
        f'font-size="11" fill="#c6cad0">{name}</text>'
    )

svg_parts.append(
    f'<text x="{PAD_L}" y="16" font-size="11" fill="#8b9198">'
    f'valid@8 / 150 (pass@8, T=0.8, no sampling seed)</text>'
)
svg_parts.append(
    f'<text x="{PAD_L}" y="30" font-size="10" fill="#5a6066">'
    f'solid = trace-retained (auditable) &#183; faded/dashed = aggregate-only, no saved traces</text>'
)
svg_parts.append("</svg>")

out = ROOT / "blog" / "valid8_chart.svg"
out.write_text("\n".join(svg_parts))
print(f"wrote {out}")
for name, vals, _ in groups:
    print(f"  {name}: {vals}")
