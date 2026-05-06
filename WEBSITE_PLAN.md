# Quilt Gallery — Website Design

## Goal

A static website where my mom can browse curated generative quilts organized
into "families" of related designs.

---

## Repository

Live at `VK9-9/quilts`, deployed via GitHub Pages from `docs/`.
Training/scoring work happens in the same repo.

---

## Site Structure

```
/ (index)
  16–20 family cards, each showing:
    - Representative thumbnail
    - Family name (e.g. "Deep Sea / Rotational")

/family/<slug>/
  16–20 variation thumbnails for that family
  Each links to its quilt detail page

/quilt/<quilt-id>/
  Full-size image
  Compact ID displayed (e.g. 3xKm7pRt2nWqA)
    - Hovering the ID shows a tooltip with the param summary
  No scoring buttons
```

---

## Compact Quilt ID

Each quilt has a 13-character base58 ID that fully encodes its parameters
(see `quilt_id.py`). The ID is self-contained — no database lookup needed
to reproduce the image. Displayed on each quilt page so interesting designs
can be shared by ID.

Example: `3xKm7pRt2nWqA`

### CLI tool (`quilt_id.py`)

```bash
# Decode an ID → params
python quilt_id.py decode 3xKm7pRt2nWqA

# Encode params from a JSON file → ID
python quilt_id.py encode params.json

# Render a quilt from an ID directly
python quilt_id.py render 3xKm7pRt2nWqA out.png
```

If she emails me IDs she likes, I can decode them, tweak params, re-encode,
and regenerate. Full reproducibility from a 13-char string.

---

## Defining Families

1. Take all liked quilts from `ratings.json`
2. Compute feature vectors (`params_to_features` from `sampler.py`)
3. K-means cluster into 16–20 groups
4. Each cluster = one family:
   - **Representative**: liked quilt nearest the centroid
   - **Name**: dominant palette + symmetry mode (e.g. "Deep Sea / Rotational")
     — auto-generated, may hand-curate later
   - **Variations**: 16–20 new quilts sampled near the cluster centroid
     (palette/symmetry fixed, other params randomized)

Script: `build_site.py`

---

## Build Process

Fully idempotent — re-run anytime after more scoring to regenerate families
and refresh the site.

```bash
python build_site.py \
    --ratings ratings.json \
    --out docs/ \
    --families 18 \
    --variations 18
```

Steps:
1. Cluster liked quilts → define families
2. Generate variation quilts for each family (PNG, ~400×400px thumbnails,
   ~800×800px for detail pages)
3. Render HTML from Jinja2 templates
4. Write everything to `docs/`
5. `git push` → GitHub Pages auto-deploys

---

## Scoring

Not implemented. She emails IDs of favorites; I decode and work from there.

---

## Tech Stack

| Concern | Choice |
|---|---|
| Hosting | GitHub Pages (`docs/`) |
| HTML generation | Python + Jinja2 |
| Image format | PNG (pre-generated at build time) |
| Scoring | None — email favorites |
| Dynamic generation | Not needed — all images pre-generated |
