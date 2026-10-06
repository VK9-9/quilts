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
from dataclasses import dataclass

import cairo

from blocks import BLOCK_PATTERNS
from palettes import PALETTES, hex_to_rgb, subset_in_tonal_order
from layout import SYMMETRY_MODES


def pick_palettes(palette_name, rng):
    """Select palette colors. Returns a list of (r,g,b) tuples."""
    if palette_name == "random":
        chosen = rng.choice(PALETTES)
    else:
        matches = [p for p in PALETTES if p[0] == palette_name]
        if not matches:
            available = ", ".join(p[0] for p in PALETTES)
            raise ValueError(f"Unknown palette '{palette_name}'. Available: {available}")
        chosen = matches[0]

    _name, colors = chosen
    return [hex_to_rgb(c) for c in colors]


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


def _block_patches(cell, size, n_colors, seed=0):
    """Build a cell's base patches in [0, size] coords: pattern → rotate.

    Passes a `seed`-seeded Random instance into the pattern so blocks that
    randomize (half_square_triangle, cherry_blossom) vary per cell yet stay
    reproducible; blocks receive x=y=0 and cannot derive variation from
    position. An instance, not the module RNG: seeding global state let two
    concurrent renders (gunicorn runs threaded) interleave their draws between
    seed() and use, making the same quilt ID render differently under load.
    random.Random(seed) yields the exact sequence random.seed(seed) did, so
    golden hashes are unchanged. No wonky jitter here — the fill and
    seam-stroke passes share one base build per cell, and seams trace the
    un-jittered outline (apply jitter via _jitter_patches).
    """
    rng = random.Random(seed)
    patches = BLOCK_PATTERNS[cell["pattern"]](0, 0, size, n_colors, rng)
    return rotate_patches(patches, size / 2, size / 2, cell["rotation"])


def _jitter_patches(patches, size, wonky, wonky_seed):
    """Nudge every vertex by up to ±(wonky*size) for the improv/wonky look."""
    wonky_rng = random.Random(wonky_seed)
    jitter = wonky * size
    return [
        (
            [
                (
                    px + wonky_rng.uniform(-jitter, jitter),
                    py + wonky_rng.uniform(-jitter, jitter),
                )
                for px, py in poly
            ],
            ci,
        )
        for poly, ci in patches
    ]


def _trace_polygon(ctx, poly, bx, by, sx, sy):  # pylint: disable=too-many-arguments,too-many-positional-arguments
    """Trace a closed polygon path, translated by (bx, by) and scaled by (sx, sy)."""
    ctx.move_to(bx + poly[0][0] * sx, by + poly[0][1] * sy)
    for pt in poly[1:]:
        ctx.line_to(bx + pt[0] * sx, by + pt[1] * sy)
    ctx.close_path()


def _fill_patches(ctx, patches, bx, by, sx, sy, color_map, active_pal, n_colors):  # pylint: disable=too-many-arguments,too-many-positional-arguments
    """Fill each patch with its mapped palette color (or a literal RGB tuple)."""
    for poly, color_idx in patches:
        if isinstance(color_idx, tuple):
            rgb = color_idx
        else:
            rgb = active_pal[color_map[color_idx % n_colors]]
        ctx.set_source_rgb(*rgb)
        _trace_polygon(ctx, poly, bx, by, sx, sy)
        ctx.fill()


def _stroke_patches(ctx, patches, bx, by, sx, sy):  # pylint: disable=too-many-arguments,too-many-positional-arguments
    """Stroke each patch outline using the context's current source and line width."""
    for poly, _ in patches:
        _trace_polygon(ctx, poly, bx, by, sx, sy)
        ctx.stroke()


def _build_tiled_grid(
    rows,
    cols,
    tile_size,
    tile_variation,
    n_patterns,  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals,too-many-nested-blocks
    n_colors,
    rng,
):
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


def _draw_border(
    ctx,
    width,
    height,
    border,
    quilt_x,
    quilt_y,
    quilt_w,  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals,too-many-branches,too-many-statements
    quilt_h,
    style,
    colors,
    block_size,
):
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
        ctx.rectangle(quilt_x + quilt_w, quilt_y, width - quilt_x - quilt_w, quilt_h)
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
                if quilt_x <= sx < quilt_x + quilt_w and quilt_y <= sy < quilt_y + quilt_h:
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
        for cx, cy in [
            (0, 0),
            (quilt_x + quilt_w, 0),
            (0, quilt_y + quilt_h),
            (quilt_x + quilt_w, quilt_y + quilt_h),
        ]:
            ctx.rectangle(cx, cy, border, border)
            ctx.fill()


BORDER_STYLES = ["solid", "stripes", "checkerboard", "piano_keys"]

QUILT_STITCH_STYLES = ["grid", "diagonal", "crosshatch", "sashiko_wave", "sashiko_asanoha"]


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
        draw_lines_at_angle(0)  # horizontal
        draw_lines_at_angle(90)  # vertical
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
                    ctx.line_to(cx + s / 2 * math.cos(angle), cy + s / 2 * math.sin(angle))
                ctx.stroke()

    ctx.set_dash([])
    ctx.restore()


def _build_grid(
    rng,
    rows,
    cols,
    symmetry,
    chaos,
    max_patterns,  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals,too-many-branches
    n_colors,
    n_palettes,
    tile_size,
    tile_variation,
):
    """Build the cell grid (pattern/palette/rotation/color_map) for a quilt.

    This is the single source of truth for the layout. It consumes only the
    main RNG (the caller must already have forked off any color RNG so that
    this sequence is stable), so both render_quilt and the PDF reconstruction
    produce identical grids for the same params.

    Returns (grid, allowed_patterns).
    """
    n_all_patterns = len(BLOCK_PATTERNS)
    if max_patterns is not None:
        available = list(range(n_all_patterns))
        rng.shuffle(available)
        allowed = sorted(available[:max_patterns])
        n_patterns = max_patterns
    else:
        allowed = None
        n_patterns = n_all_patterns

    # Non-trivial symmetries bypass tiling — they use SYMMETRY_MODES layouts.
    if symmetry != "none":
        tile_size = None

    if tile_size is not None:
        grid = _build_tiled_grid(rows, cols, tile_size, tile_variation, n_patterns, n_colors, rng)
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

        for cell in grid.values():
            cell_rng = random.Random(cell["pattern"] * 1000 + cell["palette"])
            indices = list(range(n_colors))
            cell_rng.shuffle(indices)
            cell["color_map"] = indices

    if symmetry == "bargello":
        for cell in grid.values():
            bi = cell.get("_bargello_color", 0) % n_colors
            cell["color_map"] = [bi] * n_colors

    return grid, allowed


def _strip_factors(n, variation, rng):
    """Relative widths of n strips, each 1 ± variation (all 1.0 when off).

    Stored on the design as factors rather than pixels: pixel sizes depend on
    block_size, so storing them would tie the design to one output resolution
    and leave nothing resolution-free for the PDF to measure in inches.
    """
    if variation <= 0:
        return tuple(1.0 for _ in range(n))
    return tuple(1.0 + rng.uniform(-variation, variation) for _ in range(n))


def _strip_pixels(factors, base_size):
    """Pixel sizes and cumulative offsets for strips at the given block size.

    Returns (sizes, positions): sizes[i] is strip i's width in pixels and
    positions[i] its offset, with positions[-1] the total span.
    """
    sizes = [max(1, round(base_size * f)) for f in factors]
    positions = [0]
    for s in sizes:
        positions.append(positions[-1] + s)
    return sizes, positions


def _resolve_palettes(palette_name, palette_mix, palette_name_2, max_colors, color_rng):  # pylint: disable=too-many-arguments,too-many-positional-arguments
    """Resolve palette name(s) into color-lists plus the block split count.

    Consumes color_rng in a fixed order (base → mix → second palette) so the
    RNG sequence stays stable. Returns (all_palettes, n_palettes) where
    all_palettes[0] is the primary palette.
    """
    known = {p[0] for p in PALETTES}

    def pick(name):
        colors = pick_palettes(name, color_rng)
        if max_colors is not None:
            colors = subset_in_tonal_order(colors, max_colors, color_rng)
        return colors

    palette_colors = pick(palette_name)

    # palette mixing: interleave a second palette's colors into one hybrid
    if palette_mix in known:
        mix_colors = pick(palette_mix)
        hybrid = []
        for i in range(max(len(palette_colors), len(mix_colors))):
            if i < len(palette_colors):
                hybrid.append(palette_colors[i])
            if i < len(mix_colors):
                hybrid.append(mix_colors[i])
        if max_colors is not None:
            hybrid = hybrid[:max_colors]
        palette_colors = hybrid

    # two-palette split: a valid second palette assigns n_palettes=2
    if palette_name_2 in known:
        return [palette_colors, pick(palette_name_2)], 2
    return [palette_colors], 1


@dataclass(frozen=True)
class QuiltDesign:  # pylint: disable=too-many-instance-attributes
    """Every random decision behind one quilt, resolved — no pixels.

    plan_quilt builds this; render_quilt paints it and pattern_pdf describes
    it. Both read the same decisions rather than each replaying the RNG stream,
    which is how the sewing pattern used to drift from the picture (plain cells,
    mega-blocks and mixed palettes were all invisible to the PDF's replay).

    Container fields are shared, not copied — treat them as read-only.
    """

    seed: int
    rows: int
    cols: int
    symmetry: str
    palettes: list  # [primary, second?] — each a list of RGB tuples
    grid: dict  # (r, c) -> {"pattern", "palette", "rotation", "color_map", ...}
    allowed_patterns: list  # pattern indices in use, or None for all
    tile_size: int  # None unless "none" symmetry tiles a template
    plain_cells: set  # cells drawn as one solid color
    mega_tl: set  # top-left corners of 2x2 mega-blocks
    mega_covered: set  # every cell a mega-block covers
    border_style: str  # None for no decorative border
    border_colors: list  # [c1, c2] RGB, or None without a border
    wash_alpha: float
    wash_color: tuple  # RGB, or None without a wash
    quilt_stitch: str  # None for no stitch overlay
    wonky: float
    col_factors: tuple  # relative column widths (strippy); all 1.0 when off
    row_factors: tuple  # relative row heights

    @property
    def palette_colors(self):
        """The primary palette — what border, wash and plain fills draw from."""
        return self.palettes[0]

    @property
    def n_colors(self):
        """Colors in the primary palette; every color_map has this length."""
        return len(self.palettes[0])


def _pick_plain_cells(rng, rows, cols, symmetry, plain_frac):
    """Cells drawn as one solid color: all of them for bargello, plus a
    random plain_frac of the rest."""
    plain_cells = set()
    if symmetry == "bargello":
        plain_cells = {(r, c) for r in range(rows) for c in range(cols)}
    if plain_frac > 0.0:
        for r in range(rows):
            for c in range(cols):
                if rng.random() < plain_frac:
                    plain_cells.add((r, c))
    return plain_cells


def _pick_mega_blocks(rng, rows, cols, mega_frac):
    """Greedily select non-overlapping 2x2 regions.

    Returns (mega_tl, mega_covered): top-left corners, and all covered cells.
    """
    mega_tl = set()
    mega_covered = set()
    if mega_frac > 0.0 and rows >= 2 and cols >= 2:
        candidates = [(r, c) for r in range(rows - 1) for c in range(cols - 1)]
        rng.shuffle(candidates)
        for r, c in candidates:
            covers = {(r, c), (r + 1, c), (r, c + 1), (r + 1, c + 1)}
            if not covers & mega_covered and rng.random() < mega_frac:
                mega_tl.add((r, c))
                mega_covered |= covers
    return mega_tl, mega_covered


def plan_quilt(
    rows,
    cols,
    symmetry,
    chaos,
    palette_name,
    seed,
    max_patterns=None,
    max_colors=None,
    tile_size=None,
    tile_variation=0.05,
    border_style=None,
    mega_frac=0.0,
    plain_frac=0.0,
    quilt_stitch=None,
    wash_alpha=0.0,
    palette_name_2=None,
    palette_mix=None,
    wonky=0.0,
    strippy=0.0,
):
    """Resolve every random decision for a quilt into a QuiltDesign.

    The main RNG is consumed in a fixed order — grid, plain cells, mega-blocks,
    border colors, wash color — and that order *is* the seed → quilt mapping:
    every saved rating, shared quilt ID and gallery image depends on it. The
    goldens in test_golden_render.py pin it. Color selection runs on a forked
    RNG so changing n_colors doesn't shift the layout, and strip widths on
    their own seed+7777 stream (columns, then rows).
    """
    if seed is None:
        seed = random.randint(0, 2**31)
    rng = random.Random(seed)
    color_rng = random.Random(rng.randint(0, 2**31))

    all_palettes, n_palettes = _resolve_palettes(
        palette_name, palette_mix, palette_name_2, max_colors, color_rng
    )
    palette_colors = all_palettes[0]
    n_colors = len(palette_colors)

    # Non-trivial symmetries bypass tiling — they use SYMMETRY_MODES layouts.
    if symmetry != "none":
        tile_size = None

    grid, allowed = _build_grid(
        rng,
        rows,
        cols,
        symmetry,
        chaos,
        max_patterns,
        n_colors,
        n_palettes,
        tile_size,
        tile_variation,
    )
    plain_cells = _pick_plain_cells(rng, rows, cols, symmetry, plain_frac)
    mega_tl, mega_covered = _pick_mega_blocks(rng, rows, cols, mega_frac)

    border_colors = None
    if border_style is not None:
        border_colors = [
            palette_colors[rng.randint(0, n_colors - 1)],
            palette_colors[rng.randint(0, n_colors - 1)],
        ]
    wash_color = palette_colors[rng.randint(0, n_colors - 1)] if wash_alpha > 0 else None

    strip_rng = random.Random(seed + 7777)
    col_factors = _strip_factors(cols, strippy, strip_rng)
    row_factors = _strip_factors(rows, strippy, strip_rng)

    return QuiltDesign(
        seed=seed,
        rows=rows,
        cols=cols,
        symmetry=symmetry,
        palettes=all_palettes,
        grid=grid,
        allowed_patterns=allowed,
        tile_size=tile_size,
        plain_cells=plain_cells,
        mega_tl=mega_tl,
        mega_covered=mega_covered,
        border_style=border_style,
        border_colors=border_colors,
        wash_alpha=wash_alpha,
        wash_color=wash_color,
        quilt_stitch=quilt_stitch,
        wonky=wonky,
        col_factors=col_factors,
        row_factors=row_factors,
    )


def _cell_seed(design, r, c, mega=False):
    """Per-cell seed for block randomness and wonky jitter.

    Mega-blocks offset by 500 so a mega-block anchored at (r, c) draws
    differently from the ordinary cell it displaced.
    """
    return design.seed * 10000 + r * 1000 + c + (500 if mega else 0)


def cell_patches(design, r, c, size, mega=False):
    """Base (un-jittered) patches for the block anchored at (r, c).

    In square [0, size] coords: pattern → rotate, seeded per cell. With
    mega=True, size is the 2x2 mega-block's square. The single source of block
    geometry for both the painter and the sewing pattern.
    """
    seed = _cell_seed(design, r, c, mega)
    return _block_patches(design.grid[(r, c)], size, design.n_colors, seed)


def _cell_palette(design, cell):
    """The palette a cell draws from — the second one on two-palette quilts."""
    return design.palettes[cell.get("palette", 0) % len(design.palettes)]


@dataclass(frozen=True)
class _Canvas:  # pylint: disable=too-many-instance-attributes
    """Pixel geometry of one paint: where every strip lands at a block size."""

    block_size: int
    border: int
    col_sizes: list
    col_pos: list
    row_sizes: list
    row_pos: list

    @property
    def quilt_w(self):
        """Width of the pieced area, excluding the border."""
        return self.col_pos[-1]

    @property
    def quilt_h(self):
        """Height of the pieced area, excluding the border."""
        return self.row_pos[-1]

    def cell_rect(self, r, c, span=1):
        """(x, y, w, h) of the span x span block whose top-left cell is (r, c)."""
        x = self.border + self.col_pos[c]
        y = self.border + self.row_pos[r]
        w = sum(self.col_sizes[c : c + span])
        h = sum(self.row_sizes[r : r + span])
        return x, y, w, h


def _paint_cells(ctx, design, canvas):
    """Fill every non-mega cell; returns each patterned cell's base patches.

    The base (un-jittered) patches are returned so the seam pass reuses them
    instead of rebuilding every block's geometry a second time.
    """
    size = canvas.block_size
    base_patches = {}
    for r in range(design.rows):
        for c in range(design.cols):
            if (r, c) in design.mega_covered:
                continue
            cell = design.grid[(r, c)]
            bx, by, cw, ch = canvas.cell_rect(r, c)
            palette = _cell_palette(design, cell)

            if (r, c) in design.plain_cells:
                ctx.set_source_rgb(*palette[cell["color_map"][0]])
                ctx.rectangle(bx, by, cw, ch)
                ctx.fill()
                continue

            # pattern in square coords (block_size), scaled to the cell (cw × ch)
            base = cell_patches(design, r, c, size)
            base_patches[(r, c)] = base
            patches = base
            if design.wonky > 0:
                patches = _jitter_patches(base, size, design.wonky, _cell_seed(design, r, c))
            _fill_patches(
                ctx,
                patches,
                bx,
                by,
                cw / size,
                ch / size,
                cell["color_map"],
                palette,
                design.n_colors,
            )
    return base_patches


def _paint_grid_lines(ctx, design, canvas):
    """Seam lines between blocks, skipping the interior seams of mega-blocks."""
    border = canvas.border
    mega_skip_rows = {r + 1 for r, _ in design.mega_tl}
    mega_skip_cols = {c + 1 for _, c in design.mega_tl}
    ctx.set_source_rgba(0, 0, 0, 0.15)
    ctx.set_line_width(1.0)
    for r in range(design.rows + 1):
        if r in mega_skip_rows:
            continue
        y = border + canvas.row_pos[r]
        ctx.move_to(border, y)
        ctx.line_to(border + canvas.quilt_w, y)
        ctx.stroke()
    for c in range(design.cols + 1):
        if c in mega_skip_cols:
            continue
        x = border + canvas.col_pos[c]
        ctx.move_to(x, border)
        ctx.line_to(x, border + canvas.quilt_h)
        ctx.stroke()


def _paint_tile_lines(ctx, design, canvas):
    """Heavier seams between tiles, for tiled ("none" symmetry) quilts."""
    tile_size = design.tile_size
    if tile_size is None:
        return
    border = canvas.border
    ctx.set_source_rgba(0, 0, 0, 0.4)
    ctx.set_line_width(2.5)
    for tr in range(math.ceil(design.rows / tile_size) + 1):
        y = border + canvas.row_pos[min(tr * tile_size, design.rows)]
        ctx.move_to(border, y)
        ctx.line_to(border + canvas.quilt_w, y)
        ctx.stroke()
    for tc in range(math.ceil(design.cols / tile_size) + 1):
        x = border + canvas.col_pos[min(tc * tile_size, design.cols)]
        ctx.move_to(x, border)
        ctx.line_to(x, border + canvas.quilt_h)
        ctx.stroke()


def _paint_mega_blocks(ctx, design, canvas):
    """Fill each 2x2 mega-block; returns their base patches for the seam pass.

    Painted after the grid lines so they cover the interior seams.
    """
    mega_sq = 2 * canvas.block_size  # square coord size for the pattern
    mega_base = {}
    for mr, mc in design.mega_tl:
        cell = design.grid[(mr, mc)]
        bx, by, mw, mh = canvas.cell_rect(mr, mc, span=2)
        base = cell_patches(design, mr, mc, mega_sq, mega=True)
        mega_base[(mr, mc)] = base
        patches = base
        if design.wonky > 0:
            seed = _cell_seed(design, mr, mc, mega=True)
            patches = _jitter_patches(base, mega_sq, design.wonky, seed)
        _fill_patches(
            ctx,
            patches,
            bx,
            by,
            mw / mega_sq,
            mh / mega_sq,
            cell["color_map"],
            _cell_palette(design, cell),
            design.n_colors,
        )
    return mega_base


def _paint_patch_seams(ctx, design, canvas, base_patches, mega_base):
    """Seam lines within blocks — ordinary cells first, then mega-blocks.

    Seams trace the un-jittered base outline, reusing the fill passes' builds.
    """
    size = canvas.block_size
    ctx.set_source_rgba(0, 0, 0, 0.08)
    ctx.set_line_width(0.5)
    for r in range(design.rows):
        for c in range(design.cols):
            if (r, c) in design.mega_covered or (r, c) in design.plain_cells:
                continue
            bx, by, cw, ch = canvas.cell_rect(r, c)
            _stroke_patches(ctx, base_patches[(r, c)], bx, by, cw / size, ch / size)

    mega_sq = 2 * size
    for mr, mc in design.mega_tl:
        bx, by, mw, mh = canvas.cell_rect(mr, mc, span=2)
        _stroke_patches(ctx, mega_base[(mr, mc)], bx, by, mw / mega_sq, mh / mega_sq)


def paint(design, block_size, border, output=None):
    """Draw a QuiltDesign. No randomness: every decision is already on the design.

    output=None returns PNG bytes; otherwise writes the file and returns
    (width, height).
    """
    # widen border when decorative style is active
    if design.border_style is not None:
        border = max(border, int(block_size * 0.75))

    col_sizes, col_pos = _strip_pixels(design.col_factors, block_size)
    row_sizes, row_pos = _strip_pixels(design.row_factors, block_size)
    canvas = _Canvas(block_size, border, col_sizes, col_pos, row_sizes, row_pos)
    quilt_w, quilt_h = canvas.quilt_w, canvas.quilt_h
    width = quilt_w + 2 * border
    height = quilt_h + 2 * border

    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    ctx = cairo.Context(surface)

    # background
    ctx.set_source_rgb(0.95, 0.93, 0.90)  # off-white linen background
    ctx.rectangle(0, 0, width, height)
    ctx.fill()

    if design.border_style is not None:
        _draw_border(
            ctx,
            width,
            height,
            border,
            border,
            border,
            quilt_w,
            quilt_h,
            design.border_style,
            design.border_colors,
            block_size,
        )

    base_patches = _paint_cells(ctx, design, canvas)
    _paint_grid_lines(ctx, design, canvas)
    _paint_tile_lines(ctx, design, canvas)
    mega_base = _paint_mega_blocks(ctx, design, canvas)
    _paint_patch_seams(ctx, design, canvas, base_patches, mega_base)

    # color wash — semi-transparent tint over entire quilt area
    if design.wash_alpha > 0:
        ctx.set_source_rgba(*design.wash_color, design.wash_alpha)
        ctx.rectangle(border, border, quilt_w, quilt_h)
        ctx.fill()

    # thread quilting overlay
    if design.quilt_stitch is not None:
        _draw_quilt_stitching(
            ctx, border, border, quilt_w, quilt_h, design.quilt_stitch, block_size
        )

    # save or return bytes. Finish the surface promptly so the underlying
    # cairo C buffer is released rather than lingering until GC — under a
    # long-lived web worker these large transient buffers ratchet RSS upward.
    try:
        if output is None:
            buf = io.BytesIO()
            surface.write_to_png(buf)
            return buf.getvalue()
        os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
        surface.write_to_png(output)
        # No print here: this is the library path. /pattern renders to a temp
        # file per request, so a print would put a line of noise (and a temp
        # path) into the production log on every download. main() prints.
        return (width, height)
    finally:
        surface.finish()


def render_quilt(
    rows,
    cols,
    block_size,
    symmetry,
    chaos,
    palette_name,
    seed,
    output,
    border,
    max_patterns=None,
    max_colors=None,
    tile_size=None,
    tile_variation=0.05,
    border_style=None,
    mega_frac=0.0,
    plain_frac=0.0,
    quilt_stitch=None,
    wash_alpha=0.0,
    palette_name_2=None,
    palette_mix=None,
    wonky=0.0,
    strippy=0.0,
):
    """Plan and paint a quilt: paint(plan_quilt(...)).

    Kept as the one-call entry point every caller uses (render_params, the
    sampler, both webapps, build_site); the work lives in plan_quilt (every
    random decision) and paint (pixels).
    """
    design = plan_quilt(
        rows=rows,
        cols=cols,
        symmetry=symmetry,
        chaos=chaos,
        palette_name=palette_name,
        seed=seed,
        max_patterns=max_patterns,
        max_colors=max_colors,
        tile_size=tile_size,
        tile_variation=tile_variation,
        border_style=border_style,
        mega_frac=mega_frac,
        plain_frac=plain_frac,
        quilt_stitch=quilt_stitch,
        wash_alpha=wash_alpha,
        palette_name_2=palette_name_2,
        palette_mix=palette_mix,
        wonky=wonky,
        strippy=strippy,
    )
    return paint(design, block_size, border, output)


def main():
    """Parse CLI arguments and render a quilt."""
    parser = argparse.ArgumentParser(description="Generate a quilt image")
    parser.add_argument("--rows", type=int, default=20)
    parser.add_argument("--cols", type=int, default=20)
    parser.add_argument("--block-size", type=int, default=60)
    parser.add_argument("--symmetry", default="partial", choices=list(SYMMETRY_MODES.keys()))
    parser.add_argument("--chaos", type=float, default=0.3)
    parser.add_argument("--palette", default="random")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--output", default="quilts/out.png")
    parser.add_argument("--border", type=int, default=20)
    parser.add_argument(
        "--n-patterns", type=int, default=None, help="Max block patterns to use (default: all)"
    )
    parser.add_argument(
        "--n-colors", type=int, default=None, help="Max palette colors to use (default: all)"
    )
    parser.add_argument(
        "--tile-size", type=int, default=None, help="Blocks per tile side (e.g. 5 for 5x5 tiles)"
    )
    parser.add_argument(
        "--tile-variation",
        type=float,
        default=0.05,
        help="Fraction of blocks perturbed per tile (default: 0.05)",
    )
    parser.add_argument(
        "--border-style",
        default=None,
        choices=BORDER_STYLES,
        help="Decorative border style (default: none)",
    )
    parser.add_argument(
        "--mega-frac", type=float, default=0.0, help="Fraction of 2x2 mega-blocks (default: 0.0)"
    )
    parser.add_argument(
        "--plain-frac",
        type=float,
        default=0.0,
        help="Fraction of plain solid-color blocks (default: 0.0)",
    )
    args = parser.parse_args()

    width, height = render_quilt(
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
        mega_frac=args.mega_frac,
        plain_frac=args.plain_frac,
    )
    print(f"Saved to {args.output} ({width}x{height})")


if __name__ == "__main__":
    main()
