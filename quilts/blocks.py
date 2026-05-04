"""Block pattern definitions for generative quilts.

Each block pattern is a function that takes (x, y, size, n_colors) and returns
a list of patches. Each patch is (polygon, color_index) where polygon is a list
of (px, py) points and color_index selects from the block's assigned palette.
"""
import random
import math


def half_square_triangle(x, y, size, n_colors):
    """Two triangles split along the diagonal."""
    direction = random.randint(0, 1)
    if direction == 0:
        # top-left to bottom-right diagonal
        return [
            ([(x, y), (x + size, y), (x, y + size)], 0),
            ([(x + size, y), (x + size, y + size), (x, y + size)], 1),
        ]
    else:
        # top-right to bottom-left diagonal
        return [
            ([(x, y), (x + size, y), (x + size, y + size)], 0),
            ([(x, y), (x + size, y + size), (x, y + size)], 1),
        ]


def nine_patch(x, y, size, n_colors):
    """3x3 grid of squares, alternating two colors (checkerboard)."""
    s = size / 3
    patches = []
    for r in range(3):
        for c in range(3):
            ci = (r + c) % 2
            px, py = x + c * s, y + r * s
            patches.append((
                [(px, py), (px + s, py), (px + s, py + s), (px, py + s)],
                ci,
            ))
    return patches


def log_cabin(x, y, size, n_colors):
    """Concentric rectangular strips around a center square.

    Builds outward by adding one strip per side in order: top, right, bottom,
    left, extending each strip to cover the corner created by the previous one.
    """
    patches = []
    cs = size * 0.12  # half-width of center square
    cx, cy = x + size / 2, y + size / 2
    patches.append((
        [(cx - cs, cy - cs), (cx + cs, cy - cs),
         (cx + cs, cy + cs), (cx - cs, cy + cs)],
        0,
    ))

    # current inner rectangle edges
    left, top, right, bottom = cx - cs, cy - cs, cx + cs, cy + cs
    remaining = size / 2 - cs
    n_rings = 3
    sw = remaining / n_rings  # strip width

    for ring in range(n_rings):
        ci = (ring % max(n_colors - 1, 1)) + 1 if n_colors > 1 else 0

        # top strip — spans full width including new corners
        patches.append((
            [(left - sw, top - sw), (right, top - sw),
             (right, top), (left - sw, top)],
            ci,
        ))
        top -= sw
        left -= sw

        # right strip
        ci = ((ring + 1) % max(n_colors - 1, 1)) + 1 if n_colors > 1 else 0
        patches.append((
            [(right, top), (right + sw, top),
             (right + sw, bottom), (right, bottom)],
            ci,
        ))
        right += sw

        # bottom strip
        ci = (ring % max(n_colors - 1, 1)) + 1 if n_colors > 1 else 0
        patches.append((
            [(left, bottom), (right, bottom),
             (right, bottom + sw), (left, bottom + sw)],
            ci,
        ))
        bottom += sw

        # left strip
        ci = ((ring + 1) % max(n_colors - 1, 1)) + 1 if n_colors > 1 else 0
        patches.append((
            [(left - sw, top), (left, top),
             (left, bottom), (left - sw, bottom)],
            ci,
        ))
        left -= sw

    return patches


def pinwheel(x, y, size, n_colors):
    """Four triangles arranged in a pinwheel rotation."""
    cx, cy = x + size / 2, y + size / 2
    corners = [
        (x, y), (x + size, y),
        (x + size, y + size), (x, y + size),
    ]
    patches = []
    for i in range(4):
        patches.append((
            [corners[i], corners[(i + 1) % 4], (cx, cy)],
            i % 2,
        ))
    return patches


def flying_geese(x, y, size, n_colors):
    """Row of triangles pointing upward with background triangles."""
    n = 3
    w = size / n
    h = size
    patches = []
    for i in range(n):
        gx = x + i * w
        # goose triangle (pointing up)
        patches.append((
            [(gx, y + h), (gx + w / 2, y), (gx + w, y + h)],
            0,
        ))
        # left background
        patches.append((
            [(gx, y), (gx + w / 2, y), (gx, y + h)],
            1,
        ))
        # right background
        patches.append((
            [(gx + w / 2, y), (gx + w, y), (gx + w, y + h)],
            1,
        ))
    return patches


def hourglass(x, y, size, n_colors):
    """Two triangles forming an hourglass shape with background."""
    cx, cy = x + size / 2, y + size / 2
    # top triangle
    patches = [
        ([(x, y), (x + size, y), (cx, cy)], 0),
        ([(x, y + size), (x + size, y + size), (cx, cy)], 0),
        ([(x, y), (cx, cy), (x, y + size)], 1),
        ([(x + size, y), (x + size, y + size), (cx, cy)], 1),
    ]
    return patches


def chevron(x, y, size, n_colors):
    """Horizontal V-shaped stripes (chevron / arrow pattern)."""
    patches = []
    n = 4
    h = size / n
    cx = x + size / 2
    for i in range(n):
        ci = i % min(n_colors, 2)
        top = y + i * h
        mid = top + h / 2
        bot = top + h
        # left half — triangle pointing right
        patches.append((
            [(x, top), (cx, mid), (x, bot)],
            ci,
        ))
        # right half — triangle pointing left
        patches.append((
            [(x + size, top), (cx, mid), (x + size, bot)],
            ci,
        ))
    return patches


# Registry of all block patterns
BLOCK_PATTERNS = [
    half_square_triangle,
    nine_patch,
    log_cabin,
    pinwheel,
    flying_geese,
    hourglass,
    chevron,
]
