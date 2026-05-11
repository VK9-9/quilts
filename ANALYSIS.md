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

## Round 7 — ratings 1915-1945

**Records:** 1915-1945 (31 ratings)
**Overall:** Transitional round — CLIP model deployed mid-round, too few ratings
for standalone analysis. Folded into R8 evaluation baseline.

### Changes after Round 7

- Added CLIP visual model: two-stage pipeline (param GBC → CLIP LogisticRegression)
- Backfilled 1914 CLIP embeddings from existing ratings
- Dropped 4 palettes: farmhouse, autumn harvest, stained glass, plum and gold
- Added palette: midnight moss — 7 palettes remain
- Reduced CLIP top-N from 20 → 10 for speed

---

## Round 8 — ratings 1946-2145

**Records:** 1946-2145 (200 ratings)
**Overall:** 102/200 liked (51.0%)
**Params:** rows/cols 14-19, symmetry 5 modes (none/mirror/rotational/stripe/partial),
chaos 0-0.8, 7 palettes, n_patterns 1-2, n_colors 3-4, 10% palette diversity cap,
3 border styles (solid/checkerboard/piano_keys, ~25%), sash (~10%, 5px),
mega_frac (~30%, 0.1-0.25), plain_frac (~30%, 0.1-0.4), quilt_stitch (~30%),
wash_alpha (~15%), palette_2 (~15%)
**New:** CLIP visual model active (two-stage pipeline)

### Key findings

- **Like rate jumped to 51.0%** — best round by far. Previous best was R5 at 38.3%.
  CLIP visual re-ranking is clearly helping: the param model proposes candidates,
  CLIP filters out the ones that don't look good regardless of parameters.
- **n_patterns=1 strongly preferred again** — 59% vs 36%. Consistent with R1/R4/R6.
- **n_colors converged** — 3 and 4 identical at 51%. No signal.
- **Partial symmetry top** at 60%, rotational 55%, stripe 52%, none 50%. Mirror
  weak at 36% — consider dropping.
- **Wildflower dominates** — 67% (35/52), over-exploited at 26% of samples.
  Indigo dye 61%, ocean breeze 57%. Top 3 all strong.
- **Storm collapsed** — 14% (1/7). Northern lights weak at 31%.
  Midnight moss (new) at 17% — not earning its keep.
- **rows=15 sweet spot** — 69%. rows=14 worst at 32%.
- **Sash still negative** — 9% (1/11) vs 53% without. Drop entirely.
- **quilt_stitch huge positive** — 62% with vs 9% without. 157/200 had it active
  (model heavily exploiting). Suspiciously strong signal — may be confounded with
  CLIP preference for texture detail.
- **wash_alpha slight positive** — 57% vs 50%. Keep as-is.
- **mega_frac flipped negative** — 44% vs 55%. Was positive in R6, now hurting.
- **palette_2 slightly negative** — 42% vs 53%.
- **Trend stable** — no late-round crash. Dipped to 32-40% at end but didn't
  collapse like R6.

### Palette detail

| Palette | Shown | Liked | Rate |
|---------|-------|-------|------|
| wildflower | 52 | 35 | 67% |
| indigo dye | 44 | 27 | 61% |
| ocean breeze | 35 | 20 | 57% |
| deep sea | 28 | 11 | 39% |
| northern lights | 16 | 5 | 31% |
| midnight moss | 18 | 3 | 17% |
| storm | 7 | 1 | 14% |

### Symmetry detail

| Mode | Shown | Liked | Rate |
|------|-------|-------|------|
| partial | 35 | 21 | 60% |
| rotational | 49 | 27 | 55% |
| stripe | 42 | 22 | 52% |
| none | 38 | 19 | 50% |
| mirror | 36 | 13 | 36% |

### Feature params detail

| Param | On | Off |
|-------|----|-----|
| quilt_stitch | 98/157 (62%) | 4/43 (9%) |
| wash_alpha | 20/35 (57%) | 82/165 (50%) |
| plain_frac | 37/70 (53%) | 65/130 (50%) |
| cornerstones | 46/89 (52%) | 56/111 (50%) |
| mega_frac | 33/75 (44%) | 69/125 (55%) |
| palette_2 | 14/33 (42%) | 88/167 (53%) |
| sash_width | 1/11 (9%) | 101/189 (53%) |

### Border style detail

| Style | Shown | Liked | Rate |
|-------|-------|-------|------|
| checkerboard | 18 | 10 | 56% |
| solid | 20 | 11 | 55% |
| none | 149 | 75 | 50% |
| piano_keys | 13 | 6 | 46% |

### Grid size detail

| Rows | Shown | Liked | Rate |
|------|-------|-------|------|
| 15 | 39 | 27 | 69% |
| 18 | 34 | 20 | 59% |
| 17 | 29 | 15 | 52% |
| 19 | 43 | 19 | 44% |
| 16 | 33 | 14 | 42% |
| 14 | 22 | 7 | 32% |

### Like rate trend (round 8 only)

```
1946-1970: 40%
1971-1995: 60%
1996-2020: 56%
2021-2045: 64%
2046-2070: 64%
2071-2095: 52%
2096-2120: 32%
2121-2145: 40%
```

### Palette frequency

(expected ~14% each for 7 palettes)

| Palette | Frequency |
|---------|-----------|
| wildflower | 26.0% |
| indigo dye | 22.0% |
| ocean breeze | 17.5% |
| deep sea | 14.0% |
| midnight moss | 9.0% |
| northern lights | 8.0% |
| storm | 3.5% |

### Changes after Round 8

- Drop sash entirely (9% like rate, consistently negative since R6)
- Drop storm (14%) and midnight moss (17%) — 5 palettes remain
- Cut palette_2 probability: 15% → 5% (42% vs 53% baseline)
- Cut mega_frac probability: 30% → 15% (44% vs 55% baseline)
- Drop mirror symmetry (36%, consistently weakest) — 4 modes remain
- Narrow rows to 15-19 (rows=14 at 32%, consistently weak)

---

## Round 9 — ratings 2146-2445

**Records:** 2146-2445 (300 ratings)
**Overall:** 139/300 liked (46%)

Transitional round — applied R8 changes (dropped sash, storm, midnight moss,
mirror symmetry; cut palette_2 and mega_frac probabilities). Like rate dipped
from R8's 51% likely due to search space adjustment. No standalone detailed
analysis was performed; changes carried forward into R10.

---

## Round 10 — ratings 2446-2659

**Records:** 2446-2659 (214 ratings)
**Overall:** 133/214 liked (62%)

Best approval rate yet. Applied color_wash (40%), dropped more weak palettes
(terracotta, slate and rust, coral reef, autumn harvest), added new palettes
(tide pool, lavender fields, aurora), implemented cherry blossom block with
hardcoded RGB colors, changed accent squares to same-palette.

---

## Round 11 — ratings 2660-2973

**Records:** 2660-2973 (314 ratings)
**Overall:** 190/314 liked (61%)

Sustained high approval. Added sashiko_wave and sashiko_asanoha stitch styles.

### Feature importances (top 10)

| Feature          | Importance |
|------------------|----------:|
| quilt_stitch     |    0.4980 |
| chaos            |    0.0696 |
| tile_variation   |    0.0496 |
| pal_ocean breeze |    0.0472 |
| tile_size        |    0.0345 |
| mega_frac        |    0.0342 |
| n_patterns       |    0.0296 |
| color_wash       |    0.0293 |
| pal_deep sea     |    0.0262 |
| pal_wildflower   |    0.0238 |

### Stitching is #1 feature (0.50 importance)

- `diagonal` clear winner at **80%** approval
- `grid`, `crosshatch`, `sashiko_asanoha` all solid ~61%
- `sashiko_wave` slightly lower at 57%
- No stitch: **40%** — quilts without stitching significantly less liked

### Palette detail

| Palette | Shown | Liked | Rate |
|---------|-------|-------|------|
| ocean breeze | 101 | 75 | 74% |
| tide pool | 54 | 37 | 69% |
| wildflower | 46 | 27 | 59% |
| lavender fields | 21 | 12 | 57% |
| cherry blossom | 9 | 5 | 56% |
| northern lights | 10 | 5 | 50% |
| indigo dye | 23 | 11 | 48% |
| deep sea | 26 | 10 | 38% |
| aurora | 24 | 8 | 33% |

### Symmetry detail

| Mode | Shown | Liked | Rate |
|------|-------|-------|------|
| stripe | 116 | 74 | 64% |
| rotational | 95 | 60 | 63% |
| partial | 103 | 56 | 54% |

### Stitch detail

| Style | Shown | Liked | Rate |
|-------|-------|-------|------|
| diagonal | 49 | 39 | 80% |
| crosshatch | 58 | 36 | 62% |
| grid | 66 | 40 | 61% |
| sashiko_asanoha | 41 | 25 | 61% |
| sashiko_wave | 60 | 34 | 57% |
| None | 40 | 16 | 40% |

### Other signals

- Color wash: 64% with vs 52% without
- Cornerstones: slight negative (57% with vs 63% without)
- Checkerboard border: 71% (best border style)
- Tile size 5-7: 72-76%; tile size 1-2: 29-33%
- Ocean breeze overrepresented at 32% of samples

### Changes after Round 11

- Quilt stitch probability: 65% → 80%
- Diagonal stitch gets 2x weight vs others
- Dropped palettes: aurora (33%), deep sea (38%)
- Added 6 palettes: copper canyon, winter frost, sage garden, plum wine, coastal fog, amber glow
- Tile size minimum: 0 → 2
- Implemented appliqué block (circle + leaf shapes via many-sided polygons)

---

## Round 12 — ratings 2974-3229

**Records:** 2974-3229 (256 ratings)
**Overall:** 164/256 liked (64.1%)
**Params:** rows/cols 15-19, symmetry 3 modes (rotational/partial/stripe),
chaos 0-0.8, 13 palettes (6 new from R11), n_patterns 2, n_colors 3-4,
10% palette diversity cap, quilt_stitch (~80%, diagonal 2x weight),
color_wash (~40%), mega_frac (~15%), plain_frac (~30%), appliqué block

### Key findings

- **Like rate holds at 64.1%** — on par with R10 (62%) and R11 (61%). System
  is in a stable high-approval regime. No late-round crash.
- **Lavender fields breakout palette** — 88% (30/34). Best single-palette
  performance in the entire history. Wildflower 77%, copper canyon 71%,
  tide pool 70%. All 6 new R11 palettes are performing.
- **Bottom palettes:** amber glow 33% (2/6), sage garden 40% (2/5),
  cherry blossom 40% (2/5), indigo dye 43% (3/7). Small samples but
  amber glow and sage garden trending weak.
- **Ocean breeze still over-exploited** — 33.2% of samples (85/256) vs expected
  ~8%. Like rate 60%, so model is correct to favor it, but diversity suffers.
- **n_colors=4 now preferred** — 69% vs 58% for 3. Strongest signal in several
  rounds.
- **Larger grids preferred** — rows=18 at 76%, rows=19 at 68%. Smaller grids
  (15-17) all 56-63%. Shift from earlier rounds where 15 was the sweet spot.
- **Rotational symmetry top** — 70% vs partial 62%, stripe 58%. Consistent
  with recent trend.
- **Solid border strong** — 79% (19/24). Checkerboard 69%. Piano_keys dropped
  to 60% (only 5 samples). No-border baseline 62%.
- **Stitch styles converging** — grid (70%), diagonal (69%), sashiko_wave (67%)
  all close. Crosshatch weakest at 57%. No stitch still 33%. Diagonal's
  dominance from R11 (80%) has narrowed.
- **Color wash slightly negative** — 61% with vs 71% without. Reversed from
  R11 where wash was positive. May be noise or interaction effect.
- **mega_frac neutral** — 62% on vs 64% off. No signal.
- **cornerstones slightly negative** — 61% vs 67%. Consistent weak negative
  from R11.
- **quilt_stitch still #1 feature** — 0.57 importance, dominating the param
  model. Chaos (0.06) and tile_variation (0.05) distant second/third.

### Palette detail

| Palette | Shown | Liked | Rate |
|---------|-------|-------|------|
| lavender fields | 34 | 30 | 88% |
| wildflower | 13 | 10 | 77% |
| copper canyon | 7 | 5 | 71% |
| tide pool | 20 | 14 | 70% |
| winter frost | 43 | 28 | 65% |
| ocean breeze | 85 | 51 | 60% |
| plum wine | 12 | 7 | 58% |
| coastal fog | 11 | 6 | 55% |
| northern lights | 8 | 4 | 50% |
| indigo dye | 7 | 3 | 43% |
| sage garden | 5 | 2 | 40% |
| cherry blossom | 5 | 2 | 40% |
| amber glow | 6 | 2 | 33% |

### Symmetry detail

| Mode | Shown | Liked | Rate |
|------|-------|-------|------|
| rotational | 106 | 74 | 70% |
| partial | 66 | 41 | 62% |
| stripe | 84 | 49 | 58% |

### Stitch detail

| Style | Shown | Liked | Rate |
|-------|-------|-------|------|
| grid | 47 | 33 | 70% |
| diagonal | 81 | 56 | 69% |
| sashiko_wave | 36 | 24 | 67% |
| sashiko_asanoha | 31 | 19 | 61% |
| crosshatch | 49 | 28 | 57% |
| None | 12 | 4 | 33% |

### Feature params detail

| Param | On | Off |
|-------|----|-----|
| color_wash | 107/176 (61%) | 57/80 (71%) |
| palette_2 | 8/12 (67%) | 156/244 (64%) |
| plain_frac | 63/95 (66%) | 101/161 (63%) |
| mega_frac | 23/37 (62%) | 141/219 (64%) |
| cornerstones | 79/129 (61%) | 85/127 (67%) |

### Border style detail

| Style | Shown | Liked | Rate |
|-------|-------|-------|------|
| solid | 24 | 19 | 79% |
| checkerboard | 26 | 18 | 69% |
| none | 201 | 124 | 62% |
| piano_keys | 5 | 3 | 60% |

### Like rate trend (round 12 only)

```
2974-2998: 48%
2999-3023: 88%
3024-3048: 76%
3049-3073: 88%
3074-3098: 68%
3099-3123: 64%
3124-3148: 40%
3149-3173: 56%
3174-3198: 60%
3199-3223: 56%
3224-3229: 50%
```

### Palette frequency

(expected ~8% each for 13 palettes)

| Palette | Frequency |
|---------|-----------|
| ocean breeze | 33.2% |
| winter frost | 16.8% |
| lavender fields | 13.3% |
| tide pool | 7.8% |
| wildflower | 5.1% |
| plum wine | 4.7% |
| coastal fog | 4.3% |
| northern lights | 3.1% |
| copper canyon | 2.7% |
| indigo dye | 2.7% |
| amber glow | 2.3% |
| sage garden | 2.0% |
| cherry blossom | 2.0% |

### Feature importances (top 15)

| Feature | Importance |
|---------|----------:|
| quilt_stitch | 0.5698 |
| chaos | 0.0639 |
| tile_variation | 0.0472 |
| tile_size | 0.0407 |
| pal_ocean breeze | 0.0324 |
| mega_frac | 0.0290 |
| n_patterns | 0.0257 |
| rows | 0.0207 |
| accent_count | 0.0183 |
| n_colors | 0.0175 |
| color_wash | 0.0171 |
| pal_lavender fields | 0.0164 |
| plain_frac | 0.0164 |
| pal_wildflower | 0.0154 |
| pal_indigo dye | 0.0136 |

### Changes after Round 12

- Dropped palettes: amber glow (33%), sage garden (40%) — 16 palettes remain
- Added 5 palettes: twilight, sea glass, moonstone, wisteria, honey oak
- Widened rows/cols range: 15-19 → 16-21
- Weighted n_colors: 70% toward 4, 30% toward 3
- Reduced color_wash probability: 40% → 30%
- Deprioritized cornerstones: 50% → 30%
- Equalized stitch weights; halved crosshatch (57%)
- Increased border probability: 25% → 35%
- Implemented cathedral_windows block (folded circles with diamond reveals)

---

## Favorites

Standout quilts worth revisiting or using as seeds for future exploration.

1. **winter sky / high chaos / none** — chaos=0.95, cols=18, n_colors=3,
   n_patterns=2, palette=winter sky, rows=18, symmetry=none, tile_size=0,
   tile_variation=0.3 (Round 2)
2. **ocean breeze / piano keys / partial** — border_style=piano_keys, chaos=0.74,
   cols=17, n_colors=4, n_patterns=1, palette=ocean breeze, rows=17,
   symmetry=partial, tile_size=0, tile_variation=0.07 (Round 3)
