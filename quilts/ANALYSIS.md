# Quilt Preference Analysis

## How It Works

A Flask webapp (`app.py`) shows quilts one at a time. The user rates each
like/dislike. A `GradientBoostingClassifier` (scikit-learn) learns which
parameter combinations the user prefers and biases future suggestions toward
predicted-good regions.

**Parameter space:** rows/cols (10-24), symmetry (5 modes), chaos (0-0.8),
palette (12 options), n_patterns (1-7), n_colors (2-5), tile_size (0-10),
tile_variation (0-0.3), seed (random).

**Exploration/exploitation:** 30% of suggestions are fully random; 70% are
the best of 200 random candidates scored by the model. Model activates after
10 ratings and requires at least one like and one dislike.

**Analysis script:** `python analyze.py [ratings.json]`

---

## Round 1 — 200 ratings

**Overall:** 42/200 liked (21%)

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
