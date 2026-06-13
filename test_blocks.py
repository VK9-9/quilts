"""Tests for blocks.py — block pattern geometry and color indices."""

import random

import pytest
from blocks import BLOCK_PATTERNS, _PETAL_COLORS, _BRANCH_BROWN


@pytest.fixture(params=BLOCK_PATTERNS, ids=lambda fn: fn.__name__)
def pattern_fn(request):
    return request.param


class TestAllPatterns:
    """Properties that must hold for every block pattern."""

    def test_returns_nonempty_list(self, pattern_fn):
        patches = pattern_fn(0, 0, 100, 4)
        assert isinstance(patches, list)
        assert len(patches) > 0

    def test_patches_are_polygon_color_tuples(self, pattern_fn):
        patches = pattern_fn(0, 0, 100, 4)
        for poly, color_idx in patches:
            assert isinstance(poly, list), f"polygon should be list, got {type(poly)}"
            assert len(poly) >= 3, f"polygon needs ≥3 points, got {len(poly)}"
            for pt in poly:
                assert len(pt) == 2, f"point should be (x,y), got {pt}"

    def test_color_indices_valid(self, pattern_fn):
        n_colors = 4
        patches = pattern_fn(0, 0, 100, n_colors)
        for _, color_idx in patches:
            if isinstance(color_idx, tuple):
                # RGB tuple — each component in [0, 1]
                assert len(color_idx) == 3
                for component in color_idx:
                    assert 0.0 <= component <= 1.0
            else:
                assert 0 <= color_idx < n_colors

    def test_works_with_one_color(self, pattern_fn):
        # n_colors=1 shouldn't crash — renderer applies modulo when mapping
        patches = pattern_fn(0, 0, 100, 1)
        assert len(patches) > 0

    def test_offset_shifts_coordinates(self, pattern_fn):
        # Skip patterns with internal randomness that depends on coordinates
        if pattern_fn.__name__ in ("cherry_blossom",):
            pytest.skip("uses internal RNG affected by position")
        random.seed(42)
        patches_origin = pattern_fn(0, 0, 100, 4)
        random.seed(42)
        patches_offset = pattern_fn(50, 30, 100, 4)
        # Every point should be shifted by (50, 30)
        for (p1, _), (p2, _) in zip(patches_origin, patches_offset):
            for (x1, y1), (x2, y2) in zip(p1, p2):
                assert abs((x2 - x1) - 50) < 0.01
                assert abs((y2 - y1) - 30) < 0.01

    def test_different_sizes(self, pattern_fn):
        for size in [10, 50, 200]:
            patches = pattern_fn(0, 0, size, 4)
            assert len(patches) > 0


class TestSpecificPatterns:
    """Tests for specific pattern properties."""

    def test_nine_patch_returns_9(self):
        from blocks import nine_patch

        patches = nine_patch(0, 0, 90, 4)
        assert len(patches) == 9

    def test_pinwheel_returns_4(self):
        from blocks import pinwheel

        patches = pinwheel(0, 0, 100, 4)
        assert len(patches) == 4

    def test_diagonal_is_deterministic(self):
        from blocks import diagonal

        p1 = diagonal(0, 0, 100, 2)
        p2 = diagonal(0, 0, 100, 2)
        assert p1 == p2

    def test_half_square_triangle_has_two_patches(self):
        from blocks import half_square_triangle

        patches = half_square_triangle(0, 0, 100, 4)
        assert len(patches) == 2

    def test_cherry_blossom_uses_rgb_tuples(self):
        from blocks import cherry_blossom

        patches = cherry_blossom(0, 0, 100, 4)
        rgb_patches = [(p, c) for p, c in patches if isinstance(c, tuple)]
        assert len(rgb_patches) > 0, "cherry_blossom should use RGB tuple colors"

    def test_flying_geese_geometry(self):
        from blocks import flying_geese

        patches = flying_geese(0, 0, 90, 4)
        # 3 geese × 3 patches each = 9
        assert len(patches) == 9

    def test_star_returns_9_patches(self):
        from blocks import star

        patches = star(0, 0, 100, 4)
        assert len(patches) == 9

    def test_checkerboard_4x4_returns_24(self):
        from blocks import checkerboard_4x4

        patches = checkerboard_4x4(0, 0, 100, 4)
        # 8 solid + 8×2 split = 24
        assert len(patches) == 24


class TestBlockRegistry:
    def test_registry_not_empty(self):
        assert len(BLOCK_PATTERNS) > 0

    def test_all_entries_callable(self):
        for fn in BLOCK_PATTERNS:
            assert callable(fn)

    def test_no_duplicate_functions(self):
        assert len(BLOCK_PATTERNS) == len(set(BLOCK_PATTERNS))
