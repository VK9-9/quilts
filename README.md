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

Each quilt is fully described by a 13-character base58 ID. Decode an ID
back to its parameters, or encode a params file to an ID:

```bash
python quilt_id.py decode 4Fzox25puRqsD
python quilt_id.py encode params.json
```

## Build the static gallery

```bash
python build_site.py --ratings ratings.json --out docs/ --families 18 --variations 18
```

Clusters liked quilts into families, generates variation images, and writes
a static site to `docs/`. Push to GitHub to deploy via GitHub Pages.

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
