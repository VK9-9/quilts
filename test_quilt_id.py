"""Tests for quilt_id.py — encoding/decoding quilt parameters."""

import pytest
from quilt_id import (
    encode,
    decode,
    _b58enc,
    _b58dec,
    _pack,
    _unpack,
    _quantize,
    _dequantize,
    _encode_wonky,
    _V1_PALETTES,
    _V1_SYMMETRY,
    _V1_LEN,
    _V2_PALETTES,
    _V2_SYMMETRY,
    _V2_STITCH,
    _V2_WONKY,
    _V2_LEN,
    _V2_SCHEMA,
    _V3_LEN,
    _V4_LEN,
    _V5_LEN,
    _V5_FINE,
    ENCODABLE_MAX,
    _encode_v4,
    _V4_QUILT_SIZES,
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


def test_pack_saturates_overflow():
    # 4-bit field with value 20 saturates to the max (15), not wraps to 4 —
    # wrapping would decode out-of-range params to unrelated values.
    packed = _pack([(20, 4)])
    unpacked = _unpack(packed, [("x", 4)])
    assert unpacked["x"] == 15


def test_pack_saturates_negative():
    # Negative offset values (e.g. rows-14 when rows < 14) saturate to 0.
    packed = _pack([(-3, 4)])
    unpacked = _unpack(packed, [("x", 4)])
    assert unpacked["x"] == 0


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
    "seed": 12345,
    "palette": "ocean breeze",
    "symmetry": "bargello",
    "chaos": 0.3,
    "rows": 16,
    "cols": 16,
    "n_patterns": 2,
    "n_colors": 4,
    "tile_size": 5,
    "tile_variation": 0.10,
    "border_style": "none",
    "mega_frac": 0.0,
    "plain_frac": 0.0,
    "quilt_stitch": "grid",
    "wonky": 0.0,
}


def test_v5_encode_length():
    assert len(encode(_BASE_PARAMS)) == _V5_LEN


def test_v4_ids_still_decode():
    """V4 is frozen but every shared link and gallery page made before V5
    carries one, so they must keep decoding."""
    d = decode(_encode_v4({**_BASE_PARAMS, "strippy": 0.35, "wash_alpha": 0.18, "wonky": 0.04}))
    assert len(_encode_v4(_BASE_PARAMS)) == _V4_LEN
    assert (d["strippy"], d["wash_alpha"], d["wonky"]) == (0.35, 0.18, 0.04)


class TestRoundTrip:
    """Every control the generator exposes must survive encode -> decode.

    V3 carried none of strippy/wash_alpha/palette_2/palette_mix/quilt_size even
    though all five change the render, so visibly different quilts collided on
    one ID and the scorer's generator link opened a different quilt. V4 carried
    them, but too coarsely: wonky 0.03, plain 0.15 and others came back
    different, which this class's old slider sweep missed because it only
    covered strippy and wash.
    """

    @pytest.mark.parametrize("strippy", [0.0, 0.05, 0.2, 0.35, 0.6])
    def test_strippy(self, strippy):
        assert decode(encode({**_BASE_PARAMS, "strippy": strippy}))["strippy"] == strippy

    @pytest.mark.parametrize("wash", [0.0, 0.02, 0.1, 0.18, 0.2])
    def test_wash_alpha(self, wash):
        assert decode(encode({**_BASE_PARAMS, "wash_alpha": wash}))["wash_alpha"] == wash

    @pytest.mark.parametrize("name", _V2_PALETTES)
    def test_secondary_palettes(self, name):
        d = decode(encode({**_BASE_PARAMS, "palette_2": name, "palette_mix": name}))
        assert d["palette_2"] == name
        assert d["palette_mix"] == name

    def test_secondary_palettes_default_to_none(self):
        d = decode(encode(_BASE_PARAMS))
        assert d["palette_2"] is None
        assert d["palette_mix"] is None

    @pytest.mark.parametrize("size", _V4_QUILT_SIZES)
    def test_quilt_size(self, size):
        assert decode(encode({**_BASE_PARAMS, "quilt_size": size}))["quilt_size"] == size

    def test_quilt_size_vocabulary_matches_the_generator(self):
        """quilt_id owns the wire order; generator owns the labels."""
        from generator import QUILT_SIZES

        assert list(QUILT_SIZES) == _V4_QUILT_SIZES

    def test_every_slider_position_round_trips_exactly(self):
        """Sweep every position of every range slider in the editor template,
        plus every categorical, and require an exact round trip."""
        import re

        from generator import _DEFAULTS, _PARAM_BOUNDS, complete_params

        import os

        path = os.path.join(os.path.dirname(__file__), "templates", "generator", "create.html")
        with open(path, encoding="utf-8") as f:
            html = f.read()
        sliders = re.findall(r'id="(\w+)" min="([\d.]+)" max="([\d.]+)" step="([\d.]+)"', html)
        assert {name for name, *_ in sliders} >= set(_V5_FINE), "a fractional slider is missing"

        cases = []
        for name, lo, hi, step in sliders:
            n = round((float(hi) - float(lo)) / float(step))
            for k in range(n + 1):
                value = round(float(lo) + k * float(step), 4)
                cases.append({name: int(value) if name in ("rows", "tile_size") else value})
        cases += [{"palette": name} for name in _V2_PALETTES]
        cases += [{"symmetry": name} for name in _V2_SYMMETRY]
        cases += [{"quilt_stitch": name} for name in _V2_STITCH + [None]]
        cases += [{"quilt_size": size} for size in _V4_QUILT_SIZES]
        lo, hi = _PARAM_BOUNDS["n_colors"]
        cases += [{"n_colors": n} for n in range(lo, hi + 1)]

        for overrides in cases:
            params = complete_params({**_DEFAULTS, **overrides})
            decoded = decode(encode(params))
            for field in _ROUND_TRIP_FIELDS:
                if decoded[field] != params[field]:
                    pytest.fail(
                        f"{overrides}: {field} encoded as {decoded[field]!r}, "
                        f"expected {params[field]!r}"
                    )

    def test_everything_the_sampler_produces_round_trips_exactly(self):
        """The scorer's "Open in generator" link encodes the rated params; with
        V4, 24% of R24's quilts reopened as a different quilt."""
        import random

        from sampler import sample_random_params

        for seed in range(400):
            params = sample_random_params(random.Random(seed))
            decoded = decode(encode(params))
            bad = [f for f in _ROUND_TRIP_FIELDS if decoded[f] != params.get(f)]
            if bad:
                pytest.fail(f"seed {seed}: {bad} changed in the round trip")

    def test_server_bounds_fit_the_encoding(self):
        """_pack saturates rather than raising, so a value the server accepts
        but V5 can't hold would silently become a different quilt."""
        from generator import _PARAM_BOUNDS

        for field, maximum in ENCODABLE_MAX.items():
            assert _PARAM_BOUNDS[field][1] <= maximum, f"{field} bound exceeds the encoding"


_ROUND_TRIP_FIELDS = [
    "seed",
    "palette",
    "symmetry",
    "rows",
    "n_patterns",
    "n_colors",
    "tile_size",
    "border_style",
    "quilt_stitch",
    "palette_2",
    "palette_mix",
    *_V5_FINE,
]


def test_older_versions_still_decode():
    """V1/V2/V3 IDs predate the V4 fields and must report them as off."""
    d = decode("6PpafDL86tkRBR")  # V3
    assert d["n_colors"] == 5
    assert d["strippy"] == 0.0
    assert d["wash_alpha"] == 0.0
    assert d["palette_2"] is None
    assert d["palette_mix"] is None
    assert d["quilt_size"] == "sq8"


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
        (1, 4),  # version
        (100, 31),  # seed
        (0, 4),  # palette (autumn harvest)
        (0, 3),  # symmetry (none)
        (30, 7),  # chaos (0.30)
        (2, 3),  # rows-14=2 → 16
        (1, 1),  # n_patterns-1=1 → 2
        (1, 1),  # n_colors-3=1 → 4
        (5, 4),  # tile_size
        (10, 5),  # tile_variation (0.10)
        (0, 2),  # border (none)
        (0, 1),  # sash_width
        (0, 1),  # cornerstones
        (0, 1),  # color_gradient
        (0, 4),  # mega_frac
        (0, 4),  # plain_frac
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


class TestCliCommand:
    """`quilt_id.py decode <id> --command` must print a quilt.py command that
    renders the same quilt. It used to cover only the pre-wonky parameter set
    and always made square quilts, so most current IDs printed a command for
    a different quilt."""

    _FULL = {
        **_BASE_PARAMS,
        "symmetry": "partial",
        "tile_size": 0,
        "border_style": "checkerboard",
        "mega_frac": 0.15,
        "plain_frac": 0.2,
        "wash_alpha": 0.07,
        "palette_2": "thistle",
        "palette_mix": "bluebell",
        "wonky": 0.037,
        "strippy": 0.23,
        "quilt_size": "throw",
    }

    @staticmethod
    def _cli_kwargs(params):
        from quilt import args_to_render_kwargs, build_parser
        from quilt_id import command_args

        parsed = build_parser().parse_args(command_args(params) + ["--output", "x.png"])
        return args_to_render_kwargs(parsed)

    @staticmethod
    def _design(kwargs):
        return {k: v for k, v in kwargs.items() if k not in ("block_size", "output", "border")}

    def test_decoded_non_square_size_keeps_its_aspect(self):
        from generator import _cols_for

        decoded = decode(encode(self._FULL))
        assert decoded["cols"] == _cols_for(decoded["rows"], "throw") != decoded["rows"]

    def test_command_reproduces_every_render_parameter(self):
        from render_params import params_to_render_kwargs

        decoded = decode(encode(self._FULL))
        assert self._design(self._cli_kwargs(decoded)) == self._design(
            params_to_render_kwargs(decoded)
        )

    def test_command_reproduces_sampled_quilts(self):
        import random

        from render_params import params_to_render_kwargs
        from sampler import sample_random_params

        for seed in range(200):
            decoded = decode(encode(sample_random_params(random.Random(seed))))
            cli = self._design(self._cli_kwargs(decoded))
            if cli != self._design(params_to_render_kwargs(decoded)):
                pytest.fail(f"seed {seed}: CLI command renders a different quilt")

    def test_command_renders_identical_pixels(self):
        from quilt import render_quilt
        from render_params import params_to_render_kwargs

        decoded = decode(encode(self._FULL))
        cli = self._cli_kwargs(decoded)
        cli.update(block_size=8, border=15, output=None)
        assert render_quilt(**cli) == render_quilt(**params_to_render_kwargs(decoded, block_size=8))
