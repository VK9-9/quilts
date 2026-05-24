# Pattern PDF Bugs

Found via batch generation of 42 PDFs with varied params.
Test PDFs saved to `/tmp/quilts_pdf_qa/`.

## 1. Non-square grids crash with `rotational` symmetry (DONE)
**Severity: crash** | Files: `grid_4x8`, `grid_8x4` (not generated)

`layout_rotational()` doesn't fill all cells for non-square grids — it rotates
around center but leaves gaps (e.g. 8 missing cells in a 4x8 grid).
`render_quilt` then hits a `KeyError`. All other symmetry modes handle
non-square grids fine.

## 2. Large pieces overflow across multiple pages (DONE)
**Severity: high** | Files: `00_sym_none.pdf` (pp 5-7), `09_grid_3x3.pdf` (pp 4-5+), `17_patterns_1.pdf` (pp 4-5)

When block size is large (16" or 32"), individual piece diagrams are drawn at
real scale and overflow the page. The half-square triangle at 16" needs ~3
pages. At 32" (3x3 grid), pieces are enormous. The "Individual Pieces" heading
appears on a page with nothing visible, and pieces extend across continuation
pages with no labels or dimensions visible.

## 3. Non-convex pieces have no usable piece diagrams (DONE)
**Severity: medium** | Blocks: `card_trick` (4/5 pieces), `cathedral_windows` (4/10), `path_tile` (1/6), `drunkards_path` (1/2)

Non-convex polygons skip seam allowance entirely (`sa_poly` returns `None`), so
they get a bounding-box SA instead. Combined with issue #2, these large
bounding-box outlines overflow badly — you get pages with just a corner of a
dashed rectangle visible.

## 4. `path_tile` has a self-intersecting (bowtie) polygon (DONE)
**Severity: medium** | Block index 18, piece 1

Polygon `[(0, 38), (0, 62), (62, 100), (38, 100)]` has crossing edges,
producing zero net area. It renders as two overlapping triangles. Bug in the
block pattern definition itself.

## 5. `drunkards_path` has a near-duplicate vertex from floating point (DONE)
**Severity: low** | Block index 20, piece 1

First vertex is `(6.12e-15, 100.0)` (from trig) and last vertex is `(0, 100)`.
Creates a zero-length edge that could confuse dimension labeling.

## 6. Dimension label overlap on dense blocks (DONE)
**Severity: low-medium** | 634 instances across test cases

Blocks with many edges near each other (`applique`, `cherry_blossom`,
`ohio_star`) produce overlapping dimension labels. Edge midpoints within 1.5"
get labels that collide. Most visible at larger block sizes.

## 7. Missing dimension labels on overflow pages (DONE)
**Severity: low** | Visible in `00_sym_none.pdf` p6, `17_patterns_1.pdf` p5

When pieces overflow to continuation pages, dimension labels get clipped at page
edges. The grain arrow and color label may also be off-page.
