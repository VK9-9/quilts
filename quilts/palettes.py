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
    ("midnight garden", [
        "#0D0D2B", "#2D572C", "#9B59B6", "#E8D5B7", "#1A1A40",
    ]),
    ("stained glass", [
        "#1B1B2F", "#C0392B", "#2980B9", "#F1C40F", "#1E8449",
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
    ("deep sea", [
        "#0C1445", "#1A5276", "#48C9B0", "#F5F5F5", "#0E6655",
    ]),
    ("plum and gold", [
        "#4A0E4E", "#7D3C98", "#F4D03F", "#FDEBD0", "#1A1A2E",
    ]),
    ("storm", [
        "#2C3E50", "#5D6D7E", "#AEB6BF", "#F2F3F4", "#1C2833",
    ]),
    ("northern lights", [
        "#0B0B3B", "#1B8A6B", "#7FDBCA", "#C77DFF", "#F0F8FF",
    ]),
]


def hex_to_rgb(h):
    """Convert hex color string to (r, g, b) float tuple (0-1)."""
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) / 255.0 for i in (0, 2, 4))
