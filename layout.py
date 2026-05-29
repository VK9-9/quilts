"""Grid layout engine with symmetry modes for generative quilts.

Assigns block patterns and color indices to each cell in the grid,
respecting the chosen symmetry mode.
"""
import math

import noise


def _assign_random(rows, cols, n_patterns, n_palettes, rng):
    """Assign random pattern and palette to each cell."""
    grid = {}
    for r in range(rows):
        for c in range(cols):
            grid[(r, c)] = {
                "pattern": rng.randint(0, n_patterns - 1),
                "palette": rng.randint(0, n_palettes - 1),
                "rotation": rng.randint(0, 3),
            }
    return grid


def layout_none(rows, cols, n_patterns, n_palettes, rng):
    """No symmetry — every cell independent."""
    return _assign_random(rows, cols, n_patterns, n_palettes, rng)


def layout_mirror4(rows, cols, n_patterns, n_palettes, rng):
    """4-fold mirror symmetry (reflect both axes)."""
    grid = {}
    half_r = (rows + 1) // 2
    half_c = (cols + 1) // 2
    for r in range(half_r):
        for c in range(half_c):
            cell = {
                "pattern": rng.randint(0, n_patterns - 1),
                "palette": rng.randint(0, n_palettes - 1),
                "rotation": rng.randint(0, 3),
            }
            mirrors = [
                (r, c),
                (r, cols - 1 - c),
                (rows - 1 - r, c),
                (rows - 1 - r, cols - 1 - c),
            ]
            for mr, mc in mirrors:
                grid[(mr, mc)] = dict(cell)
    return grid


def layout_rotational(rows, cols, n_patterns, n_palettes, rng):  # pylint: disable=too-many-locals
    """4-fold rotational symmetry (90-degree rotations).

    Requires a square grid (rows == cols) for true rotational symmetry.
    Non-square grids are handled defensively by filling gaps randomly.
    """
    grid = {}
    half_r = (rows + 1) // 2
    half_c = (cols + 1) // 2
    for r in range(half_r):
        for c in range(half_c):
            cell = {
                "pattern": rng.randint(0, n_patterns - 1),
                "palette": rng.randint(0, n_palettes - 1),
                "rotation": rng.randint(0, 3),
            }
            # map (r, c) through 90-degree rotations
            positions = [
                (r, c, 0),
                (c, cols - 1 - r, 1),
                (rows - 1 - r, cols - 1 - c, 2),
                (rows - 1 - c, r, 3),
            ]
            for pr, pc, rot_offset in positions:
                if 0 <= pr < rows and 0 <= pc < cols:
                    rotated = dict(cell)
                    rotated["rotation"] = (cell["rotation"] + rot_offset) % 4
                    grid[(pr, pc)] = rotated
    # fill any gaps from non-square grids
    for r in range(rows):
        for c in range(cols):
            if (r, c) not in grid:
                grid[(r, c)] = {
                    "pattern": rng.randint(0, n_patterns - 1),
                    "palette": rng.randint(0, n_palettes - 1),
                    "rotation": rng.randint(0, 3),
                }
    return grid


def layout_stripe(rows, cols, n_patterns, n_palettes, rng):
    """Horizontal stripe symmetry — mirror top-to-bottom, vary left-to-right."""
    grid = {}
    half_r = (rows + 1) // 2
    for r in range(half_r):
        for c in range(cols):
            cell = {
                "pattern": rng.randint(0, n_patterns - 1),
                "palette": rng.randint(0, n_palettes - 1),
                "rotation": rng.randint(0, 3),
            }
            grid[(r, c)] = cell
            grid[(rows - 1 - r, c)] = dict(cell)
    return grid


def layout_partial(rows, cols, n_patterns, n_palettes, rng, chaos=0.3):  # pylint: disable=too-many-arguments,too-many-positional-arguments
    """Start with mirror symmetry, then perturb cells based on Perlin noise.

    chaos: 0.0 = perfect symmetry, 1.0 = fully random.
    """
    # start from mirror4
    grid = layout_mirror4(rows, cols, n_patterns, n_palettes, rng)

    # perturb using noise
    noise_ox = rng.random() * 1000
    noise_oy = rng.random() * 1000
    scale = 0.15

    for r in range(rows):
        for c in range(cols):
            n = noise.pnoise2(
                c * scale + noise_ox,
                r * scale + noise_oy,
                octaves=2,
            )
            # n is roughly [-1, 1], map to [0, 1]
            threshold = (n + 1) / 2
            if threshold < chaos:
                # re-randomize this cell
                grid[(r, c)] = {
                    "pattern": rng.randint(0, n_patterns - 1),
                    "palette": rng.randint(0, n_palettes - 1),
                    "rotation": rng.randint(0, 3),
                }
    return grid


def layout_flower(rows, cols, n_patterns, n_palettes, rng):  # pylint: disable=too-many-locals
    """Flower/medallion symmetry — distinct center square with mirror-symmetric border.

    The center region (roughly inner 40-60% of the grid) uses one pattern/palette
    with 4-fold mirror symmetry. The outer border uses a different pattern/palette,
    also mirror-symmetric. Creates a medallion quilt look.
    """
    grid = {}

    # determine center region (randomize the proportion a bit)
    center_frac = 0.3 + rng.random() * 0.2  # 30-50% of each axis
    margin_r = int(rows * (1 - center_frac) / 2)
    margin_c = int(cols * (1 - center_frac) / 2)
    margin_r = max(margin_r, 2)
    margin_c = max(margin_c, 2)

    # pick distinct patterns for center vs border
    if n_patterns >= 2:
        center_pat = rng.randint(0, n_patterns - 1)
        border_pat = rng.randint(0, n_patterns - 1)
        while border_pat == center_pat and n_patterns > 1:
            border_pat = rng.randint(0, n_patterns - 1)
    else:
        center_pat = 0
        border_pat = 0

    # center palette index differs from border
    center_pal = 0
    border_pal = min(1, n_palettes - 1)

    # fill center with mirror4 symmetry
    cr_start, cr_end = margin_r, rows - margin_r
    cc_start, cc_end = margin_c, cols - margin_c
    ch = cr_end - cr_start
    cw = cc_end - cc_start
    half_r = (ch + 1) // 2
    half_c = (cw + 1) // 2

    for r in range(half_r):
        for c in range(half_c):
            cell = {
                "pattern": center_pat,
                "palette": center_pal,
                "rotation": rng.randint(0, 3),
            }
            mirrors = [
                (cr_start + r, cc_start + c),
                (cr_start + r, cc_end - 1 - c),
                (cr_end - 1 - r, cc_start + c),
                (cr_end - 1 - r, cc_end - 1 - c),
            ]
            for mr, mc in mirrors:
                if 0 <= mr < rows and 0 <= mc < cols:
                    grid[(mr, mc)] = dict(cell)

    # fill border with mirror4 symmetry (over the whole grid, then overwrite)
    half_r = (rows + 1) // 2
    half_c = (cols + 1) // 2
    for r in range(half_r):
        for c in range(half_c):
            # skip cells already assigned to center
            if cr_start <= r < cr_end and cc_start <= c < cc_end:
                continue
            cell = {
                "pattern": border_pat,
                "palette": border_pal,
                "rotation": rng.randint(0, 3),
            }
            mirrors = [
                (r, c),
                (r, cols - 1 - c),
                (rows - 1 - r, c),
                (rows - 1 - r, cols - 1 - c),
            ]
            for mr, mc in mirrors:
                if (mr, mc) not in grid:
                    grid[(mr, mc)] = dict(cell)

    return grid


def layout_emergent(rows, cols, n_patterns, _n_palettes, rng):  # pylint: disable=too-many-locals,too-many-branches
    """Emergent macro patterns via coordinated block rotations.

    Uses a single block pattern and assigns rotations so that block edges
    connect across boundaries, creating larger visual patterns that only
    exist in the arrangement — no single block contains the macro shape.

    Four macro templates:
    - zigzag: alternating diagonal directions create chevron/zigzag paths
    - diamond: rotations form concentric diamond rings from center
    - barn_raising: concentric frames with quadrant-aware rotation
    - pinwheel_macro: 2x2 pinwheel groups tiled across the grid
    """
    grid = {}

    macro = rng.choice(['zigzag', 'diamond', 'barn_raising', 'pinwheel_macro'])
    pat = rng.randint(0, n_patterns - 1)
    pal = 0

    mid_r = rows / 2
    mid_c = cols / 2

    for r in range(rows):
        for c in range(cols):
            if macro == 'zigzag':
                # alternating cells flip diagonal → chevron paths
                rotation = 0 if (r + c) % 2 == 0 else 1

            elif macro == 'diamond':
                # quadrant determines base rotation; Manhattan ring alternates
                cr = r - mid_r
                cc = c - mid_c
                if cr <= 0 and cc >= 0:  # pylint: disable=chained-comparison
                    rotation = 0
                elif cr >= 0 and cc >= 0:
                    rotation = 1
                elif cr >= 0 and cc <= 0:  # pylint: disable=chained-comparison
                    rotation = 2
                else:
                    rotation = 3
                dist = abs(int(cr)) + abs(int(cc))
                if dist % 2 == 1:
                    rotation = (rotation + 2) % 4

            elif macro == 'barn_raising':
                # concentric rings from edge; quadrant rotation
                ring = min(r, rows - 1 - r, c, cols - 1 - c)
                if r < mid_r and c < mid_c:
                    rotation = 0
                elif r < mid_r:
                    rotation = 1
                elif c >= mid_c:
                    rotation = 2
                else:
                    rotation = 3
                if ring % 2 == 1:
                    rotation = (rotation + 2) % 4

            elif macro == 'pinwheel_macro':
                # 2x2 groups, each cell rotated 90° from neighbors
                lr, lc = r % 2, c % 2
                rotation = [0, 1, 3, 2][lr * 2 + lc]

            grid[(r, c)] = {
                "pattern": pat,
                "palette": pal,
                "rotation": rotation,
            }

    return grid


def layout_bargello(rows, cols, _n_patterns, _n_palettes, rng):
    """Bargello: vertical strips with undulating color waves.

    Each column has the same repeating color sequence, shifted up/down
    by a wave function to create the characteristic bargello undulation.
    Cells store a _bargello_color index used by the renderer.
    """
    grid = {}
    amplitude = rng.uniform(2.0, min(rows * 0.3, 6))
    period = rng.uniform(cols * 0.3, cols * 0.8)
    phase = rng.random() * 2 * math.pi
    strip_h = rng.choice([1, 1, 2])  # height of each color strip

    for r in range(rows):
        for c in range(cols):
            shift = amplitude * math.sin(2 * math.pi * c / period + phase)
            color_row = int((r + shift) / max(strip_h, 1))
            grid[(r, c)] = {
                "pattern": 0,
                "palette": 0,
                "rotation": 0,
                "_bargello_color": color_row,
            }
    return grid


def layout_columns(rows, cols, n_patterns, _n_palettes, rng):
    """Vertical strip sampler — 4-6 columns, all sharing the same block pattern.

    Columns differ by rotation only, keeping a cohesive look while still
    having visible vertical structure.
    """
    grid = {}
    n_strips = rng.randint(4, 6)
    strip_width = cols // n_strips
    # all strips share one pattern; vary by rotation per strip
    shared_pattern = rng.randint(0, n_patterns - 1)
    rotations = [rng.randint(0, 3) for _ in range(n_strips)]

    for r in range(rows):
        for c in range(cols):
            strip = min(c // max(strip_width, 1), n_strips - 1)
            grid[(r, c)] = {
                "pattern": shared_pattern,
                "palette": 0,
                "rotation": rotations[strip],
            }
    return grid


SYMMETRY_MODES = {
    "none": layout_none,
    "mirror": layout_mirror4,
    "rotational": layout_rotational,
    "stripe": layout_stripe,
    "partial": layout_partial,
    "flower": layout_flower,
    "emergent": layout_emergent,
    "bargello": layout_bargello,
    "columns": layout_columns,
}
