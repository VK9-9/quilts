"""Tests for quilt_id.py — encoding/decoding quilt parameters."""
import pytest
from quilt_id import (
    encode, decode, _b58enc, _b58dec, _pack, _unpack,
    _quantize, _dequantize, _encode_wonky,
    _V1_PALETTES, _V1_SYMMETRY, _V1_LEN,
    _V2_PALETTES, _V2_SYMMETRY, _V2_STITCH, _V2_WONKY, _V2_LEN,
    _V2_SCHEMA, _V3_LEN,
)


# --- base58 ---

def test_b58_roundtrip():
    for n in [0, 1, 57, 58, 999, 2**31 - 1, 2**76]:
        encoded = _b58enc(n, 14)
        assert _b58dec(encoded) == n


def test_b58enc_length():
    assert len(_b58enc(0, 13)) == 13
    assert len(_b58enc(0, 14)) == 14
    assert len(_b58enc(2**80, 14)) == 14


# --- pack/unpack ---

def test_pack_unpack_roundtrip():
    schema = [("a", 4), ("b", 8), ("c", 3)]
    values = [(10, 4), (200, 8), (5, 3)]
    packed = _pack(values)
    unpacked = _unpack(packed, schema)
    assert unpacked == {"a": 10, "b": 200, "c": 5}


def test_pack_truncates_overflow():
    # 4-bit field with value 20 (0b10100) → should keep low 4 bits = 4
    packed = _pack([(20, 4)])
    unpacked = _unpack(packed, [("x", 4)])
    assert unpacked["x"] == 20 & 0xF


# --- quantize/dequantize ---

def test_quantize_zero():
    assert _quantize(0.0, 0.10, 0.01, 15) == 0


def test_quantize_nonzero():
    # 0.15 → (0.15 - 0.10) / 0.01 + 1 = 6
    assert _quantize(0.15, 0.10, 0.01, 15) == 6


def test_dequantize_zero():
    assert _dequantize(0, 0.10, 0.01) == 0.0


def test_dequantize_nonzero():
    assert _dequantize(6, 0.10, 0.01) == 0.15


def test_quantize_dequantize_roundtrip():
    for val in [0.0, 0.10, 0.15, 0.20, 0.24]:
        idx = _quantize(val, 0.10, 0.01, 15)
        recovered = _dequantize(idx, 0.10, 0.01)
        assert abs(recovered - val) < 0.015


# --- wonky ---

def test_encode_wonky_zero():
    assert _encode_wonky(0.0) == 0


def test_encode_wonky_values():
    assert _encode_wonky(0.02) == 1
    assert _encode_wonky(0.04) == 2
    assert _encode_wonky(0.06) == 3


def test_encode_wonky_clamps():
    assert _encode_wonky(0.10) == 3  # clamped to max


# --- V2 encode/decode roundtrip ---

_BASE_PARAMS = {
    "seed": 12345, "palette": "ocean breeze", "symmetry": "bargello",
    "chaos": 0.3, "rows": 16, "cols": 16, "n_patterns": 2,
    "n_colors": 4, "tile_size": 5, "tile_variation": 0.10,
    "border_style": "none", "mega_frac": 0.0, "plain_frac": 0.0,
    "quilt_stitch": "grid", "wonky": 0.0,
}


def test_v3_encode_length():
    assert len(encode(_BASE_PARAMS)) == _V3_LEN


def test_v2_roundtrip_exact_fields():
    qid = encode(_BASE_PARAMS)
    d = decode(qid)
    assert d["seed"] == 12345
    assert d["palette"] == "ocean breeze"
    assert d["symmetry"] == "bargello"
    assert d["rows"] == 16
    assert d["cols"] == 16
    assert d["n_patterns"] == 2
    assert d["n_colors"] == 4
    assert d["tile_size"] == 5
    assert d["quilt_stitch"] == "grid"
    assert d["wonky"] == 0.0


def test_v2_roundtrip_chaos_quantization():
    for chaos in [0.0, 0.01, 0.25, 0.50, 0.80]:
        p = {**_BASE_PARAMS, "chaos": chaos}
        d = decode(encode(p))
        assert abs(d["chaos"] - chaos) < 0.015


def test_v2_roundtrip_all_palettes():
    for pal in _V2_PALETTES:
        p = {**_BASE_PARAMS, "palette": pal}
        assert decode(encode(p))["palette"] == pal


def test_v2_roundtrip_all_symmetries():
    for sym in _V2_SYMMETRY:
        p = {**_BASE_PARAMS, "symmetry": sym}
        assert decode(encode(p))["symmetry"] == sym


def test_v2_roundtrip_all_stitches():
    for stitch in _V2_STITCH:
        p = {**_BASE_PARAMS, "quilt_stitch": stitch}
        assert decode(encode(p))["quilt_stitch"] == stitch


def test_v2_roundtrip_no_stitch():
    p = {**_BASE_PARAMS, "quilt_stitch": None}
    assert decode(encode(p))["quilt_stitch"] is None


def test_v2_roundtrip_wonky_values():
    for w in _V2_WONKY:
        p = {**_BASE_PARAMS, "wonky": w}
        assert decode(encode(p))["wonky"] == w


def test_v2_roundtrip_mega_frac():
    for mf in [0.0, 0.10, 0.15, 0.24]:
        p = {**_BASE_PARAMS, "mega_frac": mf}
        d = decode(encode(p))
        assert abs(d["mega_frac"] - mf) < 0.02


def test_v2_roundtrip_plain_frac():
    for pf in [0.0, 0.10, 0.20, 0.38]:
        p = {**_BASE_PARAMS, "plain_frac": pf}
        d = decode(encode(p))
        assert abs(d["plain_frac"] - pf) < 0.03


def test_v2_roundtrip_rows():
    for rows in range(14, 22):
        p = {**_BASE_PARAMS, "rows": rows, "cols": rows}
        d = decode(encode(p))
        assert d["rows"] == rows
        assert d["cols"] == rows


def test_v2_roundtrip_border_styles():
    for bs in ["none", "solid", "checkerboard", "piano_keys"]:
        p = {**_BASE_PARAMS, "border_style": bs}
        assert decode(encode(p))["border_style"] == bs


def test_v2_seed_truncation():
    # seed field is 31 bits, so only low 31 bits preserved
    big_seed = 2**31 + 42
    p = {**_BASE_PARAMS, "seed": big_seed}
    d = decode(encode(p))
    assert d["seed"] == big_seed & ((1 << 31) - 1)


def test_v2_drops_v1_fields():
    d = decode(encode(_BASE_PARAMS))
    assert d["sash_width"] == 0
    assert d["cornerstones"] is False
    assert d["color_gradient"] == "none"


# --- V1 decode ---

def test_v1_decode_legacy():
    # Build a known V1 ID by hand: version=1, seed=100, palette=0 (autumn harvest),
    # symmetry=0 (none), etc.
    from quilt_id import _V1_SCHEMA
    fields = [
        (1, 4),   # version
        (100, 31), # seed
        (0, 4),   # palette (autumn harvest)
        (0, 3),   # symmetry (none)
        (30, 7),  # chaos (0.30)
        (2, 3),   # rows-14=2 → 16
        (1, 1),   # n_patterns-1=1 → 2
        (1, 1),   # n_colors-3=1 → 4
        (5, 4),   # tile_size
        (10, 5),  # tile_variation (0.10)
        (0, 2),   # border (none)
        (0, 1),   # sash_width
        (0, 1),   # cornerstones
        (0, 1),   # color_gradient
        (0, 4),   # mega_frac
        (0, 4),   # plain_frac
    ]
    n = _pack(fields)
    qid = _b58enc(n, 13)
    d = decode(qid)
    assert d["seed"] == 100
    assert d["palette"] == "autumn harvest"
    assert d["symmetry"] == "none"
    assert d["rows"] == 16
    assert d["n_patterns"] == 2
    assert d["n_colors"] == 4


# --- error cases ---

def test_decode_invalid_length():
    with pytest.raises(ValueError, match="Unknown quilt ID version"):
        decode("abc")


def test_decode_wrong_version():
    # 14-char string but version bits don't match V2 (version=0)
    qid = _b58enc(0, 14)
    with pytest.raises(ValueError, match="Unknown quilt ID version"):
        decode(qid)


def test_encode_unknown_palette():
    p = {**_BASE_PARAMS, "palette": "nonexistent"}
    with pytest.raises(ValueError):
        encode(p)


def test_encode_unknown_symmetry():
    p = {**_BASE_PARAMS, "symmetry": "nonexistent"}
    with pytest.raises(ValueError):
        encode(p)


def test_v3_n_colors_5():
    p = {**_BASE_PARAMS, "n_colors": 5}
    d = decode(encode(p))
    assert d["n_colors"] == 5


def test_v3_n_colors_roundtrip():
    for nc in [3, 4, 5, 6]:
        p = {**_BASE_PARAMS, "n_colors": nc}
        assert decode(encode(p))["n_colors"] == nc
