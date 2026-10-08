"""Ratings and their CLIP embeddings on disk, joined by a stable rating id.

Every rating carries an integer "id". Embeddings live in two parallel files
beside the ratings — <stem>_embeddings.npy (N x 512 float32) and
<stem>_embedding_ids.npy (N int64, the rating id of each row) — and are matched
to ratings by id, never by position. They used to be paired positionally
(embeddings[i] belonged to ratings[i]), which silently mislabels every row
after the first truncation, hand edit or diverged backfill; three modules
carried truncation heuristics guarding against exactly that. A rating with no
embedding simply has no entry.

The exploit/explore label lives on the rating as "source" (it used to ride
inside params as "_source").

Usage:
    python ratings_store.py migrate [data/ratings.json]   # one-time, idempotent
"""

import json
import os
import sys

import numpy as np

EMBED_DIM = 512


class MigrationNeeded(RuntimeError):
    """The files on disk predate rating ids; run `python ratings_store.py migrate`."""


def _paths(ratings_path):
    """(embeddings_path, embedding_ids_path) beside ratings_path.

    Derived from the extension only: a plain .replace(".json", ...) would also
    rewrite a ".json" appearing earlier in the path.
    """
    root = os.path.splitext(ratings_path)[0]
    return root + "_embeddings.npy", root + "_embedding_ids.npy"


def atomic_write_json(path, obj):
    """Write JSON to a temp file then atomically replace, so an interrupted
    write (or a concurrent reader) never sees a truncated file."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)
    os.replace(tmp, path)


def _atomic_save_npy(path, arr):
    tmp = path + ".tmp.npy"
    np.save(tmp, arr)
    os.replace(tmp, path)


def load_ratings(ratings_path):
    """The ratings list ([] if the file doesn't exist). Every rating must have an id."""
    if not os.path.exists(ratings_path):
        return []
    with open(ratings_path, encoding="utf-8") as f:
        ratings = json.load(f)
    if any("id" not in r for r in ratings):
        raise MigrationNeeded(f"{ratings_path} has ratings without ids")
    return ratings


def save_ratings(ratings_path, ratings):
    """Atomically write the ratings list."""
    atomic_write_json(ratings_path, ratings)


def next_id(ratings):
    """The id for a new rating: one past the largest in use."""
    return max((r["id"] for r in ratings), default=-1) + 1


def load_embeddings(ratings_path):
    """{rating id: 512-d float32 vector} for every embedded rating ({} if none)."""
    emb_path, ids_path = _paths(ratings_path)
    if not os.path.exists(emb_path):
        return {}
    if not os.path.exists(ids_path):
        raise MigrationNeeded(f"{emb_path} has no {os.path.basename(ids_path)}")
    vectors = np.load(emb_path)
    ids = np.load(ids_path)
    if len(vectors) != len(ids):
        raise ValueError(
            f"{len(vectors)} embeddings but {len(ids)} embedding ids — the pair is "
            "out of step (interrupted save?); restore from backup or re-run backfill"
        )
    return dict(zip(ids.tolist(), vectors))


def save_embeddings(ratings_path, by_id):
    """Write {rating id: vector} as the two parallel files, ordered by id.

    Each file is replaced atomically. A crash between the two replaces leaves
    them different lengths, which load_embeddings reports rather than mispairs.
    """
    emb_path, ids_path = _paths(ratings_path)
    ids = sorted(by_id)
    vectors = (
        np.stack([by_id[i] for i in ids]).astype(np.float32)
        if ids
        else np.zeros((0, EMBED_DIM), dtype=np.float32)
    )
    _atomic_save_npy(emb_path, vectors)
    _atomic_save_npy(ids_path, np.array(ids, dtype=np.int64))


def migrate(ratings_path):
    """Give every rating an id, move params["_source"] to "source", and key the
    embeddings by id. Idempotent: a migrated store is left untouched.

    The legacy pairing was positional, so ids are assigned as positions and
    embeddings[i] goes to rating i. All-zero rows were placeholders for quilts
    that failed to render; they become "no entry", which every consumer
    already treated them as.

    Returns a summary dict.
    """
    emb_path, ids_path = _paths(ratings_path)
    with open(ratings_path, encoding="utf-8") as f:
        ratings = json.load(f)
    all_ids = all("id" in r for r in ratings)
    if all_ids and (os.path.exists(ids_path) or not os.path.exists(emb_path)):
        return {"migrated": False, "ratings": len(ratings)}
    # Anything else with ids around is a half-finished migration. Re-pairing
    # positionally then would be wrong (the embeddings may already be
    # compacted), so refuse rather than guess.
    if any("id" in r for r in ratings) or os.path.exists(ids_path):
        raise ValueError("store is partly migrated; restore data/ from backup and re-run")

    vectors = np.load(emb_path) if os.path.exists(emb_path) else np.zeros((0, EMBED_DIM))
    if len(vectors) > len(ratings):
        raise ValueError(
            f"{len(vectors)} embeddings for {len(ratings)} ratings — the positional "
            "pairing is already broken; refusing to guess"
        )

    moved = 0
    for i, r in enumerate(ratings):
        r["id"] = i
        source = r["params"].pop("_source", None)
        if source is not None:
            r["source"] = source
            moved += 1

    by_id = {i: v for i, v in enumerate(vectors) if np.any(v)}
    # Ratings first: a crash after this leaves ids with no id file, which the
    # check above refuses. Never the reverse (compacted embeddings, id-less
    # ratings), which would look like an unmigrated store.
    save_ratings(ratings_path, ratings)
    save_embeddings(ratings_path, by_id)
    return {
        "migrated": True,
        "ratings": len(ratings),
        "embeddings": len(by_id),
        "placeholder_rows_dropped": len(vectors) - len(by_id),
        "sources_moved": moved,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] != "migrate":
        print(__doc__)
        sys.exit(1)
    print(migrate(sys.argv[2] if len(sys.argv) > 2 else "data/ratings.json"))
