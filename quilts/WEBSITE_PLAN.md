# Quilt Gallery — Website Design

## Goal

A static website where my mom can browse curated generative quilts organized
into "families" of related designs, and optionally score them.

---

## Repository

Stay on the `expand_quilting` branch of `generative_art` during development.
When ready to ship, migrate to a dedicated repo:

```bash
git remote add gallery https://github.com/karld/quilt-gallery.git
git push gallery expand_quilting:main
```

The new repo can be deployed to GitHub Pages for free. The ML/training work
stays in `generative_art`.

---

## Site Structure

```
/ (index)
  16–20 family cards, each showing:
    - Representative thumbnail
    - Family name (e.g. "Indigo Dye / Rotational")
    - Like rate from training data (optional)

/family/<slug>/
  16–20 variation thumbnails for that family
  Each links to its quilt detail page

/quilt/<quilt-id>/
  Full-size image
  Compact ID displayed (e.g. 3xKm7pRt2nWqA)
  Human-readable param summary
  Optional: like/dislike button (see Scoring)
```

---

## Compact Quilt ID

Each quilt has a 13-character base58 ID that fully encodes its parameters
(see `quilt_id.py`). The ID is self-contained — no database lookup needed
to reproduce the image. Displayed on each quilt page so interesting designs
can be shared by ID.

Example: `3xKm7pRt2nWqA`

---

## Defining Families

1. Take all liked quilts from `ratings.json`
2. Compute feature vectors (`params_to_features` from `sampler.py`)
3. K-means cluster into 16–20 groups
4. Each cluster = one family:
   - **Representative**: highest-liked quilt nearest the centroid
   - **Name**: dominant palette + symmetry mode (e.g. "Ocean Breeze / Mirror")
   - **Variations**: 16–20 new quilts sampled near the cluster centroid
     (hold palette/symmetry fixed, randomize other params)

Script: `quilts/build_site.py` (to be written)

---

## Build Process

```bash
python quilts/build_site.py \
    --ratings quilts/ratings.json \
    --out docs/          # GitHub Pages serves from docs/
    --families 18 \
    --variations 20
```

Steps:
1. Cluster liked quilts → define families
2. Generate variation quilts for each family (PNG, ~400×400px for thumbnails,
   ~800×800px for detail pages)
3. Render HTML from Jinja2 templates
4. Write everything to `docs/`
5. `git push` → GitHub Pages auto-deploys

---

## Scoring (optional, later)

Use [Formspree](https://formspree.io) (free tier, no server needed):
- Each quilt page has a ❤ / ✗ form
- Hidden field carries the quilt ID
- Submission POSTs to Formspree → emails a CSV row
- No Railway, no server, no DB

Alternative: skip scoring entirely and just let her email favorites.

---

## Tech Stack

| Concern | Choice |
|---|---|
| Hosting | GitHub Pages (free, `docs/` branch) |
| HTML generation | Python + Jinja2 |
| Image format | PNG (pre-generated at build time) |
| Scoring | Formspree (optional) or email |
| Dynamic generation | Not needed — all images pre-generated |

---

## Open Questions

- How many families / variations? Start with 18 × 18 = 324 quilts.
- Family naming: auto-generated from dominant params, or hand-curated?
- Should the site show param details, or keep it simple (just images + ID)?
- Scoring: does she want to rate, or just browse and email favorites?
