"""Run every module's doctests through pytest.

`just test` used to invoke `python -m doctest` on an explicit two-module list,
so the ten doctest lines in build_site.py had never executed — and one of them
asserted the wrong answer. Discovering modules by scanning for a prompt means a
new one can't be silently left out of the run.
"""

import doctest
import importlib
import pathlib

import pytest

# app.py constructs a QuiltExplorer from sys.argv at import time, so importing
# it under pytest would read pytest's own argv. clip_embed.py needs torch and a
# 350 MB weights download; `just test` runs its doctests separately.
_NOT_IMPORTABLE_HERE = {"app", "clip_embed"}


def _modules_with_doctests():
    for path in sorted(pathlib.Path(__file__).parent.glob("*.py")):
        if path.stem.startswith("test_") or path.stem in _NOT_IMPORTABLE_HERE:
            continue
        if ">>>" in path.read_text(encoding="utf-8"):
            yield path.stem


@pytest.mark.parametrize("module_name", sorted(_modules_with_doctests()))
def test_doctests(module_name):
    result = doctest.testmod(importlib.import_module(module_name), verbose=False)
    assert result.attempted > 0, f"{module_name} was collected but ran no doctests"
    assert result.failed == 0, (
        f"{module_name}: {result.failed} of {result.attempted} doctests failed"
    )
