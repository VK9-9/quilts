# Quilts Project

Generative quilt image tool with active learning preference model.

## Language & Environment

- Python 3, Cairo (pycairo) for rendering
- Flask webapp for scoring (`app.py`)
- scikit-learn for the preference model (LogisticRegression on CLIP embeddings)
- CLIP (ViT-B/32) for image embeddings (`clip_embed.py`)
- Static site generator (`build_site.py`) with Jinja2 templates

## Commands

Tasks are run via [`just`](https://github.com/casey/just) (`just` or `just --list`
to see all recipes). Follows the standard recipe vocabulary in the global
CLAUDE.md ("Justfile Conventions"): `test`/`lint` are atomic (tests-only /
lint-only), `check` is the full local gate, `ci` verifies formatting without
rewriting.

```bash
just setup         # create venv + install deps (idempotent)
just fmt           # autoformat in place (ruff)
just lint          # pylint only
just test          # doctests + pytest (pass args: just test -k name)
just audit         # dependency vulnerability scan (pip-audit)
just check         # local gate: fmt + lint + test + audit
just ci            # like check, but verifies formatting (ruff --check)
                   # also what .github/workflows/ci.yml runs — keep them in step

just run           # public generator webapp on :5001  [generator.py; what deploy ships]
just run-score     # active-learning scorer webapp on :5555  [app.py]

just deploy        # deploy generator webapp to Railway   [wraps deploy-railway.sh]
just deploy-static # deploy docs/ to GitHub Pages         [wraps deploy-site.sh]

just build-site    # build static gallery into docs/
just backfill      # backfill CLIP embeddings for existing ratings
just analyze       # round analysis of the ratings data
just backup        # snapshot data/ to iCloud (timestamped tarball, keeps 30)
                   # run after every scoring round — ratings.json is irreplaceable
```

The deploy scripts (`deploy-site.sh`, `deploy-railway.sh`) still exist and can be
called directly; `just` is the preferred front door.

## Key Architecture

- **Block patterns** (`blocks.py`): Functions `fn(x, y, size, n_colors) -> [(polygon, color_idx), ...]`. `color_idx` can be an int (palette index) or an RGB tuple — render loops must use `isinstance(color_idx, tuple)` check.
- **Layouts** (`layout.py`): Grid layout engine with symmetry modes. Assigns block patterns, palette indices, and rotations to each cell. Modes: none, mirror, rotational, stripe, partial, flower, emergent, bargello.
- **Bargello layout**: Whole-quilt undulating color wave. Cells store `_bargello_color` index; renderer forces solid-color cells and bypasses tiling. The wave is sampled once per column, so amplitude is *derived* from the period (`_BARGELLO_MAX_SLOPE`) rather than drawn independently — above ~1 colour strip per column the band aliases into a checkerboard. Bargello also depends on consecutive palette indices being consecutive tones; see `subset_in_tonal_order`.
- **Wonky/improv mode**: `wonky` param (0.0–0.06) jitters vertex positions on any block by a small random amount, mimicking modern improv quilting. Per-cell seeded RNG for reproducibility.
- **Strippy/asymmetric grid**: `strippy` param (0.0–0.5) varies row heights and column widths for a "strippy quilt" feel. Block patterns render in square coords then scale to rectangular cells via sx/sy transform.
- **Sampler** (`sampler.py`): 30% explore (random params); otherwise CLIP LogisticRegression scores a random 30 of 200 palette-capped candidates and returns its favorite (`_source` = `exploit_clip_nofilter`, R24's A/B label). A GradientBoosting param-vector pre-filter existed until 2026-10-07; R24's A/B showed it added nothing and concentrated palettes, so it and its feature encoder were removed. Historical `exploit_clip` rows came from that filtered path.
- **Proven palettes** (`_PROVEN_PALETTES` in sampler.py): Palettes with known high approval, excluded from exploitation candidates entirely. Only injected during exploration phase at controlled probability. Prevents model from over-selecting known winners.
- **Palettes** (`palettes.py`): `(name, [hex_colors])` tuples, authored as a tonal ramp followed by accent colours. All have 6; a random `n_colors` subset is selected per quilt by `subset_in_tonal_order`, which returns it **sorted by luminance** — bargello reads one index step as one shade step, so selection order would collapse the wave. `_DROP_PALETTES` in sampler.py excludes retired palettes from sampling and must only name palettes that still exist here (pinned by `test_palette_consistency`).
- **Ratings data** lives in `data/` (gitignored). Default path: `data/ratings.json`. Companion files: `data/ratings_embeddings.npy` + `data/ratings_embedding_ids.npy` (parallel: row i is the CLIP vector of the rating whose `id` is ids[i]), `data/ratings_rounds.json`. **Always go through `ratings_store`** (`load_ratings`, `load_embeddings` → `{id: vector}`): embeddings are joined to ratings by `id`, never by position — a rating with no embedding has no entry. Each rating's explore/exploit label is top-level `source` (not `params._source`). Migrated 2026-10-08; old-format files raise `MigrationNeeded`.
- **Scoring rounds** tracked in `data/ratings_rounds.json`. Analysis written to `ANALYSIS.md`. Since 2026-10-06 each round entry also stores `policy` (`sampler.current_policy()`: probabilities, ranges, drop/proven lists, model params, training window) and `commit` (sha, `-dirty` if uncommitted) — check these first when hunting confounds. Rounds ≤ R22 have neither (absent = unknown). New sampling knobs belong in `FEATURE_PROBS`/`PARAM_SPACE`/etc., not inline, so the snapshot sees them.
- **Static site families** defined by symmetry × chaos_band buckets (calm/lively/wild). Variations fix symmetry and constrain chaos/tile_size/rows to the liked range but use random palettes for color diversity. `--clip` flag uses CLIP embeddings for representative selection only.
- **quilt_id encoding** (`quilt_id.py`): V5 current (20 base58 chars, 115 bits) — same fields as V4 but every fractional control is stored exactly (`_V5_FINE`: 0.01 steps, 0.001 for wonky); `ENCODABLE_STEP`/`ENCODABLE_MAX`/`snap()` are the single source the generator clamps and snaps to. V4 (18 chars), V3/V2 (14), V1 (13) still decoded; versions told apart by length. `decode()` derives cols from `quilt_size` (`QUILT_SIZE_INCHES`, owned here). `decode <id> --command` prints a `quilt.py` command that reproduces the quilt exactly (tested through the real parser). `_V2_PALETTES` drives both encoding and the generator dropdown; `ROWS_RANGE` is the single source for the encodable rows range that `generator._PARAM_BOUNDS` and `build_site` both derive from. `_pack` **saturates** out-of-range fields rather than raising, so anything generating params must round-trip check (`build_site._encodable`) — a silently saturated field yields an ID describing a different quilt.
- **Pattern PDF** (`pattern_pdf.py`): Generates printable quilt patterns via `generate_pattern_pdf(params, outpath)`. Includes quilt overview, color key, block diagrams with piece outlines, and individual piece templates with seam allowance outlines and dimension labels. Helpers: `_offset_polygon` (SA outlines), `_edge_lengths_inches`, `_label_edge_lengths` (spatial deconfliction), `_extract_unique_blocks`, `_reconstruct_layout`. Convention: solid line = stitch/seam line (finished size), dashed line = cut line (SA).
- **Static site V1 quilt_id encoding** frozen at 16 palettes — new palettes work in scoring but not in build_site.py V1 IDs.
- **Generator param completion** (`generator.complete_params`): presets and decoded IDs are partial. Every control the template binds must come out of here with a real value — Jinja renders a missing key as `""`, and a browser resolves an empty `<input type=range>` to the slider midpoint, silently turning "absent" into "half on".

## Workflow Preferences

- Make each logical change a separate commit (palette changes, sampler tuning, new blocks, analysis updates — all separate)
- Run `just check` after changes (or `just test` for tests-only during iteration)
- When doing round analysis: pull stats, break down by parameter, check feature importances, recommend tweaks
