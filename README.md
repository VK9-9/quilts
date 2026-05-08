# Quilts

Generative quilt art — active learning system for exploring and curating
patchwork quilt designs, with a static gallery for sharing favorites.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Rating webapp

```bash
python app.py
```

Opens a Flask server at `http://localhost:5000`. Rate quilts like/dislike;
the model learns your preferences and biases future suggestions.

## Quilt ID tool

Each quilt is fully described by a 13-character base58 ID. The ID is
self-contained — no database needed to reproduce the image.

```bash
# Decode an ID → params JSON
./quilt_id.py decode 4Fzox25puRqsD

# Print the quilt.py command to regenerate the quilt
./quilt_id.py decode 4Fzox25puRqsD --command

# Encode a params JSON file → ID
./quilt_id.py encode params.json
```

The `--command` flag is useful when someone sends you IDs they like — decode
it, optionally tweak the printed command, and re-run to regenerate or vary
the design.

## Build and deploy the static gallery

**Build** — clusters liked quilts into families, renders variation images,
writes HTML to `docs/`:

```bash
python build_site.py --ratings data/ratings.json --out docs/ --families 16 --variations 16
```

**Deploy** — syncs `docs/` to the `gh-pages` branch and pushes to GitHub Pages:

```bash
./deploy.sh
```

The site is served from the `gh-pages` branch (configured in GitHub repo
Settings → Pages → Branch: `gh-pages`, folder: `/`).
URL: `https://vk9-9.github.io/quilts/`

### Tuning family names

Names are auto-generated from chaos level, symmetry, and other traits
(e.g. "Wild Spiral", "Lattice Calm Crystal"). To preview or hand-tune them:

```bash
# Preview auto-generated names and write to family_names.json
python build_site.py --dump-names

# Edit family_names.json with better names, then rebuild + deploy
python build_site.py --ratings data/ratings.json --out docs/ --families 16 --variations 16
./deploy.sh
```

`family_names.json` is read automatically on each build if present. Slug
keys are stable as long as `--families` and `--seed` stay the same.

## Key files

| File | Purpose |
|------|---------|
| `quilt.py` | Renderer |
| `sampler.py` | Active learning sampler |
| `quilt_id.py` | Compact ID encoder/decoder |
| `palettes.py` | Color palettes |
| `blocks.py` | Block pattern definitions |
| `app.py` | Rating webapp |
| `build_site.py` | Static site generator |
| `analyze.py` | Analysis script |
| `ANALYSIS.md` | Round-by-round findings |
| `WEBSITE_PLAN.md` | Static gallery design doc |
