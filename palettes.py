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
    ("winter sky", [
        "#191970", "#4169E1", "#B0C4DE", "#F8F8FF", "#708090",
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
    ("copper canyon", [
        "#4A1501", "#C1440E", "#E8925A", "#F5DEB3", "#2D5A27",
    ]),
    ("autumn embers", [
        "#2D0D00", "#8B2500", "#D4600A", "#F4D35E", "#1B4332",
    ]),
    ("peacock feather", [
        "#0A2342", "#126872", "#3BB273", "#E9C46A", "#F4A261",
    ]),
    ("cardinal", [
        "#5C0011", "#A6192E", "#E8B84B", "#F5ECD7", "#1E3A1E",
    ]),
    ("midnight moss", [
        "#0D1F0D", "#2D6A2D", "#6B9E6B", "#C4D9A0", "#F0EDD8",
    ]),
]


def hex_to_rgb(h):
    """Convert hex color string to (r, g, b) float tuple (0-1)."""
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) / 255.0 for i in (0, 2, 4))
