"""Cross-module palette/symmetry name consistency.

Palette and symmetry identity is a bare string threaded through palettes.py,
sampler.py, and quilt_id.py. A rename in palettes.py that isn't mirrored in the
frozen encoding lists or the sampler fails silently — encode() raises and gets
swallowed to "unknown", or the generator offers a dropdown option that can't
render. These tests turn that silent drift into a red test.

Note: _V1_PALETTES (frozen V1 decode) and _DROP_PALETTES (retired-from-sampling)
are intentionally allowed to reference palettes that no longer exist — they exist
to decode old IDs / exclude old names, not to be rendered. Only the *active*
sets are required to exist.
"""
from palettes import PALETTES
from layout import SYMMETRY_MODES
import sampler
from quilt_id import _V1_PALETTES, _V2_PALETTES, _V2_SYMMETRY

CURRENT_PALETTES = {name for name, _ in PALETTES}


# --- active palettes must exist in palettes.py ---

def test_v2_palettes_all_renderable():
    """Every generator/encoding palette must exist (else the dropdown breaks)."""
    missing = [p for p in _V2_PALETTES if p not in CURRENT_PALETTES]
    assert not missing, f"_V2_PALETTES references missing palettes: {missing}"


def test_sampler_palettes_all_renderable():
    """Every palette the sampler can emit must exist."""
    missing = [p for p in sampler.PALETTE_NAMES if p not in CURRENT_PALETTES]
    assert not missing, f"sampler.PALETTE_NAMES references missing palettes: {missing}"


def test_proven_palettes_exist():
    """Proven palettes are actively injected, so they must exist."""
    missing = [p for p in sampler._PROVEN_PALETTES if p not in CURRENT_PALETTES]
    assert not missing, f"_PROVEN_PALETTES references missing palettes: {missing}"


# --- active symmetries must be real layout modes ---

def test_v2_symmetries_are_layout_modes():
    bad = [s for s in _V2_SYMMETRY if s not in SYMMETRY_MODES]
    assert not bad, f"_V2_SYMMETRY references unknown modes: {bad}"


def test_sampler_symmetries_are_layout_modes():
    bad = [s for s in sampler.SYMMETRY_NAMES if s not in SYMMETRY_MODES]
    assert not bad, f"sampler.SYMMETRY_NAMES references unknown modes: {bad}"


def test_proven_symmetries_are_layout_modes():
    bad = [s for s in sampler._PROVEN_SYMMETRIES if s not in SYMMETRY_MODES]
    assert not bad, f"_PROVEN_SYMMETRIES references unknown modes: {bad}"


# --- sampler internal consistency ---

def test_proven_and_dropped_palettes_disjoint():
    overlap = set(sampler._PROVEN_PALETTES) & sampler._DROP_PALETTES
    assert not overlap, f"palettes both proven and dropped: {overlap}"


# --- encoding integrity: index-based lookup requires unique names in budget ---

def test_encoding_lists_have_no_duplicates():
    for label, names in [("_V1_PALETTES", _V1_PALETTES),
                         ("_V2_PALETTES", _V2_PALETTES),
                         ("_V2_SYMMETRY", _V2_SYMMETRY)]:
        assert len(names) == len(set(names)), f"{label} has duplicate entries"


def test_encoding_lists_fit_bit_budget():
    # Frozen widths from quilt_id schema: V1 palette 4 bits, V2 palette 5 bits,
    # V2 symmetry 4 bits. Overflowing these silently corrupts encode/decode.
    assert len(_V1_PALETTES) <= 2 ** 4
    assert len(_V2_PALETTES) <= 2 ** 5
    assert len(_V2_SYMMETRY) <= 2 ** 4
