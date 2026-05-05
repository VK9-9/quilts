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


def _make_tile_configs(tile_rows, tile_cols, n_all_patterns, n_colors,
                       symmetry, chaos, rng, patterns_per_tile=2):
    """Create a config for each tile position using the symmetry layout.

    Each tile config has:
      - allowed_patterns: list of pattern indices this tile uses
      - color_map: shuffled palette indices
      - rotation: base rotation applied to blocks
    """
    layout_fn = SYMMETRY_MODES[symmetry]
    kwargs = {}
    if symmetry == "partial":
        kwargs["chaos"] = chaos
    # use n_all_patterns as the "pattern" dimension for the tile layout
    tile_grid = layout_fn(tile_rows, tile_cols, n_all_patterns, 1, rng,
                          **kwargs)

    configs = {}
    for (tr, tc), cell in tile_grid.items():
        # pick a small set of patterns for this tile, seeded deterministically
        tile_rng = random.Random(cell["pattern"] * 7919 + cell["rotation"])
        available = list(range(n_all_patterns))
        tile_rng.shuffle(available)
        allowed = available[:patterns_per_tile]

        # color map
        indices = list(range(n_colors))
        tile_rng.shuffle(indices)

        configs[(tr, tc)] = {
            "allowed_patterns": allowed,
            "color_map": indices,
            "rotation": cell["rotation"],
        }
    return configs


def render_quilt(rows, cols, block_size, symmetry, chaos, palette_name,
                 seed, output, border, max_patterns=None, max_colors=None,
                 tile_size=None):
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

    if tile_size is not None:
        # tiled mode: lay out tiles, then fill blocks within each tile
        tile_rows = math.ceil(rows / tile_size)
        tile_cols = math.ceil(cols / tile_size)
        ppt = min(max_patterns or 2, n_all_patterns)
        tile_configs = _make_tile_configs(
            tile_rows, tile_cols, n_all_patterns, n_colors,
            symmetry, chaos, rng, patterns_per_tile=ppt,
        )

        grid = {}
        for r in range(rows):
            for c in range(cols):
                tr, tc = r // tile_size, c // tile_size
                cfg = tile_configs[(tr, tc)]
                pat = rng.choice(cfg["allowed_patterns"])
                grid[(r, c)] = {
                    "pattern": pat,
                    "color_map": cfg["color_map"],
                    "rotation": (cfg["rotation"] + rng.randint(0, 3)) % 4,
                }
    else:
        # flat mode (original behavior)
        n_patterns = n_all_patterns
        if max_patterns is not None:
            available = list(range(n_all_patterns))
            rng.shuffle(available)
            allowed = sorted(available[:max_patterns])
            n_patterns = max_patterns
        else:
            allowed = None
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
    )


if __name__ == "__main__":
    main()
