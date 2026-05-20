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
import os
import random

import cairo

from blocks import BLOCK_PATTERNS
from palettes import PALETTES, hex_to_rgb
from layout import SYMMETRY_MODES


def pick_palettes(palette_name, _n_needed, rng):
    """Select palette colors. Returns a list of lists of (r,g,b) tuples."""
    if palette_name == "random":
        chosen = rng.choice(PALETTES)
    else:
        matches = [p for p in PALETTES if p[0] == palette_name]
        if not matches:
            available = ", ".join(p[0] for p in PALETTES)
            raise ValueError(
                f"Unknown palette '{palette_name}'. Available: {available}"
            )
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


def _build_tiled_grid(rows, cols, tile_size, tile_variation, n_patterns,  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals,too-many-nested-blocks
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
    for tr in range(tile_rows):  # pylint: disable=too-many-nested-blocks
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


def _draw_border(ctx, width, height, border, quilt_x, quilt_y, quilt_w,  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals,too-many-branches,too-many-statements
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


BORDER_STYLES = ["solid", "stripes", "checkerboard", "piano_keys"]

QUILT_STITCH_STYLES = ["grid", "diagonal", "crosshatch",
                       "sashiko_wave", "sashiko_asanoha"]


def _draw_quilt_stitching(ctx, qx, qy, qw, qh, style, spacing):  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
    """Draw dotted thread-quilting lines over the quilt area.

    style: 'grid' | 'diagonal' | 'crosshatch'
    spacing: pixel distance between parallel stitch lines
    """
    ctx.save()
    # clip to quilt interior
    ctx.rectangle(qx, qy, qw, qh)
    ctx.clip()

    ctx.set_source_rgba(0.15, 0.10, 0.05, 0.28)  # dark thread, semi-transparent
    ctx.set_line_width(0.9)
    ctx.set_dash([1.5, 5.5])  # dot, gap

    def draw_lines_at_angle(angle_deg):
        """Draw parallel lines at given angle spanning the clipped area."""
        rad = math.radians(angle_deg)
        cos_a, sin_a = math.cos(rad), math.sin(rad)
        # diagonal of bounding box — enough to span any rotation
        diag = math.sqrt(qw * qw + qh * qh)
        cx, cy = qx + qw / 2, qy + qh / 2
        # perpendicular direction to the lines
        perp_x, perp_y = -sin_a, cos_a
        n = int(diag / spacing) + 2
        for i in range(-n, n + 1):
            ox = cx + perp_x * i * spacing
            oy = cy + perp_y * i * spacing
            ctx.move_to(ox - cos_a * diag, oy - sin_a * diag)
            ctx.line_to(ox + cos_a * diag, oy + sin_a * diag)
        ctx.stroke()

    if style in ("grid", "crosshatch"):
        draw_lines_at_angle(0)    # horizontal
        draw_lines_at_angle(90)   # vertical
    if style in ("diagonal", "crosshatch"):
        draw_lines_at_angle(45)
        draw_lines_at_angle(-45)

    if style == "sashiko_wave":
        # seigaiha-inspired: rows of nested arcs
        ctx.set_source_rgba(0.95, 0.92, 0.85, 0.45)  # cream thread
        ctx.set_line_width(1.0)
        ctx.set_dash([2.0, 4.0])
        r = spacing * 0.5
        for row in range(int(qh / spacing) + 2):
            for col in range(int(qw / spacing) + 2):
                cx = qx + col * spacing + (spacing / 2 if row % 2 else 0)
                cy = qy + row * spacing * 0.6
                for ring in range(3):
                    rr = r * (ring + 1) / 3
                    ctx.arc(cx, cy, rr, math.pi, 2 * math.pi)
                    ctx.stroke()

    if style == "sashiko_asanoha":
        # hemp leaf pattern: six lines radiating from each grid point
        ctx.set_source_rgba(0.95, 0.92, 0.85, 0.45)
        ctx.set_line_width(1.0)
        ctx.set_dash([2.0, 4.0])
        s = spacing * 0.7  # cell size
        for row in range(int(qh / s) + 2):
            for col in range(int(qw / s) + 2):
                cx = qx + col * s + (s / 2 if row % 2 else 0)
                cy = qy + row * s * 0.866  # sqrt(3)/2 for hex packing
                for a in range(6):
                    angle = math.radians(a * 60)
                    ctx.move_to(cx, cy)
                    ctx.line_to(cx + s / 2 * math.cos(angle),
                                cy + s / 2 * math.sin(angle))
                ctx.stroke()

    ctx.set_dash([])
    ctx.restore()


GRADIENT_MODES = ["horizontal", "vertical", "diagonal", "radial"]


def _build_strip_sizes(n, base_size, variation, rng):
    """Generate n strip sizes with seeded variation around base_size.

    Returns (sizes, positions) where sizes[i] is the pixel size of strip i
    and positions[i] is the cumulative pixel offset.
    """
    if variation <= 0:
        sizes = [base_size] * n
    else:
        sizes = []
        for _ in range(n):
            factor = 1.0 + rng.uniform(-variation, variation)
            sizes.append(max(1, round(base_size * factor)))
    positions = [0]
    for s in sizes:
        positions.append(positions[-1] + s)
    return sizes, positions


def render_quilt(rows, cols, block_size, symmetry, chaos, palette_name,  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals,too-many-branches,too-many-statements
                 seed, output, border, max_patterns=None, max_colors=None,
                 tile_size=None, tile_variation=0.05, border_style=None,
                 sash_width=0, color_gradient=None, mega_frac=0.0,
                 cornerstones=False, plain_frac=0.0, quilt_stitch=None,
                 wash_alpha=0.0, palette_name_2=None, palette_mix=None,
                 accent_count=0, color_wash=None, wonky=0.0, strippy=0.0):
    """Generate and render a quilt to an image file."""
    if seed is None:
        seed = random.randint(0, 2**31)
    rng = random.Random(seed)

    palette_colors = pick_palettes(palette_name, 1, rng)
    if max_colors is not None and max_colors < len(palette_colors):
        palette_colors = rng.sample(palette_colors, max_colors)

    # palette mixing: blend colors from two palettes into a single hybrid palette
    if palette_mix is not None:
        mix_known = {p[0] for p in PALETTES}
        if palette_mix in mix_known:
            mix_colors = pick_palettes(palette_mix, 1, rng)
            if max_colors is not None and max_colors < len(mix_colors):
                mix_colors = rng.sample(mix_colors, max_colors)
            # interleave: take alternating colors from each palette
            hybrid = []
            for i in range(max(len(palette_colors), len(mix_colors))):
                if i < len(palette_colors):
                    hybrid.append(palette_colors[i])
                if i < len(mix_colors):
                    hybrid.append(mix_colors[i])
            # trim back to max_colors (keeps a balanced mix)
            if max_colors is not None:
                hybrid = hybrid[:max_colors]
            palette_colors = hybrid

    n_colors = len(palette_colors)

    # two-palette mixing: build a second palette; n_palettes=2 splits blocks
    _known = {p[0] for p in PALETTES}
    if palette_name_2 is not None and palette_name_2 not in _known:
        palette_name_2 = None  # retired palette — silently drop
    if palette_name_2 is not None:
        palette_colors_2 = pick_palettes(palette_name_2, 1, rng)
        if max_colors is not None and max_colors < len(palette_colors_2):
            palette_colors_2 = rng.sample(palette_colors_2, max_colors)
        all_palettes = [palette_colors, palette_colors_2]
        n_palettes = 2
    else:
        all_palettes = [palette_colors]
        n_palettes = 1

    n_all_patterns = len(BLOCK_PATTERNS)
    if max_patterns is not None:
        available = list(range(n_all_patterns))
        rng.shuffle(available)
        allowed = sorted(available[:max_patterns])
        n_patterns = max_patterns
    else:
        allowed = None
        n_patterns = n_all_patterns

    # Non-trivial symmetries bypass tiling — they use SYMMETRY_MODES layouts
    if symmetry != "none":
        tile_size = None

    if tile_size is not None:
        grid = _build_tiled_grid(rows, cols, tile_size, tile_variation,
                                 n_patterns, n_colors, rng)
        # remap pattern indices to allowed subset
        if allowed is not None:
            for cell in grid.values():
                cell["pattern"] = allowed[cell["pattern"]]
    else:
        layout_fn = SYMMETRY_MODES[symmetry]
        kwargs = {}
        if symmetry == "partial":
            kwargs["chaos"] = chaos
        grid = layout_fn(rows, cols, n_patterns, n_palettes, rng, **kwargs)

        if allowed is not None:
            for cell in grid.values():
                cell["pattern"] = allowed[cell["pattern"]]

        for _, cell in grid.items():
            cell_rng = random.Random(cell["pattern"] * 1000 + cell["palette"])
            indices = list(range(n_colors))
            cell_rng.shuffle(indices)
            cell["color_map"] = indices

    # color gradient — rotate each cell's color_map by a position-based offset
    # shift=0 → original colors; shift=1 → next palette color becomes primary
    if color_gradient is not None and n_colors > 1:
        mid_r, mid_c = (rows - 1) / 2, (cols - 1) / 2
        for (r, c), cell in grid.items():
            t = 0.0
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

    # color wash — bias palette color selection based on block position
    # direction is a unit vector; cells further along it use later palette colors
    if color_wash is not None and n_colors > 1:
        dx, dy = color_wash  # direction vector (already normalized)
        # project each cell position onto the direction
        projections = {}
        for (r, c) in grid:
            projections[(r, c)] = dx * c / max(cols - 1, 1) + dy * r / max(rows - 1, 1)
        pmin = min(projections.values())
        pmax = max(projections.values())
        prange = pmax - pmin if pmax > pmin else 1.0
        for (r, c), cell in grid.items():
            t = (projections[(r, c)] - pmin) / prange  # 0..1
            shift = round(t * (n_colors - 1))
            cm = cell["color_map"]
            cell["color_map"] = [cm[(i + shift) % n_colors]
                                  for i in range(n_colors)]

    # bargello: force all cells to solid color based on wave pattern
    if symmetry == "bargello":
        for cell in grid.values():
            bi = cell.get("_bargello_color", 0) % n_colors
            cell["color_map"] = [bi] * n_colors

    # plain blocks: random cells rendered as solid color (no pattern)
    plain_cells = set()
    if symmetry == "bargello":
        plain_cells = {(r, c) for r in range(rows) for c in range(cols)}
    if plain_frac > 0.0:
        for r in range(rows):
            for c in range(cols):
                if rng.random() < plain_frac:
                    plain_cells.add((r, c))

    # accent squares: a few cells rendered as solid color from the current palette
    accent_cells = {}  # (r, c) → (r, g, b)
    if accent_count and accent_count > 0:
        all_positions = [(r, c) for r in range(rows) for c in range(cols)]
        rng.shuffle(all_positions)
        for pos in all_positions[:accent_count]:
            accent_cells[pos] = rng.choice(palette_colors)

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

    # strippy grid: varying row heights and column widths
    sash = sash_width
    strip_rng = random.Random(seed + 7777)
    col_sizes, col_pos = _build_strip_sizes(cols, block_size, strippy, strip_rng)
    row_sizes, row_pos = _build_strip_sizes(rows, block_size, strippy, strip_rng)

    # image dimensions (sashing adds gaps between blocks)
    quilt_w = col_pos[-1] + max(0, cols - 1) * sash
    quilt_h = row_pos[-1] + max(0, rows - 1) * sash
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
    for r in range(rows):
        for c in range(cols):
            if (r, c) in mega_covered:
                continue
            cell = grid[(r, c)]
            cw, ch = col_sizes[c], row_sizes[r]
            bx = border + col_pos[c] + c * sash
            by = border + row_pos[r] + r * sash

            if (r, c) in accent_cells:
                ctx.set_source_rgb(*accent_cells[(r, c)])
                ctx.rectangle(bx, by, cw, ch)
                ctx.fill()
                continue

            if (r, c) in plain_cells:
                ci = cell["color_map"][0]
                active_pal = all_palettes[cell.get("palette", 0) % len(all_palettes)]
                ctx.set_source_rgb(*active_pal[ci])
                ctx.rectangle(bx, by, cw, ch)
                ctx.fill()
                continue

            # Generate pattern in square coordinates, then scale to cell
            pattern_fn = BLOCK_PATTERNS[cell["pattern"]]
            patches = pattern_fn(0, 0, block_size, n_colors)
            cx_sq = block_size / 2
            cy_sq = block_size / 2
            patches = rotate_patches(patches, cx_sq, cy_sq, cell["rotation"])

            if wonky > 0:
                wonky_rng = random.Random(seed * 10000 + r * 1000 + c)
                jitter = wonky * block_size
                patches = [
                    ([(px + wonky_rng.uniform(-jitter, jitter),
                       py + wonky_rng.uniform(-jitter, jitter))
                      for px, py in poly], ci)
                    for poly, ci in patches
                ]

            # Scale pattern from square (block_size) to cell (cw × ch)
            sx, sy = cw / block_size, ch / block_size
            color_map = cell["color_map"]
            active_pal = all_palettes[cell.get("palette", 0) % len(all_palettes)]
            for poly, color_idx in patches:
                if isinstance(color_idx, tuple):
                    r_c, g_c, b_c = color_idx
                else:
                    ci = color_map[color_idx % n_colors]
                    r_c, g_c, b_c = active_pal[ci]
                ctx.set_source_rgb(r_c, g_c, b_c)
                ctx.move_to(bx + poly[0][0] * sx, by + poly[0][1] * sy)
                for pt in poly[1:]:
                    ctx.line_to(bx + pt[0] * sx, by + pt[1] * sy)
                ctx.close_path()
                ctx.fill()

    # cornerstones — contrasting squares at sash intersections
    if sash > 0 and cornerstones and n_colors > 1:
        other = [i for i in range(n_colors) if i != sash_color_idx]
        cs_color = palette_colors[rng.choice(other)]
        ctx.set_source_rgb(*cs_color)
        for cr in range(rows - 1):
            for cc in range(cols - 1):
                cx = border + col_pos[cc + 1] + cc * sash
                cy = border + row_pos[cr + 1] + cr * sash
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
            y = border + row_pos[min(r, rows)]
            ctx.move_to(border, y)
            ctx.line_to(border + quilt_w, y)
            ctx.stroke()
        for c in range(cols + 1):
            if c in mega_skip_cols:
                continue
            x = border + col_pos[min(c, cols)]
            ctx.move_to(x, border)
            ctx.line_to(x, border + quilt_h)
            ctx.stroke()

    # tile boundary lines (heavier seams between tiles)
    if tile_size is not None:
        ctx.set_source_rgba(0, 0, 0, 0.4)
        ctx.set_line_width(2.5)
        for tr in range(math.ceil(rows / tile_size) + 1):
            ri = min(tr * tile_size, rows)
            y = border + row_pos[ri] + ri * sash
            ctx.move_to(border, y)
            ctx.line_to(border + quilt_w, y)
            ctx.stroke()
        for tc in range(math.ceil(cols / tile_size) + 1):
            ci = min(tc * tile_size, cols)
            x = border + col_pos[ci] + ci * sash
            ctx.move_to(x, border)
            ctx.line_to(x, border + quilt_h)
            ctx.stroke()

    # render mega-blocks (after grid lines so they paint over interior seams)
    for (mr, mc) in mega_tl:
        cell = grid[(mr, mc)]
        bx = border + col_pos[mc] + mc * sash
        by = border + row_pos[mr] + mr * sash
        mw = col_sizes[mc] + col_sizes[mc + 1] + sash
        mh = row_sizes[mr] + row_sizes[mr + 1] + sash
        mega_sq = 2 * block_size + sash  # square coord size for pattern

        pattern_fn = BLOCK_PATTERNS[cell["pattern"]]
        patches = pattern_fn(0, 0, mega_sq, n_colors)
        patches = rotate_patches(patches, mega_sq / 2, mega_sq / 2,
                                 cell["rotation"])

        if wonky > 0:
            wonky_rng = random.Random(seed * 10000 + mr * 1000 + mc + 500)
            jitter = wonky * mega_sq
            patches = [
                ([(px + wonky_rng.uniform(-jitter, jitter),
                   py + wonky_rng.uniform(-jitter, jitter))
                  for px, py in poly], ci)
                for poly, ci in patches
            ]

        sx, sy = mw / mega_sq, mh / mega_sq
        color_map = cell["color_map"]
        active_pal = all_palettes[cell.get("palette", 0) % len(all_palettes)]
        for poly, color_idx in patches:
            if isinstance(color_idx, tuple):
                r_c, g_c, b_c = color_idx
            else:
                ci = color_map[color_idx % n_colors]
                r_c, g_c, b_c = active_pal[ci]
            ctx.set_source_rgb(r_c, g_c, b_c)
            ctx.move_to(bx + poly[0][0] * sx, by + poly[0][1] * sy)
            for pt in poly[1:]:
                ctx.line_to(bx + pt[0] * sx, by + pt[1] * sy)
            ctx.close_path()
            ctx.fill()

    # patch seam lines (within blocks) — skip mega-covered, draw mega seams after
    ctx.set_source_rgba(0, 0, 0, 0.08)
    ctx.set_line_width(0.5)
    for r in range(rows):
        for c in range(cols):
            if (r, c) in mega_covered or (r, c) in plain_cells or (r, c) in accent_cells:
                continue
            cell = grid[(r, c)]
            cw, ch = col_sizes[c], row_sizes[r]
            bx = border + col_pos[c] + c * sash
            by = border + row_pos[r] + r * sash
            sx, sy = cw / block_size, ch / block_size

            pattern_fn = BLOCK_PATTERNS[cell["pattern"]]
            patches = pattern_fn(0, 0, block_size, n_colors)
            patches = rotate_patches(patches, block_size / 2, block_size / 2,
                                     cell["rotation"])

            for poly, _ in patches:
                ctx.move_to(bx + poly[0][0] * sx, by + poly[0][1] * sy)
                for pt in poly[1:]:
                    ctx.line_to(bx + pt[0] * sx, by + pt[1] * sy)
                ctx.close_path()
                ctx.stroke()

    for (mr, mc) in mega_tl:
        cell = grid[(mr, mc)]
        bx = border + col_pos[mc] + mc * sash
        by = border + row_pos[mr] + mr * sash
        mw = col_sizes[mc] + col_sizes[mc + 1] + sash
        mh = row_sizes[mr] + row_sizes[mr + 1] + sash
        mega_sq = 2 * block_size + sash
        sx, sy = mw / mega_sq, mh / mega_sq

        pattern_fn = BLOCK_PATTERNS[cell["pattern"]]
        patches = pattern_fn(0, 0, mega_sq, n_colors)
        patches = rotate_patches(patches, mega_sq / 2, mega_sq / 2,
                                 cell["rotation"])

        for poly, _ in patches:
            ctx.move_to(bx + poly[0][0] * sx, by + poly[0][1] * sy)
            for pt in poly[1:]:
                ctx.line_to(bx + pt[0] * sx, by + pt[1] * sy)
            ctx.close_path()
            ctx.stroke()

    # color wash — semi-transparent tint over entire quilt area
    if wash_alpha and wash_alpha > 0:
        wash_rgb = palette_colors[rng.randint(0, n_colors - 1)]
        ctx.set_source_rgba(*wash_rgb, wash_alpha)
        ctx.rectangle(quilt_x, quilt_y, quilt_w, quilt_h)
        ctx.fill()

    # thread quilting overlay
    if quilt_stitch is not None:
        _draw_quilt_stitching(ctx, quilt_x, quilt_y, quilt_w, quilt_h,
                              quilt_stitch, block_size)

    # save or return bytes
    if output is None:
        buf = io.BytesIO()
        surface.write_to_png(buf)
        buf.seek(0)
        return buf.getvalue()
    os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
    surface.write_to_png(output)
    print(f"Saved to {output} ({width}x{height})")
    return None


def main():
    """Parse CLI arguments and render a quilt."""
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
