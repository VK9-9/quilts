"""Tests for sampler.py — parameter sampling and the CLIP preference loop."""

import random

import numpy as np
import ratings_store
import pytest

from layout import SYMMETRY_MODES
from palettes import PALETTES
from sampler import (
    QuiltExplorer,
    _DROP_PALETTES,
    _TRAIN_FROM_ROUND,
    _DROP_STITCHES,
    _DROP_SYMMETRY,
    _PROVEN_PALETTES,
    _PROVEN_SYMMETRIES,
    FEATURE_PROBS,
    PALETTE_NAMES,
    PARAM_SPACE,
    SYMMETRY_NAMES,
    current_policy,
    sample_random_params,
)


class TestSampling:
    """Dropped values are never sampled; proven winners only while exploring."""

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
            assert p["palette"] not in _PROVEN_PALETTES
            assert p["symmetry"] not in _PROVEN_SYMMETRIES

    def test_lavender_fields_is_an_ordinary_palette(self):
        """Its proven status was dropped after R25: it competes in exploit
        candidates and is no longer injected into exploration."""
        assert "lavender fields" not in _PROVEN_PALETTES
        exploit = [sample_random_params(random.Random(s), explore_only=True) for s in range(400)]
        assert any(p["palette"] == "lavender fields" for p in exploit)
        explore = [sample_random_params(random.Random(s)) for s in range(400)]
        share = sum(p["palette"] == "lavender fields" for p in explore) / len(explore)
        assert share < 0.15, f"lavender fields still over-sampled when exploring: {share:.0%}"

    def test_proven_winners_still_reachable_when_exploring(self):
        seen = {sample_random_params(random.Random(s))["symmetry"] for s in range(60)}
        assert "bargello" in seen

    def test_drop_lists_are_consistent_with_exported_names(self):
        assert not set(PALETTE_NAMES) & _DROP_PALETTES
        assert not set(SYMMETRY_NAMES) & _DROP_SYMMETRY


class TestTrainingWindow:
    """The CLIP model trains on a recent-rounds window, not all history.

    Rounds 1-13 come from a different generative space and a differently
    calibrated rater (stitching didn't exist before R7). Walk-forward AUC over
    R18-R22: 0.598 on all history vs 0.620 from R14 for CLIP.
    """

    def _explorer(self, tmp_path, n_ratings, rounds):
        import json

        data = tmp_path / "r.json"
        data.write_text(
            json.dumps(
                [
                    {
                        "id": i,
                        "params": sample_random_params(random.Random(i)),
                        "liked": i % 3 != 0,
                    }
                    for i in range(n_ratings)
                ]
            )
        )
        (tmp_path / "r_rounds.json").write_text(json.dumps(rounds))
        # Nonzero stand-in embeddings, one per rating, so the CLIP model fits.
        rng = np.random.default_rng(0)
        vectors = rng.normal(size=(n_ratings, 512)).astype(np.float32)
        ratings_store.save_embeddings(str(data), dict(enumerate(vectors)))
        return QuiltExplorer(str(data))

    @staticmethod
    def _rounds(boundaries):
        return [
            {"round": i + 1, "label": f"R{i + 1}", "start_index": b, "ts": 0}
            for i, b in enumerate(boundaries)
        ]

    def test_window_starts_at_the_configured_round(self, tmp_path):
        rounds = self._rounds([i * 100 for i in range(20)])
        ex = self._explorer(tmp_path, 2000, rounds)
        assert ex.training_start() == rounds[_TRAIN_FROM_ROUND - 1]["start_index"]
        assert ex.stats()["train_from_round"] == _TRAIN_FROM_ROUND

    def test_falls_back_to_everything_when_the_window_is_too_small(self, tmp_path):
        """A fresh install has no R14, and a short window must not starve the fit."""
        ex = self._explorer(tmp_path, 300, self._rounds([0, 150]))
        assert ex.training_start() == 0
        assert ex.stats()["train_from_round"] == 1
        assert ex.clip_model is not None, "fallback must still produce a usable model"

    def test_window_excludes_earlier_ratings_from_the_fit(self, tmp_path):
        rounds = self._rounds([i * 100 for i in range(20)])
        ex = self._explorer(tmp_path, 2000, rounds)
        assert ex.stats()["trained_on"] == 2000 - ex.training_start()
        assert ex.stats()["trained_on"] < ex.stats()["total"]

    def test_clip_model_fits_exactly_the_window(self, tmp_path, monkeypatch):
        """Labels and embeddings must slice at the same index, or they mis-pair."""
        from sklearn.linear_model import LogisticRegression

        fitted = []
        real_fit = LogisticRegression.fit
        monkeypatch.setattr(
            LogisticRegression,
            "fit",
            lambda self, x, y: fitted.append(len(x)) or real_fit(self, x, y),
        )
        rounds = self._rounds([i * 100 for i in range(20)])
        ex = self._explorer(tmp_path, 2000, rounds)
        assert fitted[-1] == 2000 - ex.training_start() == ex.stats()["trained_on"]

    def test_no_clip_model_without_embeddings(self, tmp_path):
        """Too few embedded ratings: nothing to fit, so suggestions explore."""
        ex = QuiltExplorer(str(tmp_path / "empty.json"))
        assert ex.clip_model is None
        assert ex.suggest_params()["_source"] == "explore"


class TestPolicySnapshot:
    """Each round records the policy that generated it, so confound analyses
    (like R22's quilt_stitch-as-time-proxy) are a lookup, not git archaeology."""

    def test_policy_is_plain_json(self):
        import json

        policy = current_policy()
        assert json.loads(json.dumps(policy)) == policy

    def test_policy_reflects_live_constants(self):
        policy = current_policy()
        assert policy["feature_probs"] == FEATURE_PROBS
        assert policy["drop_palettes"] == sorted(_DROP_PALETTES)
        assert policy["train_from_round"] == _TRAIN_FROM_ROUND
        assert policy["param_space"]["rows"] == list(PARAM_SPACE["rows"])

    def test_policy_covers_every_optional_feature(self):
        """Every feature sample_random_params gates on must have a range or a
        categorical draw — a probability with nothing to draw is a typo."""
        for feature in FEATURE_PROBS:
            assert feature in PARAM_SPACE or feature in (
                "border_style",
                "quilt_stitch",
                "palette_2",
                "palette_mix",
            ), feature

    def test_start_round_records_policy_and_commit(self, tmp_path):
        import json

        ex = QuiltExplorer(str(tmp_path / "r.json"))
        ex.start_round()
        saved = json.loads((tmp_path / "r_rounds.json").read_text())
        assert saved[0]["policy"] == current_policy()
        assert "commit" in saved[0]  # None outside a git checkout, else a sha

    def test_rounds_without_policy_still_load(self, tmp_path):
        """Pre-snapshot rounds have no policy key; they must keep working."""
        import json

        (tmp_path / "r_rounds.json").write_text(
            json.dumps([{"round": 1, "label": "R1", "start_index": 0, "ts": 0}])
        )
        ex = QuiltExplorer(str(tmp_path / "r.json"))
        assert ex.start_round() == 2
        assert "policy" not in ex.rounds[0]
        assert "policy" in ex.rounds[1]


class TestSuggest:
    """Exploit picks: CLIP scores a random 30 of the palette-capped candidates.

    This is exactly R24's winning nofilter arm (the param-model shortlist it
    beat was removed), so it keeps that arm's _source label for pooling."""

    class _Clip:
        def __init__(self):
            self.calls = []

        def predict_proba(self, x):
            self.calls.append(len(x))
            p = np.linspace(0.01, 0.99, len(x))
            return np.column_stack([1 - p, p])

    @pytest.fixture
    def explorer(self, tmp_path, monkeypatch):
        import sys
        import types

        fake_clip = types.ModuleType("clip_embed")
        fake_clip.embed_images = lambda pngs: np.zeros((len(pngs), 512), dtype=np.float32)
        monkeypatch.setitem(sys.modules, "clip_embed", fake_clip)
        monkeypatch.setattr("sampler._render_small", lambda params, block_size: b"")
        ex = QuiltExplorer(str(tmp_path / "r.json"))
        ex.clip_model = self._Clip()
        return ex

    def test_exploit_scores_a_random_shortlist_of_30(self, explorer):
        pick = explorer.suggest_params(explore_prob=0.0)
        assert pick["_source"] == "exploit_clip_nofilter"
        assert explorer.clip_model.calls == [30]

    def test_exploit_never_returns_a_proven_winner(self, explorer):
        """Proven winners are explore-only injections, never exploit picks."""
        for _ in range(20):
            pick = explorer.suggest_params(explore_prob=0.0)
            assert pick["palette"] not in _PROVEN_PALETTES
            assert pick["symmetry"] not in _PROVEN_SYMMETRIES

    def test_explore_prob_one_always_explores(self, explorer):
        assert explorer.suggest_params(explore_prob=1.0)["_source"] == "explore"
        assert explorer.clip_model.calls == []

    def test_explores_until_a_clip_model_exists(self, explorer):
        explorer.clip_model = None
        assert explorer.suggest_params(explore_prob=0.0)["_source"] == "explore"

    def test_policy_records_the_random_shortlist(self):
        policy = current_policy()
        assert policy["exploit_shortlist"] == "random"
        assert "param_model" not in policy


def test_candidates_are_scored_at_the_training_render_size():
    """CLIP must judge candidates at the resolution its training embeddings
    were rendered at (until R25 it scored 8px renders against 16px training)."""
    from sampler import _CLIP_CANDIDATE_BLOCK_SIZE, _CLIP_EMBED_BLOCK_SIZE

    assert _CLIP_CANDIDATE_BLOCK_SIZE == _CLIP_EMBED_BLOCK_SIZE
    policy = current_policy()
    assert policy["clip_candidate_block_size"] == policy["clip_embed_block_size"]
