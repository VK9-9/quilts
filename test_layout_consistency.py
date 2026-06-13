"""The PDF cutting diagrams must be built from the same grid the image is.

pattern_pdf rebuilds the layout via build_layout to draw per-block cutting
patterns. If that reconstruction differs from the grid render_quilt actually
draws, the printed pattern tells the quilter to cut pieces that don't match the
picture. These tests pin the two together.

Before build_layout learned about n_palettes and tiling, the 'palette_two' and
'none_tiled' cases below produced mismatched grids — exactly the silent
wrong-pattern bug this guards against.
"""

import pytest

import quilt
import pattern_pdf
from render_params import params_to_render_kwargs
from quilt import render_quilt

# Full param dicts (sampler/generator shape) covering the cases where the
# render grid and the reconstruction historically diverged.
CASES = {
    "plain_partial": {
        "rows": 16,
        "cols": 16,
        "symmetry": "partial",
        "chaos": 0.4,
        "palette": "ocean breeze",
        "n_patterns": 2,
        "n_colors": 4,
        "tile_size": 0,
        "tile_variation": 0.1,
        "seed": 2001,
    },
    "bargello": {
        "rows": 16,
        "cols": 16,
        "symmetry": "bargello",
        "chaos": 0.3,
        "palette": "lavender fields",
        "n_patterns": 2,
        "n_colors": 4,
        "tile_size": 0,
        "tile_variation": 0.1,
        "seed": 2002,
    },
    "palette_two": {
        "rows": 16,
        "cols": 16,
        "symmetry": "partial",
        "chaos": 0.4,
        "palette": "ocean breeze",
        "palette_2": "wildflower",
        "n_patterns": 2,
        "n_colors": 4,
        "tile_size": 0,
        "tile_variation": 0.1,
        "seed": 2003,
    },
    "none_tiled": {
        "rows": 16,
        "cols": 16,
        "symmetry": "none",
        "chaos": 0.5,
        "palette": "thistle",
        "n_patterns": 2,
        "n_colors": 4,
        "tile_size": 6,
        "tile_variation": 0.15,
        "seed": 2004,
    },
}


def _render_grid(params, monkeypatch):
    """Render the quilt, capturing the grid render_quilt actually draws."""
    captured = {}
    orig = quilt._build_grid  # pylint: disable=protected-access

    def spy(*args, **kwargs):
        grid, allowed = orig(*args, **kwargs)
        captured["grid"] = grid
        return grid, allowed

    monkeypatch.setattr(quilt, "_build_grid", spy)
    render_quilt(**params_to_render_kwargs(params, block_size=10))
    return captured["grid"]


@pytest.mark.parametrize("name", sorted(CASES))
def test_pdf_reconstruction_matches_render(name, monkeypatch):
    """pattern_pdf's reconstructed grid equals the grid render_quilt draws."""
    params = CASES[name]
    render_grid = _render_grid(params, monkeypatch)
    pdf_grid, _allowed, _palette = pattern_pdf._reconstruct_layout(params)  # pylint: disable=protected-access
    assert pdf_grid == render_grid
