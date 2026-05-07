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

## Build the static gallery

```bash
python build_site.py --ratings ratings.json --out docs/ --families 18 --variations 18
```

Clusters liked quilts into families, generates variation images, and writes
a static site to `docs/`. Push to GitHub to deploy via GitHub Pages.

Family names are auto-generated from chaos level, symmetry, and other traits
(e.g. "Wild Spiral", "Lattice Calm Crystal"). To preview or hand-tune names:

```bash
# Preview auto-generated names and write to family_names.json
python build_site.py --dump-names

# Edit family_names.json with better names, then rebuild
python build_site.py --ratings ratings.json --out docs/ --families 18 --variations 18
```

`family_names.json` is read automatically on each build if present. The slug
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
