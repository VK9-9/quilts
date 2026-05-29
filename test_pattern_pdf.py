"""Tests for pattern_pdf.py — PDF sewing pattern generation."""
import math
import os
import tempfile

import pytest

from pattern_pdf import (
    _color_label,
    _human_color_name,
    _pick_palette_colors,
    _reconstruct_layout,
    _canonicalize_polygon,
    _shape_signature,
    _extract_unique_blocks,
    _rotate_polygons,
    _edge_lengths_inches,
    _label_position,
    _polygon_area_signed,
    _is_convex,
    _offset_polygon,
    _line_intersection,
    _try_layout_pieces,
    _FooterCanvas,
    generate_pattern_pdf,
)


# ---------------------------------------------------------------------------
# Minimal params fixture
# ---------------------------------------------------------------------------

def _base_params(**overrides):
    p = {
        "seed": 42, "rows": 4, "cols": 4, "symmetry": "rotational",
        "chaos": 0.3, "palette": "ocean breeze", "n_patterns": 2,
        "n_colors": 4, "tile_size": 6, "tile_variation": 0.1,
        "border_style": "none", "quilt_stitch": "grid",
    }
    p.update(overrides)
    return p


# ---------------------------------------------------------------------------
# Unit tests: pure functions
# ---------------------------------------------------------------------------

class TestColorLabel:
    def test_first_labels(self):
        assert _color_label(0) == "A"
        assert _color_label(1) == "B"
        assert _color_label(25) == "Z"


class TestHumanColorName:
    def test_white(self):
        assert _human_color_name("#FFFFFF") == "white"

    def test_black(self):
        assert _human_color_name("#000000") == "black"

    def test_red(self):
        name = _human_color_name("#FF0000")
        assert "red" in name

    def test_green(self):
        name = _human_color_name("#00FF00")
        assert "green" in name

    def test_blue(self):
        name = _human_color_name("#0000FF")
        assert "blue" in name

    def test_grey(self):
        name = _human_color_name("#808080")
        assert "grey" in name

    def test_orange(self):
        name = _human_color_name("#FF8800")
        assert "orange" in name or "brown" in name

    def test_purple(self):
        name = _human_color_name("#8800FF")
        assert "purple" in name

    def test_teal(self):
        name = _human_color_name("#008888")
        assert "teal" in name

    def test_magenta(self):
        name = _human_color_name("#FF00CC")
        assert "magenta" in name or "red" in name

    def test_dark_prefix(self):
        name = _human_color_name("#882222")
        assert "dark" in name

    def test_light_prefix(self):
        name = _human_color_name("#FFCCCC")
        assert "light" in name or "white" in name


class TestPickPaletteColors:
    def test_known_palette(self):
        import random
        colors = _pick_palette_colors("ocean breeze", 4, random.Random(42))
        assert len(colors) == 4
        assert all(c.startswith("#") for c in colors)

    def test_full_palette(self):
        import random
        colors = _pick_palette_colors("ocean breeze", None, random.Random(42))
        assert len(colors) >= 4

    def test_unknown_palette_fallback(self):
        import random
        colors = _pick_palette_colors("nonexistent", 4, random.Random(42))
        assert len(colors) == 4


class TestReconstructLayout:
    def test_returns_grid_and_palette(self):
        grid, allowed, palette = _reconstruct_layout(_base_params())
        assert len(grid) == 16  # 4×4
        assert isinstance(palette, list)
        assert len(palette) == 4


class TestCanonicalizePolygon:
    def test_square(self):
        sq = [(0, 0), (10, 0), (10, 10), (0, 10)]
        canon = _canonicalize_polygon(sq)
        assert len(canon) == 4

    def test_rotation_invariant(self):
        sq1 = [(0, 0), (10, 0), (10, 10), (0, 10)]
        sq2 = [(10, 0), (10, 10), (0, 10), (0, 0)]
        assert _canonicalize_polygon(sq1) == _canonicalize_polygon(sq2)

    def test_winding_invariant(self):
        cw = [(0, 0), (10, 0), (10, 10), (0, 10)]
        ccw = list(reversed(cw))
        assert _canonicalize_polygon(cw) == _canonicalize_polygon(ccw)


class TestShapeSignature:
    def test_same_shapes_same_sig(self):
        polys1 = [([(0, 0), (10, 0), (10, 10)], 0)]
        polys2 = [([(0, 0), (10, 0), (10, 10)], 1)]  # diff color, same shape
        assert _shape_signature(polys1) == _shape_signature(polys2)

    def test_diff_shapes_diff_sig(self):
        tri = [([(0, 0), (10, 0), (10, 10)], 0)]
        sq = [([(0, 0), (10, 0), (10, 10), (0, 10)], 0)]
        assert _shape_signature(tri) != _shape_signature(sq)


class TestRotatePolygons:
    def test_identity(self):
        polys = [([(0, 0), (10, 0), (10, 10)], 0)]
        assert _rotate_polygons(polys, 0, 10) is polys

    def test_90_degrees(self):
        # Point (10, 5) around center (5, 5): dx=5, dy=0 → 90° → dx=0, dy=5 → (5, 10)
        polys = [([(10, 5)], 0)]
        result = _rotate_polygons(polys, 1, 10)
        rx, ry = result[0][0][0]
        assert abs(rx - 5) < 0.001
        assert abs(ry - 10) < 0.001


class TestExtractUniqueBlocks:
    def test_groups_by_shape(self):
        params = _base_params()
        grid, _, palette = _reconstruct_layout(params)
        blocks = _extract_unique_blocks(grid, len(palette))
        assert len(blocks) >= 1
        total = sum(b["count"] for b in blocks)
        assert total == 16  # 4×4


class TestEdgeLengths:
    def test_unit_square(self):
        sq = [(0, 0), (100, 0), (100, 100), (0, 100)]
        lengths = _edge_lengths_inches(sq, 0.06, 0.06)
        assert len(lengths) == 4
        for l in lengths:
            assert abs(l - 6.0) < 0.01

    def test_right_triangle(self):
        tri = [(0, 0), (100, 0), (0, 100)]
        lengths = _edge_lengths_inches(tri, 0.06, 0.06)
        assert len(lengths) == 3
        assert abs(lengths[0] - 6.0) < 0.01  # base
        assert abs(lengths[2] - 6.0) < 0.01  # height
        assert abs(lengths[1] - 6.0 * math.sqrt(2)) < 0.01  # hyp


class TestLabelPosition:
    def test_returns_offset_from_center(self):
        pts = [(0, 0), (100, 0), (100, 100), (0, 100)]
        lx, ly = _label_position(pts, 0, 4, 50, 50)
        # edge 0 midpoint is (50, 0), center is (50, 50)
        # offset direction is (0, -1), so label at (50, -9-2)
        assert abs(lx - 50) < 0.1
        assert ly < 0  # above the edge (negative y direction)


class TestPolygonAreaSigned:
    def test_ccw_positive(self):
        ccw = [(0, 0), (10, 0), (10, 10), (0, 10)]
        assert _polygon_area_signed(ccw) > 0

    def test_cw_negative(self):
        cw = [(0, 0), (0, 10), (10, 10), (10, 0)]
        assert _polygon_area_signed(cw) < 0


class TestIsConvex:
    def test_square_convex(self):
        assert _is_convex([(0, 0), (10, 0), (10, 10), (0, 10)])

    def test_l_shape_not_convex(self):
        assert not _is_convex([(0, 0), (10, 0), (10, 5), (5, 5), (5, 10), (0, 10)])

    def test_triangle_convex(self):
        assert _is_convex([(0, 0), (10, 0), (5, 10)])

    def test_degenerate(self):
        assert _is_convex([(0, 0), (5, 0)])  # < 3 points


class TestOffsetPolygon:
    def test_square_shrinks_with_positive_offset(self):
        sq = [(0, 0), (10, 0), (10, 10), (0, 10)]
        result = _offset_polygon(sq, 1.0)
        xs = [p[0] for p in result]
        w = max(xs) - min(xs)
        assert w < 10  # inset

    def test_square_grows_with_negative_offset(self):
        sq = [(0, 0), (10, 0), (10, 10), (0, 10)]
        result = _offset_polygon(sq, -1.0)
        xs = [p[0] for p in result]
        w = max(xs) - min(xs)
        assert w > 10  # expanded

    def test_degenerate(self):
        assert _offset_polygon([(0, 0)], 1.0) == [(0, 0)]

    def test_triangle(self):
        tri = [(0, 0), (10, 0), (5, 10)]
        result = _offset_polygon(tri, 0.5)
        assert len(result) >= 3

    def test_concave_polygon(self):
        # L-shape has a reflex angle → bevel join
        l_shape = [(0, 0), (10, 0), (10, 5), (5, 5), (5, 10), (0, 10)]
        result = _offset_polygon(l_shape, 0.5)
        assert len(result) >= 6  # bevel adds extra vertices


class TestLineIntersection:
    def test_perpendicular(self):
        pt = _line_intersection(0, 5, 10, 5, 5, 0, 5, 10)
        assert pt is not None
        assert abs(pt[0] - 5) < 0.01
        assert abs(pt[1] - 5) < 0.01

    def test_parallel_returns_none(self):
        pt = _line_intersection(0, 0, 10, 0, 0, 5, 10, 5)
        assert pt is None


class TestTryLayoutPieces:
    def test_fits(self):
        # bboxes are (width, height, offset_x, offset_y)
        bboxes = [(50, 50, 0, 0), (50, 50, 0, 0)]
        result = _try_layout_pieces(bboxes, 1.0, 500, 500, 10)
        assert result is True

    def test_too_small(self):
        bboxes = [(500, 500, 0, 0)] * 10
        result = _try_layout_pieces(bboxes, 1.0, 100, 100, 10)
        assert result is None


class TestFooterCanvas:
    def test_creates_pdf(self):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            path = f.name
        try:
            c = _FooterCanvas(path, quilt_id="TEST123")
            c.setFont("Helvetica", 12)
            c.drawString(72, 700, "Test page")
            c.showPage()
            c.save()
            assert os.path.exists(path)
            with open(path, "rb") as f:
                assert f.read(5) == b"%PDF-"
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# End-to-end tests: generate_pattern_pdf
# ---------------------------------------------------------------------------

class TestGeneratePatternPdf:

    def _gen(self, params, **kwargs):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            path = f.name
        try:
            result = generate_pattern_pdf(params, path, **kwargs)
            assert result == path
            assert os.path.exists(path)
            with open(path, "rb") as f:
                data = f.read()
            assert data[:5] == b"%PDF-"
            return data
        finally:
            os.unlink(path)

    def test_rotational(self):
        self._gen(_base_params(symmetry="rotational"))

    def test_mirror(self):
        self._gen(_base_params(symmetry="mirror"))

    def test_bargello(self):
        self._gen(_base_params(symmetry="bargello"))

    def test_stripe(self):
        self._gen(_base_params(symmetry="stripe"))

    def test_none(self):
        self._gen(_base_params(symmetry="none"))

    def test_flower(self):
        self._gen(_base_params(symmetry="flower", rows=6, cols=6))

    def test_custom_quilt_size(self):
        self._gen(_base_params(), quilt_w=50, quilt_h=65)

    def test_square_default(self):
        self._gen(_base_params(), quilt_w=72)

    def test_seam_allowance(self):
        self._gen(_base_params(), seam_allowance=0.5)

    def test_different_blocks(self):
        # seed that produces different block patterns
        self._gen(_base_params(seed=99, rows=6, cols=6, n_patterns=2))

    def test_larger_grid(self):
        self._gen(_base_params(rows=8, cols=8))

    def test_no_stitch(self):
        self._gen(_base_params(quilt_stitch=None))

    def test_partial_symmetry(self):
        self._gen(_base_params(symmetry="partial", chaos=0.5))

    def test_emergent_symmetry(self):
        self._gen(_base_params(symmetry="emergent"))

    def test_columns_symmetry(self):
        self._gen(_base_params(symmetry="columns"))

    def test_border_style_solid(self):
        self._gen(_base_params(border_style="solid"))
