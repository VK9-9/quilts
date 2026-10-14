"""Golden regression tests for the generative core.

The mapping from (seed, params) to a quilt is defined implicitly by the order
of RNG consumption in plan_quilt. Any reordering silently invalidates every
saved seed, shared quilt_id, and static-site design. Two checks pin it, for
each fixed param set below:

* DESIGN_HASHES — an exact fingerprint of the planned QuiltDesign plus every
  block's geometry (wonky jitter included). Platform-independent: the plan's
  draws are pure-Python and identical everywhere, and geometry is rounded to
  1e-6 of a block so last-bit libm differences in trig blocks can't matter.
  This is the check CI relies on.
* GOLDEN_HASHES — the decoded RGBA pixels the painter produces. Pixel-exact
  output differs between cairo versions (CI's Linux cairo 1.18.0 draws
  strippy_wonky differently from the 1.18.4 these were recorded with), so it
  only runs on the cairo version in GOLDEN_CAIRO_VERSION and skips, saying
  why, elsewhere.

If a change to the generative core is intentional, regenerate both with:

    python -m pytest test_golden_render.py -q                # see failures
    python test_golden_render.py --regenerate                # print new hashes

and paste the new values below, in the same commit.
"""

import hashlib
import io
import json

import cairo
import pytest
from PIL import Image

from quilt import _cell_seed, _jitter_patches, cell_patches, render_quilt
from render_params import params_to_render_kwargs, plan_from_params

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
    "flower_medallion": {
        "rows": 16,
        "cols": 16,
        "symmetry": "flower",
        "chaos": 0.4,
        "palette": "cherry blossom",
        "n_patterns": 2,
        "n_colors": 4,
        "tile_size": 6,
        "tile_variation": 0.1,
        "seed": 1006,
        "quilt_stitch": "sashiko_asanoha",
    },
    "mirror_geometric": {
        "rows": 16,
        "cols": 16,
        "symmetry": "mirror",
        "chaos": 0.3,
        "palette": "ocean breeze",
        "n_patterns": 2,
        "n_colors": 4,
        "tile_size": 7,
        "tile_variation": 0.1,
        "seed": 1003,
        "quilt_stitch": "sashiko_wave",
    },
    # The three cases below pin main-RNG draw order across every post-grid
    # consumer — plain cells → mega-blocks → border colors → wash color — plus
    # the color-RNG order base → mix → second palette, ahead of the plan/paint
    # split (docs-notes/ARCHITECTURE_REVIEW_2026-10.md §1), which moves all of
    # them out of render_quilt.
    "mega_strippy_wonky_checker": {
        "rows": 16,
        "cols": 16,
        "symmetry": "partial",
        "chaos": 0.4,
        "palette": "tide pool",
        "n_patterns": 2,
        "n_colors": 4,
        "tile_size": 6,
        "tile_variation": 0.1,
        "seed": 1012,
        "mega_frac": 0.25,
        "plain_frac": 0.2,
        "strippy": 0.3,
        "wonky": 0.04,
        "border_style": "checkerboard",
        "wash_alpha": 0.1,
        "quilt_stitch": "grid",
    },
    "mix_and_second_palette_piano": {
        "rows": 16,
        "cols": 16,
        "symmetry": "rotational",
        "chaos": 0.3,
        "palette": "bluebell",
        "palette_mix": "honey oak",
        "palette_2": "wisteria",
        "n_patterns": 2,
        "n_colors": 5,
        "tile_size": 6,
        "tile_variation": 0.1,
        "seed": 1013,
        "border_style": "piano_keys",
        "wash_alpha": 0.08,
        "quilt_stitch": "diagonal",
    },
    "mega_stripes_border": {
        "rows": 14,
        "cols": 18,
        "symmetry": "stripe",
        "chaos": 0.3,
        "palette": "sea glass",
        "n_patterns": 2,
        "n_colors": 6,
        "tile_size": 6,
        "tile_variation": 0.1,
        "seed": 1014,
        "mega_frac": 0.15,
        "plain_frac": 0.1,
        "border_style": "stripes",
        "wash_alpha": 0.06,
        "quilt_stitch": "sashiko_asanoha",
    },
}


def test_every_symmetry_has_a_golden_case():
    """flower and mirror had no case, so a change to layout_flower's cell
    assignment slipped through the tripwire entirely."""
    from layout import SYMMETRY_MODES  # pylint: disable=import-outside-toplevel

    covered = {c["symmetry"] for c in GOLDEN_CASES.values()}
    missing = set(SYMMETRY_MODES) - covered
    assert not missing, f"symmetry modes with no golden case: {sorted(missing)}"


# sha256 of decoded RGBA pixels, block_size=20. Regenerate via --regenerate.
#
# Regenerated deliberately: palette subsets are now ordered by luminance
# (palettes.subset_in_tonal_order), which changes what is drawn for every quilt
# that uses fewer colors than its palette holds; and the bargello wave's
# amplitude is now derived from its period, which changes every bargello quilt.
# sha256 of the planned design + block geometry. Regenerate via --regenerate.
DESIGN_HASHES = {
    "bargello_basic": "cc85eb34dbfc9d37a55dd147594538e6ffbab1c02506400e53959fe42dcdbdb0",
    "partial_lively": "f4d52deab25257420547bd60d579f0169de21435365b9edf2e42bdaa2e506fd2",
    "rotational_calm": "388658104dee2ff243887cb1d312f74f535d118221a5458cc2140c77c4755ff5",
    "stripe_serene": "402ba18c8c1e9df06fafdd6f44c1405f85e66f7a7008f07b1c333c500046d540",
    "columns_mix": "8bb8ef5a5f9789d1cf6455457d4d9d37511ff2ea1bedc73b00c3ca41dca14302",
    "emergent_wild": "19f847c299b6fa952925abaf83a767c2dc6913deefb6107c9eb1e39339fd24d4",
    "none_tiled": "baf1bc6925b5b0ae21ca6842019248e6e40e8e235501e6846a233d86177ff374",
    "palette_two": "412abd552f000bad6cf9c065ae27ff5ad82182115605a8d276bd7264c1493d3f",
    "plain_and_wash": "4f434894cf0e0f2f0baf309e26ca383b314c4dc5fc5ffb16308a8232ef2cf388",
    "strippy_wonky": "9e630d1d9bea8281357cc572ce0641266ba1082e5fb0d011416f50fff44a4932",
    "flower_medallion": "998e3d94d15ec781e0d58ed83f68f088d378ac951a4bbad52dd6dc9b8b623245",
    "mirror_geometric": "670989cf4398eb7d50be5d183330dd3a0673cffd1b06aadeb377ae7489950745",
    "mega_strippy_wonky_checker": "86a8caff785afb058ce7ba856283183a1d218fa5d6c46a7ae97f763a6c674ede",
    "mix_and_second_palette_piano": "7d927e71f27daf378a7f954e2aa305b3d0bf97bec07633a46a9f1adbf0f90b89",
    "mega_stripes_border": "23fd878f79a915209f8965ab8122fb35ef89f78333b98e66527ce2158a7a68cd",
}

GOLDEN_HASHES = {
    "bargello_basic": "b22010cac8b047779d71dcfa7e5247f07827ad274548283aa23d4f1284555001",
    "partial_lively": "680ce672adf4d68b7f0a35e6df95a9745e593a163d0ed3c6f67ad5a473921e50",
    "rotational_calm": "636885ba05e57db9024ea94e0d0bb1334eaacc763582b23e64261a453d499d1b",
    "stripe_serene": "2e14b67f2ec7b4e7ecbaafc6cd6c34dd3169fb1a7cc526060a2f2f8c8512aaae",
    "columns_mix": "9cd21bef1fbfbb2b79ec31a70b6991defd9270d550e30f4d9459b083af2c932b",
    "emergent_wild": "9fb968ac981908dd5b5466ad2d8c4604a2459a15981e791572494078d25e2084",
    "none_tiled": "954eb001b125145723c2c8a18482752638524f11b8b7f529178eb2faece53e31",
    "palette_two": "ef39ce00718e6cafb3c8064a737620809c86cf05d5a1e0c60b4340c53637451e",
    "plain_and_wash": "211067e3a78620da5e9a7d983a8eef08bc32dafe81dc30b8875d8f4a8eb6edc8",
    "strippy_wonky": "58d0d8b636ba1f2809472872b2f6a86328e94d14c72eed633b3cc078687bb3fe",
    "flower_medallion": "ac1ccce4e9a23ab1e02c509539149b2d65b036adc07b7cad374e8cab88a5efa9",
    "mirror_geometric": "5843fb79ec821c6a93bb8dd0a65d54d757dbdd07fa2ec74832e684eceaf77024",
    "mega_strippy_wonky_checker": "4c5fd46016e8dcf55477e8b45718f7a5edef47ac891a9cacb7a43ed473560684",
    "mix_and_second_palette_piano": "85008ceef7b8062e97c46d73625c51521b657460b5d0b5ab4faec9111ab90731",
    "mega_stripes_border": "881ab9f9b3cbbb8605a0108bb5448eb038bfa6936dfc6bd2da069f9507ee8515",
}

# cairo version GOLDEN_HASHES were recorded with; pixel checks skip on others.
GOLDEN_CAIRO_VERSION = "1.18.4"

_BLOCK_SIZE = 20


def _render_hash(params):
    """Render params through the production funnel and hash the RGBA pixels."""
    png = render_quilt(**params_to_render_kwargs(params, block_size=_BLOCK_SIZE))
    img = Image.open(io.BytesIO(png)).convert("RGBA")
    return hashlib.sha256(img.tobytes()).hexdigest()


_GEOMETRY_UNITS = 100  # blocks fingerprinted in [0, 100] pattern units
_GEOMETRY_DIGITS = 6


def _patches_key(patches):
    return [
        [[[round(x, _GEOMETRY_DIGITS), round(y, _GEOMETRY_DIGITS)] for x, y in poly], color]
        for poly, color in patches
    ]


def _design_hash(params):
    """Fingerprint of everything plan_quilt decides, plus each block's geometry."""
    d = plan_from_params(params)
    blocks = []
    for r, c in sorted(d.grid):
        mega = (r, c) in d.mega_tl
        # plain cells have no block; cells under a mega-block are drawn by its anchor
        if not mega and ((r, c) in d.plain_cells or (r, c) in d.mega_covered):
            continue
        base = cell_patches(d, r, c, _GEOMETRY_UNITS, mega=mega)
        jittered = (
            _jitter_patches(base, _GEOMETRY_UNITS, d.wonky, _cell_seed(d, r, c, mega))
            if d.wonky > 0
            else base
        )
        blocks.append([r, c, mega, _patches_key(base), _patches_key(jittered)])
    design = {
        "seed": d.seed,
        "grid": [[r, c, d.grid[(r, c)]] for (r, c) in sorted(d.grid)],
        "palettes": d.palettes,
        "allowed": d.allowed_patterns,
        "tile_size": d.tile_size,
        "plain": sorted(d.plain_cells),
        "mega_tl": sorted(d.mega_tl),
        "mega_covered": sorted(d.mega_covered),
        "border": [d.border_style, d.border_colors],
        "wash": [d.wash_alpha, d.wash_color],
        "stitch": d.quilt_stitch,
        "wonky": d.wonky,
        "strips": [d.col_factors, d.row_factors],
        "blocks": blocks,
    }
    return hashlib.sha256(json.dumps(design, sort_keys=True).encode()).hexdigest()


@pytest.mark.parametrize("name", sorted(GOLDEN_CASES))
def test_golden_design(name):
    """Each fixed param set must plan exactly the recorded design."""
    assert _design_hash(GOLDEN_CASES[name]) == DESIGN_HASHES[name], (
        f"design for '{name}' changed; if intentional, regenerate hashes "
        f"(python test_golden_render.py --regenerate)"
    )


@pytest.mark.parametrize("name", sorted(GOLDEN_CASES))
def test_golden_render(name):
    """Each fixed param set must reproduce its recorded pixel hash."""
    if cairo.cairo_version_string() != GOLDEN_CAIRO_VERSION:
        pytest.skip(
            f"pixel goldens recorded with cairo {GOLDEN_CAIRO_VERSION}, running "
            f"{cairo.cairo_version_string()}; test_golden_design still pins the design"
        )
    assert _render_hash(GOLDEN_CASES[name]) == GOLDEN_HASHES[name], (
        f"render for '{name}' changed; if intentional, regenerate hashes "
        f"(python test_golden_render.py --regenerate)"
    )


def test_render_is_deterministic():
    """Re-rendering the same params twice yields identical pixels."""
    params = GOLDEN_CASES["bargello_basic"]
    assert _render_hash(params) == _render_hash(params)


def _regenerate():
    """Print fresh DESIGN_HASHES and GOLDEN_HASHES for pasting after an
    intentional change (record pixels on GOLDEN_CAIRO_VERSION)."""
    print(
        "DESIGN_HASHES =",
        json.dumps({n: _design_hash(p) for n, p in GOLDEN_CASES.items()}, indent=4),
    )
    print(f"GOLDEN_HASHES (cairo {cairo.cairo_version_string()}) =")
    print(json.dumps({n: _render_hash(p) for n, p in GOLDEN_CASES.items()}, indent=4))


if __name__ == "__main__":
    import sys

    if "--regenerate" in sys.argv:
        _regenerate()
    else:
        print("run via pytest, or pass --regenerate to print fresh hashes")
