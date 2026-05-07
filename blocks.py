"""Block pattern definitions for generative quilts.

Each block pattern is a function that takes (x, y, size, n_colors) and returns
a list of patches. Each patch is (polygon, color_index) where polygon is a list
of (px, py) points and color_index selects from the block's assigned palette.
"""
import random


def half_square_triangle(x, y, size, _n_colors):
    """Two triangles split along the diagonal."""
    direction = random.randint(0, 1)
    if direction == 0:
        # top-left to bottom-right diagonal
        return [
            ([(x, y), (x + size, y), (x, y + size)], 0),
            ([(x + size, y), (x + size, y + size), (x, y + size)], 1),
        ]
    # top-right to bottom-left diagonal
    return [
        ([(x, y), (x + size, y), (x + size, y + size)], 0),
        ([(x, y), (x + size, y + size), (x, y + size)], 1),
    ]


def nine_patch(x, y, size, _n_colors):
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


def pinwheel(x, y, size, _n_colors):
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


def flying_geese(x, y, size, _n_colors):
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


def hourglass(x, y, size, _n_colors):
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
    """Eight-pointed star — center diamond, 4 point triangles, 4 corner quads."""
    cx, cy = x + size / 2, y + size / 2
    m = size * 0.25
    # edge midpoints
    mt = (cx, y)
    mr = (x + size, cy)
    mb = (cx, y + size)
    ml = (x, cy)
    # inner diamond vertices
    it = (cx, y + m)
    ir = (x + size - m, cy)
    ib = (cx, y + size - m)
    il = (x + m, cy)
    patches = [
        ([it, ir, ib, il], 0),                            # center diamond
        ([it, mt, ir], 1 % n_colors),                     # star points
        ([ir, mr, ib], 1 % n_colors),
        ([ib, mb, il], 1 % n_colors),
        ([il, ml, it], 1 % n_colors),
        ([(x, y), mt, it, il], 2 % n_colors),             # corner quads
        ([(x + size, y), mr, ir, it], 2 % n_colors),
        ([(x + size, y + size), mb, ib, ir], 2 % n_colors),
        ([(x, y + size), ml, il, ib], 2 % n_colors),
    ]
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


def ohio_star(x, y, size, n_colors):
    """Ohio Star — 3x3 grid with center square, corner squares, and side triangles.

    Uses 3 colors: corners, center, and star points.
    """
    s = size / 3
    patches = []
    for r in range(3):
        for c in range(3):
            px, py = x + c * s, y + r * s
            if (r, c) in [(0, 0), (0, 2), (2, 0), (2, 2)]:
                # corner squares
                patches.append((
                    [(px, py), (px + s, py), (px + s, py + s), (px, py + s)],
                    0,
                ))
            elif (r, c) == (1, 1):
                # center square
                patches.append((
                    [(px, py), (px + s, py), (px + s, py + s), (px, py + s)],
                    2 % n_colors,
                ))
            else:
                # side cells: split into two triangles (star points)
                mid_x, mid_y = px + s / 2, py + s / 2
                if r == 0:  # top
                    patches.append(([(px, py), (px + s, py), (mid_x, py + s)], 1 % n_colors))
                    patches.append(([(px, py), (mid_x, py + s), (px, py + s)], 0))
                    patches.append(([(px + s, py), (px + s, py + s), (mid_x, py + s)], 0))
                elif r == 2:  # bottom
                    patches.append(([(px, py + s), (px + s, py + s), (mid_x, py)], 1 % n_colors))
                    patches.append(([(px, py), (mid_x, py), (px, py + s)], 0))
                    patches.append(([(mid_x, py), (px + s, py), (px + s, py + s)], 0))
                elif c == 0:  # left
                    patches.append(([(px, py), (px, py + s), (px + s, mid_y)], 1 % n_colors))
                    patches.append(([(px, py), (px + s, mid_y), (px + s, py)], 0))
                    patches.append(([(px, py + s), (px + s, py + s), (px + s, mid_y)], 0))
                else:  # right
                    patches.append(([(px + s, py), (px + s, py + s), (px, mid_y)], 1 % n_colors))
                    patches.append(([(px, py), (px, mid_y), (px + s, py)], 0))
                    patches.append(([(px, mid_y), (px, py + s), (px + s, py + s)], 0))
    return patches


def courthouse_steps(x, y, size, n_colors):
    """Courthouse Steps — log cabin variant with symmetric strips on opposite sides.

    Alternates two colors in concentric rectangular frames around a center.
    """
    patches = []
    cs = size * 0.1  # center half-width
    cx, cy = x + size / 2, y + size / 2
    # center square
    patches.append((
        [(cx - cs, cy - cs), (cx + cs, cy - cs),
         (cx + cs, cy + cs), (cx - cs, cy + cs)],
        0,
    ))

    left, top, right, bottom = cx - cs, cy - cs, cx + cs, cy + cs
    remaining = size / 2 - cs
    n_rings = 4
    sw = remaining / n_rings

    for ring in range(n_rings):
        ci = (ring % max(n_colors - 1, 1)) + 1 if n_colors > 1 else 0
        ci2 = ((ring + 1) % max(n_colors - 1, 1)) + 1 if n_colors > 1 else 0

        # top and bottom strips (same color)
        patches.append((
            [(left, top - sw), (right, top - sw),
             (right, top), (left, top)],
            ci,
        ))
        patches.append((
            [(left, bottom), (right, bottom),
             (right, bottom + sw), (left, bottom + sw)],
            ci,
        ))
        top -= sw
        bottom += sw

        # left and right strips (different color)
        patches.append((
            [(left - sw, top), (left, top),
             (left, bottom), (left - sw, bottom)],
            ci2,
        ))
        patches.append((
            [(right, top), (right + sw, top),
             (right + sw, bottom), (right, bottom)],
            ci2,
        ))
        left -= sw
        right += sw

    return patches


def checkerboard_4x4(x, y, size, n_colors):
    """4x4 checkerboard with diagonal splits in alternating cells.

    Half the cells are solid squares, half are split diagonally into two colors.
    Creates a complex interlocking texture.
    """
    s = size / 4
    patches = []
    for r in range(4):
        for c in range(4):
            px, py = x + c * s, y + r * s
            if (r + c) % 2 == 0:
                # solid square
                patches.append((
                    [(px, py), (px + s, py), (px + s, py + s), (px, py + s)],
                    0,
                ))
            else:
                # diagonal split
                patches.append((
                    [(px, py), (px + s, py), (px, py + s)],
                    1 % n_colors,
                ))
                patches.append((
                    [(px + s, py), (px + s, py + s), (px, py + s)],
                    2 % n_colors,
                ))
    return patches


def card_trick(x, y, size, n_colors):
    """Card Trick — overlapping rotated squares creating an interlocking pattern.

    Four overlapping triangles that create the illusion of layered cards.
    Uses up to 4 colors.
    """
    cx, cy = x + size / 2, y + size / 2
    q = size / 4  # quarter
    # center square
    patches = [
        ([(cx - q, cy - q), (cx + q, cy - q),
          (cx + q, cy + q), (cx - q, cy + q)], 0),
    ]
    # four "cards" — each is a triangle from center to a corner, clipped
    # top-left card
    patches.append(([(x, y), (cx, y), (cx, cy - q), (cx - q, cy - q), (cx - q, cy), (x, cy)], 1 % n_colors))
    # top-right card
    patches.append(([(cx, y), (x + size, y), (x + size, cy), (cx + q, cy), (cx + q, cy - q), (cx, cy - q)], 2 % n_colors))
    # bottom-right card
    patches.append(([(cx + q, cy), (x + size, cy), (x + size, y + size), (cx, y + size), (cx, cy + q), (cx + q, cy + q)], 3 % n_colors))
    # bottom-left card
    patches.append(([(x, cy), (cx - q, cy), (cx - q, cy + q), (cx, cy + q), (cx, y + size), (x, y + size)], 1 % n_colors))
    return patches


def double_pinwheel(x, y, size, n_colors):
    """Double Pinwheel — nested pinwheels at two scales.

    Outer quadrants each contain a smaller pinwheel, creating fractal-like depth.
    """
    patches = []
    half = size / 2
    cx, cy = x + size / 2, y + size / 2

    # outer pinwheel triangles (color 0 and 1)
    corners = [(x, y), (x + size, y), (x + size, y + size), (x, y + size)]
    mids = [(cx, y), (x + size, cy), (cx, y + size), (x, cy)]
    for i in range(4):
        patches.append((
            [corners[i], mids[i], (cx, cy)],
            i % 2,
        ))
        patches.append((
            [mids[i], corners[(i + 1) % 4], (cx, cy)],
            (i + 1) % 2,
        ))

    # inner pinwheel (smaller, using colors 2 and 3)
    q = size / 4
    ic = [(cx - q, cy - q), (cx + q, cy - q), (cx + q, cy + q), (cx - q, cy + q)]
    im = [(cx, cy - q), (cx + q, cy), (cx, cy + q), (cx - q, cy)]
    for i in range(4):
        patches.append((
            [ic[i], im[i], (cx, cy)],
            2 % n_colors,
        ))
        patches.append((
            [im[i], ic[(i + 1) % 4], (cx, cy)],
            3 % n_colors,
        ))
    return patches


def diagonal(x, y, size, n_colors):
    """Deterministic diagonal split — always TL-BR direction.

    Unlike half_square_triangle, has no internal randomness so rotation
    fully controls direction. Designed for emergent layout mode where
    coordinated rotations create macro patterns (zigzags, diamonds, etc).
    """
    return [
        ([(x, y), (x + size, y), (x, y + size)], 0),
        ([(x + size, y), (x + size, y + size), (x, y + size)], 1 % n_colors),
    ]


def path_tile(x, y, size, n_colors):
    """Truchet-style path tile — two diagonal bands connecting edge midpoint pairs.

    Band 1 connects top midpoint to right midpoint (through upper-right).
    Band 2 connects left midpoint to bottom midpoint (through lower-left).
    Rotation changes which midpoints connect, creating continuous winding
    paths when tiles are arranged with coordinated rotations.
    """
    cx, cy = x + size / 2, y + size / 2
    w = size * 0.12  # band half-width

    # band from top-midpoint to right-midpoint
    # band from left-midpoint to bottom-midpoint
    patches = [
        # top-to-right band (trapezoid through upper-right area)
        ([(cx - w, y), (cx + w, y),
          (x + size, cy - w), (x + size, cy + w)], 0),
        # left-to-bottom band (trapezoid through lower-left area)
        ([(x, cy - w), (x, cy + w),
          (cx + w, y + size), (cx - w, y + size)], 0),
        # upper-left background triangle
        ([(x, y), (cx - w, y), (x, cy - w)], 1 % n_colors),
        # lower-right background triangle
        ([(x + size, cy + w), (x + size, y + size), (cx + w, y + size)], 1 % n_colors),
        # upper-right background (between the two bands)
        ([(cx + w, y), (x + size, y), (x + size, cy - w)], 2 % n_colors),
        # lower-left background (between the two bands)
        ([(x, cy + w), (x, y + size), (cx - w, y + size)], 2 % n_colors),
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
    ohio_star,
    courthouse_steps,
    checkerboard_4x4,
    card_trick,
    double_pinwheel,
    diagonal,
    path_tile,
]
