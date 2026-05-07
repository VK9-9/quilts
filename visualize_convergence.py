"""Visualize active learning convergence over rounds.

Produces: quilts/convergence.png

Round boundaries (cumulative record counts):
  R1:  0 – 199    (200 ratings)
  R2:  200 – 506  (307 ratings)
  R3:  507 – 782  (276 ratings)
  R4:  783 – 1156 (374 ratings)
  R5:  1157 – 1537 (381 ratings)
  R6:  1538 – 1913 (376 ratings)
  R7:  1914 –      (in progress)
"""
import json
import sys
import os
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # pylint: disable=wrong-import-position

ROUND_SLICES = [
    ("R1", slice(0, 200)),
    ("R2", slice(200, 507)),
    ("R3", slice(507, 783)),
    ("R4", slice(783, 1157)),
    ("R5", slice(1157, 1538)),
    ("R6", slice(1538, 1914)),
    ("R7", slice(1914, None)),
]
def compute_round_rates(ratings):
    """Return list of like-rate percentages (int) for each round slice."""
    rates = []
    for _, sl in ROUND_SLICES:
        chunk = ratings[sl]
        if not chunk:
            continue
        rates.append(round(100 * sum(1 for r in chunk if r["liked"]) / len(chunk)))
    return rates

DROPPED = {
    "palette": {"berry patch", "cedar and moss", "dusty rose", "forest floor",
                "jewel box", "prairie", "slate and sage", "tidal pool",
                "frost", "ember", "mosaic", "spring garden", "patchwork classic",
                "midnight garden", "sunset"},
    "symmetry": {"flower", "emergent"},
}


def load_ratings(ratings_path):
    """Load ratings JSON from disk."""
    with open(ratings_path, encoding="utf-8") as f:
        return json.load(f)


def overall_like_rates(ratings, param):
    """Return {value: like_rate} for a given param across all ratings."""
    buckets = defaultdict(lambda: [0, 0])
    for rec in ratings:
        val = rec["params"].get(param)
        if val is None:
            continue
        buckets[val][1] += 1
        if rec["liked"]:
            buckets[val][0] += 1
    return {k: v[0] / v[1] for k, v in buckets.items() if v[1] >= 10}


def _sorted_bars(rates, dropped):
    """Split rates into (survivors, cut) sorted by like rate."""
    survivors = sorted([(k, v) for k, v in rates.items() if k not in dropped],
                       key=lambda x: x[1])
    cut = sorted([(k, v) for k, v in rates.items() if k in dropped],
                 key=lambda x: x[1])
    return survivors, cut


def _plot_trend(ax, rates):
    """Draw the like-rate-over-rounds line chart."""
    xs = range(1, len(rates) + 1)
    ax.plot(list(xs), rates, "o-", color="steelblue", linewidth=2.5, markersize=8)
    for x, y in zip(xs, rates):
        ax.text(x, y + 1.5, f"{y}%", ha="center", fontsize=11)
    ax.set_xticks(list(xs))
    ax.set_xticklabels([r for r, _ in ROUND_SLICES[:len(rates)]])
    ax.set_ylabel("Like rate %")
    ax.set_ylim(0, 50)
    ax.set_title("Like rate over rounds", fontweight="bold")
    ax.yaxis.grid(True, alpha=0.35)
    ax.set_axisbelow(True)


def _plot_bars(ax, survivors, cut, title, overall_rate, fontsize=9):  # pylint: disable=too-many-arguments,too-many-positional-arguments
    """Draw a horizontal bar chart of like rates, survivors blue, cut items red."""
    items = survivors + cut
    labels = [k for k, _ in items]
    vals = [v for _, v in items]
    colors = ["steelblue"] * len(survivors) + ["#cc4444"] * len(cut)
    ys = range(len(items))
    ax.barh(list(ys), vals, color=colors, height=0.7)
    ax.axvline(overall_rate / 100, color="gray", linestyle="--", linewidth=1)
    for i, v in enumerate(vals):
        ax.text(v + 0.005, i, f"{int(round(v*100))}%", va="center", fontsize=fontsize)
    ax.set_yticks(list(ys))
    ax.set_yticklabels(labels, fontsize=fontsize)
    ax.set_xlim(0, 0.75)
    ax.set_xlabel("Like rate")
    ax.set_title(title, fontweight="bold")
    ax.xaxis.grid(True, alpha=0.35)
    ax.set_axisbelow(True)


def make_figure(ratings):
    """Render convergence chart and save to quilts/convergence.png."""
    rates = compute_round_rates(ratings)
    pal_surv, pal_cut = _sorted_bars(
        overall_like_rates(ratings, "palette"), DROPPED["palette"])
    sym_surv, sym_cut = _sorted_bars(
        overall_like_rates(ratings, "symmetry"), DROPPED["symmetry"])

    fig, axes = plt.subplots(1, 3, figsize=(14, 6),
                             gridspec_kw={"width_ratios": [1, 2.5, 1], "wspace": 0.4})
    overall_rate = round(sum(rates) / len(rates)) if rates else 0
    _plot_trend(axes[0], rates)
    _plot_bars(axes[1], pal_surv, pal_cut, "Palettes  (red = dropped)", overall_rate, fontsize=8.5)
    _plot_bars(axes[2], sym_surv, sym_cut, "Symmetry  (red = dropped)", overall_rate)

    n_rated = len(ratings)
    n_rounds = len(ROUND_SLICES)
    fig.suptitle(f"Active learning: {n_rated} quilts rated, {n_rounds} rounds", fontsize=13)

    out = "quilts/convergence.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    print(f"Saved {out}")
    plt.close()


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "quilts/ratings.json"
    if not os.path.exists(path):
        path = "ratings.json"
    make_figure(load_ratings(path))
