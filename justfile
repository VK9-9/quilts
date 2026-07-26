# Quilts project tasks. Run `just` (or `just --list`) to see all recipes.

python := "venv/bin/python"
ratings := "data/ratings.json"

# List available recipes
default:
    @just --list

# Idempotent environment bootstrap: create venv (if missing) + install deps
setup:
    [ -d venv ] || python3 -m venv venv
    venv/bin/pip install -r requirements.txt

# Autoformat all Python in place
fmt:
    venv/bin/ruff format .

# Static analysis only (pylint), warnings as errors
lint:
    {{python}} -m pylint --ignore-patterns='test_.*\.py' *.py

# Tests only (doctests + pytest). Extra pytest args pass through: `just test -k name`
# Every other module's doctests run inside pytest via test_doctests.py, which
# discovers them by scanning; clip_embed needs torch so it stays out here.
test *args:
    {{python}} -m doctest clip_embed.py
    {{python}} -m pytest {{args}}

# Dependency vulnerability scan.
# Ignored: CVE-2025-3000 (torch.jit.script memory corruption) — no fix released,
# local-only exploit, torch is a dev-only dep (not in requirements-railway.txt)
# and the vulnerable jit.script path is unused. Re-check when a fix ships.
audit:
    venv/bin/pip-audit -r requirements.txt --ignore-vuln CVE-2025-3000

# Local pre-commit gate: format, lint, test, audit
check: fmt lint test audit

# CI gate: same as check but only verifies formatting (never rewrites)
ci: fmt-check lint test audit

[private]
fmt-check:
    venv/bin/ruff format --check .

# Run the default app: public generator webapp on :5001 (what `deploy` ships)
run:
    {{python}} generator.py

# Run the active-learning scorer webapp on :5555 (local admin tool)
run-score:
    {{python}} app.py {{ratings}}

# Deploy the generator webapp to Railway (merges main -> release). Optional source branch arg.
deploy *args:
    ./deploy-railway.sh {{args}}

# Deploy docs/ to GitHub Pages (run `just build-site` first; pass --force to re-trigger)
deploy-static *args:
    ./deploy-site.sh {{args}}

# --- project-specific tasks ---

# Build the static gallery into docs/
build-site:
    {{python}} build_site.py --ratings {{ratings}} --out docs/ --families 18 --variations 18

# Backfill CLIP embeddings for ratings that lack one
backfill:
    {{python}} backfill_embeddings.py {{ratings}}

# Re-embed every rating. Run after a change to the renderer, or the stored
# vectors describe images the current code no longer draws. Stop the scorer
# first — it holds the array in memory and rewrites it on every rating.
backfill-refresh:
    {{python}} backfill_embeddings.py {{ratings}} --refresh

# Round analysis of the ratings data
analyze:
    {{python}} analyze.py {{ratings}}
