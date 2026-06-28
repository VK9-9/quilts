"""Golden-image regression tests for the generative render core.

The mapping from (seed, params) to pixels is defined implicitly by the order
of RNG consumption in render_quilt. Any reordering silently invalidates every
saved seed, shared quilt_id, and static-site design. These tests pin that
mapping: each case renders a fixed param set through the production funnel
(params_to_render_kwargs -> render_quilt) and asserts a stable hash of the
decoded RGBA pixels.

Pixels are hashed (not the PNG bytes) so the test is insensitive to PNG/zlib
encoder version differences across machines, while still catching any change
to what is actually drawn.

If a change to the generative core is intentional, regenerate the expected
hashes with:

    python -m pytest test_golden_render.py -q                # see failures
    python test_golden_render.py --regenerate                # print new hashes

and paste the new values into GOLDEN_HASHES below, in the same commit.
"""

import hashlib
import io

import pytest
from PIL import Image

from render_params import params_to_render_kwargs
from quilt import render_quilt

# Representative param sets spanning every symmetry mode plus the feature flags
# that touch the render path (tiling, two-palette, plain/wash, strippy, wonky).
GOLDEN_CASES = {
    "bargello_basic": {
        "rows": 16,
        "cols": 16,
        "symmetry": "bargello",
        "chaos": 0.3,
        "palette": "ocean breeze",
        "n_patterns": 2,
        "n_colors": 4,
        "tile_size": 6,
        "tile_variation": 0.1,
        "seed": 1001,
        "quilt_stitch": "grid",
    },
    "partial_lively": {
        "rows": 18,
        "cols": 18,
        "symmetry": "partial",
        "chaos": 0.6,
        "palette": "wildflower",
        "n_patterns": 2,
        "n_colors": 5,
        "tile_size": 6,
        "tile_variation": 0.2,
        "seed": 1002,
        "quilt_stitch": "diagonal",
        "border_style": "solid",
    },
    "rotational_calm": {
        "rows": 16,
        "cols": 16,
        "symmetry": "rotational",
        "chaos": 0.2,
        "palette": "indigo dye",
        "n_patterns": 2,
        "n_colors": 4,
        "tile_size": 6,
        "tile_variation": 0.05,
        "seed": 1003,
        "quilt_stitch": "sashiko_wave",
    },
    "stripe_serene": {
        "rows": 16,
        "cols": 16,
        "symmetry": "stripe",
        "chaos": 0.2,
        "palette": "northern lights",
        "n_patterns": 2,
        "n_colors": 4,
        "tile_size": 8,
        "tile_variation": 0.05,
        "seed": 1004,
        "quilt_stitch": None,
    },
    "columns_mix": {
        "rows": 18,
        "cols": 18,
        "symmetry": "columns",
        "chaos": 0.4,
        "palette": "sea glass",
        "n_patterns": 2,
        "n_colors": 6,
        "tile_size": 5,
        "tile_variation": 0.15,
        "seed": 1005,
        "quilt_stitch": "grid",
    },
    "emergent_wild": {
        "rows": 18,
        "cols": 18,
        "symmetry": "emergent",
        "chaos": 0.7,
        "palette": "wisteria",
        "n_patterns": 2,
        "n_colors": 4,
        "tile_size": 5,
        "tile_variation": 0.2,
        "seed": 1006,
        "quilt_stitch": "grid",
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
        "seed": 1008,
        "wonky": 0.05,
        "quilt_stitch": "diagonal",
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
        "tile_size": 6,
        "tile_variation": 0.1,
        "seed": 1009,
        "quilt_stitch": "grid",
    },
    "plain_and_wash": {
        "rows": 16,
        "cols": 16,
        "symmetry": "partial",
        "chaos": 0.5,
        "palette": "river stone",
        "n_patterns": 2,
        "n_colors": 5,
        "tile_size": 6,
        "tile_variation": 0.1,
        "seed": 1010,
        "plain_frac": 0.3,
        "wash_alpha": 0.12,
        "quilt_stitch": "grid",
    },
    "strippy_wonky": {
        "rows": 16,
        "cols": 16,
        "symmetry": "partial",
        "chaos": 0.4,
        "palette": "honey oak",
        "n_patterns": 2,
        "n_colors": 4,
        "tile_size": 6,
        "tile_variation": 0.1,
        "seed": 1011,
        "strippy": 0.3,
        "wonky": 0.04,
        "quilt_stitch": "grid",
    },
}

# sha256 of decoded RGBA pixels, block_size=20. Regenerate via --regenerate.
GOLDEN_HASHES = {
    "bargello_basic": "7551c45c91c441234bb3293be595addb98a324efc99d368c8774969d10fb7f1a",
    "partial_lively": "4a968b9b23d1d288948d477003f41145a60a3ba16f01f40afe4619497d4d6314",
    "rotational_calm": "95c5f9e21a715a18f79c7a5faf56c4d2e3577db6b4fc8fb024864e8c255b9b58",
    "stripe_serene": "bfb917e9da8ce866c631fbd52b1acc84ab8e4fc860455234b2b1ce41303cd30c",
    "columns_mix": "8498c4a00c01a0777bf58c379a050d9a40d69b01d6e269175cba56217d1f3cc0",
    "emergent_wild": "8306b96184570320f2f174346a447744c7cab4e19db12717368a11eaa70023d8",
    "none_tiled": "dec32528d65a9963954ab53f98ddec0a8148971b1c80b4f5b50b573b22e3df45",
    "palette_two": "a59186d3d820e868820d69340a2b27c85c81717bd18bdba8045af9e33b615da0",
    "plain_and_wash": "815bd29a4cf170b365b7c32ba89143182d29ed06403ab249c67a3006d2f77ad9",
    "strippy_wonky": "82f9570f141ec34ea64a52b1850b6dda7ff1355992e605cf93ef67b2fc937623",
}

_BLOCK_SIZE = 20


def _render_hash(params):
    """Render params through the production funnel and hash the RGBA pixels."""
    png = render_quilt(**params_to_render_kwargs(params, block_size=_BLOCK_SIZE))
    img = Image.open(io.BytesIO(png)).convert("RGBA")
    return hashlib.sha256(img.tobytes()).hexdigest()


@pytest.mark.parametrize("name", sorted(GOLDEN_CASES))
def test_golden_render(name):
    """Each fixed param set must reproduce its recorded pixel hash."""
    assert _render_hash(GOLDEN_CASES[name]) == GOLDEN_HASHES[name], (
        f"render for '{name}' changed; if intentional, regenerate hashes "
        f"(python test_golden_render.py --regenerate)"
    )


def test_render_is_deterministic():
    """Re-rendering the same params twice yields identical pixels."""
    params = GOLDEN_CASES["bargello_basic"]
    assert _render_hash(params) == _render_hash(params)


def _regenerate():
    """Print fresh GOLDEN_HASHES for pasting after an intentional change."""
    import json  # pylint: disable=import-outside-toplevel

    fresh = {name: _render_hash(p) for name, p in GOLDEN_CASES.items()}
    print(json.dumps(fresh, indent=4))


if __name__ == "__main__":
    import sys

    if "--regenerate" in sys.argv:
        _regenerate()
    else:
        print("run via pytest, or pass --regenerate to print fresh hashes")
