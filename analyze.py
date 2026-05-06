"""Analyze quilt ratings data and print a summary report."""
import json
import sys
from collections import Counter, defaultdict

import numpy as np


def load_ratings(path="ratings.json"):
    with open(path) as f:
        return json.load(f)


def like_rate(ratings):
    if not ratings:
        return 0.0
    return sum(1 for r in ratings if r["liked"]) / len(ratings)


def analyze_categorical(ratings, param):
    """Return {value: (total, liked)} for a categorical/integer param."""
    buckets = defaultdict(lambda: [0, 0])
    for r in ratings:
        val = r["params"].get(param)
        if val is None:
            continue
        buckets[val][0] += 1
        if r["liked"]:
            buckets[val][1] += 1
    return dict(buckets)


def analyze_continuous(ratings, param):
    """Return (liked_mean, disliked_mean) for a continuous param."""
    liked = [r["params"][param] for r in ratings if r["liked"]]
    disliked = [r["params"][param] for r in ratings if not r["liked"]]
    return (
        np.mean(liked) if liked else float("nan"),
        np.mean(disliked) if disliked else float("nan"),
    )


def time_windows(ratings, window=25):
    """Return list of (start, end, liked, total) tuples."""
    results = []
    for i in range(0, len(ratings), window):
        chunk = ratings[i : i + window]
        liked = sum(1 for r in chunk if r["liked"])
        results.append((i + 1, i + len(chunk), liked, len(chunk)))
    return results


def palette_frequency(ratings):
    """Return Counter of palette usage."""
    return Counter(r["params"]["palette"] for r in ratings)


def print_report(ratings):
    n = len(ratings)
    liked = sum(1 for r in ratings if r["liked"])
    print(f"Total: {n} ratings, {liked} liked ({liked/n*100:.1f}%)\n")

    # Categorical / integer params
    for param in ["symmetry", "palette", "n_patterns", "n_colors", "rows",
                   "border_style"]:
        print(f"--- {param} ---")
        buckets = analyze_categorical(ratings, param)
        for val in sorted(buckets, key=lambda v: (isinstance(v, str), v)):
            total, lk = buckets[val]
            pct = lk / total * 100 if total else 0
            print(f"  {val}: {lk}/{total} ({pct:.0f}%)")
        print()

    # Continuous params
    for param in ["chaos", "tile_size", "tile_variation"]:
        lk_mean, dk_mean = analyze_continuous(ratings, param)
        print(f"--- {param} ---")
        print(f"  liked mean={lk_mean:.3f}  disliked mean={dk_mean:.3f}\n")

    # Trend
    print("--- Like rate over time (windows of 25) ---")
    for start, end, lk, total in time_windows(ratings):
        pct = lk / total * 100
        print(f"  {start:>3}-{end:>3}: {lk:>2}/{total} ({pct:.0f}%)")
    print()

    # Palette frequency
    print("--- Palette frequency (uniform would be ~8% each) ---")
    freq = palette_frequency(ratings)
    for pal, count in freq.most_common():
        print(f"  {pal}: {count}/{n} ({count/n*100:.1f}%)")
    print()


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "ratings.json"
    ratings = load_ratings(path)
    print_report(ratings)
