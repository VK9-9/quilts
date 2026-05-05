# Quilt Preference Analysis

## How It Works

A Flask webapp (`app.py`) shows quilts one at a time. The user rates each
like/dislike. A `GradientBoostingClassifier` (scikit-learn) learns which
parameter combinations the user prefers and biases future suggestions toward
predicted-good regions.

**Parameter space:** varies by round (see per-round notes for active ranges).

**Exploration/exploitation:** 30% of suggestions are fully random; 70% are
the best of 200 random candidates scored by the model. Model activates after
10 ratings and requires at least one like and one dislike.

**Analysis script:** `python analyze.py [ratings.json]`

---

## Round 1 — ratings 1-200

**Records:** 1-200 (200 ratings)
**Overall:** 42/200 liked (21%)
**Params:** rows/cols 10-24, symmetry 5 modes (none/mirror/rotational/stripe/partial),
chaos 0-0.8, 12 palettes, n_patterns 1-7, n_colors 2-5, no diversity cap

### Key findings

- **n_patterns=1 strongly preferred** — 32% like rate; n_patterns=2 at 19%;
  3+ near zero.
- **Stripe symmetry disliked** — 7% like rate vs 25-26% for none/mirror.
- **n_colors=3 is the sweet spot** — 28% like rate; 4 is worst at 13%.
- **Mid-range grid size** — rows 14-16 best (~30%); <13 and >22 both disliked.
- **Spring garden palette** has highest like rate (38%) but few samples;
  indigo dye at 28% with many samples; autumn harvest and patchwork classic
  at 0%.
- **chaos and tile_variation** show almost no signal (liked/disliked means
  nearly identical at ~0.34 and ~0.18 respectively).

### Problems observed

- **Indigo dye over-exploitation:** 37% of all samples (74/200) vs expected
  ~8% if uniform. Model is stuck in a local optimum.
- **Like rate declining:** peaked at 36% (ratings 26-50), crashed to 4%
  (126-150), recovering to 20% at end.
- **Seed noise ceiling:** the model can predict parameter envelope but not
  visual outcome, which depends heavily on the random seed.

### Palette frequency

| Palette | Shown | Expected | Ratio |
|---------|-------|----------|-------|
| indigo dye | 37.0% | 8.3% | 4.5x |
| farmhouse | 9.0% | 8.3% | 1.1x |
| forest floor | 8.0% | 8.3% | 1.0x |
| spring garden | 4.0% | 8.3% | 0.5x |
| autumn harvest | 2.0% | 8.3% | 0.2x |

### Like rate trend

```
  1- 25: 16%
 26- 50: 36%
 51- 75: 32%
 76-100: 20%
101-125: 32%
126-150:  4%
151-175:  8%
176-200: 20%
```

### Changes after Round 1

- Narrowed: rows 14-22, n_patterns 1-2, n_colors 2-4, chaos 0-1.0
- Added 5 block patterns: star, windmill, diamond_in_square, cross, bow_tie (12 total)
- Added 6 palettes: slate/sage, jewel box, tidal pool, cedar/moss, northern lights, dusty rose (18 total)
- Added flower symmetry mode (center medallion + border)
- Added palette diversity cap (15% max per palette in candidate pool)

---

## Round 2 — ratings 201-507

**Records:** 201-507 (307 ratings)
**Overall:** 61/307 liked (19.9%)
**Params:** rows/cols 14-22, symmetry 6 modes (+flower), chaos 0-1.0,
18 palettes, n_patterns 1-2, n_colors 2-4, 15% palette diversity cap,
12 block patterns

### Key findings

- **n_patterns=2 strongly preferred** — 28% vs 13% for n_patterns=1. Complete
  reversal from round 1 (32% vs 19%). With the narrowed range and 12 blocks,
  two-pattern quilts consistently win.
- **Top palettes (all ~28-32%):** winter sky (32%, 14/44), indigo dye (29%, 17/58),
  wildflower (28%, 11/40), northern lights (28%, 5/18). Winter sky emerged as
  the overall favorite with strong sample size.
- **Dead palettes (0% in 307 ratings):** berry patch (0/10), cedar and moss (0/9),
  dusty rose (0/4), prairie (0/15), slate and sage (0/4), tidal pool (0/8),
  forest floor (0/7). These can be dropped or reworked.
- **n_colors=3 and 4 converging** — 21% vs 23%. Round 1 had 3 dominant; now 4
  is slightly ahead. 2 colors still weakest (14%).
- **none and partial symmetry tied at 24%.** Flower still underperforming (12%,
  6/49) with decent sample now. Mirror weak (17%). Stripe recovered to 21%
  (was 7% in round 1).
- **rows=14 is the sweet spot** — 31% (15/49). Like rate drops for larger grids;
  21 and 22 both at 12-15%.
- **Higher chaos still preferred** — liked mean 0.58 vs disliked 0.53.
- **Lower tile_size preferred** — liked mean 4.1 vs disliked 4.8. Suggests
  smaller tiles or no tiling works better.
- **Diversity cap working** — indigo dye down to 19% of samples (was 37% in
  round 1). Winter sky and wildflower now get fair representation.

### Palette detail

| Palette | Shown | Liked | Rate |
|---------|-------|-------|------|
| winter sky | 44 | 14 | 32% |
| indigo dye | 58 | 17 | 29% |
| wildflower | 40 | 11 | 28% |
| northern lights | 18 | 5 | 28% |
| ocean breeze | 13 | 3 | 23% |
| patchwork classic | 15 | 3 | 20% |
| sunset | 13 | 2 | 15% |
| spring garden | 22 | 3 | 14% |
| autumn harvest | 9 | 1 | 11% |
| farmhouse | 9 | 1 | 11% |
| jewel box | 9 | 1 | 11% |
| berry patch | 10 | 0 | 0% |
| cedar and moss | 9 | 0 | 0% |
| dusty rose | 4 | 0 | 0% |
| forest floor | 7 | 0 | 0% |
| prairie | 15 | 0 | 0% |
| slate and sage | 4 | 0 | 0% |
| tidal pool | 8 | 0 | 0% |

### Like rate trend (round 2 only)

```
201-225: 36%
226-250: 16%
251-275: 12%
276-300: 24%
301-325: 16%
326-350: 20%
351-375: 24%
376-400:  8%
401-425: 16%
426-450: 16%
451-475: 20%
476-500: 32%
501-507: 14%
```

---

## Favorites

Standout quilts worth revisiting or using as seeds for future exploration.

1. **winter sky / high chaos / none** — chaos=0.95, cols=18, n_colors=3,
   n_patterns=2, palette=winter sky, rows=18, symmetry=none, tile_size=0,
   tile_variation=0.3 (Round 2)
