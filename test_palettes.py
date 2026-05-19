"""Tests for palettes.py."""
from palettes import PALETTES, hex_to_rgb


def test_hex_to_rgb_basic():
    assert hex_to_rgb("#FF0000") == (1.0, 0.0, 0.0)
    assert hex_to_rgb("#00FF00") == (0.0, 1.0, 0.0)
    assert hex_to_rgb("#0000FF") == (0.0, 0.0, 1.0)


def test_hex_to_rgb_strips_hash():
    assert hex_to_rgb("FF0000") == hex_to_rgb("#FF0000")


def test_hex_to_rgb_midvalue():
    r, g, b = hex_to_rgb("#808080")
    assert abs(r - 128 / 255) < 1e-6
    assert abs(g - 128 / 255) < 1e-6
    assert abs(b - 128 / 255) < 1e-6


def test_all_palettes_have_names():
    for name, colors in PALETTES:
        assert isinstance(name, str) and len(name) > 0


def test_all_palettes_have_valid_hex():
    for name, colors in PALETTES:
        assert len(colors) >= 2, f"Palette '{name}' needs at least 2 colors"
        for c in colors:
            assert c.startswith("#"), f"Color {c} in '{name}' missing #"
            assert len(c) == 7, f"Color {c} in '{name}' wrong length"
            # should parse without error
            r, g, b = hex_to_rgb(c)
            assert 0.0 <= r <= 1.0
            assert 0.0 <= g <= 1.0
            assert 0.0 <= b <= 1.0


def test_no_duplicate_palette_names():
    names = [name for name, _ in PALETTES]
    assert len(names) == len(set(names))
