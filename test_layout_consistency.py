"""The PDF must describe the same design the image paints.

If pattern_pdf's design differs from the one render_quilt paints, the printed
pattern tells the quilter to cut pieces that don't match the picture. The PDF
used to *replay* the render's RNG stream, and the replay silently missed
two-palette splits and tiling (later fixed), then plain cells, mega-blocks and
mixed palettes. Both now plan through render_params.plan_from_params; these
tests pin that they get equal QuiltDesigns — every decision, not just the grid.
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
    "plain_mega_mix_strippy": {
        "rows": 16,
        "cols": 16,
        "symmetry": "partial",
        "chaos": 0.4,
        "palette": "tide pool",
        "palette_mix": "honey oak",
        "n_patterns": 2,
        "n_colors": 4,
        "tile_size": 0,
        "tile_variation": 0.1,
        "plain_frac": 0.2,
        "mega_frac": 0.2,
        "strippy": 0.3,
        "wonky": 0.04,
        "border_style": "checkerboard",
        "wash_alpha": 0.1,
        "seed": 2005,
    },
}


def _painted_design(params, monkeypatch):
    """Render the quilt, capturing the QuiltDesign render_quilt actually paints."""
    captured = {}
    orig = quilt.paint

    def spy(design, *args, **kwargs):
        captured["design"] = design
        return orig(design, *args, **kwargs)

    monkeypatch.setattr(quilt, "paint", spy)
    render_quilt(**params_to_render_kwargs(params, block_size=10))
    return captured["design"]


@pytest.mark.parametrize("name", sorted(CASES))
def test_pdf_describes_the_painted_design(name, monkeypatch):
    """pattern_pdf's design equals the design render_quilt paints."""
    params = CASES[name]
    painted = _painted_design(params, monkeypatch)
    described = pattern_pdf._design_for(params)  # pylint: disable=protected-access
    assert described == painted
