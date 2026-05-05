"""Grid layout engine with symmetry modes for generative quilts.

Assigns block patterns and color indices to each cell in the grid,
respecting the chosen symmetry mode.
"""
import random
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


def layout_rotational(rows, cols, n_patterns, n_palettes, rng):
    """4-fold rotational symmetry (90-degree rotations)."""
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


def layout_partial(rows, cols, n_patterns, n_palettes, rng, chaos=0.3):
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


def layout_flower(rows, cols, n_patterns, n_palettes, rng):
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


SYMMETRY_MODES = {
    "none": layout_none,
    "mirror": layout_mirror4,
    "rotational": layout_rotational,
    "stripe": layout_stripe,
    "partial": layout_partial,
    "flower": layout_flower,
}
