# Quilts — Architectural Review (2026-10)

_Date: 2026-10-04 · Scope: full repository (~10k LOC Python incl. tests, plus
templates, justfile, CI, Procfile) · Prior review: [ARCHITECTURE_REVIEW.md](ARCHITECTURE_REVIEW.md) (2026-06-01)_

## Status of the 2026-06 review

The prior review's P0/P1 items are closed: golden-render tripwire
(`test_golden_render.py`), grid unification via `quilt._build_grid` +
`test_layout_consistency.py`, dead-param deletion, palette-consistency tests
(`test_palette_consistency.py`). The two audits (2026-06-22, 2026-07-25)
visibly improved the codebase. This review goes one level deeper into what is
*still* structurally weak.

---

## 1. The core structural problem: "params → design" exists only as an RNG replay

Successor to the old review's #1, still the highest-leverage move.
`render_quilt` (quilt.py:531) *derives* the design (grid, plain cells, mega
blocks, strip sizes, resolved palettes, border/wash colors) interleaved with
painting it, and `pattern_pdf._reconstruct_layout` (pattern_pdf.py:103) replays
a *prefix* of that RNG stream. Everything the replay doesn't cover silently
diverges. The grid itself is now unified and tested, but the divergence has
moved downstream of the grid:

- **Plain cells and mega-blocks are invisible to the PDF.** `render_quilt`
  selects them *after* `_build_grid` (quilt.py:588–607); the PDF never computes
  them. With `plain_frac`/`mega_frac` set (both are public sliders in
  create.html, and `/pattern` accepts them), the assembly diagram, block
  counts, and cutting summary describe a quilt with pieced blocks where the
  image has solid or 2×2-merged cells. Wrong fabric counts.
- **`palette_mix` gives the PDF the wrong colors.** `_pick_palette_colors`
  (pattern_pdf.py:89) replays only the base-palette draw;
  `quilt._resolve_palettes` (quilt.py:495) builds an interleaved hybrid. Grid
  matches, but the color key, swatches, and per-color piece tallies are keyed
  to colors the quilt doesn't use.
- **The PDF cover image is rendered from a hand-picked subset of params**
  (`_render_quilt_image`, pattern_pdf.py:263 — no border_style, plain/mega,
  wonky, strippy, wash, palette_2/mix). Even the picture inside the PDF
  disagrees with the preview it was downloaded from. Five-minute fix: call
  `params_to_render_kwargs(params)` and override `block_size`/`border`/`output`
  — that funnel exists precisely for this.
- Plus the already-known strippy/wonky gaps (STILL OPEN since June).

**Recommendation:** split planning from painting. A
`plan_quilt(params) -> QuiltDesign` that is pure and deterministic — grid,
`plain_cells`, `mega_tl`, strip *fractions*, resolved palettes (hybrid
included), per-cell seeds, border/wash color choices — then
`paint(design, block_size) -> PNG` and `pattern_pdf.render(design, ...)`.
Parity becomes structural instead of test-enforced; `test_layout_consistency`
shrinks to "plan is deterministic"; the 22-param god-function problem and the
old review's `RenderSpec` idea are solved by the same move.

Until then, a cheap honesty fix: have `/pattern` refuse (or stamp a warning
page on) params it can't reconstruct — strippy, wonky, plain_frac, mega_frac,
palette_mix — rather than emitting a confidently wrong pattern.

A wrinkle the IR should fix in passing: `_build_strip_sizes` rounds to *pixels*
(`round(base_size * factor)`, quilt.py:488), so strippy geometry is
block_size-dependent — `/download` at 72px is not a scale-up of the `/render`
preview at 36px, and inch-space PDF reconstruction can never match it exactly.
Store fractions in the design; round only at paint time.

## 2. Correctness: two concurrency holes

- **The block RNG is process-global under a threaded server.** `_block_patches`
  does `random.seed(cell_seed)` and block fns draw from module `random`
  (quilt.py:64–75, blocks.py:24). The Procfile runs gunicorn
  `--workers 1 --threads 2`: two overlapping `/render` requests can interleave
  between the `seed()` and the draws, so a shared quilt ID can render
  differently under load — the one thing a quilt ID must never do. The same
  race exists in the scorer (threaded dev server: `/render` vs. the render
  inside `add_rating`'s CLIP embed, which would poison an embedding). Fix: pass
  an explicit `random.Random(cell_seed)` into block fns (and drop the vestigial
  always-zero `x, y` while changing the signature). This intentionally changes
  golden hashes — regenerate deliberately.
- **`/next` reads the model unlocked while `/rate` retrains.** `_explorer_lock`
  (app.py:44) guards mutations only. `_retrain` swaps `self.vocab` *then* fits
  and swaps models (sampler.py:370–387); a concurrent `suggest_params` can
  encode candidates with the new vocab against the old model →
  feature-dimension `ValueError` on `predict_proba`, a 500 on `/next`. The
  rate-then-next sequence the UI fires makes this a realistic interleaving.
  Either take the lock in `/next`, or build `(vocab, model, clip_model)`
  locally and publish them as one atomic tuple assignment.

## 3. The data layer is the most valuable and least protected part of the project

`data/ratings.json` is ~5,100 hand-ratings — the one artifact in this repo that
cannot be regenerated — and it is gitignored with **no backup mechanism at
all**. A `just backup` (tar to iCloud/Dropbox, or push to a private repo) is
the single best effort-to-value change in this review.

Beyond that:

- **Positional alignment of `ratings[i] ↔ embeddings[i]` is a standing
  liability.** Truncation heuristics and warnings already exist in three places
  (sampler.py:293–302, backfill_embeddings.py:62, build_site.py:131) because
  the invariant has broken before. Give each rating a stable id at creation
  (e.g. `ts` + quilt_id) and key embeddings by it (`.npz` dict or SQLite). The
  heuristics and their edge cases disappear.
- **Rewrite cost per rating:** every click rewrites the full ~10 MB `.npy` plus
  the full JSON. Fine today; append-only JSONL + periodic compaction (and
  append-format embeddings) would be both faster and more crash-tolerant.
  Lower priority than the id change.

## 4. Record the policy, not just the outcome

The R22 post-mortem (quilt_stitch importance was a *time* confound;
`_TRAIN_FROM_ROUND = 14`) shows the real cost of the current design: the
sampling policy — `_DROP_*`, `_PROVEN_*`, the inline probabilities in
`sample_random_params`, `PARAM_SPACE`, the training window — lives as scattered
code constants, so reconstructing "what distribution generated round N" is
archaeology through git and memory notes. Two changes:

1. Collect the policy into one declarative structure (a `SamplerPolicy`
   dict/dataclass in sampler.py).
2. **Snapshot it into `ratings_rounds.json` at `start_round`.** Every future
   confound analysis becomes a join, not a dig, and "policy at R17 vs R22" is
   mechanical. Move `_source` from inside `params` to the rating record at the
   same time (it currently rides along into `encode()` and the feature encoder
   as an ignored passenger).

Also: the walk-forward AUC analysis that justified `_TRAIN_FROM_ROUND` exists
only as a comment table (sampler.py:91–99) with "re-derive this as rounds
accumulate." Codify it — `just eval-model` running the walk-forward loop — so
the per-round checklist can include it instead of trusting a stale constant.

## 5. ML pipeline: question the GB stage, and close the resolution gap

- **The param model may not be earning its complexity.** It's a ~0.60 AUC
  ranker whose sole job is picking which 30 of 200 candidates the CLIP model
  sees — yet it drags along the entire feature-vocab subsystem, which was the
  source of the worst bug in the project's history (the 27% all-zero block).
  The marginal value is cheaply measurable: add a
  `_source="exploit_clip_nofilter"` arm that CLIP-scores 30 *random*
  candidates, interleave it for a round, compare. If the gap is ~0, delete the
  GB stage and the vocab machinery with it.
- **Three different images stand in for "the quilt":** candidates are
  CLIP-scored at block_size=8, training embeddings use 16, and the human rates
  at 40 (sampler.py:109–111, app.py default). CLIP scores different pictures
  than the ones that produced its labels, and both differ from what the user
  judged — seam lines and stitching mostly vanish at 8px. Unify candidate and
  embed size (16 is cheap at n=30), and consider whether 16 is faithful enough
  to the rated 40px image. A plausible contributor to the weak explore/exploit
  gap.
- Smaller: `suggest_params` is pure greedy argmax + ε-uniform explore. Since
  labels are expensive, an occasional uncertainty-sampled candidate (near the
  CLIP model's decision boundary) would buy more model improvement per rating
  than another uniform-random one.

## 6. One spec, three copies: the generator's control surface

Parameter ranges live in three places that must agree by hand: `_PARAM_BOUNDS`
(generator.py:251), the hardcoded slider min/max/step in create.html
(lines 229–294), and the quilt_id quantization steps (quilt_id.py:353–357).
They already disagree benignly (wonky bound 0.1 vs UI max 0.06; wash 0.3 vs
0.2; tile_size 0–12 vs UI 2–10), and the UI steps for strippy/wash happen to
exactly match the V4 quantization — a coincidence nothing enforces; if it
breaks, the share-ID silently reconstructs a slightly different quilt than the
preview. Define one `CONTROLS` spec (id, lo, hi, step, default) in
generator.py, render the sliders from it in the template, and derive
`_PARAM_BOUNDS` from it.

Same disease, smaller case: `quilt.py main()` and `quilt_id._decode_cmd
--command` both expose a CLI frozen at the pre-wonky/strippy/wash param set —
either generate them from the spec or stop claiming CLI coverage of the full
space.

Related hygiene: generator.py imports `_V2_PALETTES`/`_V2_SYMMETRY`/`_V2_STITCH`
— underscore-private names that are load-bearing public API across three
modules. Export them properly (e.g. `ENCODABLE_PALETTES`) from quilt_id.

## 7. Smaller notes

- `define_families` re-derives bucket membership by re-filtering `liked`
  (build_site.py:338–344) instead of `bucket_families` returning indices — a
  latent desync if bucketing ever changes; return indices from one place.
- New-palette workflow has a silent step: a palette added to palettes.py is
  samplable/scorable but won't appear in the generator or encode into IDs until
  appended to `_V2_PALETTES`. The consistency tests check the reverse direction
  only. Add `test_samplable_palettes_are_encodable`
  (`sampler.PALETTE_NAMES ⊆ _V2_PALETTES`) — passes today, catches the
  forgotten append tomorrow.
- `app.py`'s `add_rating` does JSON save → CLIP render+embed → retrain while
  holding the lock; retrain cost grows with history. Fine for now; if rating
  ever feels sluggish, move embed+retrain off the request path (the next
  `/next` doesn't strictly need the model updated by *this* rating).
- `suggest_params` uses an unseeded RNG — fine, but a scoring session is
  unreproducible even in principle; thread a seed through if replaying a round
  against a new policy ever matters.

## Suggested order of attack

1. **`just backup` for `data/`** — an hour, protects the irreplaceable thing.
2. **`/pattern` honesty gate + cover-image fix** via `params_to_render_kwargs`
   — small, closes user-facing wrongness now.
3. **Explicit-RNG block functions** (+ golden regen) and the **`/next` lock** —
   both small correctness fixes.
4. **Policy snapshot in `start_round`** — before R23 generates more
   un-provenanced data.
5. **The `QuiltDesign` plan/paint split** — the big one; do it under the golden
   tripwire, one extraction per commit.
6. **The nofilter A/B and block-size unification** next round; act on the
   result.
