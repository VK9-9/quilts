#!/bin/bash
# Deploy docs/ to the gh-pages branch.
# Run from the repo root after rebuilding the site.
set -e

REPO_ROOT="$(git rev-parse --show-toplevel)"
CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
DOCS="$REPO_ROOT/docs"

if [ ! -f "$DOCS/index.html" ]; then
    echo "docs/index.html not found — run build_site.py first"
    exit 1
fi

# Stash any uncommitted changes so we can switch branches cleanly
STASHED=0
if ! git diff --quiet || ! git diff --cached --quiet; then
    git stash push -m "deploy.sh auto-stash"
    STASHED=1
fi

git checkout gh-pages

# Sync docs/ contents to repo root (images/ + index.html + family HTML)
rsync -a --delete \
    --exclude='.git' \
    "$DOCS/" "$REPO_ROOT/"

git add -A
if git diff --cached --quiet; then
    echo "Nothing changed — gh-pages already up to date."
else
    git commit -m "rebuild gallery"
    git push origin gh-pages
    echo "Deployed to gh-pages."
fi

git checkout "$CURRENT_BRANCH"

if [ "$STASHED" -eq 1 ]; then
    git stash pop
fi
