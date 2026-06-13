# Quilts

Generative quilt art — active learning system for exploring and curating
patchwork quilt designs, with a static gallery for sharing favorites.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Tasks

Common tasks are run with [`just`](https://github.com/casey/just)
(`brew install just`). Run `just` or `just --list` to see everything; the
recipes used below are noted inline. `just check` runs the full local gate
(format, lint, test, audit); `just test` is tests-only and `just lint` is
lint-only.

## Generator webapp

```bash
just run
```

Opens at `http://localhost:5001`. Pick a preset family or tweak params
(symmetry, palette, chaos, etc.) and see the quilt update live. Download
high-res PNGs. (This is the default app; `just deploy` ships it.)

Deploy to Railway:

```bash
just deploy
```

## Rating webapp (private)

```bash
just run-score
```

Opens at `http://localhost:5555`. Rate quilts like/dislike;
the model learns your preferences and biases future suggestions.

## Quilt ID tool

Each quilt is fully described by a 14-character base58 ID (V2 encoding). The ID is
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

**Build** — groups liked quilts into families by palette × symmetry,
renders variation images, writes HTML to `docs/`:

```bash
just build-site
```

This runs `build_site.py --ratings data/ratings.json --out docs/ --families 18
--variations 18`. To pass other flags (e.g. `--clip`, to use CLIP embeddings for
picking better family representatives — slower, requires backfilled embeddings),
call the script directly.

**Deploy** — syncs `docs/` to the `gh-pages` branch and pushes to GitHub Pages:

```bash
just deploy-static   # or: just static
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
just build-site
just deploy-static
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
| `layout.py` | Grid layout engine (symmetry modes) |
| `generator.py` | Public generator webapp (Railway) |
| `app.py` | Private rating webapp |
| `build_site.py` | Static site generator |
| `analyze.py` | Analysis script |
| `ANALYSIS.md` | Round-by-round findings |
