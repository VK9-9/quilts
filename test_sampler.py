"""Tests for sampler.py — parameter sampling and the preference-model encoder."""

import random

import numpy as np
import pytest

from layout import SYMMETRY_MODES
from palettes import PALETTES
from sampler import (
    _DROP_PALETTES,
    _DROP_STITCHES,
    _DROP_SYMMETRY,
    PALETTE_NAMES,
    SYMMETRY_NAMES,
    build_feature_vocab,
    feature_names,
    params_to_features,
    sample_random_params,
)


def _rating(liked=True, **params):
    base = {
        "rows": 16,
        "cols": 16,
        "symmetry": "partial",
        "chaos": 0.3,
        "palette": "ocean breeze",
        "n_patterns": 2,
        "n_colors": 4,
        "tile_size": 6,
        "tile_variation": 0.1,
    }
    base.update(params)
    return {"params": base, "liked": liked}


class TestFeatureVocab:
    """The encoder must represent the whole ratings history, not just what is
    currently samplable.

    _retrain fits on every rating ever made. Encoding over the post-drop set
    collapsed every retired or deleted value into one all-zero block, which
    (because values are retired for underperforming) was a large, uniformly
    disliked bucket that no candidate can ever fall into at prediction time.
    """

    def test_covers_values_deleted_from_palettes_py(self):
        gone = "a palette that no longer exists"
        assert gone not in {p[0] for p in PALETTES}
        vocab = build_feature_vocab([_rating(palette=gone)])
        assert gone in vocab["palette"]

    def test_covers_values_dropped_from_sampling(self):
        """A value retired from sampling but still defined must stay encodable."""
        vocab = build_feature_vocab()
        still_defined = _DROP_PALETTES & {p[0] for p in PALETTES}
        for name in still_defined:
            assert name in vocab["palette"], f"retired palette {name} missing from vocab"
        for name in _DROP_SYMMETRY:
            assert name in vocab["symmetry"], f"retired symmetry {name} missing from vocab"

    def test_covers_every_palette_the_history_mentions(self):
        """Including ones since deleted from palettes.py — 25 of them, today."""
        retired = sorted(_DROP_PALETTES)
        vocab = build_feature_vocab([_rating(palette=name) for name in retired])
        for name in retired:
            assert name in vocab["palette"], f"history palette {name} missing from vocab"

    def test_no_categorical_block_is_all_zero(self):
        """Every row must land in exactly one bucket of every categorical."""
        ratings = [
            _rating(palette="storm", symmetry="mirror"),
            _rating(palette="a deleted palette", symmetry="none"),
            _rating(palette="ocean breeze", symmetry="bargello", border_style="solid"),
            _rating(palette="lavender fields", symmetry="partial", border_style=None),
        ]
        vocab = build_feature_vocab(ratings)
        names = feature_names(vocab)
        rows = np.array([params_to_features(r["params"], vocab) for r in ratings])
        for prefix in ("pal_", "sym_", "brd_"):
            idx = [i for i, n in enumerate(names) if n.startswith(prefix)]
            block = rows[:, idx]
            assert (block.sum(axis=1) == 1).all(), f"{prefix} block is not one-hot"

    def test_retired_and_active_palettes_stay_distinguishable(self):
        """Two different retired palettes must not encode identically.

        This is the actual defect: they both produced an all-zero palette block,
        so the model could not tell them apart from each other or from a value
        it had never seen.
        """
        ratings = [_rating(palette="storm"), _rating(palette="terracotta")]
        vocab = build_feature_vocab(ratings)
        a = params_to_features(ratings[0]["params"], vocab)
        b = params_to_features(ratings[1]["params"], vocab)
        assert not np.array_equal(a, b)

    def test_names_match_vector_length(self):
        vocab = build_feature_vocab([_rating(palette="gone")])
        assert len(feature_names(vocab)) == len(params_to_features(_rating()["params"], vocab))

    def test_vocab_order_is_deterministic(self):
        ratings = [_rating(palette="zeta"), _rating(palette="alpha")]
        assert build_feature_vocab(ratings) == build_feature_vocab(list(reversed(ratings)))

    def test_absent_border_style_encodes_as_none(self):
        vocab = build_feature_vocab()
        explicit = params_to_features(_rating(border_style="none")["params"], vocab)
        absent = params_to_features(_rating()["params"], vocab)
        assert np.array_equal(explicit, absent)

    def test_widens_as_history_grows(self):
        narrow = build_feature_vocab()
        wide = build_feature_vocab([_rating(palette="brand new palette")])
        assert len(wide["palette"]) == len(narrow["palette"]) + 1


class TestParamsToFeatures:
    def test_is_finite_and_float(self):
        vec = params_to_features(sample_random_params(random.Random(0)))
        assert vec.dtype == np.float64
        assert np.isfinite(vec).all()

    def test_tolerates_missing_optional_params(self):
        """Old records predate wonky/strippy/wash_alpha and must still encode."""
        params_to_features({"symmetry": "partial", "palette": "ocean breeze"})

    def test_same_vocab_gives_stable_encoding(self):
        vocab = build_feature_vocab()
        p = sample_random_params(random.Random(3))
        assert np.array_equal(params_to_features(p, vocab), params_to_features(p, vocab))


class TestSampling:
    """Dropping a value must affect sampling only — never the encoder."""

    @pytest.mark.parametrize("seed", range(60))
    def test_never_samples_dropped_values(self, seed):
        p = sample_random_params(random.Random(seed))
        assert p["palette"] not in _DROP_PALETTES
        assert p["symmetry"] not in _DROP_SYMMETRY
        assert p["quilt_stitch"] not in _DROP_STITCHES
        assert p["border_style"] != "stripes"

    @pytest.mark.parametrize("seed", range(60))
    def test_sampled_params_are_in_range(self, seed):
        p = sample_random_params(random.Random(seed))
        assert p["rows"] == p["cols"]
        assert 3 <= p["n_colors"] <= 6
        assert 0.0 <= p["chaos"] <= 0.8
        assert p["symmetry"] in SYMMETRY_MODES
        assert p["palette"] in {name for name, _ in PALETTES}

    def test_explore_only_excludes_proven_winners(self):
        """Exploitation candidates must not be able to pick proven winners."""
        for seed in range(60):
            p = sample_random_params(random.Random(seed), explore_only=True)
            assert p["palette"] != "lavender fields"
            assert p["symmetry"] != "bargello"

    def test_proven_winners_still_reachable_when_exploring(self):
        seen = {sample_random_params(random.Random(s))["symmetry"] for s in range(60)}
        assert "bargello" in seen

    def test_drop_lists_are_consistent_with_exported_names(self):
        assert not set(PALETTE_NAMES) & _DROP_PALETTES
        assert not set(SYMMETRY_NAMES) & _DROP_SYMMETRY
