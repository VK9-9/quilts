"""Generate printable PDF sewing patterns from quilt designs.

Takes quilt parameters (same dict as sampler/render) and produces a
multi-page PDF with cover, assembly diagram, and per-block cutting patterns.
"""

# pylint: disable=too-many-lines
import math
import os
import tempfile

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas as rl_canvas

from blocks import BLOCK_PATTERNS
from palettes import hex_to_rgb, rgb_to_hex
from quilt import cell_patches, paint, patch_rgb
from quilt_id import encode
from render_params import plan_from_params

# Page layout constants
PAGE_W, PAGE_H = letter  # 8.5 x 11 inches in points
MARGIN = 0.5 * inch
PRINTABLE_W = PAGE_W - 2 * MARGIN
PRINTABLE_H = PAGE_H - 2 * MARGIN


class _FooterCanvas(rl_canvas.Canvas):  # pylint: disable=abstract-method
    """Canvas subclass that adds a footer with quilt_id and page number."""

    def __init__(self, *args, quilt_id="", **kwargs):
        super().__init__(*args, **kwargs)
        self._quilt_id = quilt_id
        self._page_num = 0

    def showPage(self):
        self._page_num += 1
        self.saveState()
        self.setFont("Helvetica", 7)
        self.setFillColorRGB(0.6, 0.6, 0.6)
        if self._quilt_id:
            self.drawString(MARGIN, 0.3 * inch, self._quilt_id)
        self.drawRightString(PAGE_W - MARGIN, 0.3 * inch, f"Page {self._page_num}")
        self.restoreState()
        super().showPage()


def _color_label(index):
    """Map color index to letter: 0->'A', 1->'B', etc."""
    return chr(ord("A") + index)


def _human_color_name(hex_color):  # pylint: disable=too-many-return-statements
    """Map hex to a human-readable color name."""
    r, g, b = hex_to_rgb(hex_color)
    # simple heuristic: classify by hue and lightness
    lightness = (r + g + b) / 3
    if lightness > 0.85:
        return "white"
    if lightness < 0.15:
        return "black"

    # dominant channel
    mx = max(r, g, b)
    mn = min(r, g, b)
    if mx - mn < 0.1:
        if lightness > 0.6:
            return "light grey"
        return "dark grey"

    prefix = "light " if lightness > 0.65 else ("dark " if lightness < 0.35 else "")

    if r >= g and r >= b:
        if g > b + 0.15:
            return prefix + "orange" if r > 0.6 else prefix + "brown"
        if b > g + 0.1:
            return prefix + "magenta"
        return prefix + "red"
    if g >= r and g >= b:
        if b > r + 0.1:
            return prefix + "teal"
        return prefix + "green"
    # blue dominant
    if r > g + 0.1:
        return prefix + "purple"
    return prefix + "blue"


def _design_for(params):
    """The QuiltDesign this pattern describes — the same one the renderer paints.

    Planned through render_params' funnel rather than by replaying the RNG
    stream: a replay covers only what it was written to cover, and the
    previous one silently missed plain cells, mega-blocks and mixed palettes.
    Partial param dicts (tests, the CLI) get the defaults below; tile_size
    resolves falsy → no tiling, as the renderer does.
    """
    full = {
        "cols": params.get("cols", params["rows"]),
        "chaos": 0.3,
        "n_patterns": 2,
        "n_colors": 4,
        "tile_variation": 0.05,
        **params,
    }
    full["tile_size"] = full.get("tile_size") or 0
    return plan_from_params(full)


def _hex_palette(design):
    """The primary palette as hex strings — the PDF labels colors by hex."""
    return [rgb_to_hex(c) for c in design.palette_colors]


_PATTERN_UNITS = 100  # block geometry is extracted in [0, 100] pattern units
_SQUARE = [(0, 0), (100, 0), (100, 100), (0, 100)]


def _fabric_list(design):
    """Every fabric the quilt can use, as hex strings.

    The primary palette comes first, so on single-palette quilts the letters
    A, B, ... mean exactly what they always have; second-palette colors not
    already listed follow.
    """
    fabrics = _hex_palette(design)
    for palette in design.palettes[1:]:
        for rgb in palette:
            if rgb_to_hex(rgb) not in fabrics:
                fabrics.append(rgb_to_hex(rgb))
    return fabrics


def _colored_pieces(design, r, c, fabrics, mega=False):
    """The block at (r, c) before its rotation, each piece colored by fabric.

    Colors resolve through quilt.patch_rgb — the painter's own rule — into the
    cell's palette (the second one on two-palette quilts). Literal RGB pieces
    (cherry_blossom's petals) keep their tuple. Plain cells are one square.
    """
    cell = design.grid[(r, c)]
    palette = design.palettes[cell.get("palette", 0) % len(design.palettes)]
    if not mega and (r, c) in design.plain_cells:
        fill = rgb_to_hex(palette[cell["color_map"][0]])
        return [(list(_SQUARE), fabrics.index(fill))]
    pieces = []
    for poly, ci in cell_patches(design, r, c, _PATTERN_UNITS, mega=mega, rotate=False):
        if isinstance(ci, tuple):
            pieces.append((poly, ci))
        else:
            rgb = patch_rgb(ci, cell["color_map"], palette, design.n_colors)
            pieces.append((poly, fabrics.index(rgb_to_hex(rgb))))
    return pieces


def _block_key(pieces):
    """Identity of a colored block, independent of piece order and of where
    each polygon's vertex list starts. Coordinates are rounded so geometry
    reached by different float paths (a rotated variant vs. a differently
    seeded base) still compares equal."""

    def poly_key(poly):
        pts = [(round(x, 4), round(y, 4)) for x, y in poly]
        start = pts.index(min(pts))
        return tuple(pts[start:] + pts[:start])

    return tuple(sorted((poly_key(poly), repr(color)) for poly, color in pieces))


def _is_applique(color):
    """Literal-RGB pieces (cherry_blossom's petals, branch and centers) are
    appliqué embellishment, not pieces cut from the palette's fabrics."""
    return isinstance(color, tuple)


def _design_key(pieces, span, pattern_idx):
    """What makes two blocks the same design: their cut (palette-fabric)
    pieces, at the same span.

    Appliqué pieces don't count — cherry_blossom scatters its petals randomly
    per cell, so including them made every cherry block its own design (one
    21x21 quilt: ~200 pages). Blocks that carry appliqué also key on their
    pattern, or a cherry block would merge with a plain square of its
    background fabric.
    """
    cut = [(poly, color) for poly, color in pieces if not _is_applique(color)]
    has_applique = len(cut) < len(pieces)
    return (span, pattern_idx if has_applique else None, _block_key(cut))


def _extract_unique_blocks(design):
    """Group the quilt's blocks into designs: cells whose cut pieces match up
    to a quarter-turn share one design (appliqué is free — see _design_key).

    Cells are compared by the pieces actually painted (quilt.cell_patches with
    each cell's own seed), not by (pattern, rotation) bookkeeping. That
    bookkeeping merged different blocks with the same piece shapes (pinwheel,
    hourglass and bow tie are all four equal triangles), described every
    half-square triangle with one fixed diagonal whatever the cell drew, and
    couldn't see second-palette colors. Plain cells become solid-square designs
    and mega-blocks designs of span 2.

    Returns (blocks, placements, fabrics):
      blocks — design dicts, most-used first: kind ("block" | "plain"),
        pattern_idx (None for plain), pattern_name, span, count, rotations
        (quarter-turns in use), applique (has free appliqué pieces), ref
        (pieces at 0°, for the rotation page) and polygons (pieces as the
        first cell has them, for the block page — appliqué shown as an example)
      placements — {(r, c): (block, quarter_turns)} per placed block's
        top-left cell; cells a mega-block covers are omitted
      fabrics — the hex colors piece color indices refer to
    """
    fabrics = _fabric_list(design)
    blocks = []
    by_key = {}
    placements = {}
    for (r, c), cell in design.grid.items():
        mega = (r, c) in design.mega_tl
        if (r, c) in design.mega_covered and not mega:
            continue
        plain = not mega and (r, c) in design.plain_cells
        span = 2 if mega else 1
        base = _colored_pieces(design, r, c, fabrics, mega=mega)
        nominal = 0 if plain else cell["rotation"]
        pattern_idx = None if plain else cell["pattern"]
        pieces = _rotate_polygons(base, nominal, _PATTERN_UNITS)
        key = _design_key(pieces, span, pattern_idx)

        block = by_key.get(key)
        if block is None:
            block = {
                "kind": "plain" if plain else "block",
                "pattern_idx": pattern_idx,
                "pattern_name": "solid square"
                if plain
                else BLOCK_PATTERNS[cell["pattern"]].__name__,
                "span": span,
                "count": 0,
                "rotations": set(),
                "applique": any(_is_applique(color) for _poly, color in base),
                "ref": base,
                "polygons": pieces,
                "_keys": [
                    _design_key(_rotate_polygons(base, k, _PATTERN_UNITS), span, pattern_idx)
                    for k in range(4)
                ],
            }
            blocks.append(block)
            for k in block["_keys"]:
                by_key.setdefault(k, block)

        # Prefer the cell's nominal rotation when it describes the cell — a
        # symmetric block looks the same several ways, and the nominal one is
        # what the quilter would expect — else the first quarter-turn that does.
        turns = [k for k, k_key in enumerate(block["_keys"]) if k_key == key]
        turn = nominal if nominal in turns else turns[0]
        block["count"] += 1
        block["rotations"].add(turn)
        placements[(r, c)] = (block, turn)

    blocks.sort(key=lambda b: (-b["count"], b["kind"] != "block", b["pattern_idx"] or 0))
    return blocks, placements, fabrics


def _rotate_polygons(polygons, rotation, size):
    """Rotate polygons by 90*rotation degrees around (size/2, size/2)."""
    if rotation == 0:
        return polygons
    cx, cy = size / 2, size / 2
    result = []
    for poly, color_idx in polygons:
        rotated_pts = []
        for px, py in poly:
            dx, dy = px - cx, py - cy
            for _ in range(rotation):
                dx, dy = -dy, dx
            rotated_pts.append((cx + dx, cy + dy))
        result.append((rotated_pts, color_idx))
    return result


def _render_quilt_image(design):
    """Paint the design to a temp PNG file for the cover, return the path.

    Paints the very design the cutting pages describe, so the cover can't show
    a different quilt than the instructions build.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)  # pylint: disable=consider-using-with
    tmp.close()
    paint(design, block_size=40, border=0, output=tmp.name)
    return tmp.name


def _draw_cover_page(
    c,
    params,
    quilt_image_path,
    palette_colors,  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
    quilt_w,
    quilt_h,
    block_w_in,
    block_h_in,
):
    """Draw cover page with quilt image, dimensions, and color legend."""
    rows = params["rows"]
    cols = params.get("cols", rows)

    # Title
    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(PAGE_W / 2, PAGE_H - MARGIN - 30, "Quilt Pattern")

    c.setFont("Helvetica", 12)
    y = PAGE_H - MARGIN - 55
    c.drawCentredString(PAGE_W / 2, y, f"{params['palette']} / {params['symmetry']}")

    # Quilt image — centered, fit to ~4.5 inches wide
    img_size = 4.5 * inch
    img_x = (PAGE_W - img_size) / 2
    img_y = y - 20 - img_size
    c.drawImage(quilt_image_path, img_x, img_y, img_size, img_size, preserveAspectRatio=True)

    # Dimensions info
    y = img_y - 25
    c.setFont("Helvetica", 11)
    border_style = params.get("border_style")
    border_width_in = min(block_w_in, block_h_in) * 0.75 if border_style else 0

    size_str = f"{quilt_w:.0f}\" x {quilt_h:.0f}\"  ({quilt_w / 12:.1f}' x {quilt_h / 12:.1f}')"
    block_str = f'{block_w_in:.2f}" x {block_h_in:.2f}"'

    info_lines = [
        f"Finished size: {size_str}",
        f"Grid: {rows} rows x {cols} columns",
        f"Block size: {block_str}",
        "Seam allowance: added to all pieces (solid = stitch, dashed = cut)",
    ]
    if border_style:
        info_lines.append(f'Border: {border_style} — {border_width_in:.2f}" wide')
    for line in info_lines:
        c.drawString(MARGIN + 20, y, line)
        y -= 16

    # Color legend
    y -= 10
    c.setFont("Helvetica-Bold", 12)
    c.drawString(MARGIN + 20, y, "Color Legend")
    y -= 5

    c.setFont("Helvetica", 10)
    for i, hex_color in enumerate(palette_colors):
        y -= 20
        r, g, b = hex_to_rgb(hex_color)
        label = _color_label(i)
        name = _human_color_name(hex_color)

        # color swatch
        c.setFillColorRGB(r, g, b)
        c.setStrokeColorRGB(0.3, 0.3, 0.3)
        c.rect(MARGIN + 25, y - 2, 14, 14, fill=1, stroke=1)

        # label text
        c.setFillColorRGB(0, 0, 0)
        c.drawString(MARGIN + 45, y, f"{label}  —  {name}  ({hex_color})")

    c.showPage()


def _block_title(blk):
    """Human name for a design, e.g. 'bow tie' or 'star (2x2 mega-block)'."""
    name = blk["pattern_name"].replace("_", " ")
    if blk["span"] > 1:
        name += f" ({blk['span']}x{blk['span']} mega-block)"
    return name


def _draw_assembly_page(
    c,
    placements,
    unique_blocks,
    params,  # pylint: disable=too-many-locals
    _quilt_w,
    _quilt_h,
    _block_w_in,
    _block_h_in,
):
    """Draw assembly diagram showing block placement in the grid.

    Each placed block is labelled with its design number and the quarter-turns
    that orient the design's reference drawing (see the rotation page) to match
    it. Mega-blocks are drawn as one 2x2 square.
    """
    rows = params["rows"]
    cols = params.get("cols", rows)

    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(PAGE_W / 2, PAGE_H - MARGIN - 25, "Assembly Diagram")

    design_nums = {id(blk): i + 1 for i, blk in enumerate(unique_blocks)}

    # fit grid into printable area
    max_cell = min(PRINTABLE_W / cols, (PRINTABLE_H - 50) / rows)
    cell_size = min(max_cell, 0.6 * inch)
    grid_w = cols * cell_size
    grid_h = rows * cell_size
    ox = (PAGE_W - grid_w) / 2
    oy = PAGE_H - MARGIN - 55 - grid_h

    # light colors for each design number
    design_colors = [
        (0.85, 0.92, 1.0),
        (1.0, 0.90, 0.85),
        (0.85, 1.0, 0.88),
        (1.0, 1.0, 0.85),
        (0.93, 0.85, 1.0),
        (0.85, 1.0, 1.0),
        (1.0, 0.85, 0.93),
        (0.95, 0.95, 0.85),
        (0.88, 0.92, 0.96),
        (0.96, 0.88, 0.92),
    ]

    c.setFont("Helvetica", max(5, min(8, cell_size / 3)))
    for r in range(rows):
        for col in range(cols):
            placed = placements.get((r, col))
            if placed is None:  # covered by a mega-block anchored elsewhere
                continue
            blk, turn = placed
            size = cell_size * blk["span"]
            x = ox + col * cell_size
            y = oy + (rows - r - blk["span"]) * cell_size
            design_num = design_nums[id(blk)]

            # fill
            dc = design_colors[(design_num - 1) % len(design_colors)]
            c.setFillColorRGB(*dc)
            c.setStrokeColorRGB(0.5, 0.5, 0.5)
            c.rect(x, y, size, size, fill=1, stroke=1)

            # label
            c.setFillColorRGB(0, 0, 0)
            rot_label = ["", "↻90", "↻180", "↻270"][turn]
            label = f"#{design_num}"
            c.drawCentredString(x + size / 2, y + size / 2 + 2, label)
            if rot_label:
                c.setFont("Helvetica", max(4, min(6, cell_size / 4)))
                c.drawCentredString(x + size / 2, y + size / 2 - 8, rot_label)
                c.setFont("Helvetica", max(5, min(8, cell_size / 3)))

    # legend below grid
    y = oy - 25
    c.setFont("Helvetica", 9)
    for i, blk in enumerate(unique_blocks):
        design_num = i + 1
        count = blk["count"]
        rots = sorted(blk["rotations"])
        line = f"#{design_num}: {_block_title(blk)}"
        if len(rots) > 1:
            rot_strs = [f"{r * 90}\u00b0" for r in rots]
            line += f" (rotations: {', '.join(rot_strs)})"
        elif rots[0] > 0:
            line += f" (rotated {rots[0] * 90}\u00b0)"
        line += f" \u2014 {count} block{'s' if count != 1 else ''}"
        c.drawString(MARGIN + 20, y, line)
        y -= 14

    c.showPage()


def _draw_bargello_pages(
    c,
    grid,
    palette_colors,
    params,  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals,too-many-statements
    _quilt_w,
    quilt_h,
    block_w_in,
    block_h_in,
    seam_allowance,
):
    """Draw bargello-specific pattern pages showing strip color arrangement.

    Bargello quilts are made from strips of fabric, not pieced blocks.
    Each column has a repeating color sequence shifted by the wave function.
    """
    rows = params["rows"]
    cols = params.get("cols", rows)
    n_colors = len(palette_colors)
    bm = 0.35 * inch

    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(PAGE_W / 2, PAGE_H - bm - 20, "Bargello Strip Layout")

    c.setFont("Helvetica", 10)
    y = PAGE_H - bm - 40
    c.drawString(
        bm,
        y,
        f'Strip width: {block_w_in:.2f}"  |  '
        f'Strip height: {quilt_h:.0f}"  |  '
        f'Seam allowance: {seam_allowance:.2f}"',
    )
    y -= 16
    c.drawString(
        bm, y, "Each column below shows the color sequence for that strip (top to bottom)."
    )
    y -= 25

    # Build column color sequences
    col_sequences = []
    for col in range(cols):
        seq = []
        for row in range(rows):
            cell = grid.get((row, col), {})
            bi = cell.get("_bargello_color", 0) % n_colors
            seq.append(bi)
        col_sequences.append(seq)

    # Draw strip diagram — show each column as a vertical strip of colored cells
    strip_display_w = min(25, (PAGE_W - 2 * bm) / (cols + 1))
    cell_h = min(12, (y - bm - 40) / rows)
    grid_w = cols * strip_display_w
    ox = (PAGE_W - grid_w) / 2
    top_y = y

    # column headers
    c.setFont("Helvetica", max(5, min(7, strip_display_w * 0.4)))
    for col in range(cols):
        cx = ox + col * strip_display_w + strip_display_w / 2
        c.drawCentredString(cx, top_y + 3, f"C{col + 1}")

    # draw cells
    for col in range(cols):
        for row in range(rows):
            bi = col_sequences[col][row]
            hex_color = palette_colors[bi % len(palette_colors)]
            r, g, b = hex_to_rgb(hex_color)

            cell_x = ox + col * strip_display_w
            cell_y = top_y - (row + 1) * cell_h

            c.setFillColorRGB(r, g, b)
            c.setStrokeColorRGB(0.5, 0.5, 0.5)
            c.setLineWidth(0.3)
            c.rect(cell_x, cell_y, strip_display_w, cell_h, fill=1, stroke=1)

            # color label
            c.setFillColorRGB(1, 1, 1)
            c.setFont("Helvetica", max(4, min(6, cell_h * 0.6)))
            c.drawCentredString(
                cell_x + strip_display_w / 2, cell_y + cell_h / 2 - 2, _color_label(bi)
            )

    # row labels on left
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica", max(5, min(7, cell_h * 0.7)))
    for row in range(rows):
        ry = top_y - (row + 1) * cell_h + cell_h / 2 - 2
        c.drawRightString(ox - 4, ry, str(row + 1))

    # cutting instructions below
    below_y = top_y - rows * cell_h - 25
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(bm, below_y, "Cutting Instructions")
    below_y -= 16

    c.setFont("Helvetica", 9)
    cut_w = block_w_in + 2 * seam_allowance
    cut_h = block_h_in + 2 * seam_allowance

    # count strips per color
    color_counts = {}
    for col in range(cols):
        for bi in col_sequences[col]:
            color_counts[bi] = color_counts.get(bi, 0) + 1

    c.drawString(
        bm,
        below_y,
        f'Cut each cell: {cut_w:.2f}" wide x {cut_h:.2f}" tall '
        f'(includes {seam_allowance:.2f}" seam allowance)',
    )
    below_y -= 14

    for bi in sorted(color_counts):
        label = _color_label(bi)
        hex_color = palette_colors[bi % len(palette_colors)]
        name = _human_color_name(hex_color)
        count = color_counts[bi]
        c.drawString(bm + 10, below_y, f"Color {label} ({name}): {count} cells")
        below_y -= 13

    c.showPage()

    # --- Page 2: Real-size cutting template ---
    _draw_bargello_template(c, block_w_in, block_h_in, seam_allowance)


def _draw_bargello_template(c, cell_w_in, cell_h_in, seam_allowance):  # pylint: disable=too-many-locals,too-many-statements
    """Draw a real-size cutting template for bargello cells."""
    bm = 0.35 * inch

    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(PAGE_W / 2, PAGE_H - bm - 20, "Bargello Cutting Template")

    c.setFont("Helvetica", 10)
    info_y = PAGE_H - bm - 42
    c.drawString(bm, info_y, f'Finished size: {cell_w_in:.2f}" x {cell_h_in:.2f}"')
    info_y -= 14
    cut_w = cell_w_in + 2 * seam_allowance
    cut_h = cell_h_in + 2 * seam_allowance
    c.drawString(
        bm,
        info_y,
        f'Cut size (with {seam_allowance:.2f}" seam allowance): {cut_w:.2f}" x {cut_h:.2f}"',
    )
    info_y -= 20

    # Convert to points
    finished_w = cell_w_in * inch
    finished_h = cell_h_in * inch
    cut_w_pt = cut_w * inch
    cut_h_pt = cut_h * inch

    # Check if it fits on page; scale down if needed
    avail_w = PAGE_W - 2 * bm
    avail_h = info_y - bm - 30
    scale = min(1.0, avail_w / cut_w_pt, avail_h / cut_h_pt)

    if scale < 1.0:
        c.drawString(bm, info_y, f"Scaled to {scale * 100:.0f}% to fit page")
        info_y -= 14

    c.drawString(
        bm,
        info_y,
        "Solid line = seam/stitch line (finished size)  |  "
        "Dashed line = cutting line (+seam allowance)",
    )
    info_y -= 25

    # Center the template
    sw = cut_w_pt * scale
    sh = cut_h_pt * scale
    rx = (PAGE_W - sw) / 2
    ry = info_y - sh

    sa_pt = seam_allowance * inch * scale

    # Seam/stitch line (solid) — finished size
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(1.2)
    c.setDash([])
    c.rect(rx + sa_pt, ry + sa_pt, finished_w * scale, finished_h * scale, fill=0, stroke=1)

    # Cutting line (dashed) — seam allowance
    c.setStrokeColorRGB(0.4, 0.4, 0.4)
    c.setLineWidth(0.8)
    c.setDash([4, 3])
    c.rect(rx, ry, sw, sh, fill=0, stroke=1)

    # Dimension labels
    c.setFont("Helvetica", 8)
    c.setFillColorRGB(0, 0, 0)

    # Width dimension (below)
    mid_x = rx + sw / 2
    c.drawCentredString(mid_x, ry - 12, f'{cut_w:.2f}"')

    # Height dimension (right)
    mid_y = ry + sh / 2
    c.saveState()
    c.translate(rx + sw + 14, mid_y)
    c.rotate(90)
    c.drawCentredString(0, 0, f'{cut_h:.2f}"')
    c.restoreState()

    # Finished size dimensions (inside)
    fin_mid_x = rx + sa_pt + finished_w * scale / 2
    fin_top_y = ry + sa_pt + finished_h * scale
    c.setFont("Helvetica", 7)
    c.setFillColorRGB(0.3, 0.3, 0.3)
    c.drawCentredString(fin_mid_x, fin_top_y + 4, f'{cell_w_in:.2f}" x {cell_h_in:.2f}" finished')

    # Seam allowance annotation
    c.setFont("Helvetica", 6)
    c.drawString(rx + 2, ry + sa_pt / 2 - 2, f'{seam_allowance:.2f}" SA')

    # Grain line arrow (vertical — parallel to long edge)
    arrow_len = min(finished_h * scale * 0.4, 50)
    arrow_x = rx + sa_pt + finished_w * scale / 2
    arrow_cy = ry + sa_pt + finished_h * scale / 2
    c.setStrokeColorRGB(0.4, 0.4, 0.4)
    c.setLineWidth(0.6)
    c.line(arrow_x, arrow_cy - arrow_len / 2, arrow_x, arrow_cy + arrow_len / 2)
    # arrowhead
    c.line(arrow_x, arrow_cy + arrow_len / 2, arrow_x - 3, arrow_cy + arrow_len / 2 - 5)
    c.line(arrow_x, arrow_cy + arrow_len / 2, arrow_x + 3, arrow_cy + arrow_len / 2 - 5)

    c.setFont("Helvetica", 6)
    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.drawCentredString(arrow_x, arrow_cy - arrow_len / 2 - 8, "grain")

    c.showPage()


def _edge_lengths_inches(poly, sx, sy):
    """Return list of edge lengths in real inches for a pattern polygon."""
    n = len(poly)
    lengths = []
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        dx_in = (x2 - x1) * sx
        dy_in = (y2 - y1) * sy
        lengths.append(math.sqrt(dx_in * dx_in + dy_in * dy_in))
    return lengths


def _label_position(pts, i, n, center_x, center_y):
    """Compute label (x, y) for edge i, offset 9pt outward from center."""
    mx = (pts[i][0] + pts[(i + 1) % n][0]) / 2
    my = (pts[i][1] + pts[(i + 1) % n][1]) / 2
    odx, ody = mx - center_x, my - center_y
    dist = math.sqrt(odx * odx + ody * ody)
    if dist > 0.1:
        odx /= dist
        ody /= dist
    return mx + odx * 9, my + ody * 9 - 2


def _label_edge_lengths(c, pts, edge_lengths, center_x, center_y):
    """Label one instance of each unique edge length, offset outward.

    Skips labels whose position would overlap with an already-placed label.
    """
    n = len(pts)
    labeled = set()
    placed = []  # (lx, ly) of placed labels for spatial deconfliction
    min_dist = 12  # minimum distance between label centers in points
    for i in range(n):
        key = round(edge_lengths[i], 1)
        if key in labeled or key < 0.1:
            continue

        lx, ly = _label_position(pts, i, n, center_x, center_y)

        # skip if too close to an existing label
        if any(math.sqrt((lx - px) ** 2 + (ly - py) ** 2) < min_dist for px, py in placed):
            continue

        labeled.add(key)
        placed.append((lx, ly))
        c.drawCentredString(lx, ly, f'{edge_lengths[i]:.1f}"')
    return labeled


def _draw_edge_dimensions(c, pts, poly, block_w_in, block_h_in):
    """Draw dimension labels near edges of a piece polygon.

    Labels unique edge lengths placed near the edge midpoint.
    For shapes where the bounding-box height doesn't match any edge
    (trapezoids, non-right triangles), adds a height label too.
    """
    n = len(pts)
    if n < 3:
        return

    sx = block_w_in / 100
    sy = block_h_in / 100
    edge_lengths = _edge_lengths_inches(poly, sx, sy)

    bbox_h = (max(py for _, py in poly) - min(py for _, py in poly)) * sy

    center_x = sum(p[0] for p in pts) / n
    center_y = sum(p[1] for p in pts) / n

    c.setFont("Helvetica", 6)
    c.setFillColorRGB(0.2, 0.2, 0.2)

    labeled = _label_edge_lengths(c, pts, edge_lengths, center_x, center_y)

    # If bbox height differs from all labeled edges, show it
    if round(bbox_h, 1) not in labeled and round(bbox_h, 1) >= 0.1:
        c.drawCentredString(
            min(p[0] for p in pts) - 10,
            (max(p[1] for p in pts) + min(p[1] for p in pts)) / 2 - 2,
            f'h:{bbox_h:.1f}"',
        )


def _draw_grain_arrow(c, pts, cx, cy):  # pylint: disable=too-many-locals
    """Draw a grain line arrow inside the piece, parallel to longest edge."""
    # find longest edge direction
    best_len = 0
    best_dx, best_dy = 0, 1  # default vertical
    for i, (x1, y1) in enumerate(pts):
        x2, y2 = pts[(i + 1) % len(pts)]
        dx, dy = x2 - x1, y2 - y1
        edge_len = math.sqrt(dx * dx + dy * dy)
        if edge_len > best_len:
            best_len = edge_len
            best_dx, best_dy = dx / edge_len, dy / edge_len

    # draw arrow centered on piece, 40% of longest edge length
    arrow_len = best_len * 0.35
    ax1 = cx - best_dx * arrow_len / 2
    ay1 = cy - best_dy * arrow_len / 2
    ax2 = cx + best_dx * arrow_len / 2
    ay2 = cy + best_dy * arrow_len / 2

    c.setStrokeColorRGB(0.4, 0.4, 0.4)
    c.setLineWidth(0.6)
    c.setDash([])
    c.line(ax1, ay1, ax2, ay2)

    # arrowhead
    head = 3
    # perpendicular
    px, py = -best_dy, best_dx
    c.line(ax2, ay2, ax2 - best_dx * head + px * head * 0.5, ay2 - best_dy * head + py * head * 0.5)
    c.line(ax2, ay2, ax2 - best_dx * head - px * head * 0.5, ay2 - best_dy * head - py * head * 0.5)


def _resolve_color(color_idx, palette_colors):
    """Return (r, g, b) for a color index or RGB tuple."""
    if isinstance(color_idx, tuple):
        return color_idx
    return hex_to_rgb(palette_colors[color_idx % len(palette_colors)])


def _draw_block_thumbnail(c, polygons, palette_colors, pos, display_size):
    """Draw a small colored block at the given position."""
    x, y = pos
    scale = display_size / 100
    c.setStrokeColorRGB(0.3, 0.3, 0.3)
    c.setLineWidth(0.4)
    for poly, color_idx in polygons:
        rgb = _resolve_color(color_idx, palette_colors)
        path = c.beginPath()
        pts = [(x + px * scale, y + display_size - py * scale) for px, py in poly]
        path.moveTo(*pts[0])
        for pt in pts[1:]:
            path.lineTo(*pt)
        path.close()
        c.setFillColorRGB(*rgb)
        c.drawPath(path, fill=1, stroke=1)


def _draw_rotation_summary(c, unique_blocks, palette_colors):  # pylint: disable=too-many-locals
    """Draw a page showing each pieced design in all 4 rotations.

    Each design's 0° drawing is its reference orientation; the assembly page's
    turn labels are quarter-turns from it. Solid squares look the same every
    way, so they're left off.
    """
    bm = 0.35 * inch
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(PAGE_W / 2, PAGE_H - bm - 20, "Block Rotations")

    thumb_size = 1.2 * inch
    spacing = 0.3 * inch
    label_height = 16
    row_height = thumb_size + label_height + 20

    y = PAGE_H - bm - 50

    for blk in unique_blocks:
        if blk["kind"] == "plain":
            continue
        design_num = blk["_design_num"]
        name = _block_title(blk)
        base_polygons = blk["ref"]

        if y - row_height < bm:
            c.showPage()
            y = PAGE_H - bm - 30

        # Block label
        c.setFont("Helvetica-Bold", 11)
        c.setFillColorRGB(0, 0, 0)
        c.drawString(bm, y, f"Block #{design_num}: {name}")
        y -= 5

        # Draw all 4 rotations
        for rot in range(4):
            rotated = _rotate_polygons(base_polygons, rot, 100)
            rx = bm + rot * (thumb_size + spacing)
            ry = y - thumb_size
            _draw_block_thumbnail(c, rotated, palette_colors, (rx, ry), thumb_size)
            # rotation label
            c.setFont("Helvetica", 8)
            c.setFillColorRGB(0.3, 0.3, 0.3)
            c.drawCentredString(rx + thumb_size / 2, ry - 12, f"{rot * 90}\u00b0")

        y -= thumb_size + label_height + 15

    c.showPage()


def _draw_block_page(
    c,
    block,
    palette_colors,
    block_w_in,
    block_h_in,  # pylint: disable=too-many-locals,too-many-statements,too-many-branches,too-many-arguments,too-many-positional-arguments
    seam_allowance,
):
    """Draw one block's pattern page with assembled view and individual pieces."""
    design_num = block["_design_num"]
    name = _block_title(block)
    polygons = block["polygons"]
    rotations = sorted(block["rotations"])
    pattern_size = 100  # polygons generated at size=100
    bm = 0.35 * inch  # tighter margins for block pages

    # --- Header row: assembled block (left) + info (right) ---
    c.setFont("Helvetica-Bold", 13)
    title = f"Block #{design_num}: {name}"
    c.drawString(bm, PAGE_H - bm - 16, title)

    # Assembled block — 1.8 inches, top-left
    assembled_display = 1.8 * inch
    scale = assembled_display / pattern_size
    ax = bm
    ay = PAGE_H - bm - 28 - assembled_display

    c.setStrokeColorRGB(0.3, 0.3, 0.3)
    c.setLineWidth(0.5)
    for poly, color_idx in polygons:
        if isinstance(color_idx, tuple):
            r, g, b = color_idx
        else:
            hex_color = palette_colors[color_idx % len(palette_colors)]
            r, g, b = hex_to_rgb(hex_color)
        path = c.beginPath()
        pts = [(ax + px * scale, ay + assembled_display - py * scale) for px, py in poly]
        path.moveTo(*pts[0])
        for pt in pts[1:]:
            path.lineTo(*pt)
        path.close()
        c.setFillColorRGB(r, g, b)
        c.drawPath(path, fill=1, stroke=1)
        # color label in center
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        label = _color_label(color_idx) if not isinstance(color_idx, tuple) else "?"
        c.setFillColorRGB(1, 1, 1)
        c.setFont("Helvetica-Bold", 8)
        c.drawCentredString(cx, cy - 3, label)

    # Info text — right of assembled block
    info_x = ax + assembled_display + 15
    info_y = PAGE_H - bm - 38
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica", 9)
    c.drawString(info_x, info_y, f'Finished: {block_w_in:.2f}" x {block_h_in:.2f}"')
    c.drawString(info_x, info_y - 13, f"Count: {block['count']} blocks")
    info_offset = 26
    if len(rotations) > 1:
        rot_strs = [f"{r * 90}\u00b0" for r in rotations]
        c.drawString(
            info_x, info_y - info_offset, f"Rotations: {', '.join(rot_strs)} (same pieces)"
        )
        info_offset += 13
    c.drawString(info_x, info_y - info_offset, "Solid = seam/stitch line (finished size)")
    c.drawString(
        info_x,
        info_y - info_offset - 13,
        f'Dashed = cut line (+{seam_allowance:.2f}" seam allowance)',
    )
    if block.get("applique"):
        c.drawString(
            info_x,
            info_y - info_offset - 26,
            "? = appliqué: placement varies from block to block, place freely",
        )

    # --- Individual pieces section ---
    pieces_top = ay - 15
    c.setFont("Helvetica-Bold", 10)
    c.drawString(bm, pieces_top, "Individual Pieces")
    pieces_top -= 12

    # Compute scale: fit pieces as large as possible
    # Seam allowance in pattern units (may differ per axis for rectangular blocks)
    sa_pat_x = seam_allowance * pattern_size / block_w_in
    sa_pat_y = seam_allowance * pattern_size / block_h_in
    piece_bboxes = []
    for poly, color_idx in polygons:
        xs = [px for px, py in poly]
        ys = [py for px, py in poly]
        # bbox in pattern units, including seam allowance
        pw = max(xs) - min(xs) + 2 * sa_pat_x
        ph = max(ys) - min(ys) + 2 * sa_pat_y
        piece_bboxes.append((pw, ph, min(xs), min(ys)))

    real_scale = max(block_w_in, block_h_in) * inch / pattern_size
    avail_w = PAGE_W - 2 * bm
    avail_h = pieces_top - bm

    # scale down until all pieces fit on one page
    piece_gap = 8
    while (
        _try_layout_pieces(piece_bboxes, real_scale, avail_w, avail_h, piece_gap) is None
        and real_scale > 0.5
    ):
        real_scale *= 0.75

    # draw pieces
    col_x = bm
    cur_y = pieces_top
    row_h = 0

    for idx, (poly, color_idx) in enumerate(polygons):
        pw_pat, ph_pat, ox, oy = piece_bboxes[idx]
        pw = pw_pat * real_scale
        ph = ph_pat * real_scale

        # wrap to next row?
        if col_x + pw + piece_gap > PAGE_W - bm and col_x > bm + 1:
            col_x = bm
            cur_y -= row_h + piece_gap
            row_h = 0

        # new page?
        if cur_y - ph < bm:
            c.showPage()
            cur_y = PAGE_H - bm - 20
            col_x = bm
            row_h = 0
            c.setFont("Helvetica-Bold", 10)
            c.drawString(bm, PAGE_H - bm - 10, f"Block #{design_num} (continued)")

        # draw seam/stitch line (solid) — finished size
        c.setStrokeColorRGB(0, 0, 0)
        c.setLineWidth(0.8)
        c.setDash([])
        path = c.beginPath()
        pts = [
            (col_x + (px - ox + sa_pat_x) * real_scale, cur_y - (py - oy + sa_pat_y) * real_scale)
            for px, py in poly
        ]
        path.moveTo(*pts[0])
        for pt in pts[1:]:
            path.lineTo(*pt)
        path.close()
        c.drawPath(path, fill=0, stroke=1)

        # draw cut line (dashed) — true seam allowance outward in inch space
        # (correct on both axes for rectangular blocks); skip for non-convex
        sa_poly = _offset_polygon_real(poly, -seam_allowance, block_w_in / 100, block_h_in / 100)
        if sa_poly is not None:
            c.setStrokeColorRGB(0.4, 0.4, 0.4)
            c.setLineWidth(0.5)
            c.setDash([3, 3])
            path_sa = c.beginPath()
            sa_pts = [
                (
                    col_x + (px - ox + sa_pat_x) * real_scale,
                    cur_y - (py - oy + sa_pat_y) * real_scale,
                )
                for px, py in sa_poly
            ]
            path_sa.moveTo(*sa_pts[0])
            for pt in sa_pts[1:]:
                path_sa.lineTo(*pt)
            path_sa.close()
            c.drawPath(path_sa, fill=0, stroke=1)

        # color label
        c.setDash([])
        label = _color_label(color_idx) if not isinstance(color_idx, tuple) else "?"
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        c.setFillColorRGB(0, 0, 0)
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(cx, cy - 3, label)

        # edge dimensions on the finished (seam) line — matches the cover's
        # "solid = finished size" convention, and is consistent for every piece
        # (cut = finished + the stated seam allowance).
        _draw_edge_dimensions(c, pts, poly, block_w_in, block_h_in)

        # grain line arrow
        _draw_grain_arrow(c, pts, cx, cy)

        col_x += pw + piece_gap
        row_h = max(row_h, ph)

    c.showPage()


def _try_layout_pieces(bboxes, scale, avail_w, avail_h, gap):
    """Check if pieces fit in the available area at the given scale.

    Returns True if they fit, None if not.
    """
    col_x = 0.0
    cur_y = 0.0
    row_h = 0.0

    for pw_pat, ph_pat, _ox, _oy in bboxes:
        pw = pw_pat * scale
        ph = ph_pat * scale

        # Wrap predicate must match the draw loop (which includes `gap`), else
        # the planner can validate a layout the drawer then wraps onto an extra
        # row/page.
        if col_x + pw + gap > avail_w and col_x > 0.1:
            col_x = 0.0
            cur_y += row_h + gap
            row_h = 0.0

        if cur_y + ph > avail_h:
            return None

        col_x += pw + gap
        row_h = max(row_h, ph)

    return True


def _polygon_area_signed(polygon):
    """Compute signed area of polygon (positive = CCW, negative = CW)."""
    total = 0.0
    n = len(polygon)
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        total += x1 * y2 - x2 * y1
    return total / 2.0


def _is_convex(polygon):
    """Check if a polygon is convex by testing that all cross products
    have the same sign."""
    n = len(polygon)
    if n < 3:
        return True
    sign = None
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        x3, y3 = polygon[(i + 2) % n]
        cross = (x2 - x1) * (y3 - y2) - (y2 - y1) * (x3 - x2)
        if abs(cross) < 1e-10:
            continue
        if sign is None:
            sign = cross > 0
        elif (cross > 0) != sign:
            return False
    return True


def _offset_polygon(polygon, offset):  # pylint: disable=too-many-locals
    """Offset polygon edges outward by offset amount (simple approach).

    For each edge, shift it outward by offset along its normal.
    Then find intersections of adjacent shifted edges.
    """
    n = len(polygon)
    if n < 3:
        return polygon

    # detect winding: flip normal direction for CCW polygons
    sign = -1.0 if _polygon_area_signed(polygon) > 0 else 1.0

    # compute outward-shifted edges
    edges = []
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        dx, dy = x2 - x1, y2 - y1
        length = math.sqrt(dx * dx + dy * dy)
        if length < 1e-10:
            edges.append((x1, y1, x2, y2, 0, 0))
            continue
        # outward normal — direction depends on winding
        nx, ny = sign * dy / length, sign * -dx / length
        edges.append(
            (
                x1 + nx * offset,
                y1 + ny * offset,
                x2 + nx * offset,
                y2 + ny * offset,
                nx,
                ny,
            )
        )

    # find intersection of adjacent shifted edges
    max_dist = abs(offset) * 4  # clamp wildly divergent intersections
    result = []
    for i in range(n):
        e1 = edges[i]
        e2 = edges[(i + 1) % n]
        # original vertex at the junction of these two edges
        orig = polygon[(i + 1) % n]

        # check if this is a reflex angle (edges double back) via cross product
        d1x, d1y = e1[2] - e1[0], e1[3] - e1[1]  # direction of edge 1
        d2x, d2y = e2[2] - e2[0], e2[3] - e2[1]  # direction of edge 2
        cross = d1x * d2y - d1y * d2x
        is_reflex = (cross * sign) > 0  # reflex when cross matches winding

        if is_reflex:
            # bevel join: include both offset edge endpoints
            result.append((e1[2], e1[3]))
            result.append((e2[0], e2[1]))
            continue

        pt = _line_intersection(e1[0], e1[1], e1[2], e1[3], e2[0], e2[1], e2[2], e2[3])
        if pt:
            dx, dy = pt[0] - orig[0], pt[1] - orig[1]
            dist = math.sqrt(dx * dx + dy * dy)
            if dist > max_dist:
                # bevel join: flat cap at sharp corners
                result.append((e1[2], e1[3]))
                result.append((e2[0], e2[1]))
            else:
                result.append(pt)
        else:
            result.append((e1[2], e1[3]))

    return result


def _offset_polygon_real(polygon, offset_in, sx, sy):
    """Offset a pattern-space polygon outward by `offset_in` inches.

    Pattern units map to inches anisotropically for rectangular blocks
    (sx = block_w_in/100, sy = block_h_in/100), so a single pattern-unit
    scalar offset gives too much seam allowance on one axis. Convert to inch
    space, offset by a uniform `offset_in`, and convert back. For square
    blocks (sx == sy) this is identical to _offset_polygon with a scalar.
    """
    scaled = [(px * sx, py * sy) for px, py in polygon]
    off = _offset_polygon(scaled, offset_in)
    if off is None:
        return None
    return [(x / sx, y / sy) for x, y in off]


def _line_intersection(x1, y1, x2, y2, x3, y3, x4, y4):  # pylint: disable=too-many-arguments,too-many-positional-arguments
    """Find intersection of line (x1,y1)-(x2,y2) with (x3,y3)-(x4,y4)."""
    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(denom) < 1e-10:
        return None
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
    return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))


def _draw_cutting_summary(
    c,
    unique_blocks,
    palette_colors,
    _grid,  # pylint: disable=too-many-locals,too-many-arguments,too-many-positional-arguments
    block_w_in,
    block_h_in,
    seam_allowance,
    params=None,
):
    """Draw a cutting summary page tallying total pieces per color."""
    bm = 0.35 * inch

    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(PAGE_W / 2, PAGE_H - bm - 20, "Cutting Summary")
    y = PAGE_H - bm - 50

    # Tally pieces: color_idx -> total count across all blocks × block count
    color_totals = {}  # color_idx -> piece count
    for blk in unique_blocks:
        block_count = blk["count"]
        for _poly, color_idx in blk["polygons"]:
            if isinstance(color_idx, tuple):
                continue
            color_totals[color_idx] = color_totals.get(color_idx, 0) + block_count

    # Table header
    c.setFont("Helvetica-Bold", 10)
    col_swatch = bm + 5
    col_label = col_swatch + 22
    col_color = col_label + 30
    col_pieces = col_color + 130
    c.drawString(col_swatch, y, "")
    c.drawString(col_label, y, "Color")
    c.drawString(col_color, y, "Name")
    c.drawString(col_pieces, y, "Total Pieces")
    y -= 5
    c.setLineWidth(0.5)
    c.setStrokeColorRGB(0.5, 0.5, 0.5)
    c.line(bm, y, PAGE_W - bm, y)
    y -= 15

    c.setFont("Helvetica", 10)
    grand_total = 0
    for i, hex_color in enumerate(palette_colors):
        count = color_totals.get(i, 0)
        grand_total += count
        r, g, b = hex_to_rgb(hex_color)
        label = _color_label(i)
        name = _human_color_name(hex_color)

        # swatch
        c.setFillColorRGB(r, g, b)
        c.setStrokeColorRGB(0.3, 0.3, 0.3)
        c.rect(col_swatch, y - 2, 14, 14, fill=1, stroke=1)

        c.setFillColorRGB(0, 0, 0)
        c.drawString(col_label, y, label)
        c.drawString(col_color, y, f"{name}  ({hex_color})")
        c.drawString(col_pieces, y, str(count))
        y -= 20

    # Grand total
    y -= 5
    c.line(bm, y + 10, PAGE_W - bm, y + 10)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(col_color, y, "Total")
    c.drawString(col_pieces, y, str(grand_total))

    y = _draw_block_breakdown(c, unique_blocks, bm, y)
    y = _draw_border_info(c, params, block_w_in, block_h_in, seam_allowance, bm, y)
    c.showPage()


def _draw_block_breakdown(c, unique_blocks, bm, y):  # pylint: disable=too-many-locals
    """Draw per-block piece breakdown within the cutting summary."""
    y -= 35
    c.setFont("Helvetica-Bold", 12)
    c.drawString(bm, y, "Per-Block Breakdown")
    y -= 18

    c.setFont("Helvetica", 9)
    for blk in unique_blocks:
        design_num = blk["_design_num"]
        name = _block_title(blk)
        count = blk["count"]
        rots = sorted(blk["rotations"])
        title = f"Block #{design_num}: {name}"
        if len(rots) > 1:
            rot_strs = [f"{r * 90}\u00b0" for r in rots]
            title += f" (rotations: {', '.join(rot_strs)})"
        title += f" \u00d7 {count}"

        c.setFont("Helvetica-Bold", 9)
        c.drawString(bm + 5, y, title)
        y -= 14

        block_colors = {}
        for _poly, color_idx in blk["polygons"]:
            if isinstance(color_idx, tuple):
                continue
            block_colors[color_idx] = block_colors.get(color_idx, 0) + 1

        c.setFont("Helvetica", 9)
        for ci in sorted(block_colors.keys()):
            pc = block_colors[ci]
            total = pc * count
            label = _color_label(ci)
            c.drawString(bm + 15, y, f"Color {label}: {pc} per block ({total} total)")
            y -= 12

        y -= 6
        if y < bm + 30:
            c.showPage()
            y = PAGE_H - bm - 20
    return y


def _draw_border_info(
    c,
    params,
    block_w_in,
    block_h_in,
    seam_allowance,  # pylint: disable=too-many-arguments,too-many-positional-arguments
    bm,
    y,
):
    """Draw border strip info within the cutting summary."""
    if not params:
        return y
    border_style = params.get("border_style")
    if not border_style:
        return y

    if y < bm + 80:
        c.showPage()
        y = PAGE_H - bm - 20
    y -= 10
    border_w = min(block_w_in, block_h_in) * 0.75
    rows = params["rows"]
    cols = params.get("cols", rows)
    q_w = block_w_in * cols
    q_h = block_h_in * rows
    c.setFont("Helvetica-Bold", 12)
    c.drawString(bm, y, "Border Strips")
    y -= 18
    c.setFont("Helvetica", 9)
    c.drawString(bm + 5, y, f"Style: {border_style}")
    y -= 14
    c.drawString(
        bm + 5,
        y,
        f'Strip width: {border_w:.2f}" '
        f'(+ {seam_allowance:.2f}" seam allowance each side '
        f'= cut {border_w + 2 * seam_allowance:.2f}" wide)',
    )
    y -= 14
    c.drawString(bm + 5, y, f'2 strips: {q_w:.1f}" long (top/bottom)')
    y -= 14
    c.drawString(
        bm + 5, y, f'2 strips: {q_h + 2 * border_w:.1f}" long (sides, including border corners)'
    )
    return y


def generate_pattern_pdf(
    params,
    output_path,
    quilt_w=96,
    quilt_h=None,  # pylint: disable=too-many-locals
    seam_allowance=0.25,
):
    """Generate a printable PDF pattern from quilt parameters.

    Args:
        params: quilt parameter dict (same format as sampler output)
        output_path: path for the output PDF file
        quilt_w: finished quilt width in inches (default 96)
        quilt_h: finished quilt height in inches (default same as quilt_w)
        seam_allowance: seam allowance in inches (default 0.25)
    """
    if quilt_h is None:
        quilt_h = quilt_w
    rows = params["rows"]
    cols = params.get("cols", rows)
    block_w_in = quilt_w / cols
    block_h_in = quilt_h / rows

    design = _design_for(params)
    grid = design.grid

    # find unique blocks; palette_colors is every fabric they're cut from
    unique_blocks, placements, palette_colors = _extract_unique_blocks(design)
    for i, blk in enumerate(unique_blocks):
        blk["_design_num"] = i + 1

    # Render the quilt image for the cover. delete=False means nothing reclaims
    # it unless we do, and /pattern calls this once per request on a long-lived
    # worker — so it is removed in the finally below.
    quilt_image = _render_quilt_image(design)

    # encode quilt ID for footer
    try:
        qid = encode(params)
    except (ValueError, KeyError):
        qid = ""

    # build PDF
    c = _FooterCanvas(output_path, pagesize=letter, quilt_id=qid)

    try:
        _draw_cover_page(
            c, params, quilt_image, palette_colors, quilt_w, quilt_h, block_w_in, block_h_in
        )

        if params["symmetry"] != "bargello":
            _draw_assembly_page(
                c, placements, unique_blocks, params, quilt_w, quilt_h, block_w_in, block_h_in
            )
            _draw_rotation_summary(c, unique_blocks, palette_colors)

        if params["symmetry"] == "bargello":
            # Primary palette only: bargello cells never use a second palette,
            # and the strip colors index it modulo its own length.
            _draw_bargello_pages(
                c,
                grid,
                _hex_palette(design),
                params,
                quilt_w,
                quilt_h,
                block_w_in,
                block_h_in,
                seam_allowance,
            )
        else:
            for blk in unique_blocks:
                span = blk["span"]
                _draw_block_page(
                    c, blk, palette_colors, block_w_in * span, block_h_in * span, seam_allowance
                )

        if params["symmetry"] != "bargello":
            _draw_cutting_summary(
                c,
                unique_blocks,
                palette_colors,
                grid,
                block_w_in,
                block_h_in,
                seam_allowance,
                params,
            )

        c.save()
    finally:
        try:
            os.unlink(quilt_image)
        except OSError:
            pass
    return output_path


if __name__ == "__main__":
    import sys

    test_params = {
        "seed": 42,
        "rows": 8,
        "cols": 8,
        "symmetry": "rotational",
        "chaos": 0.3,
        "palette": "ocean breeze",
        "n_patterns": 2,
        "n_colors": 4,
        "tile_size": 6,
        "quilt_stitch": "grid",
    }
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/test_pattern.pdf"
    generate_pattern_pdf(test_params, out)
    print(f"Generated: {out}")
