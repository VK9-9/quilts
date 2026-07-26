# Pattern PDF Bugs

---

# Round 1

Found via batch generation of 42 PDFs with varied params.

## 1. Non-square grids crash with `rotational` symmetry (DONE)
**Severity: crash**

`layout_rotational()` doesn't fill all cells for non-square grids — it rotates
around center but leaves gaps. Fix: defensive gap-fill with random cells.

## 2. Large pieces overflow across multiple pages (DONE)
**Severity: high**

Piece diagrams drawn at real scale overflow the page for large blocks (16"+).
Fix: scale down iteratively until all pieces fit on one page.

## 3. Non-convex pieces have no usable piece diagrams (DONE)
**Severity: medium** | Blocks: `card_trick`, `cathedral_windows`, `path_tile`, `drunkards_path`

Non-convex polygons skipped seam allowance entirely. Fix: removed the
`_is_convex` bail-out — the offset math works fine for our 90-degree concavities.

## 4. `path_tile` has a self-intersecting (bowtie) polygon (DONE)
**Severity: medium** | Block index 18, piece 1

Vertex winding order was wrong, creating a bowtie with zero area.
Fix: swapped last two vertices.

## 5. `drunkards_path` has a near-duplicate vertex from floating point (DONE)
**Severity: low** | Block index 20, piece 1

`cos(pi/2)` produced `6.12e-15` instead of `0`. Fix: use exact start/end
points for the arc, only use trig for intermediate segments.

## 6. Dimension label overlap on dense blocks (DONE)
**Severity: low-medium** | 634 instances across test cases

Fix: spatial deconfliction — skip labels whose position is within 12pt of an
already-placed label.

## 7. Missing dimension labels on overflow pages (DONE)
**Severity: low**

Resolved as side-effect of fixes #2 (pieces fit on page) and #6 (label spacing).

---

# Round 2

Generated 97 PDFs (94 succeeded, 3 failed on dropped palette name in test
script). Test PDFs in `/tmp/quilts_pdf_qa_r2/`.

## Summary

**All Round 1 bugs confirmed fixed.** Structural analysis of 75 param sets found:
- Zero zero-area polygons (was 8 in R1)
- Zero duplicate vertices (was 6 in R1)
- Zero short edges (was 6 in R1)
- Zero layout crashes
- 123 "SA area smaller than piece" on non-convex blocks — **false positive**,
  this is expected geometry at concave vertices (offset converges inward)

## Visual audit

Spot-checked PDFs with non-convex blocks:
- **card_trick** (p12 of `034_nonconvex_s757`): L-shaped pieces have proper SA
  outlines with correct notching at inner corners. Dimensions readable.
- **drunkards_path** (p9 of `031_nonconvex_s454`): Curved SA outlines follow
  the arc beautifully. Height label placed correctly.
- **path_tile** (p8 of `031_nonconvex_s454`): Formerly-bowtie piece now renders
  as proper trapezoid with correct SA. All 6 pieces fit on one page.

## No new bugs found

---

# Round 3

Generated 100 fully randomized PDFs (new seeds 10000–99999, all symmetry modes,
grid sizes 3–12, random wonky/strippy/border/stitch combos). Test PDFs in
`/tmp/quilts_pdf_qa_r3/`.

## Summary

**100/100 succeeded, 0 failures.** Structural analysis found:
- Zero zero-area polygons
- Zero duplicate vertices
- Zero SA failures
- 16 short-edge warnings on `cathedral_windows` (0.082" edges inherent to block
  geometry — not a bug)

## No new bugs found
