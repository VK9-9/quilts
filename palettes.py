"""Curated color palettes for generative quilts.

Each palette is a tuple of (name, list_of_hex_colors).
Colors within a palette are meant to coordinate like real quilting fabric selections.
"""

PALETTES = [
    ("ocean breeze", [
        "#1B3A5C", "#4682B4", "#87CEEB", "#F0F8FF", "#2E8B57",
    ]),
    ("wildflower", [
        "#8B008B", "#DA70D6", "#FFB6C1", "#FFFACD", "#228B22",
    ]),
    ("indigo dye", [
        "#1A0533", "#3F00FF", "#7B68EE", "#E6E6FA", "#F5F5F5",
    ]),
    ("deep sea", [
        "#0C1445", "#1A5276", "#48C9B0", "#F5F5F5", "#0E6655",
    ]),
    ("storm", [
        "#2C3E50", "#5D6D7E", "#AEB6BF", "#F2F3F4", "#1C2833",
    ]),
    ("northern lights", [
        "#0B0B3B", "#1B8A6B", "#7FDBCA", "#C77DFF", "#F0F8FF",
    ]),
    ("midnight moss", [
        "#0D1F0D", "#2D6A2D", "#6B9E6B", "#C4D9A0", "#F0EDD8",
    ]),
    ("terracotta", [
        "#8B3A2F", "#C25B3F", "#E8A87C", "#F5DEB3", "#4A2511",
    ]),
    ("autumn harvest", [
        "#7B2D1A", "#D4762C", "#F2B84B", "#5C7A29", "#2E1B0E",
    ]),
    ("cherry blossom", [
        "#FFB7C5", "#FF69B4", "#D1426E", "#F8E8EE", "#4A0E2B",
    ]),
    ("slate and rust", [
        "#3B444B", "#708090", "#B7410E", "#D2691E", "#F5F5DC",
    ]),
    ("coral reef", [
        "#FF6F61", "#FFD700", "#00CED1", "#20B2AA", "#1C1C3C",
    ]),
]


def hex_to_rgb(h):
    """Convert hex color string to (r, g, b) float tuple (0-1)."""
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) / 255.0 for i in (0, 2, 4))
