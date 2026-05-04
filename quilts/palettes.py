"""Curated color palettes for generative quilts.

Each palette is a tuple of (name, list_of_hex_colors).
Colors within a palette are meant to coordinate like real quilting fabric selections.
"""

PALETTES = [
    ("autumn harvest", [
        "#8B2500", "#D2691E", "#DAA520", "#F5DEB3", "#2F4F2F",
    ]),
    ("ocean breeze", [
        "#1B3A5C", "#4682B4", "#87CEEB", "#F0F8FF", "#2E8B57",
    ]),
    ("wildflower", [
        "#8B008B", "#DA70D6", "#FFB6C1", "#FFFACD", "#228B22",
    ]),
    ("farmhouse", [
        "#8B0000", "#F5F5DC", "#2F4F4F", "#D2B48C", "#4A4A4A",
    ]),
    ("sunset", [
        "#FF4500", "#FF6347", "#FFD700", "#FFF8DC", "#4B0082",
    ]),
    ("winter sky", [
        "#191970", "#4169E1", "#B0C4DE", "#F8F8FF", "#708090",
    ]),
    ("forest floor", [
        "#2E4E1E", "#556B2F", "#8FBC8F", "#D2B48C", "#8B4513",
    ]),
    ("berry patch", [
        "#800020", "#C71585", "#FFB7C5", "#FFF0F5", "#4B0050",
    ]),
    ("prairie", [
        "#DAA520", "#F4A460", "#FFDEAD", "#FFFFF0", "#6B8E23",
    ]),
    ("indigo dye", [
        "#1A0533", "#3F00FF", "#7B68EE", "#E6E6FA", "#F5F5F5",
    ]),
    ("patchwork classic", [
        "#B22222", "#1E3A5F", "#F5F5DC", "#DAA520", "#2F4F4F",
    ]),
    ("spring garden", [
        "#FF69B4", "#98FB98", "#FFFFE0", "#DDA0DD", "#3CB371",
    ]),
]


def hex_to_rgb(h):
    """Convert hex color string to (r, g, b) float tuple (0-1)."""
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) / 255.0 for i in (0, 2, 4))
