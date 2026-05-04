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


SYMMETRY_MODES = {
    "none": layout_none,
    "mirror": layout_mirror4,
    "rotational": layout_rotational,
    "stripe": layout_stripe,
    "partial": layout_partial,
}
