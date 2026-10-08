"""Tests for ratings_store — ratings and CLIP embeddings joined by id."""

import json
import os

import numpy as np
import pytest

import ratings_store
from ratings_store import MigrationNeeded


def _legacy_store(tmp_path, n=6, zero_rows=(2,), n_embeddings=None):
    """Pre-migration files: id-less ratings with params["_source"], and a
    positionally paired embeddings array with zero placeholder rows."""
    path = str(tmp_path / "ratings.json")
    ratings = []
    for i in range(n):
        params = {"palette": "tide pool", "seed": i}
        if i % 2:
            params["_source"] = "explore"
        rating = {"params": params, "liked": i % 3 != 0}
        if i >= 2:  # the oldest ratings predate timestamps
            rating["ts"] = 1000.0 + i
        ratings.append(rating)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(ratings, f)
    vectors = np.arange((n_embeddings or n) * 512, dtype=np.float32).reshape(-1, 512) + 1
    for i in zero_rows:
        vectors[i] = 0
    np.save(tmp_path / "ratings_embeddings.npy", vectors)
    return path, ratings, vectors


class TestMigrate:
    def test_assigns_positional_ids_and_moves_source(self, tmp_path):
        path, old, _ = _legacy_store(tmp_path)
        summary = ratings_store.migrate(path)
        new = ratings_store.load_ratings(path)
        assert summary["migrated"] and summary["sources_moved"] == 3
        for i, (o, n) in enumerate(zip(old, new)):
            assert n["id"] == i
            assert "_source" not in n["params"]
            assert n.get("source") == o["params"].get("_source")
            assert n.get("ts") == o.get("ts")

    def test_embeddings_keyed_by_id_and_placeholders_dropped(self, tmp_path):
        path, _, vectors = _legacy_store(tmp_path, zero_rows=(2, 4))
        ratings_store.migrate(path)
        by_id = ratings_store.load_embeddings(path)
        assert set(by_id) == {0, 1, 3, 5}
        for i in by_id:
            assert np.array_equal(by_id[i], vectors[i])

    def test_short_embeddings_leave_later_ratings_unembedded(self, tmp_path):
        path, _, _ = _legacy_store(tmp_path, n=6, zero_rows=(), n_embeddings=4)
        ratings_store.migrate(path)
        assert set(ratings_store.load_embeddings(path)) == {0, 1, 2, 3}

    def test_is_idempotent(self, tmp_path):
        path, _, _ = _legacy_store(tmp_path)
        ratings_store.migrate(path)
        before = open(path, encoding="utf-8").read()
        assert ratings_store.migrate(path) == {"migrated": False, "ratings": 6}
        assert open(path, encoding="utf-8").read() == before

    def test_refuses_more_embeddings_than_ratings(self, tmp_path):
        """Positional pairing is already broken; guessing would mislabel."""
        path, _, _ = _legacy_store(tmp_path, n=4, zero_rows=(), n_embeddings=6)
        with pytest.raises(ValueError, match="refusing to guess"):
            ratings_store.migrate(path)

    def test_refuses_a_half_finished_migration(self, tmp_path):
        """A crash after the ratings were written (ids, but no id file) must not
        be re-paired positionally."""
        path, _, _ = _legacy_store(tmp_path)
        ratings_store.migrate(path)
        os.remove(tmp_path / "ratings_embedding_ids.npy")
        with pytest.raises(ValueError, match="partly migrated"):
            ratings_store.migrate(path)

    def test_refuses_compacted_embeddings_with_unmigrated_ratings(self, tmp_path):
        path, legacy, _ = _legacy_store(tmp_path)
        ratings_store.migrate(path)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(legacy, f)
        with pytest.raises(ValueError, match="partly migrated"):
            ratings_store.migrate(path)


class TestLoad:
    def test_unmigrated_ratings_are_refused(self, tmp_path):
        path, _, _ = _legacy_store(tmp_path)
        with pytest.raises(MigrationNeeded):
            ratings_store.load_ratings(path)

    def test_unmigrated_embeddings_are_refused(self, tmp_path):
        path, _, _ = _legacy_store(tmp_path)
        with pytest.raises(MigrationNeeded):
            ratings_store.load_embeddings(path)

    def test_out_of_step_pair_is_reported_not_mispaired(self, tmp_path):
        path = str(tmp_path / "ratings.json")
        ratings_store.save_embeddings(path, {0: np.ones(512), 1: np.ones(512)})
        np.save(tmp_path / "ratings_embedding_ids.npy", np.array([0], dtype=np.int64))
        with pytest.raises(ValueError, match="out of step"):
            ratings_store.load_embeddings(path)

    def test_missing_files_are_empty(self, tmp_path):
        path = str(tmp_path / "nothing.json")
        assert ratings_store.load_ratings(path) == []
        assert ratings_store.load_embeddings(path) == {}

    def test_next_id(self):
        assert ratings_store.next_id([]) == 0
        assert ratings_store.next_id([{"id": 0}, {"id": 7}]) == 8


def test_add_rating_writes_the_new_format(tmp_path, monkeypatch):
    """The UI posts back params with "_source"; it's stored as "source", the
    rating gets the next id, and its embedding is saved under that id."""
    import sys
    import types

    import sampler

    fake = types.ModuleType("clip_embed")
    fake.embed_image = lambda png: np.full(512, 0.5, dtype=np.float32)
    monkeypatch.setitem(sys.modules, "clip_embed", fake)
    monkeypatch.setattr("sampler._render_small", lambda params, block_size: b"")

    path = str(tmp_path / "ratings.json")
    ex = sampler.QuiltExplorer(path)
    ex.add_rating({"palette": "tide pool", "_source": "explore"}, True)
    ex.add_rating({"palette": "twilight"}, False)

    saved = ratings_store.load_ratings(path)
    assert [r["id"] for r in saved] == [0, 1]
    assert saved[0]["source"] == "explore" and "_source" not in saved[0]["params"]
    assert "source" not in saved[1]
    assert set(ratings_store.load_embeddings(path)) == {0, 1}


def test_gallery_embeddings_join_by_id(tmp_path):
    from build_site import load_clip_embeddings

    path = str(tmp_path / "ratings.json")
    ratings_store.save_embeddings(path, {3: np.full(512, 3.0), 7: np.full(512, 7.0)})
    emb, valid = load_clip_embeddings(path, [7, 5, 3])
    assert valid.tolist() == [True, False, True]
    assert emb[0][0] == 7.0 and emb[2][0] == 3.0 and not emb[1].any()
