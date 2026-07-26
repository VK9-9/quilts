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
#
# Regenerated deliberately: palette subsets are now ordered by luminance
# (palettes.subset_in_tonal_order), which changes what is drawn for every quilt
# that uses fewer colors than its palette holds.
GOLDEN_HASHES = {
    "bargello_basic": "fbd93893b8f3d28499ed6f882a34f3f2fa2cea9498a151917143812e91448941",
    "partial_lively": "680ce672adf4d68b7f0a35e6df95a9745e593a163d0ed3c6f67ad5a473921e50",
    "rotational_calm": "636885ba05e57db9024ea94e0d0bb1334eaacc763582b23e64261a453d499d1b",
    "stripe_serene": "2e14b67f2ec7b4e7ecbaafc6cd6c34dd3169fb1a7cc526060a2f2f8c8512aaae",
    "columns_mix": "9cd21bef1fbfbb2b79ec31a70b6991defd9270d550e30f4d9459b083af2c932b",
    "emergent_wild": "9fb968ac981908dd5b5466ad2d8c4604a2459a15981e791572494078d25e2084",
    "none_tiled": "954eb001b125145723c2c8a18482752638524f11b8b7f529178eb2faece53e31",
    "palette_two": "ef39ce00718e6cafb3c8064a737620809c86cf05d5a1e0c60b4340c53637451e",
    "plain_and_wash": "211067e3a78620da5e9a7d983a8eef08bc32dafe81dc30b8875d8f4a8eb6edc8",
    "strippy_wonky": "58d0d8b636ba1f2809472872b2f6a86328e94d14c72eed633b3cc078687bb3fe",
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
