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

### Changes after Round 3

- Dropped 4 dead palettes (frost, midnight garden, sunset, storm from R3) — kept storm as it recovered to 34% in R4
- Added sashing: ~30% chance, 3–8px width, colored strips between blocks
- Added color gradient: ~25% chance, 4 modes (horizontal, vertical, diagonal, radial)
- Removed stripes border style (consistently 0%)

### Changes after Round 4

- Dropped palettes: ember (0%), frost (8%), mosaic (8%)
- Removed stripes border style (from BORDER_STYLES constant)
- Narrowed sash to [5, 8]px only (3/6/7px hurt)
- Removed horizontal and vertical gradient modes (dead or weak)
- Lowered chaos range to 0–0.8
- Added block scale mixing: `mega_frac` (~30% chance, 0.1–0.25 fraction of 2×2 mega-blocks)

---

## Round 4 — ratings 784-1157

**Records:** 784-1157 (374 ratings)
**Overall:** 116/374 liked (31.0%)
**Params:** rows/cols 14-19, symmetry 7 modes, chaos 0-1.0, 18 palettes,
n_patterns 1-2, n_colors 3-4, 15% palette diversity cap, 19 block patterns,
3 border styles (solid/checkerboard/piano_keys, ~25%), sashing (~30%, 3-8px),
color gradient (~25%, 4 modes)

### Key findings

- **Like rate up again** — 31.0% vs 27.9% in Round 3. Trend continues upward.
- **Emergent still top symmetry** — 36% (30/84). None close behind at 35% (18/51).
  Flower continues to underperform at 23% (9/39).
- **n_patterns flipped back to 1** — 34% vs 26% for n_patterns=2. May interact
  with new features (sashing, gradient); simpler quilts win more often.
- **n_colors flipped back to 3** — 36% vs 26% for 4. Clear signal now.
- **Ocean breeze now top palette** — 44% (22/50), up from 38%. Indigo dye
  39% (28/71), wildflower 39% (16/41).
- **Storm recovered strongly** — 34% (13/38), up from 0% in Round 3 (only 2 samples).
- **Dead palettes**: ember (0/9), frost (8%), mosaic (8%), sunset (9%),
  patchwork classic (11%).
- **Solid border jumped to 48%** (13/27) — now best border style.
  Checkerboard still strong at 38%. Piano_keys dropped to 29%. Stripes still 0%.
- **Grid size**: rows=15 new sweet spot at 39% (29/75). 16 dropped to 25%.
- **Chaos signal reversed** — liked mean 0.51 vs disliked 0.54. Lower chaos
  now slightly preferred (opposite of Rounds 1-3).
- **Sashing net negative overall** — 27% with sash vs 33% without. Width matters:
  5px (39%) and 8px (40%) competitive; 3px (12%), 6px (14%), 7px (19%) hurt.
- **Color gradient**: radial is the standout at 35% (44/125, large sample).
  Horizontal dead (0/8), vertical weak (12%). Diagonal neutral (27%).

### Palette detail

| Palette | Shown | Liked | Rate |
|---------|-------|-------|------|
| ocean breeze | 50 | 22 | 44% |
| indigo dye | 71 | 28 | 39% |
| wildflower | 41 | 16 | 39% |
| northern lights | 14 | 5 | 36% |
| storm | 38 | 13 | 34% |
| farmhouse | 9 | 3 | 33% |
| deep sea | 19 | 6 | 32% |
| spring garden | 7 | 2 | 29% |
| winter sky | 15 | 4 | 27% |
| plum and gold | 19 | 5 | 26% |
| midnight garden | 8 | 2 | 25% |
| stained glass | 18 | 4 | 22% |
| autumn harvest | 10 | 2 | 20% |
| patchwork classic | 9 | 1 | 11% |
| sunset | 11 | 1 | 9% |
| frost | 13 | 1 | 8% |
| mosaic | 13 | 1 | 8% |
| ember | 9 | 0 | 0% |

### Border style detail

| Style | Shown | Liked | Rate |
|-------|-------|-------|------|
| solid | 27 | 13 | 48% |
| checkerboard | 39 | 15 | 38% |
| none | 261 | 76 | 29% |
| piano_keys | 42 | 12 | 29% |
| stripes | 5 | 0 | 0% |

### Sashing detail

| Width | Shown | Liked | Rate |
|-------|-------|-------|------|
| 8px | 20 | 8 | 40% |
| 5px | 18 | 7 | 39% |
| 4px | 19 | 6 | 32% |
| none | 270 | 88 | 33% |
| 7px | 16 | 3 | 19% |
| 6px | 14 | 2 | 14% |
| 3px | 17 | 2 | 12% |

### Color gradient detail

| Mode | Shown | Liked | Rate |
|------|-------|-------|------|
| radial | 125 | 44 | 35% |
| diagonal | 11 | 3 | 27% |
| none | 213 | 67 | 31% |
| vertical | 17 | 2 | 12% |
| horizontal | 8 | 0 | 0% |

### Symmetry detail

| Mode | Shown | Liked | Rate |
|------|-------|-------|------|
| emergent | 84 | 30 | 36% |
| none | 51 | 18 | 35% |
| mirror | 46 | 14 | 30% |
| partial | 55 | 16 | 29% |
| rotational | 50 | 15 | 30% |
| stripe | 49 | 14 | 29% |
| flower | 39 | 9 | 23% |

### Like rate trend (round 4 only)

```
784-808:  28%
809-833:  36%
834-858:  24%
859-883:  32%
884-908:  60%
909-933:  32%
934-958:  36%
959-983:  56%
984-1008: 16%
1009-1033: 36%
1034-1058: 24%
1059-1083: 20%
1084-1108: 16%
1109-1133: 28%
1134-1157: 21%
```

---

## Round 5 — ratings 1158-1538

**Records:** 1158-1538 (381 ratings)
**Overall:** 146/381 liked (38.3%)
**Params:** rows/cols 14-19, symmetry 7 modes, chaos 0-0.8, 15 palettes (dropped frost/mosaic/ember),
n_patterns 1-2, n_colors 3-4, 15% palette diversity cap, 3 border styles (solid/checkerboard/piano_keys),
sashing (~30%, 5 or 8px only), color gradient (~25%, diagonal/radial only), mega_frac (~30%, 0.1–0.25)

### Key findings

- **Like rate up to 38.3%** — best round yet. Round 5 param changes working.
- **Rotational symmetry dominant** — 46% (57/124), clear winner this round. Was mediocre in earlier rounds.
  Emergent dropped to 30% (14/47) — underperforming.
- **Deep sea massively over-exploited** — 30.4% of round (116/381) vs expected ~7%. Diversity cap not
  controlling it. Scored 47%, making model heavily prefer it.
- **Top palettes:** northern lights 53% (8/15, small sample), deep sea 47% (54/116), autumn harvest 45%
  (13/29), indigo dye 46% (22/48), wildflower 44% (15/34).
- **Dead palettes:** spring garden 9% (1/11), patchwork classic 12% (1/8), midnight garden 20% (2/10),
  sunset 17% (2/12). Ocean breeze dropped from 44% (R4) to 25% — surprising decline.
- **mega_frac neutral** — flat across all values (37-39%). Adds visual variety without hurting like rate.
- **sash_width=8 hurts badly** — 18% (7/38); sash=5 fine at 42% (28/67); no-sash 40%. Drop 8px.
- **Color gradient declining** — radial slipped to 33% (24/72); diagonal 39% (17/44); none 40%. Both
  modes slightly below baseline.
- **Border styles all neutral** — checkerboard 40%, solid 40%, piano_keys 37%, none 37%. No signal.
- **Chaos**: liked mean 0.49 vs disliked 0.43 — moderate chaos still preferred.
- **Grid size**: rows 14 and 16 best at 44%; 17-19 range 33-36%.

### Palette detail

| Palette | Shown | Liked | Rate |
|---------|-------|-------|------|
| northern lights | 15 | 8 | 53% |
| deep sea | 116 | 54 | 47% |
| indigo dye | 48 | 22 | 46% |
| autumn harvest | 29 | 13 | 45% |
| wildflower | 34 | 15 | 44% |
| storm | 17 | 6 | 35% |
| plum and gold | 13 | 4 | 31% |
| farmhouse | 10 | 3 | 30% |
| stained glass | 11 | 3 | 27% |
| winter sky | 11 | 3 | 27% |
| ocean breeze | 36 | 9 | 25% |
| midnight garden | 10 | 2 | 20% |
| sunset | 12 | 2 | 17% |
| patchwork classic | 8 | 1 | 12% |
| spring garden | 11 | 1 | 9% |

### Symmetry detail

| Mode | Shown | Liked | Rate |
|------|-------|-------|------|
| rotational | 124 | 57 | 46% |
| stripe | 38 | 15 | 39% |
| mirror | 59 | 22 | 37% |
| none | 52 | 18 | 35% |
| partial | 41 | 15 | 37% |
| emergent | 47 | 14 | 30% |
| flower | 20 | 5 | 25% |

### New params detail

| mega_frac | Shown | Liked | Rate |
|-----------|-------|-------|------|
| 0.0 (none) | 216 | 84 | 39% |
| ~0.1 | 52 | 19 | 37% |
| ~0.2 | 113 | 43 | 38% |

| sash_width | Shown | Liked | Rate |
|------------|-------|-------|------|
| 5px | 67 | 28 | 42% |
| none | 276 | 111 | 40% |
| 8px | 38 | 7 | 18% |

| color_gradient | Shown | Liked | Rate |
|----------------|-------|-------|------|
| none | 265 | 105 | 40% |
| diagonal | 44 | 17 | 39% |
| radial | 72 | 24 | 33% |

### Like rate trend (round 5 only)

```
1158-1182: 64%
1183-1207: 24%
1208-1232: 68%
1233-1257: 40%
1258-1282: 36%
1283-1307: 48%
1308-1332: 40%
1333-1357: 32%
1358-1382:  8%
1383-1407: 40%
1408-1432: 24%
1433-1457: 24%
1458-1482: 24%
1483-1507: 48%
1508-1532: 56%
1533-1538: 33%
```

### Changes after Round 5

- Dropped palettes: spring garden (9%), patchwork classic (12%), sunset (17%), midnight garden (20%)
- Drop sash_width=8 (18%); keep only 5px
- Tighten palette diversity cap (deep sea at 30.4%, cap not working)
- Consider dropping emergent symmetry (30%) and flower (25%)
- Color gradient marginal — consider dropping radial; keep only diagonal or remove entirely

---

## Round 6 — ratings 1539-1914

**Records:** 1539-1914 (376 ratings)
**Overall:** 95/376 liked (25.3%)
**Params:** rows/cols 14-19, symmetry 5 modes (none/mirror/rotational/stripe/partial),
chaos 0-0.8, 11 palettes, n_patterns 1-2, n_colors 3-4, 10% palette diversity cap,
3 border styles (solid/checkerboard/piano_keys, ~25%), sash (~30%, 5px only),
color gradient (~25%, diagonal only), mega_frac (~30%, 0.1–0.25),
plain_frac (~30%, 0.1–0.4), cornerstones (~50% when sash active)

### Key findings

- **Like rate dropped to 25.3%** — down from 38.3% in Round 5. Two new params
  (cornerstones, plain_frac) expanded the search space, temporarily disrupting the
  model's exploitation signal. Model needs more data to learn the new param effects.
- **Trend: strong start, weak finish** — opened at 40%+ for first 5 windows, then
  collapsed to 8-12% in the final stretch. Classic over-exploitation crash pattern.
- **Wildflower top palette** — 36% (21/59). Deep sea 33% (33/101), ocean breeze 26%,
  indigo dye 25%. All holding well.
- **Bottom 4 palettes weak all round:** farmhouse 9% (1/11), autumn harvest 6% (1/16),
  stained glass 6% (1/17), plum and gold 6% (1/18). Drop all four.
- **Sash strongly negative** — 0px = 28%, 5px = 17%. Even the 5px "good" width from
  R5 is now a negative. Cut sash probability sharply.
- **Cornerstones neutral** — True=27%, False=24%. Slight positive edge, keep as-is.
- **mega_frac positive signal** — off=22%, on=30%. Clear positive now after R5's flat
  signal. Keep at current probability.
- **plain_frac positive** — off=22%, on=29%. New param validated in first round.
- **Diagonal gradient weak** — 21% vs none=27%. Not earning its keep. Drop entirely.

### Palette detail

| Palette | Shown | Liked | Rate |
|---------|-------|-------|------|
| wildflower | 59 | 21 | 36% |
| deep sea | 101 | 33 | 33% |
| ocean breeze | 42 | 11 | 26% |
| indigo dye | 48 | 12 | 25% |
| storm | 34 | 8 | 24% |
| northern lights | 20 | 4 | 20% |
| winter sky | 10 | 2 | 20% |
| farmhouse | 11 | 1 | 9% |
| autumn harvest | 16 | 1 | 6% |
| stained glass | 17 | 1 | 6% |
| plum and gold | 18 | 1 | 6% |

### Symmetry detail

| Mode | Shown | Liked | Rate |
|------|-------|-------|------|
| rotational | 119 | 37 | 31% |
| stripe | 77 | 19 | 25% |
| none | 53 | 14 | 26% |
| mirror | 64 | 13 | 20% |
| partial | 63 | 12 | 19% |

### New params detail

| sash_width | Shown | Liked | Rate |
|------------|-------|-------|------|
| 0px (none) | 274 | 78 | 28% |
| 5px | 102 | 17 | 17% |

| cornerstones | Shown | Liked | Rate |
|------------|-------|-------|------|
| True | 164 | 45 | 27% |
| False | 212 | 50 | 24% |

| mega_frac | Shown | Liked | Rate |
|-----------|-------|-------|------|
| 0.0 (off) | 218 | 48 | 22% |
| >0.0 (on) | 158 | 47 | 30% |

| plain_frac | Shown | Liked | Rate |
|------------|-------|-------|------|
| 0.0 (off) | 207 | 46 | 22% |
| >0.0 (on) | 169 | 49 | 29% |

| color_gradient | Shown | Liked | Rate |
|----------------|-------|-------|------|
| none | 273 | 73 | 27% |
| diagonal | 103 | 22 | 21% |

### Like rate trend (round 6 only)

```
1539-1563: 44%
1564-1588: 40%
1589-1613: 36%
1614-1638: 32%
1639-1663: 36%
1664-1688: 24%
1689-1713: 24%
1714-1738: 16%
1739-1763: 36%
1764-1788:  8%
1789-1813: 28%
1814-1838: 12%
1839-1863:  8%
1864-1888: 20%
1889-1914: 14%
```

### Changes after Round 6

- Dropped palettes: farmhouse (9%), autumn harvest (6%), stained glass (6%),
  plum and gold (6%) — 7 palettes remain
- Cut sash probability: 30% → 10% (5px clearly a negative this round)
- Dropped color_gradient entirely — diagonal at 21% vs 27% baseline, no longer worth the noise

---

## Favorites

Standout quilts worth revisiting or using as seeds for future exploration.

1. **winter sky / high chaos / none** — chaos=0.95, cols=18, n_colors=3,
   n_patterns=2, palette=winter sky, rows=18, symmetry=none, tile_size=0,
   tile_variation=0.3 (Round 2)
2. **ocean breeze / piano keys / partial** — border_style=piano_keys, chaos=0.74,
   cols=17, n_colors=4, n_patterns=1, palette=ocean breeze, rows=17,
   symmetry=partial, tile_size=0, tile_variation=0.07 (Round 3)
