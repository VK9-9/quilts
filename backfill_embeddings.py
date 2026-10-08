"""Backfill CLIP embeddings for existing ratings.

Usage:
    python backfill_embeddings.py [ratings.json] [--refresh]

Renders each rated quilt at block_size=16, embeds it with CLIP, and stores the
vector under the rating's id (see ratings_store).

By default only ratings with no embedding are done, so the script is safe to
resume if interrupted, and ratings that failed to render on an earlier run are
retried in case the cause has since been fixed.

--refresh additionally re-embeds ratings that already have one, for when the
renderer itself has changed and the stored vectors no longer describe what the
current code draws. A rating's vector is only replaced once its new render
succeeds, so ratings whose palette has since been deleted from palettes.py keep
their existing vector — those can never be regenerated, and they are still
valid preference data.
"""

import sys

import ratings_store
from clip_embed import embed_image
from render_params import params_to_render_kwargs
from sampler import _CLIP_EMBED_BLOCK_SIZE
from quilt import render_quilt

_SAVE_EVERY = 50


def backfill(ratings_path, refresh=False):
    """Embed every rating that lacks an embedding (all of them with refresh)."""
    ratings = ratings_store.load_ratings(ratings_path)
    by_id = ratings_store.load_embeddings(ratings_path)

    todo = ratings if refresh else [r for r in ratings if r["id"] not in by_id]
    if not todo:
        print(f"All {len(ratings)} ratings already embedded.")
        return
    print(f"Embedding {len(todo)} ratings ({len(ratings) - len(todo)} skipped)...")

    failed = kept = 0
    for n, rating in enumerate(todo):
        try:
            kwargs = params_to_render_kwargs(rating["params"], block_size=_CLIP_EMBED_BLOCK_SIZE)
            # Assign only on success, so a refresh can't destroy a usable vector.
            by_id[rating["id"]] = embed_image(render_quilt(**kwargs))
        except Exception as exc:  # pylint: disable=broad-except
            # Deleted palette or other render failure. An existing vector stays:
            # it can never be regenerated, and it is still a valid (image,
            # label) pair for the CLIP model.
            if rating["id"] in by_id:
                kept += 1
            else:
                print(f"  rating {rating['id']} failed ({type(exc).__name__}: {exc})")
                failed += 1
        if (n + 1) % _SAVE_EVERY == 0 or (n + 1) == len(todo):
            print(f"  {n + 1}/{len(todo)}  (unrenderable: {failed} missing, {kept} kept as-is)")
            ratings_store.save_embeddings(ratings_path, by_id)  # save incrementally

    print(
        f"Saved {len(by_id)} embeddings for {len(ratings)} ratings "
        f"({failed} without one, {kept} kept from before)"
    )


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    path = args[0] if args else "data/ratings.json"
    backfill(path, refresh="--refresh" in sys.argv[1:])
