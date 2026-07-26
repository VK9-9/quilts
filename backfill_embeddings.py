"""One-time script to backfill CLIP embeddings for all existing ratings.

Usage:
    python backfill_embeddings.py [ratings.json]

Renders each rated quilt at block_size=16, embeds with CLIP, and saves
to <ratings_stem>_embeddings.npy alongside the ratings file.

Rows that already have a non-zero embedding are skipped, so the script is safe
to resume if interrupted. Rows left zero by an earlier render failure are
retried on each run (in case the underlying issue has since been fixed).
"""

import json
import os
import sys

import numpy as np

from clip_embed import embed_image
from render_params import params_to_render_kwargs
from sampler import _CLIP_EMBED_BLOCK_SIZE
from quilt import render_quilt


def _save_atomic(dest, arr):
    """Write to a temp file then rename, matching sampler._save_embeddings.

    This runs every 50 rows over a multi-thousand-row array; a plain np.save
    interrupted mid-write leaves a truncated .npy that the next run loads as
    the resume point.
    """
    tmp = dest + ".tmp.npy"
    np.save(tmp, arr)
    os.replace(tmp, dest)


def backfill(ratings_path):
    """Embed every rating that lacks a (non-zero) embedding."""
    # Derive the companion path from the extension only — see sampler.py.
    embeddings_path = os.path.splitext(ratings_path)[0] + "_embeddings.npy"

    with open(ratings_path, encoding="utf-8") as f:
        ratings = json.load(f)
    total = len(ratings)

    if os.path.exists(embeddings_path):
        embeddings = np.load(embeddings_path)
    else:
        embeddings = np.zeros((0, 512), dtype=np.float32)

    if len(embeddings) > total:
        print(f"WARNING: {len(embeddings)} embeddings > {total} ratings; truncating.")
        embeddings = embeddings[:total]

    # Positionally-aligned buffer: rows[i] is the embedding for ratings[i].
    rows = np.zeros((total, 512), dtype=np.float32)
    rows[: len(embeddings)] = embeddings

    # (Re)embed new rows plus any left zero by an earlier failure.
    todo = [i for i in range(total) if not np.any(rows[i])]
    if not todo:
        print(f"All {total} ratings already embedded.")
        return

    print(f"Embedding {len(todo)} ratings ({total - len(todo)} already done)...")

    failed = 0
    for n, i in enumerate(todo):
        try:
            kwargs = params_to_render_kwargs(
                ratings[i]["params"], block_size=_CLIP_EMBED_BLOCK_SIZE
            )
            png_bytes = render_quilt(**kwargs)
            rows[i] = embed_image(png_bytes)
        except Exception as exc:  # pylint: disable=broad-except
            # retired palette or other render failure — leave a zero vector
            print(f"  row {i} failed ({type(exc).__name__}: {exc}); zero-padded")
            failed += 1
        if (n + 1) % 50 == 0 or (n + 1) == len(todo):
            print(f"  {n + 1}/{len(todo)}  (failed so far: {failed})")
            _save_atomic(embeddings_path, rows)  # save incrementally

    _save_atomic(embeddings_path, rows)
    print(f"Saved {embeddings_path}  shape={rows.shape}  ({failed} zero-padded due to failures)")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data/ratings.json"
    backfill(path)
