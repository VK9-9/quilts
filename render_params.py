"""Shared conversion from sampler param dicts to render_quilt kwargs.

Used by sampler.py (scoring pipeline) and generator.py (public webapp)
so both always pass the same set of params to render_quilt.
"""

from palettes import PALETTES

PALETTE_NAMES = [p[0] for p in PALETTES]
_ACTIVE_PALETTES = set(PALETTE_NAMES)


def params_to_render_kwargs(params, block_size=40):
    """Convert a sampled/decoded param dict to kwargs for render_quilt."""
    kwargs = {
        "rows": params["rows"],
        "cols": params["cols"],
        "block_size": block_size,
        "symmetry": params["symmetry"],
        "chaos": params["chaos"],
        "palette_name": params["palette"],
        "seed": params["seed"],
        "output": None,  # return bytes
        "border": 15,
        "max_patterns": params["n_patterns"],
        "max_colors": params["n_colors"],
        "tile_size": params["tile_size"] if params["tile_size"] > 0 else None,
        "tile_variation": params["tile_variation"],
        "border_style": params.get("border_style", "none"),
        "mega_frac": params.get("mega_frac", 0.0),
        "plain_frac": params.get("plain_frac", 0.0),
        "quilt_stitch": params.get("quilt_stitch"),
        "wash_alpha": params.get("wash_alpha", 0.0),
        "palette_name_2": params.get("palette_2"),
        "palette_mix": params.get("palette_mix"),
        "wonky": params.get("wonky", 0.0),
        "strippy": params.get("strippy", 0.0),
    }
    # Drop palette_2/palette_mix if they reference a retired palette
    if kwargs["palette_name_2"] and kwargs["palette_name_2"] not in _ACTIVE_PALETTES:
        kwargs["palette_name_2"] = None
    if kwargs.get("palette_mix") and kwargs["palette_mix"] not in _ACTIVE_PALETTES:
        kwargs["palette_mix"] = None
    if kwargs["border_style"] == "none":
        kwargs["border_style"] = None
    return kwargs
