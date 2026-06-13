"""One-time script to backfill CLIP embeddings for all existing ratings.

Usage:
    python backfill_embeddings.py [ratings.json]

Renders each rated quilt at block_size=16, embeds with CLIP, and saves
to <ratings_stem>_embeddings.npy alongside the ratings file.

Already-embedded ratings (rows up to existing embeddings count) are
skipped so the script is safe to resume if interrupted.
"""

import json
import os
import sys

import numpy as np

from clip_embed import embed_image
from render_params import params_to_render_kwargs
from sampler import _CLIP_EMBED_BLOCK_SIZE
from quilt import render_quilt


def backfill(ratings_path):
    """Embed all ratings that don't yet have an embedding."""
    embeddings_path = ratings_path.replace(".json", "_embeddings.npy")

    with open(ratings_path, encoding="utf-8") as f:
        ratings = json.load(f)

    if os.path.exists(embeddings_path):
        embeddings = np.load(embeddings_path)
    else:
        embeddings = np.zeros((0, 512), dtype=np.float32)

    start = len(embeddings)
    total = len(ratings)
    remaining = total - start

    if remaining == 0:
        print(f"All {total} ratings already embedded.")
        return

    print(f"Embedding {remaining} ratings (skipping first {start})...")

    rows = list(embeddings)
    skipped = 0
    for i, rec in enumerate(ratings[start:], start=start):
        try:
            kwargs = params_to_render_kwargs(rec["params"], block_size=_CLIP_EMBED_BLOCK_SIZE)
            png_bytes = render_quilt(**kwargs)
            vec = embed_image(png_bytes)
        except Exception:  # pylint: disable=broad-except
            # retired palette or other render failure — store zero vector
            vec = np.zeros(512, dtype=np.float32)
            skipped += 1
        rows.append(vec)
        if (i + 1) % 50 == 0 or (i + 1) == total:
            print(f"  {i + 1}/{total}  (skipped so far: {skipped})")
            # save incrementally so interruption doesn't lose work
            np.save(embeddings_path, np.array(rows, dtype=np.float32))

    print(
        f"Saved {embeddings_path}  shape={np.array(rows).shape}  "
        f"({skipped} zero-padded due to retired palettes)"
    )


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data/ratings.json"
    backfill(path)
