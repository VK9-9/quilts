#!/bin/bash
# Merge main → release and deploy to Railway, then monitor until done.
set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m'

# --- pre-flight checks ---
SOURCE=${1:-main}
BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$BRANCH" != "$SOURCE" ]; then
    echo -e "${RED}Must be on $SOURCE (currently on $BRANCH)${NC}" >&2
    exit 1
fi

if ! git diff --quiet || ! git diff --cached --quiet; then
    echo -e "${RED}Working tree is dirty — commit or stash changes first${NC}" >&2
    exit 1
fi

if ! git diff --quiet "$SOURCE" "origin/$SOURCE" 2>/dev/null; then
    echo -e "${RED}$SOURCE is not in sync with origin/$SOURCE — push first${NC}" >&2
    exit 1
fi

# --- railway auth check ---
if ! railway status &>/dev/null; then
    echo -e "${RED}Not logged in to Railway. Run: railway login${NC}" >&2
    exit 1
fi

# --- merge and push ---
COMMIT=$(git rev-parse --short HEAD)
echo "Releasing $COMMIT from $SOURCE to production..."

git checkout release
git merge "$SOURCE" --ff-only
git push origin release
git checkout "$SOURCE"

echo -e "${GREEN}Pushed release branch — Railway deploy triggered${NC}"

# --- poll for completion ---
echo "Monitoring deployment..."
TIMEOUT=600  # 10 minutes
ELAPSED=0
INTERVAL=10

while [ $ELAPSED -lt $TIMEOUT ]; do
    sleep $INTERVAL
    ELAPSED=$((ELAPSED + INTERVAL))

    STATUS=$(railway deployment list --json 2>/dev/null \
        | python3 -c "import json,sys; d=json.load(sys.stdin); print(d[0]['status'])" 2>/dev/null || echo "UNKNOWN")

    case "$STATUS" in
        SUCCESS)
            echo -e "${GREEN}Deploy succeeded${NC} (${ELAPSED}s)"
            exit 0
            ;;
        FAILED|CRASHED)
            echo -e "${RED}Deploy $STATUS${NC} (${ELAPSED}s)"
            exit 1
            ;;
        *)
            echo -e "${YELLOW}  ${STATUS}...${NC} (${ELAPSED}s)"
            ;;
    esac
done

echo -e "${RED}Timed out waiting for deployment${NC}" >&2
exit 1
