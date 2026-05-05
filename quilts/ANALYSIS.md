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

### Changes after Round 2

- Replaced 7 dead palettes (berry patch, cedar/moss, dusty rose, forest floor,
  prairie, slate/sage, tidal pool) with: midnight garden, stained glass, frost,
  deep sea, plum and gold, storm, mosaic, ember (18 total)
- Narrowed: rows 14-19, n_colors 3-4
- Added 5 block patterns: ohio_star, courthouse_steps, checkerboard_4x4,
  card_trick, double_pinwheel (17 total)
- Added 2 emergent blocks: diagonal, path_tile (19 total)
- Added emergent symmetry mode (coordinated rotations for macro patterns:
  zigzag, diamond, barn_raising, pinwheel_macro)
- Added decorative border styles: solid, stripes, checkerboard, piano_keys
  (~25% chance of appearing)

---

## Round 3 — ratings 508-783

**Records:** 508-783 (276 ratings)
**Overall:** 77/276 liked (27.9%)
**Params:** rows/cols 14-19, symmetry 7 modes (+emergent), chaos 0-1.0,
18 palettes (8 new replacements), n_patterns 1-2, n_colors 3-4,
15% palette diversity cap, 19 block patterns, 4 border styles (~25%)

### Key findings

- **Like rate up significantly** — 27.9% vs 19.9% in Round 2. Narrowed params
  and new features are working.
- **Emergent layout validated** — 31% like rate (24/78), most-sampled mode.
  Coordinated rotations creating macro patterns resonate.
- **Mirror top symmetry at 34%** (12/35) but fewer samples than emergent.
- **n_patterns converged** — 1 and 2 nearly identical (29% vs 27%). No longer
  a differentiator.
- **n_colors converged** — 3 and 4 nearly identical (27% vs 28%).
- **Top palettes:** indigo dye (38%, 23/61), ocean breeze (38%, 13/34),
  wildflower (36%, 13/36). Ocean breeze rose from 23% in Round 2.
- **Dead palettes:** frost (0/6), midnight garden (0/6), sunset (0/6),
  storm (0/2). Frost and midnight garden are new additions that failed.
- **Borders are a net positive** — checkerboard (34%, 11/32) and piano_keys
  (35%, 7/20) both beat no-border (27%, 51/187). Stripes weakest (15%, 2/13).
- **Grid 16-17 sweet spot** — 32-33% like rate. 18 drops to 20%.
- **Higher chaos still preferred** — liked mean 0.58 vs disliked 0.53.
- **Indigo dye still over-exploited** — 22% of samples (61/276) vs expected
  ~6% uniform. Model keeps favoring it despite diversity cap.

### Palette detail

| Palette | Shown | Liked | Rate |
|---------|-------|-------|------|
| indigo dye | 61 | 23 | 38% |
| ocean breeze | 34 | 13 | 38% |
| wildflower | 36 | 13 | 36% |
| deep sea | 17 | 5 | 29% |
| ember | 8 | 2 | 25% |
| farmhouse | 8 | 2 | 25% |
| spring garden | 12 | 3 | 25% |
| flower | 20 | 5 | 25% |
| northern lights | 17 | 4 | 24% |
| winter sky | 21 | 5 | 24% |
| patchwork classic | 10 | 2 | 20% |
| stained glass | 10 | 2 | 20% |
| plum and gold | 7 | 1 | 14% |
| mosaic | 7 | 1 | 14% |
| autumn harvest | 8 | 1 | 12% |
| frost | 6 | 0 | 0% |
| midnight garden | 6 | 0 | 0% |
| sunset | 6 | 0 | 0% |
| storm | 2 | 0 | 0% |

### Border style detail

| Style | Shown | Liked | Rate |
|-------|-------|-------|------|
| piano_keys | 20 | 7 | 35% |
| checkerboard | 32 | 11 | 34% |
| none | 187 | 51 | 27% |
| solid | 24 | 6 | 25% |
| stripes | 13 | 2 | 15% |

### Symmetry detail

| Mode | Shown | Liked | Rate |
|------|-------|-------|------|
| mirror | 35 | 12 | 34% |
| emergent | 78 | 24 | 31% |
| partial | 45 | 13 | 29% |
| stripe | 24 | 6 | 25% |
| flower | 20 | 5 | 25% |
| none | 33 | 8 | 24% |
| rotational | 41 | 9 | 22% |

### Like rate trend (round 3 only)

```
508-532: 24%
533-557: 36%
558-582: 36%
583-607: 16%
608-632: 32%
633-657: 36%
658-682: 20%
683-707: 20%
708-732: 32%
733-757: 32%
758-783: 28%
```

---

## Favorites

Standout quilts worth revisiting or using as seeds for future exploration.

1. **winter sky / high chaos / none** — chaos=0.95, cols=18, n_colors=3,
   n_patterns=2, palette=winter sky, rows=18, symmetry=none, tile_size=0,
   tile_variation=0.3 (Round 2)
2. **ocean breeze / piano keys / partial** — border_style=piano_keys, chaos=0.74,
   cols=17, n_colors=4, n_patterns=1, palette=ocean breeze, rows=17,
   symmetry=partial, tile_size=0, tile_variation=0.07 (Round 3)
