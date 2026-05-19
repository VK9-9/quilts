#!/bin/bash

VERBOSE=0
[ "$1" = "-v" ] && VERBOSE=1

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# Use local venv if present
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$SCRIPT_DIR/venv/bin/python" ]; then
    PYTHON="$SCRIPT_DIR/venv/bin/python"
else
    PYTHON="python3"
fi

if [ $VERBOSE -eq 1 ]; then
    set -e
    echo "=== Doctests ==="
    $PYTHON -m doctest -v quilt_id.py clip_embed.py
    echo ""
    echo "=== pytest + coverage ==="
    $PYTHON -m pytest -v
    echo ""
    echo "=== pylint ==="
    $PYTHON -m pylint --ignore-patterns='test_.*\.py' *.py
    exit 0
fi

# Summary mode
FAILED=0

DOCTEST_OUT=$($PYTHON -m doctest -v quilt_id.py clip_embed.py 2>&1)
DOCTEST_EXIT=$?
TOTAL=$(echo "$DOCTEST_OUT" | awk '/^[0-9]+ tests in [0-9]+ items/{sum+=$1} END{print sum+0}')
PASSED=$(echo "$DOCTEST_OUT" | awk '/^[0-9]+ passed/{sum+=$1} END{print sum+0}')
if [ "$DOCTEST_EXIT" -eq 0 ]; then
    echo -e "${GREEN}Doctests: ${PASSED}/${TOTAL} passed${NC}"
else
    echo -e "${RED}Doctests: ${PASSED}/${TOTAL} passed (FAILED)${NC}"
    FAILED=1
fi

PYLINT_OUT=$($PYTHON -m pylint --ignore-patterns='test_.*\.py' *.py 2>&1)
PYLINT_EXIT=$?
SCORE=$(echo "$PYLINT_OUT" | grep "Your code has been rated" | grep -oE '[0-9]+\.[0-9]+/[0-9]+' | head -1)
# pylint exit codes are bitmasks: 1=fatal, 2=error, 4=warning, 8=refactor, 16=convention
# fail only on fatal or error (bits 1 and 2)
if [ $(( PYLINT_EXIT & 3 )) -eq 0 ]; then
    echo -e "${GREEN}pylint:   ${SCORE}${NC}"
else
    echo -e "${RED}pylint:   ${SCORE} (errors — see test.sh -v)${NC}"
    FAILED=1
fi

PYTEST_OUT=$($PYTHON -m pytest 2>&1)
PYTEST_EXIT=$?
SUMMARY=$(echo "$PYTEST_OUT" | tail -1 | tr -d '=' | xargs)
if [ "$PYTEST_EXIT" -eq 0 ] || [ "$PYTEST_EXIT" -eq 5 ]; then
    echo -e "${GREEN}pytest:   ${SUMMARY}${NC}"
else
    echo -e "${RED}pytest:   ${SUMMARY}${NC}"
    FAILED=1
fi

[ "$FAILED" -eq 0 ] || exit 1
