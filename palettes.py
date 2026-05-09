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
    ("storm", [
        "#2C3E50", "#5D6D7E", "#AEB6BF", "#F2F3F4", "#1C2833",
    ]),
    ("northern lights", [
        "#0B0B3B", "#1B8A6B", "#7FDBCA", "#C77DFF", "#F0F8FF",
    ]),
    ("midnight moss", [
        "#0D1F0D", "#2D6A2D", "#6B9E6B", "#C4D9A0", "#F0EDD8",
    ]),
    ("cherry blossom", [
        "#FFB7C5", "#FF69B4", "#D1426E", "#F8E8EE", "#4A0E2B",
    ]),
    ("tide pool", [
        "#1B6B7D", "#3CACBB", "#7DD8C7", "#E0F5F0", "#0E4D5A",
    ]),
    ("lavender fields", [
        "#5B3A8C", "#9B72CF", "#C8A2E8", "#E8D5F5", "#3D6B4F",
    ]),
    ("copper canyon", [
        "#8B4513", "#CD853F", "#DEB887", "#F5E6CC", "#A0522D",
    ]),
    ("winter frost", [
        "#4A6FA5", "#89ABD9", "#C5D8ED", "#F0F4F8", "#2C4A6E",
    ]),
    ("sage garden", [
        "#4A6741", "#7D9B6E", "#A8C49A", "#E8F0E0", "#3B5332",
    ]),
    ("plum wine", [
        "#4A0028", "#7B2D5F", "#B85C8A", "#E8B4D0", "#F5E6EF",
    ]),
    ("coastal fog", [
        "#5B7B8A", "#8FAAB5", "#C4D4DB", "#EDF2F4", "#3E5A66",
    ]),
    ("amber glow", [
        "#8B5E00", "#D4940A", "#F0C040", "#FFF3D4", "#6B4500",
    ]),
]


def hex_to_rgb(h):
    """Convert hex color string to (r, g, b) float tuple (0-1)."""
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) / 255.0 for i in (0, 2, 4))
