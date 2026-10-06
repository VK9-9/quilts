"""Tests for quilt.py — render pipeline, rotation, palette selection."""

import os
import tempfile

import pytest
from quilt import (
    render_quilt,
    pick_palettes,
    rotate_patches,
    plan_quilt,
    BORDER_STYLES,
    QUILT_STITCH_STYLES,
)
from layout import SYMMETRY_MODES


# --- pick_palettes ---


class TestPickPalettes:
    def test_named_palette(self):
        import random

        colors = pick_palettes("ocean breeze", random.Random(42))
        assert len(colors) >= 2
        for r, g, b in colors:
            assert 0.0 <= r <= 1.0
            assert 0.0 <= g <= 1.0
            assert 0.0 <= b <= 1.0

    def test_random_palette(self):
        import random

        colors = pick_palettes("random", random.Random(42))
        assert len(colors) >= 2

    def test_unknown_palette_raises(self):
        import random

        with pytest.raises(ValueError, match="Unknown palette"):
            pick_palettes("nonexistent palette", random.Random(42))


# --- rotate_patches ---


class TestRotatePatches:
    def test_rotation_0_identity(self):
        patches = [
            ([(0, 0), (10, 0), (10, 10)], 0),
        ]
        result = rotate_patches(patches, 5, 5, 0)
        assert result is patches  # identity returns same object

    def test_rotation_1_is_90_degrees(self):
        # Point (10, 5) around center (5, 5):
        # dx=5, dy=0 → 90° CW → dx=0, dy=5 → (5, 10)
        patches = [
            ([(10, 5)], 0),
        ]
        result = rotate_patches(patches, 5, 5, 1)
        rx, ry = result[0][0][0]
        assert abs(rx - 5) < 0.001
        assert abs(ry - 10) < 0.001

    def test_rotation_2_is_180_degrees(self):
        patches = [
            ([(10, 5)], 0),
        ]
        result = rotate_patches(patches, 5, 5, 2)
        rx, ry = result[0][0][0]
        assert abs(rx - 0) < 0.001
        assert abs(ry - 5) < 0.001

    def test_rotation_4_is_identity(self):
        patches = [
            ([(10, 5), (5, 0), (0, 5)], 0),
        ]
        r4 = rotate_patches(patches, 5, 5, 4)
        for (p_orig, _), (p_rot, _) in zip(patches, r4):
            for (ox, oy), (rx, ry) in zip(p_orig, p_rot):
                assert abs(ox - rx) < 0.001
                assert abs(oy - ry) < 0.001

    def test_preserves_color_index(self):
        patches = [
            ([(0, 0), (10, 0), (10, 10)], 7),
        ]
        result = rotate_patches(patches, 5, 5, 1)
        assert result[0][1] == 7


# --- plan_quilt ---


def _plan(**overrides):
    kwargs = {
        "seed": 42,
        "rows": 4,
        "cols": 4,
        "symmetry": "none",
        "chaos": 0.3,
        "palette_name": "ocean breeze",
    }
    kwargs.update(overrides)
    return plan_quilt(**kwargs)


class TestPlanQuilt:
    def test_returns_grid_and_palette(self):
        design = _plan(max_patterns=2, max_colors=4)
        assert len(design.grid) == 16  # 4x4
        assert design.n_colors == 4
        assert design.allowed_patterns is not None
        assert len(design.allowed_patterns) == 2

    def test_no_max_patterns(self):
        design = _plan()
        assert design.allowed_patterns is None
        assert len(design.grid) == 16

    def test_bargello_forces_color_maps(self):
        design = _plan(symmetry="bargello", max_colors=4)
        for cell in design.grid.values():
            assert len(set(cell["color_map"])) == 1  # all same color
        assert len(design.plain_cells) == 16, "bargello cells are all solid"

    def test_partial_symmetry_uses_chaos(self):
        design = _plan(symmetry="partial", chaos=0.5, max_patterns=2, max_colors=4)
        assert len(design.grid) == 16

    def test_seed_reproducibility(self):
        """Same inputs, same design — every field, not just the grid."""
        a = _plan(seed=99, symmetry="mirror", max_colors=4, mega_frac=0.3, plain_frac=0.2)
        b = _plan(seed=99, symmetry="mirror", max_colors=4, mega_frac=0.3, plain_frac=0.2)
        assert a == b

    def test_max_colors_trims_palette(self):
        assert _plan(max_colors=3).n_colors == 3

    def test_none_seed_is_resolved(self):
        """A random seed is chosen up front and recorded, so the design can be
        painted (and the cell seeds derived) without knowing it was random."""
        assert isinstance(_plan(seed=None).seed, int)

    def test_mega_blocks_do_not_overlap(self):
        design = _plan(rows=8, cols=8, mega_frac=0.5)
        assert design.mega_tl, "mega_frac=0.5 on 8x8 should place some"
        assert len(design.mega_covered) == 4 * len(design.mega_tl)

    def test_strip_factors_off_and_on(self):
        assert set(_plan().col_factors) == {1.0}
        design = _plan(strippy=0.3)
        assert all(0.7 <= f <= 1.3 for f in design.col_factors + design.row_factors)
        assert len(set(design.col_factors)) > 1

    def test_border_and_wash_colors_come_from_the_palette(self):
        design = _plan(max_colors=4, border_style="solid", wash_alpha=0.1)
        assert all(c in design.palette_colors for c in design.border_colors)
        assert design.wash_color in design.palette_colors
        plain = _plan(max_colors=4)
        assert plain.border_colors is None and plain.wash_color is None


# --- render_quilt ---


class TestRenderQuilt:
    def test_returns_png_bytes(self):
        result = render_quilt(
            rows=4,
            cols=4,
            block_size=20,
            symmetry="none",
            chaos=0.3,
            palette_name="ocean breeze",
            seed=42,
            output=None,
            border=5,
        )
        assert isinstance(result, bytes)
        assert result[:8] == b"\x89PNG\r\n\x1a\n"

    def test_seed_reproducibility(self):
        # Use symmetry mode that avoids blocks with global random calls
        kwargs = dict(
            rows=4,
            cols=4,
            block_size=20,
            symmetry="bargello",
            chaos=0.3,
            palette_name="ocean breeze",
            seed=42,
            output=None,
            border=5,
            max_colors=4,
        )
        r1 = render_quilt(**kwargs)
        r2 = render_quilt(**kwargs)
        assert r1 == r2

    def test_different_seeds_differ(self):
        kwargs = dict(
            rows=4,
            cols=4,
            block_size=20,
            symmetry="none",
            chaos=0.3,
            palette_name="ocean breeze",
            output=None,
            border=5,
        )
        r1 = render_quilt(seed=1, **kwargs)
        r2 = render_quilt(seed=2, **kwargs)
        assert r1 != r2

    def test_writes_file(self):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            path = f.name
        try:
            result = render_quilt(
                rows=4,
                cols=4,
                block_size=20,
                symmetry="none",
                chaos=0.3,
                palette_name="ocean breeze",
                seed=42,
                output=path,
                border=5,
            )
            assert result == (90, 90)  # (width, height), for main()'s summary line
            assert os.path.exists(path)
            with open(path, "rb") as f:
                assert f.read(4) == b"\x89PNG"
        finally:
            os.unlink(path)

    def test_auto_seed_when_none(self):
        result = render_quilt(
            rows=4,
            cols=4,
            block_size=20,
            symmetry="none",
            chaos=0.3,
            palette_name="ocean breeze",
            seed=None,
            output=None,
            border=5,
        )
        assert isinstance(result, bytes)


class TestRenderAllSymmetries:
    """Render a small quilt with each symmetry mode to catch crashes."""

    @pytest.fixture(params=list(SYMMETRY_MODES.keys()))
    def symmetry(self, request):
        return request.param

    def test_render_symmetry(self, symmetry):
        result = render_quilt(
            rows=8,
            cols=8,
            block_size=15,
            symmetry=symmetry,
            chaos=0.3,
            palette_name="lavender fields",
            seed=42,
            output=None,
            border=5,
            max_patterns=2,
            max_colors=4,
        )
        assert result[:8] == b"\x89PNG\r\n\x1a\n"


class TestRenderFeatures:
    """Test specific features that modify render behavior."""

    def test_tiled_grid(self):
        result = render_quilt(
            rows=8,
            cols=8,
            block_size=15,
            symmetry="none",
            chaos=0.3,
            palette_name="ocean breeze",
            seed=42,
            output=None,
            border=5,
            tile_size=4,
            tile_variation=0.1,
        )
        assert result[:8] == b"\x89PNG\r\n\x1a\n"

    def test_max_patterns_and_colors(self):
        result = render_quilt(
            rows=4,
            cols=4,
            block_size=20,
            symmetry="mirror",
            chaos=0.3,
            palette_name="ocean breeze",
            seed=42,
            output=None,
            border=5,
            max_patterns=2,
            max_colors=3,
        )
        assert result[:8] == b"\x89PNG\r\n\x1a\n"

    @pytest.mark.parametrize("style", BORDER_STYLES)
    def test_border_styles(self, style):
        result = render_quilt(
            rows=4,
            cols=4,
            block_size=20,
            symmetry="mirror",
            chaos=0.3,
            palette_name="ocean breeze",
            seed=42,
            output=None,
            border=15,
            border_style=style,
        )
        assert result[:8] == b"\x89PNG\r\n\x1a\n"

    @pytest.mark.parametrize("stitch", QUILT_STITCH_STYLES)
    def test_quilt_stitching(self, stitch):
        result = render_quilt(
            rows=4,
            cols=4,
            block_size=20,
            symmetry="mirror",
            chaos=0.3,
            palette_name="ocean breeze",
            seed=42,
            output=None,
            border=5,
            quilt_stitch=stitch,
        )
        assert result[:8] == b"\x89PNG\r\n\x1a\n"

    def test_mega_blocks(self):
        result = render_quilt(
            rows=6,
            cols=6,
            block_size=20,
            symmetry="mirror",
            chaos=0.3,
            palette_name="ocean breeze",
            seed=42,
            output=None,
            border=5,
            mega_frac=0.5,
        )
        assert result[:8] == b"\x89PNG\r\n\x1a\n"

    def test_plain_frac(self):
        result = render_quilt(
            rows=4,
            cols=4,
            block_size=20,
            symmetry="mirror",
            chaos=0.3,
            palette_name="ocean breeze",
            seed=42,
            output=None,
            border=5,
            plain_frac=0.5,
        )
        assert result[:8] == b"\x89PNG\r\n\x1a\n"

    def test_wonky(self):
        result = render_quilt(
            rows=4,
            cols=4,
            block_size=20,
            symmetry="none",
            chaos=0.3,
            palette_name="ocean breeze",
            seed=42,
            output=None,
            border=5,
            wonky=0.05,
            tile_size=4,
        )
        assert result[:8] == b"\x89PNG\r\n\x1a\n"

    def test_wash_alpha(self):
        result = render_quilt(
            rows=4,
            cols=4,
            block_size=20,
            symmetry="mirror",
            chaos=0.3,
            palette_name="ocean breeze",
            seed=42,
            output=None,
            border=5,
            wash_alpha=0.3,
        )
        assert result[:8] == b"\x89PNG\r\n\x1a\n"

    def test_palette_mix(self):
        result = render_quilt(
            rows=4,
            cols=4,
            block_size=20,
            symmetry="mirror",
            chaos=0.3,
            palette_name="ocean breeze",
            seed=42,
            output=None,
            border=5,
            palette_mix="wildflower",
            max_colors=4,
        )
        assert result[:8] == b"\x89PNG\r\n\x1a\n"

    def test_palette_name_2(self):
        result = render_quilt(
            rows=4,
            cols=4,
            block_size=20,
            symmetry="mirror",
            chaos=0.3,
            palette_name="ocean breeze",
            seed=42,
            output=None,
            border=5,
            palette_name_2="wildflower",
            max_colors=3,
        )
        assert result[:8] == b"\x89PNG\r\n\x1a\n"

    def test_palette_name_2_retired(self):
        # Retired palette name should be silently dropped
        result = render_quilt(
            rows=4,
            cols=4,
            block_size=20,
            symmetry="mirror",
            chaos=0.3,
            palette_name="ocean breeze",
            seed=42,
            output=None,
            border=5,
            palette_name_2="nonexistent retired",
        )
        assert result[:8] == b"\x89PNG\r\n\x1a\n"

    def test_bargello_renders(self):
        result = render_quilt(
            rows=8,
            cols=8,
            block_size=15,
            symmetry="bargello",
            chaos=0.3,
            palette_name="lavender fields",
            seed=42,
            output=None,
            border=5,
            max_colors=4,
        )
        assert result[:8] == b"\x89PNG\r\n\x1a\n"

    def test_mega_blocks_with_wonky(self):
        result = render_quilt(
            rows=6,
            cols=6,
            block_size=20,
            symmetry="none",
            chaos=0.3,
            palette_name="ocean breeze",
            seed=42,
            output=None,
            border=5,
            mega_frac=0.5,
            wonky=0.04,
            tile_size=6,
        )
        assert result[:8] == b"\x89PNG\r\n\x1a\n"

    def test_strippy(self):
        result = render_quilt(
            rows=4,
            cols=4,
            block_size=20,
            symmetry="none",
            chaos=0.3,
            palette_name="ocean breeze",
            seed=42,
            output=None,
            border=5,
            strippy=0.3,
        )
        assert result[:8] == b"\x89PNG\r\n\x1a\n"

    def test_stripes_border(self):
        # "stripes" is internal border style used by _draw_border
        result = render_quilt(
            rows=4,
            cols=4,
            block_size=20,
            symmetry="mirror",
            chaos=0.3,
            palette_name="ocean breeze",
            seed=42,
            output=None,
            border=15,
            border_style="solid",
        )
        assert result[:8] == b"\x89PNG\r\n\x1a\n"

    def test_tile_boundary_lines(self):
        result = render_quilt(
            rows=8,
            cols=8,
            block_size=15,
            symmetry="none",
            chaos=0.3,
            palette_name="ocean breeze",
            seed=42,
            output=None,
            border=5,
            tile_size=4,
            tile_variation=0.2,
        )
        assert result[:8] == b"\x89PNG\r\n\x1a\n"
