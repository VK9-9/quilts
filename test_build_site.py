"""Tests for build_site.py — family bucketing, naming, and variation sampling."""

import random

import pytest

from build_site import (
    _ENCODABLE_PALETTES,
    _SYM_NOUN,
    _chaos_band,
    _encodable,
    bucket_families,
    family_name,
    generate_variations,
    nearest_square,
    params_summary,
    representative,
    slugify,
    unique_name,
    unique_slug,
)
from layout import SYMMETRY_MODES
from quilt_id import ROWS_RANGE, decode, encode, _V2_SYMMETRY


def _params(**overrides):
    base = {
        "seed": 7,
        "palette": "ocean breeze",
        "symmetry": "partial",
        "chaos": 0.3,
        "rows": 16,
        "cols": 16,
        "n_patterns": 2,
        "n_colors": 4,
        "tile_size": 6,
        "tile_variation": 0.1,
        "border_style": "none",
        "mega_frac": 0.0,
        "plain_frac": 0.0,
    }
    base.update(overrides)
    return base


class TestChaosBands:
    @pytest.mark.parametrize(
        "chaos,band",
        [
            (0.0, "calm"),
            (0.24, "calm"),
            (0.25, "steady"),
            (0.49, "steady"),
            (0.5, "lively"),
            (0.69, "lively"),
            (0.7, "wild"),
            (1.0, "wild"),
        ],
    )
    def test_bands(self, chaos, band):
        assert _chaos_band(chaos) == band


class TestFamilyName:
    def test_every_symmetry_mode_has_a_noun(self):
        """A missing entry silently degrades to the generic "Quilt"."""
        for mode in SYMMETRY_MODES:
            assert mode in _SYM_NOUN, f"symmetry '{mode}' has no noun"

    def test_bargello_is_not_called_quilt(self):
        """All four bargello families used to be named "... Quilt"."""
        name = family_name("calm", [_params(symmetry="bargello", rows=16)])
        assert "Quilt" not in name
        assert "Waves" in name

    def test_adjective_comes_from_the_bucket_band(self):
        members = [_params(chaos=0.72)]
        assert family_name("wild", members).endswith("Mosaic")
        assert family_name("wild", members).split()[-2] == "Wild"

    def test_secondary_modifier_applied(self):
        plain = [_params(plain_frac=0.3, rows=15)]
        assert family_name("calm", plain).startswith("Spare")

    def test_no_modifier_when_nothing_qualifies(self):
        assert family_name("calm", [_params(rows=15)]) == "Calm Mosaic"


class TestBucketing:
    def test_groups_by_symmetry_and_band(self):
        liked = [
            _params(symmetry="partial", chaos=0.1),
            _params(symmetry="partial", chaos=0.2),
            _params(symmetry="partial", chaos=0.8),
            _params(symmetry="stripe", chaos=0.1),
        ]
        buckets = bucket_families(liked, 10)
        keys = {(sym, band) for sym, band, _ in buckets}
        assert keys == {("partial", "calm"), ("partial", "wild"), ("stripe", "calm")}

    def test_ranked_by_size(self):
        liked = [_params(symmetry="partial", chaos=0.1)] * 3
        liked += [_params(symmetry="stripe", chaos=0.1)]
        sizes = [len(m) for _, _, m in bucket_families(liked, 10)]
        assert sizes == sorted(sizes, reverse=True)

    def test_limits_to_n_families(self):
        liked = [_params(symmetry=s, chaos=c) for s in _V2_SYMMETRY for c in (0.1, 0.8)]
        assert len(bucket_families(liked, 4)) == 4


class TestEncodable:
    def test_accepts_a_normal_param_set(self):
        assert _encodable(_params())

    def test_rejects_unencodable_palette(self):
        assert not _encodable(_params(palette="a palette that does not exist"))

    @pytest.mark.parametrize("rows", [4, 8, 13, 22, 30])
    def test_rejects_rows_outside_the_encodable_range(self, rows):
        """_pack saturates, so these would get an ID describing another quilt."""
        assert not _encodable(_params(rows=rows))

    @pytest.mark.parametrize("rows", range(ROWS_RANGE[0], ROWS_RANGE[1] + 1))
    def test_accepts_rows_inside_the_encodable_range(self, rows):
        assert _encodable(_params(rows=rows))


class TestGenerateVariations:
    def _members(self, **overrides):
        return [_params(**overrides)]

    def test_every_variation_round_trips(self):
        rng = random.Random(0)
        for sym in ("partial", "bargello", "stripe"):
            for v in generate_variations(sym, self._members(symmetry=sym), 12, rng):
                assert _encodable(v), f"{sym} variation is not encodable: {v}"
                assert decode(encode(v))["rows"] == v["rows"]

    def test_rows_clamped_even_when_members_are_out_of_range(self):
        """Historical members can sit outside what the ID can represent."""
        rng = random.Random(1)
        members = [_params(rows=8), _params(rows=30)]
        for v in generate_variations("partial", members, 12, rng):
            assert ROWS_RANGE[0] <= v["rows"] <= ROWS_RANGE[1]
            assert v["cols"] == v["rows"]

    def test_symmetry_is_fixed_to_the_family(self):
        rng = random.Random(2)
        for v in generate_variations("bargello", self._members(symmetry="bargello"), 8, rng):
            assert v["symmetry"] == "bargello"

    def test_palette_is_not_constrained_to_the_family(self):
        """Variations deliberately vary colour for diversity."""
        rng = random.Random(3)
        seen = {v["palette"] for v in generate_variations("partial", self._members(), 30, rng)}
        assert len(seen) > 1
        assert seen <= _ENCODABLE_PALETTES

    def test_count(self):
        rng = random.Random(4)
        assert len(generate_variations("partial", self._members(), 9, rng)) == 9


class TestNaming:
    def test_nearest_square(self):
        assert nearest_square(18) == 16
        assert nearest_square(20) == 16  # 16 is 4 away, 25 is 5
        assert nearest_square(25) == 25

    def test_slugify(self):
        assert slugify("Grand Wild Waves") == "grand-wild-waves"
        assert slugify("  Spare  Calm  ") == "spare-calm"

    def test_unique_name(self):
        assert unique_name("A", set()) == "A"
        assert unique_name("A", {"A"}) == "A 2"
        assert unique_name("A", {"A", "A 2"}) == "A 3"

    def test_unique_slug(self):
        assert unique_slug("Grand Waves", set()) == "grand-waves"
        assert unique_slug("Grand Waves", {"grand-waves"}) == "grand-waves-2"


class TestMisc:
    def test_representative_picks_a_member(self):
        members = [_params(chaos=0.1), _params(chaos=0.5), _params(chaos=0.9)]
        assert representative(members) in members

    def test_params_summary_includes_optional_fields_only_when_set(self):
        assert "mega_frac" not in params_summary(_params())
        assert "mega_frac" in params_summary(_params(mega_frac=0.15))
