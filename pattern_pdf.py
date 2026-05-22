"""Generate printable PDF sewing patterns from quilt designs.

Takes quilt parameters (same dict as sampler/render) and produces a
multi-page PDF with cover, assembly diagram, and per-block cutting patterns.
"""
import math
import random
import tempfile

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas as rl_canvas

from blocks import BLOCK_PATTERNS
from layout import SYMMETRY_MODES
from palettes import PALETTES, hex_to_rgb
from quilt import render_quilt

# Page layout constants
PAGE_W, PAGE_H = letter  # 8.5 x 11 inches in points
MARGIN = 0.5 * inch
PRINTABLE_W = PAGE_W - 2 * MARGIN
PRINTABLE_H = PAGE_H - 2 * MARGIN


def _color_label(index):
    """Map color index to letter: 0->'A', 1->'B', etc."""
    return chr(ord('A') + index)


_COLOR_NAMES = {
    # rough mapping from hue/saturation/lightness to human names
    # populated lazily by _human_color_name
}


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


def _pick_palette_colors(palette_name, max_colors, rng):
    """Resolve palette name to list of hex colors, sampled to max_colors."""
    for name, colors in PALETTES:
        if name == palette_name:
            if max_colors and max_colors < len(colors):
                return rng.sample(colors, max_colors)
            return list(colors)
    return ["#000000", "#FFFFFF", "#FF0000", "#0000FF"]


def _reconstruct_layout(params):  # pylint: disable=too-many-locals
    """Rebuild the layout grid and block info from quilt params.

    Returns (grid, allowed_patterns, palette_colors, n_colors)
    where grid is {(r,c): cell_dict} matching what render_quilt builds.
    """
    seed = params["seed"]
    rows = params["rows"]
    cols = params.get("cols", rows)
    symmetry = params["symmetry"]
    chaos = params.get("chaos", 0.3)
    max_patterns = params.get("n_patterns", 2)
    max_colors = params.get("n_colors", 4)
    palette_name = params["palette"]

    rng = random.Random(seed)

    palette_colors = _pick_palette_colors(palette_name, max_colors, rng)
    n_colors = len(palette_colors)

    n_all_patterns = len(BLOCK_PATTERNS)
    available = list(range(n_all_patterns))
    rng.shuffle(available)
    allowed = sorted(available[:max_patterns])
    n_patterns = max_patterns

    # symmetry modes bypass tiling
    n_palettes = 1
    layout_fn = SYMMETRY_MODES[symmetry]
    kwargs = {}
    if symmetry == "partial":
        kwargs["chaos"] = chaos
    grid = layout_fn(rows, cols, n_patterns, n_palettes, rng, **kwargs)

    # remap pattern indices to allowed block functions
    for cell in grid.values():
        cell["pattern"] = allowed[cell["pattern"]]

    # build color_map per cell (same logic as render_quilt)
    for cell in grid.values():
        cell_rng = random.Random(cell["pattern"] * 1000 + cell["palette"])
        indices = list(range(n_colors))
        cell_rng.shuffle(indices)
        cell["color_map"] = indices

    # bargello override
    if symmetry == "bargello":
        for cell in grid.values():
            bi = cell.get("_bargello_color", 0) % n_colors
            cell["color_map"] = [bi] * n_colors

    return grid, allowed, palette_colors


def _extract_unique_blocks(grid, n_colors):
    """Find unique (pattern_index, rotation) combos in the grid.

    Returns list of dicts:
        {"pattern_idx": int, "rotation": int, "count": int,
         "polygons": [(polygon, color_idx), ...]}
    """
    seen = {}
    for cell in grid.values():
        key = (cell["pattern"], cell["rotation"])
        if key in seen:
            seen[key]["count"] += 1
        else:
            pat_fn = BLOCK_PATTERNS[cell["pattern"]]
            polygons = pat_fn(0, 0, 100, n_colors)  # generate at size=100
            # apply rotation
            rotated = _rotate_polygons(polygons, cell["rotation"], 100)
            seen[key] = {
                "pattern_idx": cell["pattern"],
                "pattern_name": pat_fn.__name__,
                "rotation": cell["rotation"],
                "count": 1,
                "polygons": rotated,
            }
    return sorted(seen.values(), key=lambda b: (-b["count"], b["pattern_idx"]))


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


def _render_quilt_image(params):
    """Render the quilt to a temp PNG file, return the path."""
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)  # pylint: disable=consider-using-with
    tmp.close()
    render_quilt(
        seed=params["seed"],
        rows=params["rows"],
        cols=params.get("cols", params["rows"]),
        symmetry=params["symmetry"],
        chaos=params.get("chaos", 0.3),
        palette_name=params["palette"],
        max_patterns=params.get("n_patterns", 2),
        max_colors=params.get("n_colors", 4),
        tile_size=params.get("tile_size", 6),
        block_size=40,
        output=tmp.name,
        border=0,
        quilt_stitch=params.get("quilt_stitch"),
    )
    return tmp.name


def _draw_cover_page(c, params, quilt_image_path, palette_colors,  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
                     quilt_size_in, block_size_in):
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
    c.drawImage(quilt_image_path, img_x, img_y, img_size, img_size,
                preserveAspectRatio=True)

    # Dimensions info
    y = img_y - 25
    c.setFont("Helvetica", 11)
    info_lines = [
        f"Finished size: {quilt_size_in:.0f}\" x {quilt_size_in:.0f}\""
        f"  ({quilt_size_in/12:.1f}' x {quilt_size_in/12:.1f}')",
        f"Grid: {rows} rows x {cols} columns",
        f"Block size: {block_size_in:.2f}\" x {block_size_in:.2f}\"",
        "Seam allowance: added to all pieces (shown dashed)",
    ]
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


def _draw_assembly_page(c, grid, unique_blocks, params,  # pylint: disable=too-many-locals
                        _quilt_size_in, _block_size_in):
    """Draw assembly diagram showing block placement in the grid."""
    rows = params["rows"]
    cols = params.get("cols", rows)

    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(PAGE_W / 2, PAGE_H - MARGIN - 25, "Assembly Diagram")

    # build a label map: (pattern_idx, rotation) -> design number
    design_map = {}
    for i, blk in enumerate(unique_blocks):
        design_map[(blk["pattern_idx"], blk["rotation"])] = i + 1

    # fit grid into printable area
    max_cell = min(PRINTABLE_W / cols, (PRINTABLE_H - 50) / rows)
    cell_size = min(max_cell, 0.6 * inch)
    grid_w = cols * cell_size
    grid_h = rows * cell_size
    ox = (PAGE_W - grid_w) / 2
    oy = PAGE_H - MARGIN - 55 - grid_h

    # light colors for each design number
    design_colors = [
        (0.85, 0.92, 1.0), (1.0, 0.90, 0.85), (0.85, 1.0, 0.88),
        (1.0, 1.0, 0.85), (0.93, 0.85, 1.0), (0.85, 1.0, 1.0),
        (1.0, 0.85, 0.93), (0.95, 0.95, 0.85), (0.88, 0.92, 0.96),
        (0.96, 0.88, 0.92),
    ]

    c.setFont("Helvetica", max(5, min(8, cell_size / 3)))
    for r in range(rows):
        for col in range(cols):
            cell = grid.get((r, col))
            if not cell:
                continue
            x = ox + col * cell_size
            y = oy + (rows - 1 - r) * cell_size

            key = (cell["pattern"], cell["rotation"])
            design_num = design_map.get(key, 0)

            # fill
            dc = design_colors[(design_num - 1) % len(design_colors)]
            c.setFillColorRGB(*dc)
            c.setStrokeColorRGB(0.5, 0.5, 0.5)
            c.rect(x, y, cell_size, cell_size, fill=1, stroke=1)

            # label
            c.setFillColorRGB(0, 0, 0)
            rot_label = ["", "↻90", "↻180", "↻270"][cell["rotation"]]
            label = f"#{design_num}"
            c.drawCentredString(x + cell_size / 2, y + cell_size / 2 + 2, label)
            if rot_label:
                c.setFont("Helvetica", max(4, min(6, cell_size / 4)))
                c.drawCentredString(x + cell_size / 2, y + cell_size / 2 - 8, rot_label)
                c.setFont("Helvetica", max(5, min(8, cell_size / 3)))

    # legend below grid
    y = oy - 25
    c.setFont("Helvetica", 9)
    for i, blk in enumerate(unique_blocks):
        design_num = i + 1
        name = blk["pattern_name"].replace("_", " ")
        rot = blk["rotation"] * 90
        count = blk["count"]
        line = f"#{design_num}: {name}"
        if rot > 0:
            line += f" (rotated {rot}\u00b0)"
        line += f" \u2014 {count} block{'s' if count != 1 else ''}"
        c.drawString(MARGIN + 20, y, line)
        y -= 14

    c.showPage()


def _draw_block_page(c, block, palette_colors, block_size_in, seam_allowance):  # pylint: disable=too-many-locals,too-many-statements
    """Draw one block's pattern page with assembled view and individual pieces."""
    design_num = block["_design_num"]
    name = block["pattern_name"].replace("_", " ")
    rot = block["rotation"] * 90

    # Header
    c.setFont("Helvetica-Bold", 14)
    title = f"Block #{design_num}: {name}"
    if rot > 0:
        title += f" (rotated {rot}\u00b0)"
    c.drawString(MARGIN, PAGE_H - MARGIN - 20, title)

    c.setFont("Helvetica", 10)
    c.drawString(MARGIN, PAGE_H - MARGIN - 36,
                 f"Finished size: {block_size_in:.2f}\" x {block_size_in:.2f}\""
                 f"  |  Count: {block['count']} blocks")

    # Draw assembled block (colored) in top portion
    polygons = block["polygons"]
    pattern_size = 100  # polygons generated at size=100

    # scale to fit ~3 inches on page
    assembled_display = 3.0 * inch
    scale = assembled_display / pattern_size
    ax = MARGIN + 20
    ay = PAGE_H - MARGIN - 55 - assembled_display

    c.setStrokeColorRGB(0.3, 0.3, 0.3)
    c.setLineWidth(0.5)
    for poly, color_idx in polygons:
        if isinstance(color_idx, tuple):
            r, g, b = color_idx
        else:
            hex_color = palette_colors[color_idx % len(palette_colors)]
            r, g, b = hex_to_rgb(hex_color)

        path = c.beginPath()
        pts = [(ax + px * scale, ay + assembled_display - py * scale)
               for px, py in poly]
        path.moveTo(*pts[0])
        for pt in pts[1:]:
            path.lineTo(*pt)
        path.close()

        c.setFillColorRGB(r, g, b)
        c.drawPath(path, fill=1, stroke=1)

        # color label in center of piece
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        label = _color_label(color_idx) if not isinstance(color_idx, tuple) else "?"
        c.setFillColorRGB(1, 1, 1)
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(cx, cy - 3, label)

    # Draw individual pieces below
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 11)
    pieces_y = ay - 30
    c.drawString(MARGIN, pieces_y, "Individual Pieces (with seam allowance)")

    pieces_y -= 15
    c.setFont("Helvetica", 9)
    c.drawString(MARGIN, pieces_y,
                 f"Solid line = finished size  |  "
                 f"Dashed line = cutting line (+{seam_allowance:.2f}\")")

    # Scale pieces to real inches, fit on remaining page space
    pieces_y -= 20

    # target: draw each piece at 1:1 if possible
    real_scale = block_size_in * inch / pattern_size  # points per pattern unit
    # check if pieces fit at 1:1
    if block_size_in * inch > PRINTABLE_W * 0.45:
        # scale down to fit
        real_scale = PRINTABLE_W * 0.45 / pattern_size

    # lay out pieces in a grid
    piece_margin = 15
    col_x = MARGIN + 10
    cur_y = pieces_y

    for poly, color_idx in polygons:
        # compute bounding box
        xs = [px for px, py in poly]
        ys = [py for px, py in poly]
        pw = (max(xs) - min(xs)) * real_scale + seam_allowance * 2 * inch
        ph = (max(ys) - min(ys)) * real_scale + seam_allowance * 2 * inch

        # check if we need to wrap to next row
        if col_x + pw + piece_margin > PAGE_W - MARGIN:
            col_x = MARGIN + 10
            cur_y -= ph + piece_margin + 20

        if cur_y - ph < MARGIN:
            c.showPage()
            cur_y = PAGE_H - MARGIN - 30
            col_x = MARGIN + 10
            c.setFont("Helvetica-Bold", 11)
            c.drawString(MARGIN, PAGE_H - MARGIN - 15,
                         f"Block #{design_num}: {name} (continued)")

        # offset so piece starts at origin
        ox = min(xs)
        oy = min(ys)

        # draw finished size (solid)
        c.setStrokeColorRGB(0, 0, 0)
        c.setLineWidth(0.8)
        c.setDash([])
        path = c.beginPath()
        pts = [(col_x + (px - ox) * real_scale + seam_allowance * inch,
                cur_y - (py - oy) * real_scale - seam_allowance * inch)
               for px, py in poly]
        path.moveTo(*pts[0])
        for pt in pts[1:]:
            path.lineTo(*pt)
        path.close()
        c.drawPath(path, fill=0, stroke=1)

        # draw seam allowance (dashed)
        sa_poly = _offset_polygon(poly, seam_allowance * pattern_size / block_size_in)
        c.setDash([3, 3])
        c.setLineWidth(0.5)
        c.setStrokeColorRGB(0.5, 0.5, 0.5)
        path_sa = c.beginPath()
        sa_pts = [(col_x + (px - ox) * real_scale + seam_allowance * inch,
                   cur_y - (py - oy) * real_scale - seam_allowance * inch)
                  for px, py in sa_poly]
        if sa_pts:
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
        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(cx, cy - 3, label)

        # dimension label
        piece_w_in = (max(xs) - min(xs)) / pattern_size * block_size_in
        piece_h_in = (max(ys) - min(ys)) / pattern_size * block_size_in
        c.setFont("Helvetica", 7)
        c.drawCentredString(cx, cy - 14,
                            f"{piece_w_in:.2f}\" x {piece_h_in:.2f}\"")

        col_x += pw + piece_margin

    c.showPage()


def _offset_polygon(polygon, offset):  # pylint: disable=too-many-locals
    """Offset polygon edges outward by offset amount (simple approach).

    For each edge, shift it outward by offset along its normal.
    Then find intersections of adjacent shifted edges.
    """
    n = len(polygon)
    if n < 3:
        return polygon

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
        # outward normal (assuming clockwise winding)
        nx, ny = dy / length, -dx / length
        edges.append((
            x1 + nx * offset, y1 + ny * offset,
            x2 + nx * offset, y2 + ny * offset,
            nx, ny,
        ))

    # find intersection of adjacent shifted edges
    result = []
    for i in range(n):
        e1 = edges[i]
        e2 = edges[(i + 1) % n]
        pt = _line_intersection(e1[0], e1[1], e1[2], e1[3],
                                e2[0], e2[1], e2[2], e2[3])
        if pt:
            result.append(pt)
        else:
            result.append((e1[2], e1[3]))

    return result


def _line_intersection(x1, y1, x2, y2, x3, y3, x4, y4):  # pylint: disable=too-many-arguments,too-many-positional-arguments
    """Find intersection of line (x1,y1)-(x2,y2) with (x3,y3)-(x4,y4)."""
    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(denom) < 1e-10:
        return None
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
    return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))


def generate_pattern_pdf(params, output_path, quilt_size=96,  # pylint: disable=too-many-locals
                         seam_allowance=0.25):
    """Generate a printable PDF pattern from quilt parameters.

    Args:
        params: quilt parameter dict (same format as sampler output)
        output_path: path for the output PDF file
        quilt_size: finished quilt size in inches (default 96 = 8 feet)
        seam_allowance: seam allowance in inches (default 0.25)
    """
    rows = params["rows"]
    cols = params.get("cols", rows)
    block_size_in = quilt_size / max(rows, cols)

    # reconstruct layout
    grid, _allowed, palette_colors = _reconstruct_layout(params)
    n_colors = len(palette_colors)

    # find unique blocks
    unique_blocks = _extract_unique_blocks(grid, n_colors)
    for i, blk in enumerate(unique_blocks):
        blk["_design_num"] = i + 1

    # render quilt image for cover
    quilt_image = _render_quilt_image(params)

    # build PDF
    c = rl_canvas.Canvas(output_path, pagesize=letter)

    _draw_cover_page(c, params, quilt_image, palette_colors,
                     quilt_size, block_size_in)

    _draw_assembly_page(c, grid, unique_blocks, params,
                        quilt_size, block_size_in)

    for blk in unique_blocks:
        _draw_block_page(c, blk, palette_colors, block_size_in,
                         seam_allowance)

    c.save()
    return output_path


if __name__ == "__main__":
    import sys
    test_params = {
        "seed": 42, "rows": 8, "cols": 8, "symmetry": "rotational",
        "chaos": 0.3, "palette": "ocean breeze", "n_patterns": 2,
        "n_colors": 4, "tile_size": 6, "quilt_stitch": "grid",
    }
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/test_pattern.pdf"
    generate_pattern_pdf(test_params, out)
    print(f"Generated: {out}")
