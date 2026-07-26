"""Backfill CLIP embeddings for existing ratings.

Usage:
    python backfill_embeddings.py [ratings.json] [--refresh]

Renders each rated quilt at block_size=16, embeds with CLIP, and saves
to <ratings_stem>_embeddings.npy alongside the ratings file.

By default only rows with no embedding are done, so the script is safe to
resume if interrupted, and rows left zero by an earlier render failure are
retried each run in case the cause has since been fixed.

--refresh additionally re-embeds rows that already have one, for when the
renderer itself has changed and the stored vectors no longer describe what the
current code draws. It re-embeds in place and only overwrites a row once the
new render succeeds, so rows whose palette has since been deleted from
palettes.py keep their existing vector instead of being zeroed — those can
never be regenerated, and they are still valid preference data.
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


def backfill(ratings_path, refresh=False):
    """Embed every rating that lacks a (non-zero) embedding.

    With refresh=True, re-embed rows that already have one as well.
    """
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

    # (Re)embed new rows plus any left zero by an earlier failure. With
    # --refresh, every row is a candidate.
    if refresh:
        todo = list(range(total))
    else:
        todo = [i for i in range(total) if not np.any(rows[i])]
    if not todo:
        print(f"All {total} ratings already embedded.")
        return

    print(f"Embedding {len(todo)} ratings ({total - len(todo)} skipped)...")

    failed = 0
    kept = 0
    for n, i in enumerate(todo):
        had_one = bool(np.any(rows[i]))
        try:
            kwargs = params_to_render_kwargs(
                ratings[i]["params"], block_size=_CLIP_EMBED_BLOCK_SIZE
            )
            png_bytes = render_quilt(**kwargs)
            # Assign only on success, so a refresh can't destroy a usable vector.
            rows[i] = embed_image(png_bytes)
        except Exception as exc:  # pylint: disable=broad-except
            # Deleted palette or other render failure. If this row already had
            # an embedding it stays: it can never be regenerated, and it is
            # still a valid (image, label) pair for the CLIP model.
            if had_one:
                kept += 1
            else:
                print(f"  row {i} failed ({type(exc).__name__}: {exc}); zero-padded")
                failed += 1
        if (n + 1) % 50 == 0 or (n + 1) == len(todo):
            print(f"  {n + 1}/{len(todo)}  (unrenderable: {failed} zeroed, {kept} kept as-is)")
            _save_atomic(embeddings_path, rows)  # save incrementally

    _save_atomic(embeddings_path, rows)
    print(
        f"Saved {embeddings_path}  shape={rows.shape}  "
        f"({failed} zero-padded, {kept} kept from the previous run)"
    )


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    path = args[0] if args else "data/ratings.json"
    backfill(path, refresh="--refresh" in sys.argv[1:])
