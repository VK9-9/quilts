"""Tests for render_params.py — shared param conversion."""
from render_params import params_to_render_kwargs


def _base_params(**overrides):
    p = {
        "palette": "ocean breeze", "symmetry": "bargello",
        "chaos": 0.3, "rows": 16, "cols": 16, "n_patterns": 2,
        "n_colors": 4, "tile_size": 6, "tile_variation": 0.1,
        "border_style": "none", "seed": 42,
    }
    p.update(overrides)
    return p


class TestRetiredPaletteFiltering:

    def test_retired_palette_2_dropped(self):
        params = _base_params(palette_2="nonexistent_retired_palette")
        kwargs = params_to_render_kwargs(params)
        assert kwargs["palette_name_2"] is None

    def test_valid_palette_2_preserved(self):
        params = _base_params(palette_2="wildflower")
        kwargs = params_to_render_kwargs(params)
        assert kwargs["palette_name_2"] == "wildflower"

    def test_retired_palette_mix_dropped(self):
        params = _base_params(palette_mix="nonexistent_retired_palette")
        kwargs = params_to_render_kwargs(params)
        assert kwargs["palette_mix"] is None

    def test_valid_palette_mix_preserved(self):
        params = _base_params(palette_mix="wildflower")
        kwargs = params_to_render_kwargs(params)
        assert kwargs["palette_mix"] == "wildflower"

    def test_none_palette_2_stays_none(self):
        params = _base_params()
        kwargs = params_to_render_kwargs(params)
        assert kwargs["palette_name_2"] is None

    def test_none_palette_mix_stays_none(self):
        params = _base_params()
        kwargs = params_to_render_kwargs(params)
        assert kwargs["palette_mix"] is None
