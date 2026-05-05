"""Generative quilt renderer using pycairo.

Usage:
    python quilts/quilt.py [options]

Options:
    --rows N          Grid rows (default: 20)
    --cols N          Grid cols (default: 20)
    --block-size N    Block size in pixels (default: 60)
    --symmetry MODE   none|mirror|rotational|stripe|partial (default: partial)
    --chaos FLOAT     Chaos amount for partial symmetry, 0-1 (default: 0.3)
    --palette NAME    Palette name, or 'random' (default: random)
    --seed N          Random seed (default: random)
    --output FILE     Output filename (default: quilts/out.png)
    --border N        Border/margin in pixels (default: 20)
"""
import argparse
import math
import random
import sys
import os

import cairo

from blocks import BLOCK_PATTERNS
from palettes import PALETTES, hex_to_rgb
from layout import SYMMETRY_MODES


def pick_palettes(palette_name, n_needed, rng):
    """Select palette colors. Returns a list of lists of (r,g,b) tuples."""
    if palette_name == "random":
        chosen = rng.choice(PALETTES)
    else:
        matches = [p for p in PALETTES if p[0] == palette_name]
        if not matches:
            print(f"Unknown palette '{palette_name}'. Available:")
            for name, _ in PALETTES:
                print(f"  {name}")
            sys.exit(1)
        chosen = matches[0]

    name, colors = chosen
    print(f"Palette: {name}")
    rgb_colors = [hex_to_rgb(c) for c in colors]
    return rgb_colors


def rotate_patches(patches, cx, cy, rotation):
    """Rotate patches 0/90/180/270 degrees around (cx, cy)."""
    if rotation == 0:
        return patches

    def rot_point(px, py, n):
        dx, dy = px - cx, py - cy
        for _ in range(n):
            dx, dy = -dy, dx
        return cx + dx, cy + dy

    rotated = []
    for poly, ci in patches:
        new_poly = [rot_point(px, py, rotation) for px, py in poly]
        rotated.append((new_poly, ci))
    return rotated


def _build_tiled_grid(rows, cols, tile_size, tile_variation, n_patterns,
                      n_colors, rng):
    """Build grid by stamping a template tile with tiny per-copy variations.

    1. Generate one template tile (tile_size x tile_size) with the layout engine
    2. Copy it into every tile position
    3. Perturb a small fraction of blocks per copy (nudge rotation, swap pattern)
    """
    ts = tile_size
    # generate template tile
    template = {}
    for r in range(ts):
        for c in range(ts):
            template[(r, c)] = {
                "pattern": rng.randint(0, n_patterns - 1),
                "palette": 0,
                "rotation": rng.randint(0, 3),
            }

    # stamp into full grid
    grid = {}
    tile_rows = math.ceil(rows / ts)
    tile_cols = math.ceil(cols / ts)
    for tr in range(tile_rows):
        for tc in range(tile_cols):
            for lr in range(ts):
                for lc in range(ts):
                    gr, gc = tr * ts + lr, tc * ts + lc
                    if gr >= rows or gc >= cols:
                        continue
                    cell = dict(template[(lr, lc)])
                    # perturb
                    if rng.random() < tile_variation:
                        # pick a random perturbation: rotation or pattern swap
                        if rng.random() < 0.6:
                            cell["rotation"] = (cell["rotation"] + rng.choice([1, 3])) % 4
                        else:
                            cell["pattern"] = rng.randint(0, n_patterns - 1)
                    grid[(gr, gc)] = cell

    # assign color maps
    for cell in grid.values():
        cell_rng = random.Random(cell["pattern"] * 1000 + cell["palette"])
        indices = list(range(n_colors))
        cell_rng.shuffle(indices)
        cell["color_map"] = indices

    return grid


def render_quilt(rows, cols, block_size, symmetry, chaos, palette_name,
                 seed, output, border, max_patterns=None, max_colors=None,
                 tile_size=None, tile_variation=0.05):
    """Generate and render a quilt to an image file."""
    if seed is None:
        seed = random.randint(0, 2**31)
    rng = random.Random(seed)
    print(f"Seed: {seed}")

    palette_colors = pick_palettes(palette_name, 1, rng)
    if max_colors is not None:
        palette_colors = palette_colors[:max_colors]
    n_colors = len(palette_colors)

    n_all_patterns = len(BLOCK_PATTERNS)
    if max_patterns is not None:
        available = list(range(n_all_patterns))
        rng.shuffle(available)
        allowed = sorted(available[:max_patterns])
        n_patterns = max_patterns
    else:
        allowed = None
        n_patterns = n_all_patterns

    if tile_size is not None:
        grid = _build_tiled_grid(rows, cols, tile_size, tile_variation,
                                 n_patterns, n_colors, rng)
        # remap pattern indices to allowed subset
        if allowed is not None:
            for cell in grid.values():
                cell["pattern"] = allowed[cell["pattern"]]
    else:
        n_palettes = 1
        layout_fn = SYMMETRY_MODES[symmetry]
        kwargs = {}
        if symmetry == "partial":
            kwargs["chaos"] = chaos
        grid = layout_fn(rows, cols, n_patterns, n_palettes, rng, **kwargs)

        if allowed is not None:
            for cell in grid.values():
                cell["pattern"] = allowed[cell["pattern"]]

        for key, cell in grid.items():
            cell_rng = random.Random(cell["pattern"] * 1000 + cell["palette"])
            indices = list(range(n_colors))
            cell_rng.shuffle(indices)
            cell["color_map"] = indices

    # image dimensions
    width = cols * block_size + 2 * border
    height = rows * block_size + 2 * border

    # create surface
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    ctx = cairo.Context(surface)

    # background
    ctx.set_source_rgb(0.95, 0.93, 0.90)  # off-white linen background
    ctx.rectangle(0, 0, width, height)
    ctx.fill()

    # render blocks
    for r in range(rows):
        for c in range(cols):
            cell = grid[(r, c)]
            bx = border + c * block_size
            by = border + r * block_size
            cx_block = bx + block_size / 2
            cy_block = by + block_size / 2

            pattern_fn = BLOCK_PATTERNS[cell["pattern"]]
            patches = pattern_fn(bx, by, block_size, n_colors)
            patches = rotate_patches(patches, cx_block, cy_block,
                                     cell["rotation"])

            color_map = cell["color_map"]
            for poly, color_idx in patches:
                ci = color_map[color_idx % n_colors]
                r_c, g_c, b_c = palette_colors[ci]
                ctx.set_source_rgb(r_c, g_c, b_c)
                ctx.move_to(*poly[0])
                for pt in poly[1:]:
                    ctx.line_to(*pt)
                ctx.close_path()
                ctx.fill()

    # grid lines (seam lines between blocks)
    ctx.set_source_rgba(0, 0, 0, 0.15)
    ctx.set_line_width(1.0)
    for r in range(rows + 1):
        y = border + r * block_size
        ctx.move_to(border, y)
        ctx.line_to(border + cols * block_size, y)
        ctx.stroke()
    for c in range(cols + 1):
        x = border + c * block_size
        ctx.move_to(x, border)
        ctx.line_to(x, border + rows * block_size)
        ctx.stroke()

    # tile boundary lines (heavier seams between tiles)
    if tile_size is not None:
        ctx.set_source_rgba(0, 0, 0, 0.4)
        ctx.set_line_width(2.5)
        for tr in range(math.ceil(rows / tile_size) + 1):
            y = border + min(tr * tile_size, rows) * block_size
            ctx.move_to(border, y)
            ctx.line_to(border + cols * block_size, y)
            ctx.stroke()
        for tc in range(math.ceil(cols / tile_size) + 1):
            x = border + min(tc * tile_size, cols) * block_size
            ctx.move_to(x, border)
            ctx.line_to(x, border + rows * block_size)
            ctx.stroke()

    # patch seam lines (within blocks)
    ctx.set_source_rgba(0, 0, 0, 0.08)
    ctx.set_line_width(0.5)
    for r in range(rows):
        for c in range(cols):
            cell = grid[(r, c)]
            bx = border + c * block_size
            by = border + r * block_size
            cx_block = bx + block_size / 2
            cy_block = by + block_size / 2

            pattern_fn = BLOCK_PATTERNS[cell["pattern"]]
            patches = pattern_fn(bx, by, block_size, n_colors)
            patches = rotate_patches(patches, cx_block, cy_block,
                                     cell["rotation"])

            for poly, _ in patches:
                ctx.move_to(*poly[0])
                for pt in poly[1:]:
                    ctx.line_to(*pt)
                ctx.close_path()
                ctx.stroke()

    # save
    os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
    surface.write_to_png(output)
    print(f"Saved to {output} ({width}x{height})")


def main():
    parser = argparse.ArgumentParser(description="Generate a quilt image")
    parser.add_argument("--rows", type=int, default=20)
    parser.add_argument("--cols", type=int, default=20)
    parser.add_argument("--block-size", type=int, default=60)
    parser.add_argument("--symmetry", default="partial",
                        choices=list(SYMMETRY_MODES.keys()))
    parser.add_argument("--chaos", type=float, default=0.3)
    parser.add_argument("--palette", default="random")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--output", default="quilts/out.png")
    parser.add_argument("--border", type=int, default=20)
    parser.add_argument("--n-patterns", type=int, default=None,
                        help="Max block patterns to use (default: all)")
    parser.add_argument("--n-colors", type=int, default=None,
                        help="Max palette colors to use (default: all)")
    parser.add_argument("--tile-size", type=int, default=None,
                        help="Blocks per tile side (e.g. 5 for 5x5 tiles)")
    parser.add_argument("--tile-variation", type=float, default=0.05,
                        help="Fraction of blocks perturbed per tile (default: 0.05)")
    args = parser.parse_args()

    render_quilt(
        rows=args.rows,
        cols=args.cols,
        block_size=args.block_size,
        symmetry=args.symmetry,
        chaos=args.chaos,
        palette_name=args.palette,
        seed=args.seed,
        output=args.output,
        border=args.border,
        max_patterns=args.n_patterns,
        max_colors=args.n_colors,
        tile_size=args.tile_size,
        tile_variation=args.tile_variation,
    )


if __name__ == "__main__":
    main()
