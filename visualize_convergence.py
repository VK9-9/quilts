"""Visualize active learning convergence over 5 rounds.

Produces: quilts/convergence.png
"""
import json
import sys
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from collections import defaultdict

ROUND_SLICES = [
    ("R1", slice(0, 200)),
    ("R2", slice(200, 507)),
    ("R3", slice(507, 783)),
    ("R4", slice(783, 1157)),
    ("R5", slice(1157, None)),
]
OVERALL_RATES = [21, 20, 28, 31, 38]

DROPPED = {
    "palette": {"berry patch", "cedar and moss", "dusty rose", "forest floor",
                "jewel box", "prairie", "slate and sage", "tidal pool",
                "frost", "ember", "mosaic", "spring garden", "patchwork classic",
                "midnight garden", "sunset"},
    "symmetry": {"flower", "emergent"},
}


def load_ratings(ratings_path):
    with open(ratings_path, encoding="utf-8") as f:
        return json.load(f)


def overall_like_rates(ratings, param):
    buckets = defaultdict(lambda: [0, 0])
    for rec in ratings:
        val = rec["params"].get(param)
        if val is None:
            continue
        buckets[val][1] += 1
        if rec["liked"]:
            buckets[val][0] += 1
    return {k: v[0] / v[1] for k, v in buckets.items() if v[1] >= 10}


def make_figure(ratings):
    pal_rates = overall_like_rates(ratings, "palette")
    sym_rates = overall_like_rates(ratings, "symmetry")

    def sorted_bars(rates, dropped):
        survivors = sorted([(k, v) for k, v in rates.items() if k not in dropped],
                           key=lambda x: x[1])
        cut = sorted([(k, v) for k, v in rates.items() if k in dropped],
                     key=lambda x: x[1])
        return survivors, cut

    pal_surv, pal_cut = sorted_bars(pal_rates, DROPPED["palette"])
    sym_surv, sym_cut = sorted_bars(sym_rates, DROPPED["symmetry"])

    fig, axes = plt.subplots(1, 3, figsize=(14, 6),
                             gridspec_kw={"width_ratios": [1, 2.5, 1], "wspace": 0.4})

    # --- like rate trend ---
    ax = axes[0]
    xs = range(1, 6)
    ax.plot(xs, OVERALL_RATES, "o-", color="steelblue", linewidth=2.5, markersize=8)
    for x, y in zip(xs, OVERALL_RATES):
        ax.text(x, y + 1.5, f"{y}%", ha="center", fontsize=11)
    ax.set_xticks(list(xs))
    ax.set_xticklabels([r for r, _ in ROUND_SLICES])
    ax.set_ylabel("Like rate %")
    ax.set_ylim(0, 50)
    ax.set_title("Like rate over rounds", fontweight="bold")
    ax.yaxis.grid(True, alpha=0.35)
    ax.set_axisbelow(True)

    # --- palette bars ---
    ax = axes[1]
    all_pals = pal_surv + pal_cut
    labels = [k for k, _ in all_pals]
    vals = [v for _, v in all_pals]
    colors = ["steelblue"] * len(pal_surv) + ["#cc4444"] * len(pal_cut)
    y = range(len(all_pals))
    ax.barh(list(y), vals, color=colors, height=0.7)
    ax.axvline(np.mean(OVERALL_RATES) / 100, color="gray", linestyle="--",
               linewidth=1, label="avg like rate")
    for i, v in enumerate(vals):
        ax.text(v + 0.005, i, f"{int(round(v*100))}%", va="center", fontsize=8.5)
    ax.set_yticks(list(y))
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlim(0, 0.75)
    ax.set_xlabel("Like rate")
    ax.set_title("Palettes  (red = dropped)", fontweight="bold")
    ax.xaxis.grid(True, alpha=0.35)
    ax.set_axisbelow(True)

    # --- symmetry bars ---
    ax = axes[2]
    all_syms = sym_surv + sym_cut
    slabels = [k for k, _ in all_syms]
    svals = [v for _, v in all_syms]
    scolors = ["steelblue"] * len(sym_surv) + ["#cc4444"] * len(sym_cut)
    sy = range(len(all_syms))
    ax.barh(list(sy), svals, color=scolors, height=0.7)
    ax.axvline(np.mean(OVERALL_RATES) / 100, color="gray", linestyle="--", linewidth=1)
    for i, v in enumerate(svals):
        ax.text(v + 0.005, i, f"{int(round(v*100))}%", va="center", fontsize=9)
    ax.set_yticks(list(sy))
    ax.set_yticklabels(slabels, fontsize=9)
    ax.set_xlim(0, 0.75)
    ax.set_xlabel("Like rate")
    ax.set_title("Symmetry  (red = dropped)", fontweight="bold")
    ax.xaxis.grid(True, alpha=0.35)
    ax.set_axisbelow(True)

    fig.suptitle("Active learning: 1538 quilts rated, 5 rounds", fontsize=13)

    out = "quilts/convergence.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    print(f"Saved {out}")
    plt.close()


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "quilts/ratings.json"
    if not os.path.exists(path):
        path = "ratings.json"
    make_figure(load_ratings(path))
