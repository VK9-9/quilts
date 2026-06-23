"""Visualize active learning convergence over rounds.

Produces: convergence.png

Round boundaries are read from the companion <ratings>_rounds.json file (the
same source analyze.round_summary uses) rather than hardcoded — the dataset
grows every round, so any fixed slice list goes stale immediately.
"""

import json
import sys
import os
from collections import defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # pylint: disable=wrong-import-position

from sampler import _DROP_PALETTES, _DROP_SYMMETRY  # pylint: disable=wrong-import-position

# Single source of truth for what's been retired (was a hand-maintained copy).
DROPPED = {"palette": _DROP_PALETTES, "symmetry": _DROP_SYMMETRY}


def compute_round_rates(ratings, rounds):
    """Return (labels, rates%) per round, from each round's start_index boundary."""
    labels, rates = [], []
    for i, rnd in enumerate(rounds):
        start = rnd["start_index"]
        end = rounds[i + 1]["start_index"] if i + 1 < len(rounds) else len(ratings)
        chunk = ratings[start:end]
        if not chunk:
            continue
        labels.append(rnd.get("label", f"R{rnd.get('round', i + 1)}"))
        rates.append(round(100 * sum(1 for r in chunk if r["liked"]) / len(chunk)))
    return labels, rates


def load_ratings(ratings_path):
    """Load ratings JSON from disk."""
    with open(ratings_path, encoding="utf-8") as f:
        return json.load(f)


def load_rounds(rounds_json):
    """Load round boundaries, or [] if the file is absent."""
    if not os.path.exists(rounds_json):
        return []
    with open(rounds_json, encoding="utf-8") as f:
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
    survivors = sorted([(k, v) for k, v in rates.items() if k not in dropped], key=lambda x: x[1])
    cut = sorted([(k, v) for k, v in rates.items() if k in dropped], key=lambda x: x[1])
    return survivors, cut


def _plot_trend(ax, labels, rates):
    """Draw the like-rate-over-rounds line chart."""
    xs = range(1, len(rates) + 1)
    ax.plot(list(xs), rates, "o-", color="steelblue", linewidth=2.5, markersize=8)
    for x, y in zip(xs, rates):
        ax.text(x, y + 1.5, f"{y}%", ha="center", fontsize=11)
    ax.set_xticks(list(xs))
    ax.set_xticklabels(labels, rotation=90 if len(labels) > 10 else 0, fontsize=8)
    ax.set_ylabel("Like rate %")
    ax.set_ylim(0, 100)
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
        ax.text(v + 0.005, i, f"{int(round(v * 100))}%", va="center", fontsize=fontsize)
    ax.set_yticks(list(ys))
    ax.set_yticklabels(labels, fontsize=fontsize)
    ax.set_xlim(0, 0.75)
    ax.set_xlabel("Like rate")
    ax.set_title(title, fontweight="bold")
    ax.xaxis.grid(True, alpha=0.35)
    ax.set_axisbelow(True)


def make_figure(ratings, rounds, out="convergence.png"):
    """Render convergence chart and save to `out`."""
    labels, rates = compute_round_rates(ratings, rounds)
    pal_surv, pal_cut = _sorted_bars(overall_like_rates(ratings, "palette"), DROPPED["palette"])
    sym_surv, sym_cut = _sorted_bars(overall_like_rates(ratings, "symmetry"), DROPPED["symmetry"])

    fig, axes = plt.subplots(
        1, 3, figsize=(14, 6), gridspec_kw={"width_ratios": [1, 2.5, 1], "wspace": 0.4}
    )
    overall_rate = round(sum(rates) / len(rates)) if rates else 0
    _plot_trend(axes[0], labels, rates)
    _plot_bars(axes[1], pal_surv, pal_cut, "Palettes  (red = dropped)", overall_rate, fontsize=8.5)
    _plot_bars(axes[2], sym_surv, sym_cut, "Symmetry  (red = dropped)", overall_rate)

    fig.suptitle(
        f"Active learning: {len(ratings)} quilts rated, {len(labels)} rounds", fontsize=13
    )

    out_dir = os.path.dirname(out)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    plt.savefig(out, dpi=150, bbox_inches="tight")
    print(f"Saved {out}")
    plt.close()


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data/ratings.json"
    rounds_path = os.path.splitext(path)[0] + "_rounds.json"
    make_figure(load_ratings(path), load_rounds(rounds_path))
