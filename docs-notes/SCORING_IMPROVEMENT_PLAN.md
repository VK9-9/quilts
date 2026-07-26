# Scoring Improvement Plan

## Problem Statement

With fixed parameters (symmetry, palette, stitch, chaos, etc.), changing only
the seed can take a quilt from hated to loved. The seed controls which block
patterns land in which cells, diagonal directions, color shuffling, and other
compositional details. But the seed is just a hash input — the param-based
model (GradientBoosting) literally cannot learn anything from it.

This means the param model has a hard ceiling: it can find good parameter
neighborhoods (e.g. "bargello + lavender fields + grid stitch") but cannot
distinguish good vs bad quilts *within* that neighborhood. The remaining
variance is entirely visual and seed-driven.

## Baseline (pre-R17)

| Metric | R14 | R15 | R16 |
|--------|-----|-----|-----|
| Overall like rate | 85.4% | 81.2% | 80.0% |
| CLIP top-N | 10 | 10 | 10 |
| Exploitation fraction | — | — | ~70% |
| Bargello like rate | — | — | 96% |

## Changes Made

### 1. CLIP candidate pool: 10 -> 30 (done)

**Commit**: `sampler: increase CLIP candidate pool from 10 to 30`

The CLIP visual model now sees 30 param-filtered candidates instead of 10.
At block_size=8 (~128px), the extra 20 renders add ~50ms; the CLIP forward
passes add ~1-2s total. Negligible impact on batch generation time.

**Rationale**: The param model gets candidates into the right neighborhood.
Within that neighborhood, seed variance dominates. Giving CLIP 3x more
candidates to visually rank increases the chance of finding a great seed.

### 2. Block pattern determinism fixes (done)

**Commits**:
- `blocks: make half_square_triangle deterministic` — was using unseeded
  `random.randint()`; now uses `hash((x, y)) % 2`
- `blocks: seed cherry_blossom RNG from position` — was using unseeded
  `random.Random()`; now seeded with `hash((x, y))`

These fix a reproducibility bug where the same quilt ID could produce different
images on different runs. Not directly a scoring improvement, but ensures that
when CLIP picks a good-looking quilt, it stays good-looking when rendered at
full resolution.

## Metrics to Track (R17 vs R16)

### Primary metrics

- **Overall like rate**: R16 was 80%. Higher = better.
- **Exploitation like rate**: The purest signal. These are quilts where the
  sampler is trying its hardest. If CLIP is picking better seeds, this should
  improve even though the param model hasn't changed.
- **Exploration vs exploitation gap**: If CLIP is doing its job, the gap
  between random exploration quilts and CLIP-selected exploitation quilts
  should widen.

### Secondary metrics

- **Per-symmetry like rates**: Has the improvement been uniform, or does CLIP
  help more with certain symmetry modes?
- **Per-palette like rates**: Same question for palettes.
- **Visual inspection**: Do exploitation quilts subjectively feel better?
  Fewer "right params, ugly arrangement" duds?

### Confounding factors

- R17 also includes the block determinism fixes, so we can't cleanly attribute
  improvement to CLIP alone. Both changes are improvements though.
- The param model retrains each round, so it may independently improve.
- Rating mood/fatigue varies between sessions.

## Future Steps (in priority order)

### Next: Analyze visual features on existing ratings
Extract simple image stats (color entropy, contrast, spatial balance) from
liked vs disliked quilts across all rounds. This tells us:
- Whether "good seeds" share measurable visual properties
- Whether cheap heuristics could pre-filter before CLIP
- Whether the visual signal is learnable at all without CLIP

### Then: Shift weight from params to CLIP
Use the param model as a coarse accept/reject filter (threshold on param
score) rather than top-N ranking. Let CLIP rank all accepted candidates.
This prevents the param model from over-constraining when it's converged.

### Then: Cheap visual pre-filters (if analysis supports it)
Before CLIP, compute quick image statistics to reject obviously bad quilts:
color entropy, contrast ratio, spatial balance, edge density. Only worth
building if the visual feature analysis shows these correlate with preference.

### Later: Increase candidate pool further
If 30 helps, try 50 or 100. The render cost is trivial; the CLIP embedding
cost scales linearly but may still be acceptable.
