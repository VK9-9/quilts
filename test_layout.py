"""Tests for layout.py — symmetry modes and grid generation."""
import random

import pytest
from layout import (
    SYMMETRY_MODES, layout_none, layout_mirror4, layout_rotational,
    layout_stripe, layout_partial, layout_flower, layout_emergent,
    layout_bargello,
)

ROWS, COLS = 16, 16
N_PATTERNS, N_PALETTES = 4, 2


def _make_grid(fn, rows=ROWS, cols=COLS, seed=42, **kwargs):
    rng = random.Random(seed)
    return fn(rows, cols, N_PATTERNS, N_PALETTES, rng, **kwargs)


# --- Properties that hold for all modes ---

@pytest.fixture(params=list(SYMMETRY_MODES.items()), ids=lambda x: x[0])
def mode_and_fn(request):
    return request.param


class TestAllModes:

    def test_grid_has_all_cells(self, mode_and_fn):
        name, fn = mode_and_fn
        kwargs = {"chaos": 0.3} if name == "partial" else {}
        grid = _make_grid(fn, **kwargs)
        for r in range(ROWS):
            for c in range(COLS):
                assert (r, c) in grid, f"Missing cell ({r},{c}) in {name}"

    def test_grid_size(self, mode_and_fn):
        name, fn = mode_and_fn
        kwargs = {"chaos": 0.3} if name == "partial" else {}
        grid = _make_grid(fn, **kwargs)
        assert len(grid) == ROWS * COLS

    def test_cells_have_required_keys(self, mode_and_fn):
        name, fn = mode_and_fn
        kwargs = {"chaos": 0.3} if name == "partial" else {}
        grid = _make_grid(fn, **kwargs)
        for (r, c), cell in grid.items():
            assert "pattern" in cell
            assert "palette" in cell
            assert "rotation" in cell

    def test_rotation_in_range(self, mode_and_fn):
        name, fn = mode_and_fn
        kwargs = {"chaos": 0.3} if name == "partial" else {}
        grid = _make_grid(fn, **kwargs)
        for cell in grid.values():
            assert 0 <= cell["rotation"] <= 3

    def test_deterministic_with_seed(self, mode_and_fn):
        name, fn = mode_and_fn
        kwargs = {"chaos": 0.3} if name == "partial" else {}
        g1 = _make_grid(fn, seed=99, **kwargs)
        g2 = _make_grid(fn, seed=99, **kwargs)
        for key in g1:
            assert g1[key] == g2[key]

    def test_different_seeds_differ(self, mode_and_fn):
        name, fn = mode_and_fn
        kwargs = {"chaos": 0.3} if name == "partial" else {}
        g1 = _make_grid(fn, seed=1, **kwargs)
        g2 = _make_grid(fn, seed=2, **kwargs)
        # At least some cells should differ
        diffs = sum(1 for k in g1 if g1[k] != g2[k])
        assert diffs > 0

    def test_odd_dimensions(self, mode_and_fn):
        name, fn = mode_and_fn
        kwargs = {"chaos": 0.3} if name == "partial" else {}
        grid = _make_grid(fn, rows=15, cols=17, **kwargs)
        assert len(grid) == 15 * 17


# --- Mode-specific tests ---

class TestMirror4:

    def test_horizontal_symmetry(self):
        grid = _make_grid(layout_mirror4)
        for r in range(ROWS):
            for c in range(COLS):
                mirrored_c = COLS - 1 - c
                assert grid[(r, c)]["pattern"] == grid[(r, mirrored_c)]["pattern"]
                assert grid[(r, c)]["palette"] == grid[(r, mirrored_c)]["palette"]

    def test_vertical_symmetry(self):
        grid = _make_grid(layout_mirror4)
        for r in range(ROWS):
            for c in range(COLS):
                mirrored_r = ROWS - 1 - r
                assert grid[(r, c)]["pattern"] == grid[(mirrored_r, c)]["pattern"]


class TestRotational:

    def test_quadrants_share_pattern(self):
        grid = _make_grid(layout_rotational)
        # Top-left and bottom-right should use same pattern (180° rotation)
        for r in range(ROWS // 2):
            for c in range(COLS // 2):
                tl = grid[(r, c)]
                br = grid[(ROWS - 1 - r, COLS - 1 - c)]
                assert tl["pattern"] == br["pattern"]

    def test_rotation_offsets(self):
        grid = _make_grid(layout_rotational)
        # Cell (0,0) and (0, COLS-1) should differ in rotation by 1
        r0c0 = grid[(0, 0)]
        r0cn = grid[(0, COLS - 1)]
        assert r0c0["pattern"] == r0cn["pattern"]
        assert (r0cn["rotation"] - r0c0["rotation"]) % 4 == 1


class TestStripe:

    def test_top_bottom_mirror(self):
        grid = _make_grid(layout_stripe)
        for r in range(ROWS // 2):
            for c in range(COLS):
                top = grid[(r, c)]
                bot = grid[(ROWS - 1 - r, c)]
                assert top["pattern"] == bot["pattern"]
                assert top["palette"] == bot["palette"]


class TestPartial:

    def test_chaos_zero_is_mirror(self):
        g_mirror = _make_grid(layout_mirror4, seed=42)
        g_partial = _make_grid(layout_partial, seed=42, chaos=0.0)
        # With chaos=0, partial should equal mirror4 (no perturbation)
        for key in g_mirror:
            assert g_mirror[key] == g_partial[key]

    def test_high_chaos_differs_from_mirror(self):
        g_mirror = _make_grid(layout_mirror4, seed=42)
        g_partial = _make_grid(layout_partial, seed=42, chaos=0.9)
        diffs = sum(1 for k in g_mirror if g_mirror[k] != g_partial[k])
        assert diffs > 0


class TestFlower:

    def test_has_two_patterns(self):
        grid = _make_grid(layout_flower)
        patterns = {cell["pattern"] for cell in grid.values()}
        assert len(patterns) == 2

    def test_all_cells_filled(self):
        grid = _make_grid(layout_flower)
        assert len(grid) == ROWS * COLS

    def test_single_pattern(self):
        rng = random.Random(42)
        grid = layout_flower(16, 16, 1, 2, rng)
        patterns = {cell["pattern"] for cell in grid.values()}
        assert patterns == {0}


class TestEmergent:

    def test_single_pattern(self):
        grid = _make_grid(layout_emergent)
        patterns = {cell["pattern"] for cell in grid.values()}
        assert len(patterns) == 1

    def test_single_palette(self):
        grid = _make_grid(layout_emergent)
        palettes = {cell["palette"] for cell in grid.values()}
        assert len(palettes) == 1

    def test_all_macro_templates_reachable(self):
        """Sweep seeds to ensure all 4 emergent macros get exercised."""
        macros_hit = set()
        for seed in range(100):
            rng = random.Random(seed)
            grid = layout_emergent(8, 8, 2, 2, rng)
            # Infer macro from rotation pattern
            rotations = [grid[(r, c)]["rotation"] for r in range(8) for c in range(8)]
            macros_hit.add(tuple(rotations))
            if len(macros_hit) >= 4:
                break
        assert len(macros_hit) >= 4, "Not all emergent macros were reached"


class TestBargello:

    def test_has_bargello_color(self):
        grid = _make_grid(layout_bargello)
        for cell in grid.values():
            assert "_bargello_color" in cell

    def test_zero_rotation(self):
        grid = _make_grid(layout_bargello)
        for cell in grid.values():
            assert cell["rotation"] == 0

    def test_wave_pattern_varies_by_column(self):
        grid = _make_grid(layout_bargello)
        # Different columns should have different color shifts
        col_colors = {}
        for (r, c), cell in grid.items():
            col_colors.setdefault(c, []).append(cell["_bargello_color"])
        # At least 2 columns should have different color patterns
        unique = {tuple(v) for v in col_colors.values()}
        assert len(unique) > 1


class TestSymmetryModeRegistry:

    def test_all_modes_present(self):
        expected = {"none", "mirror", "rotational", "stripe", "partial",
                    "flower", "emergent", "bargello", "columns"}
        assert set(SYMMETRY_MODES.keys()) == expected

    def test_all_modes_callable(self):
        for fn in SYMMETRY_MODES.values():
            assert callable(fn)
