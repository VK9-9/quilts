# Pattern PDF Export — Implementation Plan

## Goal
Generate printable PDF sewing patterns from any quilt design, enabling
quilters to physically construct the quilt with real fabric.

## Reference Quilts
Five test quilts in /tmp/ for iterative feedback:
1. `ref1_rotational.png` — rotational / ocean breeze / 8x8 grid
2. `ref2_partial.png` — partial / lavender fields / 10x10 grid
3. `ref3_bargello.png` — bargello / wisteria / 12x12 (special case: solid color cells)
4. `ref4_columns.png` — columns / tide pool / 10x10
5. `ref5_border.png` — stripe / cherry blossom / 8x8 with solid border

## PDF Structure (per quilt)

### Page 1: Cover
- Full-color rendered quilt image (embedded PNG)
- Title: quilt_id or custom name
- Overall dimensions (e.g. "96 x 96 inches / 8 x 8 feet")
- Block size in inches
- Grid: rows x cols
- Color legend: swatch + hex + human-readable name for each color label (A, B, C, D...)
- Seam allowance note

### Page 2: Assembly Diagram
- Grid showing block placement
- Each cell labeled with block design number + rotation indicator
- Color-coded by block design for quick reference
- Border treatment noted if applicable

### Pages 3+: Block Pattern Pages (one per unique block design)
- Block design name (e.g. "Block #1: Half Square Triangle")
- Full block shown assembled, with color fills and labels
- Each piece drawn individually:
  - 1:1 scale if fits on 8.5x11 (with 0.5" page margins)
  - Scaled down with noted scale factor if too large
  - Finished size line (solid)
  - Seam allowance line (dashed, default 0.25")
  - Color label on each piece (A, B, C, etc.)
  - Dimensions in inches on key edges
  - Grain line arrow (lengthwise, parallel to longest straight edge)
- Piece inventory table: color, shape description, cut count for this block

### Final Page: Cutting Summary
- Total pieces per color across all blocks
- Fabric yardage estimate (future enhancement)

## Architecture

### New module: `pattern_pdf.py`
Depends on `reportlab` (add to requirements.txt).

### Key functions:

```
generate_pattern_pdf(params, output_path, quilt_size=96, seam_allowance=0.25)
    Main entry point. params dict (same as sampler/render).

_reconstruct_layout(params) -> grid, block_fns, palette_colors
    Rebuild layout grid and map pattern indices to block functions.
    Reuses layout.py SYMMETRY_MODES and blocks.py BLOCK_PATTERNS.

_extract_unique_blocks(grid, block_fns, n_colors) -> list[BlockDesign]
    Identify unique (pattern_fn, rotation) combos.
    For each, call pattern_fn(0, 0, size, n_colors) to get polygons.
    Apply rotation transform. Deduplicate.

_polygon_with_seam_allowance(polygon, allowance) -> polygon
    Offset each edge outward by allowance amount.
    Works for both straight-edge and curved (many-point) polygons.

_fit_to_page(pieces, page_w, page_h, margin) -> scale, positions
    Arrange pieces on page. Scale down if needed to fit.

_draw_cover_page(canvas, params, quilt_image_path, palette_colors)
_draw_assembly_page(canvas, grid, unique_blocks)
_draw_block_page(canvas, block_design, palette_colors, seam_allowance)
_draw_cutting_summary(canvas, all_blocks, grid)

_grain_line_direction(polygon) -> (dx, dy)
    Find longest straight edge, grain arrow parallel to it.

_color_label(index) -> str
    Map color index to letter: 0->"A", 1->"B", etc.

_human_color_name(hex_color) -> str
    Map hex to nearest human-readable name (e.g. "#1B3A5C" -> "dark navy").
    Simple lookup table or nearest-match from a small dictionary.
```

### Rendering the quilt image for cover page
- Call render_quilt() to a temp PNG, embed in PDF.

### Handling special cases
- **Bargello**: solid-color cells, no block pattern. Pattern page shows
  simple rectangles with color assignments per row.
- **Strippy**: blocks are rectangular, not square. Piece dimensions
  reflect the actual cell width x height.
- **Wonky**: ignore for PDF patterns (wonky is a rendering effect,
  not a construction technique). Use clean geometry.
- **Borders**: document border strip dimensions separately.
- **Sash**: if sash_width > 0, document sash strip dimensions.

### Rotation handling
Block patterns are generated at rotation=0. For rotated cells, we
rotate all polygon vertices by 90*rotation degrees around block center.
Different rotations of the same pattern produce different cut pieces
only if the pattern is asymmetric.

## Implementation Phases

### Phase 1: Core infrastructure
- [ ] Install reportlab, add to requirements.txt
- [ ] Create pattern_pdf.py skeleton with generate_pattern_pdf()
- [ ] Implement _reconstruct_layout() — rebuild grid from params
- [ ] Implement _extract_unique_blocks() — deduplicate designs
- [ ] Generate first PDF: cover page only (embedded quilt image)
- [ ] Test with ref1 (rotational)

### Phase 2: Block pattern pages
- [ ] Draw assembled block with color fills
- [ ] Draw individual pieces with dimensions
- [ ] Add seam allowance outlines (dashed)
- [ ] Add color labels (A, B, C, D)
- [ ] Add grain line arrows
- [ ] Page fitting / scaling logic
- [ ] Test with ref1-ref4

### Phase 3: Assembly + special cases
- [ ] Assembly diagram page
- [ ] Bargello handling (ref3)
- [ ] Border documentation (ref5)
- [ ] Cutting summary page
- [ ] Test with all 5 refs

### Phase 4: Polish
- [ ] Human-readable color names
- [ ] Piece inventory tables
- [ ] Edge dimension labels on pieces
- [ ] Page headers/footers with quilt_id
- [ ] User feedback iteration

## Page Layout Constants
- Page size: 8.5 x 11 inches (letter)
- Margins: 0.5 inches all sides
- Printable area: 7.5 x 10 inches
- Default seam allowance: 0.25 inches (configurable)
- Default quilt size: 96 inches (8 feet, configurable)
