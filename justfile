# Quilts project tasks. Run `just` (or `just --list`) to see all recipes.

# Use the project venv if present, else fall back to system python3.
python := `[ -x venv/bin/python ] && echo venv/bin/python || echo python3`
ratings := "data/ratings.json"

# List available recipes
default:
    @just --list

# Run the full test suite (doctests + pylint + pytest). Pass -v for verbose: `just test -v`
test *args:
    ./test.sh {{args}}

# Run pylint only
lint:
    {{python}} -m pylint --ignore-patterns='test_.*\.py' *.py

# Rating webapp (active-learning scorer) on :5555
score:
    {{python}} app.py {{ratings}}

# Public generator webapp on :5001
generator:
    {{python}} generator.py

# Build the static gallery into docs/
build-site:
    {{python}} build_site.py --ratings {{ratings}} --out docs/ --families 18 --variations 18

# Deploy the generator webapp to Railway (merges main -> release). Optional source branch arg.
deploy *args:
    ./deploy-railway.sh {{args}}

# Deploy docs/ to GitHub Pages (run `just build-site` first; pass --force to re-trigger)
deploy-static *args:
    ./deploy-site.sh {{args}}

# Backfill CLIP embeddings for existing ratings
backfill:
    {{python}} backfill_embeddings.py {{ratings}}

# Round analysis of the ratings data
analyze:
    {{python}} analyze.py {{ratings}}

alias static := deploy-static
