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
import io
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


def _draw_border(ctx, width, height, border, quilt_x, quilt_y, quilt_w,
                  quilt_h, style, colors, block_size):
    """Draw a decorative border around the quilt area.

    styles: solid, stripes, checkerboard, piano_keys
    colors: list of (r,g,b) tuples (1 or 2 colors)
    """
    c1 = colors[0]
    c2 = colors[1] if len(colors) > 1 else (0.95, 0.93, 0.90)

    if style == "solid":
        ctx.set_source_rgb(*c1)
        # top
        ctx.rectangle(0, 0, width, quilt_y)
        ctx.fill()
        # bottom
        ctx.rectangle(0, quilt_y + quilt_h, width, height - quilt_y - quilt_h)
        ctx.fill()
        # left
        ctx.rectangle(0, quilt_y, quilt_x, quilt_h)
        ctx.fill()
        # right
        ctx.rectangle(quilt_x + quilt_w, quilt_y, width - quilt_x - quilt_w,
                      quilt_h)
        ctx.fill()

    elif style == "stripes":
        stripe_w = max(4, border // 4)
        # draw full background in c1, then overlay stripes in c2
        ctx.set_source_rgb(*c1)
        ctx.rectangle(0, 0, width, height)
        ctx.fill()
        # cover quilt area with background so blocks draw clean
        ctx.set_source_rgb(0.95, 0.93, 0.90)
        ctx.rectangle(quilt_x, quilt_y, quilt_w, quilt_h)
        ctx.fill()
        # horizontal stripes on top and bottom
        ctx.set_source_rgb(*c2)
        for i in range(0, border, stripe_w * 2):
            ctx.rectangle(0, i, width, stripe_w)
            ctx.fill()
            ctx.rectangle(0, quilt_y + quilt_h + i, width, stripe_w)
            ctx.fill()
        # vertical stripes on left and right
        for i in range(0, border, stripe_w * 2):
            ctx.rectangle(i, quilt_y, stripe_w, quilt_h)
            ctx.fill()
            ctx.rectangle(quilt_x + quilt_w + i, quilt_y, stripe_w, quilt_h)
            ctx.fill()

    elif style == "checkerboard":
        sq = max(4, border // 3)
        for sy in range(0, height, sq):
            for sx in range(0, width, sq):
                # skip quilt interior
                if (quilt_x <= sx < quilt_x + quilt_w and
                        quilt_y <= sy < quilt_y + quilt_h):
                    continue
                color = c1 if (sx // sq + sy // sq) % 2 == 0 else c2
                ctx.set_source_rgb(*color)
                ctx.rectangle(sx, sy, sq, sq)
                ctx.fill()

    elif style == "piano_keys":
        key_w = max(6, block_size // 3)
        # top edge
        for i, kx in enumerate(range(quilt_x, quilt_x + quilt_w, key_w)):
            ctx.set_source_rgb(*(c1 if i % 2 == 0 else c2))
            ctx.rectangle(kx, 0, key_w, border)
            ctx.fill()
        # bottom edge
        for i, kx in enumerate(range(quilt_x, quilt_x + quilt_w, key_w)):
            ctx.set_source_rgb(*(c1 if i % 2 == 0 else c2))
            ctx.rectangle(kx, quilt_y + quilt_h, key_w, border)
            ctx.fill()
        # left edge
        for i, ky in enumerate(range(quilt_y, quilt_y + quilt_h, key_w)):
            ctx.set_source_rgb(*(c1 if i % 2 == 0 else c2))
            ctx.rectangle(0, ky, border, key_w)
            ctx.fill()
        # right edge
        for i, ky in enumerate(range(quilt_y, quilt_y + quilt_h, key_w)):
            ctx.set_source_rgb(*(c1 if i % 2 == 0 else c2))
            ctx.rectangle(quilt_x + quilt_w, ky, border, key_w)
            ctx.fill()
        # corners solid
        ctx.set_source_rgb(*c1)
        for cx, cy in [(0, 0), (quilt_x + quilt_w, 0),
                        (0, quilt_y + quilt_h),
                        (quilt_x + quilt_w, quilt_y + quilt_h)]:
            ctx.rectangle(cx, cy, border, border)
            ctx.fill()


BORDER_STYLES = ["solid", "checkerboard", "piano_keys"]


GRADIENT_MODES = ["diagonal"]


def render_quilt(rows, cols, block_size, symmetry, chaos, palette_name,
                 seed, output, border, max_patterns=None, max_colors=None,
                 tile_size=None, tile_variation=0.05, border_style=None,
                 sash_width=0, color_gradient=None, mega_frac=0.0,
                 cornerstones=False, plain_frac=0.0):
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

    # color gradient — rotate each cell's color_map by a position-based offset
    # shift=0 → original colors; shift=1 → next palette color becomes primary
    if color_gradient is not None and n_colors > 1:
        mid_r, mid_c = (rows - 1) / 2, (cols - 1) / 2
        for (r, c), cell in grid.items():
            if color_gradient == "horizontal":
                t = c / max(cols - 1, 1)
            elif color_gradient == "vertical":
                t = r / max(rows - 1, 1)
            elif color_gradient == "diagonal":
                t = (r + c) / max(rows + cols - 2, 1)
            elif color_gradient == "radial":
                dr = (r - mid_r) / max(mid_r, 1)
                dc = (c - mid_c) / max(mid_c, 1)
                t = min(1.0, math.sqrt(dr * dr + dc * dc))
            shift = round(t * (n_colors - 1))
            cm = cell["color_map"]
            cell["color_map"] = [cm[(i + shift) % n_colors]
                                  for i in range(n_colors)]

    # plain blocks: random cells rendered as solid color (no pattern)
    plain_cells = set()
    if plain_frac > 0.0:
        for r in range(rows):
            for c in range(cols):
                if rng.random() < plain_frac:
                    plain_cells.add((r, c))

    # mega-blocks: greedily select non-overlapping 2x2 regions
    mega_tl = set()       # top-left corners of mega-blocks
    mega_covered = set()  # all 4 cells covered by mega-blocks
    if mega_frac > 0.0 and rows >= 2 and cols >= 2:
        candidates = [(r, c) for r in range(rows - 1) for c in range(cols - 1)]
        rng.shuffle(candidates)
        for r, c in candidates:
            covers = {(r, c), (r + 1, c), (r, c + 1), (r + 1, c + 1)}
            if not covers & mega_covered and rng.random() < mega_frac:
                mega_tl.add((r, c))
                mega_covered |= covers

    # widen border when decorative style is active
    if border_style is not None:
        border = max(border, int(block_size * 0.75))

    # image dimensions (sashing adds gaps between blocks)
    sash = sash_width
    quilt_w = cols * block_size + max(0, cols - 1) * sash
    quilt_h = rows * block_size + max(0, rows - 1) * sash
    width = quilt_w + 2 * border
    height = quilt_h + 2 * border
    quilt_x, quilt_y = border, border

    # create surface
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    ctx = cairo.Context(surface)

    # background
    ctx.set_source_rgb(0.95, 0.93, 0.90)  # off-white linen background
    ctx.rectangle(0, 0, width, height)
    ctx.fill()

    # sash background — fill quilt area with sash color; blocks draw on top
    sash_color_idx = None
    if sash > 0:
        sash_color_idx = rng.randint(0, n_colors - 1)
        sash_color = palette_colors[sash_color_idx]
        ctx.set_source_rgb(*sash_color)
        ctx.rectangle(quilt_x, quilt_y, quilt_w, quilt_h)
        ctx.fill()

    # decorative border
    if border_style is not None:
        # pick 2 border colors from palette
        border_c1 = palette_colors[rng.randint(0, n_colors - 1)]
        border_c2 = palette_colors[rng.randint(0, n_colors - 1)]
        _draw_border(ctx, width, height, border, quilt_x, quilt_y,
                     quilt_w, quilt_h, border_style,
                     [border_c1, border_c2], block_size)

    # render blocks (skip cells covered by mega-blocks)
    stride = block_size + sash
    for r in range(rows):
        for c in range(cols):
            if (r, c) in mega_covered:
                continue
            cell = grid[(r, c)]
            bx = border + c * stride
            by = border + r * stride

            if (r, c) in plain_cells:
                ci = cell["color_map"][0]
                ctx.set_source_rgb(*palette_colors[ci])
                ctx.rectangle(bx, by, block_size, block_size)
                ctx.fill()
                continue

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

    # cornerstones — contrasting squares at sash intersections
    if sash > 0 and cornerstones and n_colors > 1:
        other = [i for i in range(n_colors) if i != sash_color_idx]
        cs_color = palette_colors[rng.choice(other)]
        ctx.set_source_rgb(*cs_color)
        for cr in range(rows - 1):
            for cc in range(cols - 1):
                cx = border + cc * stride + block_size
                cy = border + cr * stride + block_size
                ctx.rectangle(cx, cy, sash, sash)
                ctx.fill()

    # grid lines (seam lines between blocks) — skipped when sashing is active
    # interior seam lines of mega-blocks are also skipped
    mega_skip_rows = {r + 1 for r, _ in mega_tl}
    mega_skip_cols = {c + 1 for _, c in mega_tl}
    if sash == 0:
        ctx.set_source_rgba(0, 0, 0, 0.15)
        ctx.set_line_width(1.0)
        for r in range(rows + 1):
            if r in mega_skip_rows:
                continue
            y = border + r * stride
            ctx.move_to(border, y)
            ctx.line_to(border + quilt_w, y)
            ctx.stroke()
        for c in range(cols + 1):
            if c in mega_skip_cols:
                continue
            x = border + c * stride
            ctx.move_to(x, border)
            ctx.line_to(x, border + quilt_h)
            ctx.stroke()

    # tile boundary lines (heavier seams between tiles)
    if tile_size is not None:
        ctx.set_source_rgba(0, 0, 0, 0.4)
        ctx.set_line_width(2.5)
        for tr in range(math.ceil(rows / tile_size) + 1):
            y = border + min(tr * tile_size, rows) * stride
            ctx.move_to(border, y)
            ctx.line_to(border + quilt_w, y)
            ctx.stroke()
        for tc in range(math.ceil(cols / tile_size) + 1):
            x = border + min(tc * tile_size, cols) * stride
            ctx.move_to(x, border)
            ctx.line_to(x, border + quilt_h)
            ctx.stroke()

    # render mega-blocks (after grid lines so they paint over interior seams)
    mega_size = 2 * block_size + sash
    for (mr, mc) in mega_tl:
        cell = grid[(mr, mc)]
        bx = border + mc * stride
        by = border + mr * stride
        cx_block = bx + mega_size / 2
        cy_block = by + mega_size / 2

        pattern_fn = BLOCK_PATTERNS[cell["pattern"]]
        patches = pattern_fn(bx, by, mega_size, n_colors)
        patches = rotate_patches(patches, cx_block, cy_block, cell["rotation"])

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

    # patch seam lines (within blocks) — skip mega-covered, draw mega seams after
    ctx.set_source_rgba(0, 0, 0, 0.08)
    ctx.set_line_width(0.5)
    for r in range(rows):
        for c in range(cols):
            if (r, c) in mega_covered or (r, c) in plain_cells:
                continue
            cell = grid[(r, c)]
            bx = border + c * stride
            by = border + r * stride
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

    for (mr, mc) in mega_tl:
        cell = grid[(mr, mc)]
        bx = border + mc * stride
        by = border + mr * stride
        cx_block = bx + mega_size / 2
        cy_block = by + mega_size / 2

        pattern_fn = BLOCK_PATTERNS[cell["pattern"]]
        patches = pattern_fn(bx, by, mega_size, n_colors)
        patches = rotate_patches(patches, cx_block, cy_block, cell["rotation"])

        for poly, _ in patches:
            ctx.move_to(*poly[0])
            for pt in poly[1:]:
                ctx.line_to(*pt)
            ctx.close_path()
            ctx.stroke()

    # save or return bytes
    if output is None:
        buf = io.BytesIO()
        surface.write_to_png(buf)
        buf.seek(0)
        return buf.getvalue()
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
    parser.add_argument("--border-style", default=None,
                        choices=BORDER_STYLES,
                        help="Decorative border style (default: none)")
    parser.add_argument("--sash-width", type=int, default=0,
                        help="Sash width in px between blocks (default: 0)")
    parser.add_argument("--cornerstones", action="store_true",
                        help="Draw cornerstone squares at sash intersections")
    parser.add_argument("--mega-frac", type=float, default=0.0,
                        help="Fraction of 2x2 mega-blocks (default: 0.0)")
    parser.add_argument("--plain-frac", type=float, default=0.0,
                        help="Fraction of plain solid-color blocks (default: 0.0)")
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
        border_style=args.border_style,
        sash_width=args.sash_width,
        cornerstones=args.cornerstones,
        mega_frac=args.mega_frac,
        plain_frac=args.plain_frac,
    )


if __name__ == "__main__":
    main()
