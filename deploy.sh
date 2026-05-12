#!/bin/bash
# Deploy docs/ to the gh-pages branch using a git worktree.
# Run from the repo root after rebuilding the site with build_site.py.
# Never switches your working branch.
set -e

REPO_ROOT="$(git rev-parse --show-toplevel)"
DOCS="$REPO_ROOT/docs"
WORKTREE="$REPO_ROOT/.gh-pages-worktree"

if [ ! -f "$DOCS/index.html" ]; then
    echo "docs/index.html not found — run build_site.py first"
    exit 1
fi

# Set up a worktree pointing at gh-pages (created once, reused after)
if [ ! -d "$WORKTREE" ]; then
    git worktree add "$WORKTREE" gh-pages
fi

# Wipe worktree contents (except .git) and copy fresh docs/
find "$WORKTREE" -mindepth 1 -maxdepth 1 ! -name '.git' -exec rm -rf {} +
cp -r "$DOCS"/. "$WORKTREE"/

# Commit and push from the worktree
cd "$WORKTREE"
git add -A
if [ "$1" = "--force" ]; then
    git commit --allow-empty -m "rebuild gallery"
    git push origin gh-pages
    echo "Deployed to gh-pages (forced)."
elif git diff --cached --quiet; then
    echo "Nothing changed — gh-pages already up to date."
else
    git commit -m "rebuild gallery"
    git push origin gh-pages
    echo "Deployed to gh-pages."
fi
