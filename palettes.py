"""Curated color palettes for generative quilts.

Each palette is a tuple of (name, list_of_hex_colors).
Colors within a palette are meant to coordinate like real quilting fabric selections.
"""

PALETTES = [
    (
        "ocean breeze",
        [
            "#1B3A5C",
            "#4682B4",
            "#87CEEB",
            "#F0F8FF",
            "#2E8B57",
            "#C4A35A",
        ],
    ),
    (
        "wildflower",
        [
            "#8B008B",
            "#DA70D6",
            "#FFB6C1",
            "#FFFACD",
            "#228B22",
            "#E8963A",
        ],
    ),
    (
        "indigo dye",
        [
            "#1A0533",
            "#3F00FF",
            "#7B68EE",
            "#E6E6FA",
            "#F5F5F5",
            "#4A7B9B",
        ],
    ),
    (
        "storm",
        [
            "#2C3E50",
            "#5D6D7E",
            "#AEB6BF",
            "#F2F3F4",
            "#1C2833",
            "#8B6B4A",
        ],
    ),
    (
        "northern lights",
        [
            "#0B0B3B",
            "#1B8A6B",
            "#7FDBCA",
            "#C77DFF",
            "#F0F8FF",
            "#E85D75",
        ],
    ),
    (
        "midnight moss",
        [
            "#0D1F0D",
            "#2D6A2D",
            "#6B9E6B",
            "#C4D9A0",
            "#F0EDD8",
            "#7B5B3A",
        ],
    ),
    (
        "cherry blossom",
        [
            "#FFB7C5",
            "#FF69B4",
            "#D1426E",
            "#F8E8EE",
            "#4A0E2B",
            "#8B6B50",
        ],
    ),
    (
        "tide pool",
        [
            "#1B6B7D",
            "#3CACBB",
            "#7DD8C7",
            "#E0F5F0",
            "#0E4D5A",
            "#D4976A",
        ],
    ),
    (
        "lavender fields",
        [
            "#5B3A8C",
            "#9B72CF",
            "#C8A2E8",
            "#E8D5F5",
            "#3D6B4F",
            "#D4A060",
        ],
    ),
    (
        "copper canyon",
        [
            "#8B4513",
            "#CD853F",
            "#DEB887",
            "#F5E6CC",
            "#A0522D",
            "#4A7068",
        ],
    ),
    (
        "winter frost",
        [
            "#4A6FA5",
            "#89ABD9",
            "#C5D8ED",
            "#F0F4F8",
            "#2C4A6E",
            "#A0887B",
        ],
    ),
    (
        "sage garden",
        [
            "#4A6741",
            "#7D9B6E",
            "#A8C49A",
            "#E8F0E0",
            "#3B5332",
            "#B8946A",
        ],
    ),
    (
        "plum wine",
        [
            "#4A0028",
            "#7B2D5F",
            "#B85C8A",
            "#E8B4D0",
            "#F5E6EF",
            "#6B5040",
        ],
    ),
    (
        "coastal fog",
        [
            "#5B7B8A",
            "#8FAAB5",
            "#C4D4DB",
            "#EDF2F4",
            "#3E5A66",
            "#B89878",
        ],
    ),
    (
        "amber glow",
        [
            "#8B5E00",
            "#D4940A",
            "#F0C040",
            "#FFF3D4",
            "#6B4500",
            "#7B8B5A",
        ],
    ),
    (
        "twilight",
        [
            "#1A1040",
            "#3D2C7C",
            "#7B5EA7",
            "#D4A0C0",
            "#F0E0E8",
            "#4A8B7B",
        ],
    ),
    (
        "sea glass",
        [
            "#2D7D6E",
            "#6BBFAB",
            "#A8E0D0",
            "#E8F5F0",
            "#1A5C50",
            "#B87B6B",
        ],
    ),
    (
        "moonstone",
        [
            "#3A4B7C",
            "#7B8FBF",
            "#B0C4DE",
            "#E8EEF5",
            "#9B8EC4",
            "#6B9B7B",
        ],
    ),
    (
        "wisteria",
        [
            "#5C2D82",
            "#8B5DAF",
            "#C49BD8",
            "#E8D0F0",
            "#D47FAA",
            "#5B8B6B",
        ],
    ),
    (
        "honey oak",
        [
            "#7A5230",
            "#B8864A",
            "#D4AA70",
            "#F0E0C8",
            "#5C3D20",
            "#6B8B7A",
        ],
    ),
    (
        "thistle",
        [
            "#6B5B7B",
            "#9B89A8",
            "#C8B8D8",
            "#E8DDE8",
            "#7B8B6B",
            "#A07858",
        ],
    ),
    (
        "river stone",
        [
            "#4A5568",
            "#7B8FA0",
            "#A8B8C4",
            "#E0E8EC",
            "#6B8B7A",
            "#8B6B5B",
        ],
    ),
    (
        "bluebell",
        [
            "#2A3B6B",
            "#4A6BAB",
            "#7B9BD0",
            "#C0D4E8",
            "#4A7B5C",
            "#C4907B",
        ],
    ),
    (
        "frosted berry",
        [
            "#6B3A5C",
            "#9B6B8A",
            "#C89BB0",
            "#E8D0DC",
            "#5B7B8C",
            "#A08B5B",
        ],
    ),
    (
        "dove grey",
        [
            "#5A5060",
            "#8B7F90",
            "#B8AEBA",
            "#E0D8E0",
            "#7A8B7A",
            "#9B7B68",
        ],
    ),
    (
        "handloom",
        [
            "#F5EDE3",
            "#D4793A",
            "#B51E4A",
            "#1C3D52",
            "#E8907A",
            "#D4503E",
        ],
    ),
]


def hex_to_rgb(h):
    """Convert hex color string to (r, g, b) float tuple (0-1)."""
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4))


def luminance(color):
    """Perceived brightness of a hex string or an (r, g, b) float tuple.

    >>> luminance("#000000")
    0.0
    >>> luminance("#FFFFFF")
    1.0
    """
    r, g, b = hex_to_rgb(color) if isinstance(color, str) else color
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def subset_in_tonal_order(colors, k, rng):
    """Pick k of `colors` at random, returned ordered dark to light.

    Bargello reads consecutive palette indices as consecutive tones — the
    undulating wave is only legible if stepping one index steps one shade.
    Palettes are authored as a tonal ramp followed by accent colors, so
    neither selection order (what rng.sample returns) nor palette order
    gives that; a subset that picks up an accent puts a hue jump in the
    middle of the ramp and the wave aliases into a checkerboard. Sorting by
    luminance makes the invariant true by construction, whatever was drawn.

    Every other symmetry reshuffles per cell via color_map, so the ordering
    is a no-op for them.

    >>> import random
    >>> subset_in_tonal_order(["#FFFFFF", "#000000", "#808080"], 3, random.Random(0))
    ['#000000', '#808080', '#FFFFFF']
    >>> pal = ["#5B3A8C", "#9B72CF", "#C8A2E8", "#E8D5F5", "#3D6B4F", "#D4A060"]
    >>> vals = [luminance(c) for c in subset_in_tonal_order(pal, 4, random.Random(1))]
    >>> vals == sorted(vals)
    True
    """
    # Leave the RNG untouched when no choice is actually being made — the PDF
    # reconstruction replays this stream and must stay in step with the render.
    chosen = list(colors) if k >= len(colors) else rng.sample(colors, k)
    return sorted(chosen, key=luminance)
