"""Tests for pattern_pdf.py — PDF sewing pattern generation."""

import math
import os
import tempfile

import pytest

from pattern_pdf import (
    _color_label,
    _human_color_name,
    _design_for,
    _hex_palette,
    _extract_unique_blocks,
    _block_key,
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
        "seed": 42,
        "rows": 4,
        "cols": 4,
        "symmetry": "rotational",
        "chaos": 0.3,
        "palette": "ocean breeze",
        "n_patterns": 2,
        "n_colors": 4,
        "tile_size": 6,
        "tile_variation": 0.1,
        "border_style": "none",
        "quilt_stitch": "grid",
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


class TestDesignFor:
    def test_returns_grid_and_palette(self):
        design = _design_for(_base_params())
        assert len(design.grid) == 16  # 4×4
        palette = _hex_palette(design)
        assert len(palette) == 4
        assert all(c.startswith("#") for c in palette)

    def test_fills_defaults_for_partial_params(self):
        design = _design_for({"seed": 1, "rows": 4, "symmetry": "mirror", "palette": "thistle"})
        assert design.cols == 4
        assert design.n_colors == 4


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


def _painted_key(design, r, c, mega):
    """The block at (r, c) exactly as the painter draws it, colors as hex."""
    from palettes import rgb_to_hex
    from quilt import cell_patches, patch_rgb

    cell = design.grid[(r, c)]
    palette = design.palettes[cell.get("palette", 0) % len(design.palettes)]
    if not mega and (r, c) in design.plain_cells:
        fill = rgb_to_hex(palette[cell["color_map"][0]])
        pieces = [([(0, 0), (100, 0), (100, 100), (0, 100)], fill)]
    else:
        pieces = [
            (
                poly,
                ci
                if isinstance(ci, tuple)
                else rgb_to_hex(patch_rgb(ci, cell["color_map"], palette, design.n_colors)),
            )
            for poly, ci in cell_patches(design, r, c, 100, mega=mega)
        ]
    return _block_key(pieces)


def _assert_pdf_describes_every_cell(params):
    """Each placement, drawn as the PDF instructs (the design's reference
    rotated by the labelled turns, in the listed fabrics), must be the block
    the painter draws in that cell."""
    design = _design_for(params)
    blocks, placements, fabrics = _extract_unique_blocks(design)
    for (r, c), (blk, turn) in placements.items():
        described = [
            (poly, color if isinstance(color, tuple) else fabrics[color])
            for poly, color in _rotate_polygons(blk["ref"], turn, 100)
        ]
        # pytest.fail, not a bare assert: on failure pytest would diff these
        # large nested tuples, which takes minutes and looks like a hang.
        if _block_key(described) != _painted_key(design, r, c, blk["span"] == 2):
            pytest.fail(
                f"cell {(r, c)}: PDF says design {blk['pattern_name']} turned "
                f"{turn * 90}°, which is not what the render draws there"
            )
    placed_area = sum(blk["span"] ** 2 for blk, _ in placements.values())
    assert placed_area == design.rows * design.cols, "every cell covered exactly once"
    return blocks, fabrics


class TestExtractUniqueBlocks:
    def test_groups_by_shape(self):
        blocks, _fabrics = _assert_pdf_describes_every_cell(_base_params())
        assert sum(b["count"] for b in blocks) == 16  # 4×4

    def test_different_blocks_with_the_same_piece_shapes_stay_separate(self):
        """bow_tie and pinwheel are both four equal triangles; grouping by piece
        shapes merged them, so the PDF said to sew every block as one of them.
        These are the "Flower — Medallion" preset's params."""
        params = _base_params(
            rows=16, cols=16, symmetry="flower", palette="cherry blossom", seed=1006
        )
        blocks, _ = _assert_pdf_describes_every_cell(params)
        names = {b["pattern_name"] for b in blocks}
        assert {"bow_tie", "pinwheel"} <= names

    def test_second_palette_colors_are_listed_and_used(self):
        """palette_2 cells draw from the second palette; the color key used to
        list only the primary, mislabelling ~half the quilt's pieces."""
        params = _base_params(
            rows=16, cols=16, symmetry="partial", palette_2="wildflower", seed=2003
        )
        blocks, fabrics = _assert_pdf_describes_every_cell(params)
        assert len(fabrics) > 4
        used = {col for b in blocks for _p, col in b["polygons"] if not isinstance(col, tuple)}
        assert max(used) >= 4, "no piece is cut from a second-palette fabric"

    @pytest.mark.parametrize("seed", range(1, 40))
    def test_half_square_triangle_orientation_matches_render(self, seed):
        """Each HST cell draws its diagonal from its own seed; the PDF used one
        fixed representative, so ~45% of HST turn labels were wrong."""
        params = _base_params(rows=8, cols=8, symmetry="mirror", seed=seed)
        _assert_pdf_describes_every_cell(params)

    def test_plain_cells_and_mega_blocks(self):
        params = _base_params(
            rows=12, cols=12, symmetry="partial", plain_frac=0.2, mega_frac=0.3, seed=77
        )
        blocks, _ = _assert_pdf_describes_every_cell(params)
        kinds = {(b["kind"], b["span"]) for b in blocks}
        assert ("plain", 1) in kinds
        assert ("block", 2) in kinds

    def test_palette_mix(self):
        params = _base_params(rows=12, cols=12, palette_mix="honey oak", seed=5)
        _assert_pdf_describes_every_cell(params)


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


def test_generate_leaves_no_temp_files(tmp_path):
    """The cover render goes to a NamedTemporaryFile(delete=False).

    Nothing reclaimed it, so /pattern leaked one PNG per request on a
    long-lived worker.
    """
    import glob
    import tempfile

    params = {
        "seed": 42,
        "rows": 6,
        "cols": 6,
        "symmetry": "rotational",
        "chaos": 0.3,
        "palette": "ocean breeze",
        "n_patterns": 2,
        "n_colors": 4,
        "tile_size": 6,
        "quilt_stitch": "grid",
    }
    pattern = os.path.join(tempfile.gettempdir(), "*.png")
    before = set(glob.glob(pattern))
    generate_pattern_pdf(params, str(tmp_path / "out.pdf"))
    assert not set(glob.glob(pattern)) - before, "generate_pattern_pdf leaked a temp PNG"


def test_generate_cleans_up_even_on_failure(tmp_path):
    import glob
    import tempfile

    pattern = os.path.join(tempfile.gettempdir(), "*.png")
    before = set(glob.glob(pattern))
    with pytest.raises((KeyError, TypeError, ValueError)):
        generate_pattern_pdf({"seed": 1, "rows": 6, "palette": "ocean breeze"}, str(tmp_path / "x"))
    assert not set(glob.glob(pattern)) - before


def test_cover_image_paints_the_described_design(monkeypatch):
    """The cover paints the same QuiltDesign the cutting pages describe, so it
    can't show a different quilt (it once rendered from a hand-picked kwarg
    subset that dropped border, wash and the second palette)."""
    import pattern_pdf

    painted = []
    real_paint = pattern_pdf.paint
    monkeypatch.setattr(
        pattern_pdf,
        "paint",
        lambda design, **kw: painted.append(design) or real_paint(design, **kw),
    )
    params = _base_params(border_style="solid", wash_alpha=0.1, palette_2="wildflower")
    described = []
    real_design_for = pattern_pdf._design_for  # pylint: disable=protected-access
    monkeypatch.setattr(
        pattern_pdf, "_design_for", lambda p: described.append(real_design_for(p)) or described[-1]
    )
    with tempfile.TemporaryDirectory() as d:
        generate_pattern_pdf(params, os.path.join(d, "p.pdf"))
    assert painted == described
    assert painted[0].border_style == "solid"
    assert painted[0].wash_alpha == 0.1
    assert len(painted[0].palettes) == 2
