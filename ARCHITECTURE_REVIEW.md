# Quilts — Architectural Review

_Date: 2026-06-01 · Scope: full repository (7.5k LOC Python, excluding venv)_

## Executive summary

This is a healthy, well-tested hobby/research codebase that has clearly earned
its keep — the generative output is good and the active-learning loop works. Tests
are green (420 passing, 25 doctests), pylint is a clean 10.00/10, and the module
boundaries are mostly sensible (rendering, layout, blocks, palettes, sampler,
encoding, PDF, two webapps, static site).

The risks are not "it's broken" — they're **structural drift**: a handful of
god-functions carry the whole system, the same logic is reproduced in two places
that can silently disagree, a meaningful fraction of the code is dead but still
tested (giving false confidence), and the hardest-to-get-right area (PDF seam
geometry) has absorbed a disproportionate amount of bug-fixing churn.

The single highest-leverage theme: **`render_quilt` is the source of truth for
"params → pixels", but three other code paths re-derive pieces of that mapping
independently** (`build_layout`/PDF reconstruction, `quilt_id` encoding, the
sampler feature vector). Every time one drifts from `render_quilt`, you get a
silent inconsistency, not a crash.

Churn evidence: **44 commits** touch PDF/seam/polygon geometry; **31**
`too-many-locals` and **28** `too-many-arguments`/`positional` pylint
suppressions across the repo; the RNG-forking fix was committed twice
identically. These are the fingerprints of where the design fights back.

---

## P0 — Correctness coupling (fix first)

### 1. `render_quilt` and `build_layout` reconstruct the layout independently and can disagree
`render_quilt` (quilt.py:363) builds the grid inline. `build_layout` (quilt.py:295)
is a *second*, partial reimplementation, extracted only so `pattern_pdf.py` could
rebuild the grid for cutting diagrams. They have already diverged:

- `build_layout` hardcodes `n_palettes=1` (quilt.py:324). `render_quilt` passes 2
  when `palette_2` is set (quilt.py:444). → For any two-palette quilt, the PDF's
  per-block cutting diagram is reconstructed from a **different grid** than the
  rendered image.
- `build_layout` has no concept of `tile_size`. `render_quilt` uses
  `_build_tiled_grid` whenever `symmetry == "none"` and a tile size is set
  (quilt.py:429-438). → The **`improv-wonky` preset** (`symmetry: "none"`,
  `tile_size: 6`, generator.py:130) renders a tiled grid in the preview but the
  PDF reconstructs a plain `layout_none` grid. The cover image and the cutting
  pages in the same PDF disagree.
- `build_layout` knows nothing about `plain_frac`, `mega_frac`, `color_gradient`,
  `color_wash`, or `accent_count`, so any of those shift the image away from what
  the pattern claims.

**Impact:** wrong sewing patterns for a subset of designs — the worst kind of bug
for the tool's actual purpose (your mother cuts fabric from these). It cannot be
caught by the current tests because nothing asserts that the reconstructed grid
equals the rendered grid.

**Fix:** make `render_quilt` *call* `build_layout` for the layout/color-map stage
so there is exactly one implementation, then have it apply the post-layout
effects on top. At minimum, add a test that builds a grid both ways for a matrix
of params (including `none+tile`, `palette_2`) and asserts equality.

### 2. The "params → pixels" mapping is implicitly defined by RNG call order
Reproducibility depends on the *exact sequence* of `rng` calls. The code is full
of defensive comments ("Fork a separate RNG … so changing n_colors doesn't shift
the main RNG sequence", quilt.py:375) and the fix "fork color selection RNG so
n_colors doesn't shift layout" was committed **twice, identically** (2264096,
91a3348) — a tell that this is fragile and was hard to land.

Because seeds in `data/ratings.json`, every static-site quilt, and every shared
`quilt_id` are only meaningful relative to today's code structure, **any
reordering of RNG consumption silently invalidates all historical designs.** This
is inherent to seed-based generative art, but right now nothing pins it down:
there is no golden-image / hash test asserting that `seed X → bytes with hash Y`.

**Fix:** add a regression test that renders ~10 fixed param sets and asserts a
stable hash of the PNG bytes. That converts "silent drift" into "a test goes
red", which is exactly what you want guarding a generative core.

---

## P1 — Dead code masquerading as live (kills trust in the tests)

### 3. Five parameters are dead in production but still fully wired and tested
`sash_width`, `cornerstones`, `color_gradient`, `color_wash`, `accent_count` are
accepted by `render_quilt` and exercised by `test_quilt.py` (lines 250-364), but
**no production caller ever sets them non-default**: `render_params.py` (the one
funnel both the sampler and both webapps use) doesn't pass them, the sampler hard-
codes `color_wash=None`/`accent_count=0`, and `quilt_id` V2/V3 dropped them.

This is ~80 lines of `render_quilt` (the gradient, wash, accent, cornerstone, and
sash branches — quilt.py:456-643) plus their interactions with seam-line and
mega-block drawing. The tests passing on these paths is **false confidence**: they
prove dead code still runs, not that the product works.

**Fix:** delete the five params and their branches from `render_quilt`, drop the
dead tests, keep only the `quilt_id` V1 decode bits (frozen, fine). This is the
biggest single readability win available and it shrinks the riskiest function.

### 4. The tiling path is nearly dead too
`_build_tiled_grid` (quilt.py:67) only runs when `symmetry == "none"`. The sampler
**drops `none`** (`_DROP_SYMMETRY`, sampler.py:35), so scoring never tiles. Only
the generator can reach it (via the `none` dropdown / `improv-wonky` preset) — and
that's exactly the path that produces wrong PDFs (finding #1). Either commit to
tiling as a real feature (and fix the PDF path) or retire `symmetry: "none"` from
the generator and delete `_build_tiled_grid`.

---

## P1 — `render_quilt` is a 430-line god-function

`render_quilt` (quilt.py:363-791) takes **24 parameters** and carries four
stacked `# pylint: disable` directives (too-many-arguments, -locals, -branches,
-statements). Inside, the "patches → cairo path" loop is **duplicated four times**
nearly verbatim: regular-cell fill (620-631), mega-block fill (711-722),
regular-cell seam stroke (742-747), mega-block seam stroke (763-768).

This is why every new visual feature (wash, strippy, wonky, palette_2) required
touching the same enormous function and why the pylint suppressions accumulate
rather than resolve — the repo has **31 `too-many-locals`** and **28
arg-count** suppressions, concentrated here and in `pattern_pdf.py`. Silencing the
linter is being used as a substitute for decomposition.

**Fix (incremental, after #3 trims it):**
- Extract `_draw_patches(ctx, patches, ox, oy, sx, sy, palette, color_map, n_colors, fill=True)`
  and call it from all four sites. Removes the duplication and the `isinstance`
  tuple-vs-int color logic lives in one place.
- Extract `_render_cells(...)` and `_render_mega(...)`.
- Group the 24 params into a small `RenderSpec` dataclass (the webapps/sampler
  already build a kwargs dict in `render_params.py` — that's the natural seam).

---

## P2 — Palette / encoding has no single source of truth

Palette identity is a bare string threaded through `palettes.py`, `sampler.py`
(`_DROP_PALETTES`, `PALETTE_NAMES`), `quilt_id.py` (`_V1_PALETTES` 16-frozen,
`_V2_PALETTES` 18-frozen), `render_params.py`, `build_site.py`
(`_ENCODABLE_PALETTES`), and `generator.py`. There is **no check that the names in
these frozen lists still exist in `palettes.py`** — `build_site.py` even
intersects `_V2_PALETTES & renderable` defensively because they're known to drift.

Failure mode is silent: `render_quilt` "silently drops" an unknown `palette_2`
(quilt.py:406-407), `render_params` silently nulls retired palettes, and
`encode()` throws `ValueError` that callers swallow into `qid="unknown"`
(generator.py:259-261). A renamed palette doesn't fail loudly anywhere — it just
quietly changes or drops output.

**Fix:** one module-level test asserting every name in `_V1_PALETTES`,
`_V2_PALETTES`, `_PROVEN_PALETTES`, and `_DROP_PALETTES` is either a current
palette or explicitly marked legacy-decode-only. Cheap, and it turns a class of
silent drift into a red test. Longer term, a `Palette` value object with an
explicit `legacy` flag would centralize this.

---

## P2 — PDF geometry is the proven bug hotspot

`pattern_pdf.py` is the largest module (1396 lines, carries `too-many-lines`) and
the seam-allowance / polygon-offset math accounts for **44 fix commits**:
self-intersecting `path_tile`, duplicate vertices in `drunkards_path` from trig
rounding, SA-offset spikes on curved pieces (multiple attempts), reflex-vertex
detection inversion, non-convex handling, scale-to-fit, label deconfliction, and
the solid/dashed convention swapped twice. `PDF_BUGS.md` documents three audit
rounds over 242 PDFs.

It's *now* at 95% coverage and stable, so this is not urgent — but it's the part
of the system where geometry correctness is genuinely hard, and finding #1 means
it can still be fed an inconsistent grid. Treat it as load-bearing and fragile:
don't refactor it casually, and keep the golden-PDF audit habit when block shapes
change. The `_offset_polygon` SA logic is the specific thing to be most careful
around.

---

## P3 — Smaller notes

- **`import-outside-toplevel` ×10**: deliberate (lazy CLIP/torch import to keep the
  Railway slim build importable). Fine, but worth a one-line comment at each site
  explaining it's intentional rather than a suppression that looks accidental.
- **`generator.py` imports private names** from `quilt_id` (`_V2_PALETTES`,
  `_V2_SYMMETRY`, `_V2_STITCH`). The underscore says "private" but they're public
  API in practice. Promote them to real exported constants.
- **`app.py` runs Flask `debug=True`** (app.py:63) and reads the ratings path from
  `sys.argv[1]` — fine for a local single-user tool, just don't ever expose it.
- **Two near-identical `_render_small`/`_render_png`/`_render_small`** helpers exist
  in sampler.py, generator.py, and app.py, all wrapping `params_to_render_kwargs +
  render_quilt`. Minor, but they could be one helper in `render_params.py`.
- **`stripes` border style** is defined and drawable but excluded from sampling
  (sampler.py:114) — another defined-but-unused branch; decide in or out.

---

## What's working well (keep doing this)

- **Clear module seams**: blocks / layout / palettes / sampler / encoding / PDF /
  webapps are genuinely separable, and `render_params.py` is a good instinct — a
  single funnel so the sampler and both webapps render identically.
- **The active-learning design is sound**: two-stage param-model → CLIP pipeline,
  proven-palette/symmetry exploration carve-outs, per-round tracking. The R17-R21
  tuning churn is *healthy* iteration, not instability — don't mistake it for the
  bug churn.
- **Versioned, forward-compatible `quilt_id`** with frozen schemas and backward
  decode is exactly the right call for shareable IDs.
- **Test discipline is high** for a project this size; the gaps are about *what*
  is asserted (cross-consistency, golden images), not effort.

---

## Recommended order of attack

1. **Golden-render hash test** (P0 #2) — cheap insurance before any refactor.
2. **Grid-equality test** between `render_quilt` and `build_layout` (P0 #1) — will
   immediately go red on `none+tile` and `palette_2`; then fix by unifying.
3. **Delete the 5 dead params + their tests** (P1 #3) — shrinks the god-function
   with zero behavior change, making the rest safer to touch.
4. **Extract `_draw_patches`** and decompose `render_quilt` (P1) — now tractable.
5. **Palette-name consistency test** (P2) — one small test, closes a silent class.
6. Leave `pattern_pdf` alone unless block shapes change; keep the golden-PDF audit.
