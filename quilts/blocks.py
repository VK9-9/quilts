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


def star(x, y, size, n_colors):
    """Eight-pointed star — center square rotated 45 degrees with corner kites."""
    cx, cy = x + size / 2, y + size / 2
    # inner square inset
    d = size * 0.25
    inner = [
        (cx, y + d), (x + size - d, cy),
        (cx, y + size - d), (x + d, cy),
    ]
    # center diamond
    patches = [(inner, 0)]
    # star points — triangles from each inner vertex to adjacent corners
    corners = [
        (x, y), (x + size, y),
        (x + size, y + size), (x, y + size),
    ]
    for i in range(4):
        patches.append((
            [inner[i], corners[i], inner[(i + 1) % 4]],
            1 % n_colors,
        ))
    # corner squares
    patches.append(([(x, y), (cx, y + d), (x + d, cy), (x, y)], 0))
    patches.append(([(x, y), (x + d, cy)], 0))  # degenerate, skip
    # simpler: fill four corner triangles
    patches = [(inner, 0)]
    for i in range(4):
        patches.append((
            [inner[i], corners[i], inner[(i + 1) % 4]],
            1 % n_colors,
        ))
    # background corner triangles
    edges_mid = [(cx, y), (x + size, cy), (cx, y + size), (x, cy)]
    for i in range(4):
        patches.append((
            [corners[i], edges_mid[i], corners[i]],
            0,
        ))
    # Actually let me redo this cleanly
    patches = []
    # the star is 8 kite-shaped triangles radiating from center
    # plus 4 corner squares
    m = size * 0.25  # margin for inner square
    # midpoints of each edge
    mt = (cx, y)      # mid-top
    mr = (x + size, cy)  # mid-right
    mb = (cx, y + size)  # mid-bottom
    ml = (x, cy)      # mid-left
    # inner diamond vertices
    it = (cx, y + m)
    ir = (x + size - m, cy)
    ib = (cx, y + size - m)
    il = (x + m, cy)
    # center diamond
    patches.append(([it, ir, ib, il], 0))
    # star points (triangles)
    patches.append(([it, mt, ir], 1 % n_colors))
    patches.append(([ir, mr, ib], 1 % n_colors))
    patches.append(([ib, mb, il], 1 % n_colors))
    patches.append(([il, ml, it], 1 % n_colors))
    # corner squares
    patches.append(([(x, y), mt, it, il], 2 % n_colors))
    patches.append(([(x + size, y), mr, ir, it], 2 % n_colors))
    patches.append(([(x + size, y + size), mb, ib, ir], 2 % n_colors))
    patches.append(([(x, y + size), ml, il, ib], 2 % n_colors))
    return patches


def windmill(x, y, size, n_colors):
    """Four paired triangles creating a spinning windmill effect."""
    cx, cy = x + size / 2, y + size / 2
    mx, my = x + size, y + size
    patches = [
        # top-left quadrant
        ([(x, y), (cx, y), (cx, cy)], 0),
        ([(x, y), (cx, cy), (x, cy)], 1 % n_colors),
        # top-right quadrant
        ([(cx, y), (mx, y), (cx, cy)], 1 % n_colors),
        ([(mx, y), (mx, cy), (cx, cy)], 0),
        # bottom-right quadrant
        ([(mx, cy), (mx, my), (cx, cy)], 1 % n_colors),
        ([(cx, cy), (mx, my), (cx, my)], 0),
        # bottom-left quadrant
        ([(x, cy), (cx, cy), (cx, my)], 0),
        ([(x, cy), (cx, my), (x, my)], 1 % n_colors),
    ]
    return patches


def diamond_in_square(x, y, size, n_colors):
    """Diamond (rotated square) centered inside a square."""
    cx, cy = x + size / 2, y + size / 2
    # diamond vertices at edge midpoints
    top = (cx, y)
    right = (x + size, cy)
    bottom = (cx, y + size)
    left = (x, cy)
    # center diamond
    patches = [([top, right, bottom, left], 0)]
    # four corner triangles
    patches.append(([(x, y), top, left], 1 % n_colors))
    patches.append(([(x + size, y), right, top], 1 % n_colors))
    patches.append(([(x + size, y + size), bottom, right], 1 % n_colors))
    patches.append(([(x, y + size), left, bottom], 1 % n_colors))
    return patches


def cross(x, y, size, n_colors):
    """Plus/cross shape with colored corners."""
    s3 = size / 3
    x0, x1, x2, x3 = x, x + s3, x + 2 * s3, x + size
    y0, y1, y2, y3 = y, y + s3, y + 2 * s3, y + size
    # cross arms (one color)
    patches = [
        ([(x1, y0), (x2, y0), (x2, y3), (x1, y3)], 0),  # vertical bar
        ([(x0, y1), (x3, y1), (x3, y2), (x0, y2)], 0),  # horizontal bar
    ]
    # corner squares
    patches.append(([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], 1 % n_colors))
    patches.append(([(x2, y0), (x3, y0), (x3, y1), (x2, y1)], 1 % n_colors))
    patches.append(([(x0, y2), (x1, y2), (x1, y3), (x0, y3)], 1 % n_colors))
    patches.append(([(x2, y2), (x3, y2), (x3, y3), (x2, y3)], 1 % n_colors))
    return patches


def bow_tie(x, y, size, n_colors):
    """Two triangles meeting at center, forming a bow-tie shape."""
    cx, cy = x + size / 2, y + size / 2
    # left triangle
    patches = [
        ([(x, y), (cx, cy), (x, y + size)], 0),
        ([(x + size, y), (cx, cy), (x + size, y + size)], 0),
        # top and bottom background triangles
        ([(x, y), (x + size, y), (cx, cy)], 1 % n_colors),
        ([(x, y + size), (x + size, y + size), (cx, cy)], 1 % n_colors),
    ]
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
    star,
    windmill,
    diamond_in_square,
    cross,
    bow_tie,
]
