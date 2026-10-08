#!/usr/bin/env python3
"""Compact identifier for quilt parameter sets.

Encodes all parameters needed to reproduce a quilt into a short base58 string.
The version field (top 4 bits) selects the decode schema, so new params can be
added in future versions without breaking existing IDs.

Version 1: 76 bits → 13 base58 characters (FROZEN)
    version(4) seed(31) palette(4) symmetry(3) chaos(7) rows(3)
    n_patterns(1) n_colors(1) tile_size(4) tile_variation(5)
    border_style(2) sash_width(1) cornerstones(1) color_gradient(1)
    mega_frac(4) plain_frac(4)

Version 2: 80 bits → 14 base58 characters (FROZEN)
    version(4) seed(31) palette(5) symmetry(4) chaos(7) rows(3)
    n_patterns(1) n_colors(1) tile_size(4) tile_variation(5)
    border_style(2) mega_frac(4) plain_frac(4)
    quilt_stitch(3) wonky(2)
    Drops: sash_width, cornerstones, color_gradient (all hardcoded off)
    Adds: all symmetry modes (bargello, flower, emergent), all current palettes,
          quilt_stitch, wonky

Version 3: 81 bits → 14 base58 characters (FROZEN)
    Same as V2 but n_colors expanded from 1 bit to 2 bits (supports 3-6 colors).

Version 4: 102 bits → 18 base58 characters (FROZEN)
    Same as V3 plus strippy(4) wash_alpha(4) palette_2(5) palette_mix(5)
    quilt_size(3).
    Those five are exposed as controls in the generator UI and all change what
    is rendered, but no earlier version carried any of them — so two visibly
    different quilts could share one ID, and the scorer's "open in generator"
    link resolved to a different quilt than the one being rated.

Version 5: 115 bits → 20 base58 characters (current)
    Same fields as V4, but every fractional control (chaos, tile_variation,
    mega_frac, plain_frac, wonky, strippy, wash_alpha) is stored as an exact
    multiple of a fine step (0.01; 0.001 for wonky) — see _V5_FINE. V4's
    coarse steps couldn't hold many values the sliders and sampler produce, so
    24% of R24's rated quilts reopened as a different quilt. Versions are told
    apart by length (13/14/18/20), so no probe is needed.

Usage:
    from quilt_id import encode, decode
    qid = encode(params)          # e.g. "3xKm7pRt2nWqA4Bc9dEf"
    params = decode(qid)
"""

import json
import sys

# Base58 alphabet — no 0/O/I/l to avoid visual confusion
_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def _b58enc(n, length):
    chars = []
    while n:
        chars.append(_B58[n % 58])
        n //= 58
    while len(chars) < length:
        chars.append(_B58[0])
    return "".join(reversed(chars))


def _b58dec(s):
    n = 0
    for c in s:
        n = n * 58 + _B58.index(c)
    return n


# ---------------------------------------------------------------------------
# Version 1 schema — FROZEN. Do not change these lists even as the sampler
# evolves. Only include params relevant to the 13-char v1 budget.
# To add params: define V2 below.
# ---------------------------------------------------------------------------

# Only the 11 currently-active palettes (v1 uses 4 bits → max 15 entries)
_V1_PALETTES = [
    "autumn harvest",
    "ocean breeze",
    "wildflower",
    "farmhouse",
    "winter sky",
    "stained glass",
    "indigo dye",
    "deep sea",
    "plum and gold",
    "storm",
    "northern lights",
    "copper canyon",
    "autumn embers",
    "peacock feather",
    "cardinal",
    "midnight moss",
]

# Active symmetry modes (3 bits → max 7 entries)
_V1_SYMMETRY = ["none", "mirror", "rotational", "stripe", "partial"]

_V1_BORDER = ["none", "solid", "checkerboard", "piano_keys"]  # 2 bits
_V1_GRADIENT = ["none", "diagonal"]  # 1 bit

# Bit layout — total must equal _V1_TOTAL_BITS
_V1_SCHEMA = [
    ("version", 4),
    ("seed", 31),
    ("palette", 4),
    ("symmetry", 3),
    ("chaos", 7),  # 0–80 representing 0.00–0.80 in steps of 0.01
    ("rows", 3),  # offset 14: stored as rows-14, range 0–5
    ("n_patterns", 1),  # offset 1: stored as n_patterns-1
    ("n_colors", 1),  # offset 3: stored as n_colors-3
    ("tile_size", 4),  # 0–10
    ("tile_variation", 5),  # 0–30 representing 0.00–0.30 in steps of 0.01
    ("border_style", 2),
    ("sash_width", 1),  # 0=off, 1=5px
    ("cornerstones", 1),
    ("color_gradient", 1),
    ("mega_frac", 4),  # 0=off, 1–15 → 0.10–0.24 in steps of 0.01
    ("plain_frac", 4),  # 0=off, 1–15 → 0.10–0.38 in steps of 0.02
]

_V1_TOTAL_BITS = sum(bits for _, bits in _V1_SCHEMA)  # 76
_V1_LEN = 13  # ceil(76 / log2(58)) = 13 chars


# ---------------------------------------------------------------------------
# Version 2 schema — current. Adds bargello/flower/emergent symmetry, all
# current palettes, quilt_stitch, wonky. Drops sash_width/cornerstones/
# color_gradient (all hardcoded off in sampler).
# ---------------------------------------------------------------------------

_V2_PALETTES = [
    "ocean breeze",
    "wildflower",
    "indigo dye",
    "northern lights",
    "cherry blossom",
    "tide pool",
    "lavender fields",
    "winter frost",
    "twilight",
    "sea glass",
    "wisteria",
    "honey oak",
    "thistle",
    "river stone",
    "bluebell",
    "frosted berry",
    "dove grey",
    "handloom",
]  # 5 bits → max 31 entries

_V2_SYMMETRY = [
    "none",
    "mirror",
    "rotational",
    "stripe",
    "partial",
    "flower",
    "emergent",
    "bargello",
    "columns",
]  # 4 bits → max 15 entries

_V2_BORDER = ["none", "solid", "checkerboard", "piano_keys"]  # 2 bits (same as V1)

# 0 = no stitch; 1-4 = style index+1
_V2_STITCH = ["grid", "diagonal", "sashiko_wave", "sashiko_asanoha"]  # 3 bits → max 7 styles

# wonky: 0=off, 1=0.02, 2=0.04, 3=0.06
_V2_WONKY = [0.0, 0.02, 0.04, 0.06]  # 2 bits

_V2_SCHEMA = [
    ("version", 4),
    ("seed", 31),
    ("palette", 5),
    ("symmetry", 4),
    ("chaos", 7),  # 0–80 representing 0.00–0.80 in steps of 0.01
    ("rows", 3),  # offset 14: stored as rows-14, range 0–7
    ("n_patterns", 1),  # offset 1: stored as n_patterns-1
    ("n_colors", 1),  # offset 3: stored as n_colors-3
    ("tile_size", 4),  # 0–10
    ("tile_variation", 5),  # 0–30 representing 0.00–0.30 in steps of 0.01
    ("border_style", 2),
    ("mega_frac", 4),  # 0=off, 1–15 → 0.10–0.24 in steps of 0.01
    ("plain_frac", 4),  # 0=off, 1–15 → 0.10–0.38 in steps of 0.02
    ("quilt_stitch", 3),  # 0=none, 1-4=style
    ("wonky", 2),  # 0=off, 1=0.02, 2=0.04, 3=0.06
]

_V2_TOTAL_BITS = sum(bits for _, bits in _V2_SCHEMA)  # 80
_V2_LEN = 14  # ceil(80 / log2(58)) = 14 chars


# ---------------------------------------------------------------------------
# Version 3 schema — same as V2 but n_colors expanded to 2 bits (3-6 colors).
# Still fits in 14 base58 characters (81 bits < log2(58^14) ≈ 82.0).
# ---------------------------------------------------------------------------

_V3_SCHEMA = [
    ("version", 4),
    ("seed", 31),
    ("palette", 5),
    ("symmetry", 4),
    ("chaos", 7),
    ("rows", 3),
    ("n_patterns", 1),
    ("n_colors", 2),  # offset 3: stored as n_colors-3, range 0–3 (3-6 colors)
    ("tile_size", 4),
    ("tile_variation", 5),
    ("border_style", 2),
    ("mega_frac", 4),
    ("plain_frac", 4),
    ("quilt_stitch", 3),
    ("wonky", 2),
]

_V3_TOTAL_BITS = sum(bits for _, bits in _V3_SCHEMA)  # 81
_V3_LEN = 14  # ceil(81 / log2(58)) = 14 chars


# ---------------------------------------------------------------------------
# Version 4 schema — FROZEN. Adds the five render-affecting controls the
# generator UI exposes but no earlier version encoded.
# ---------------------------------------------------------------------------

# Quilt aspect-ratio presets, in generator.QUILT_SIZES order. 3 bits → max 7.
# test_quilt_id asserts the two stay in step.
_V4_QUILT_SIZES = ["throw", "twin", "queen", "king", "sq6", "sq8", "sq10"]
_V4_DEFAULT_QUILT_SIZE = "sq8"

_V4_SCHEMA = _V3_SCHEMA + [
    ("strippy", 4),  # 0=off, 1–12 → 0.05–0.60 in steps of 0.05
    ("wash_alpha", 4),  # 0=off, 1–10 → 0.02–0.20 in steps of 0.02
    ("palette_2", 5),  # 0=none, else _V2_PALETTES index + 1
    ("palette_mix", 5),  # 0=none, else _V2_PALETTES index + 1
    ("quilt_size", 3),  # index into _V4_QUILT_SIZES
]

_V4_TOTAL_BITS = sum(bits for _, bits in _V4_SCHEMA)  # 102
_V4_LEN = 18  # ceil(102 / log2(58)) = 18 chars


# ---------------------------------------------------------------------------
# Version 5 schema — current. Same fields as V4, but every fractional control
# is stored as an exact integer multiple of a fine step instead of V4's coarse
# quantization. V4 couldn't represent many values the generator sliders and
# the sampler actually produce (wonky 0.01/0.03, plain 0.05/0.15, strippy 0.23,
# wash 0.05, ...): 24% of R24's rated quilts opened in the generator as a
# different quilt than the one rated.
# ---------------------------------------------------------------------------

# field -> (bits, scale): stored as round(value * scale), so the step is
# 1/scale and the largest encodable value is (2**bits - 1) / scale. This is the
# single source for what a fractional control can take; generator snaps query
# values to it and its tests check every slider position against it.
_V5_FINE = {
    "chaos": (7, 100),  # 0.00–1.27
    "tile_variation": (6, 100),  # 0.00–0.63
    "mega_frac": (6, 100),  # 0.00–0.63
    "plain_frac": (6, 100),  # 0.00–0.63
    "wonky": (7, 1000),  # 0.000–0.127
    "strippy": (6, 100),  # 0.00–0.63
    "wash_alpha": (5, 100),  # 0.00–0.31
}

# Exact step and largest encodable value for each fractional control.
ENCODABLE_STEP = {field: 1 / scale for field, (_bits, scale) in _V5_FINE.items()}
ENCODABLE_MAX = {field: ((1 << bits) - 1) / scale for field, (bits, scale) in _V5_FINE.items()}

_V5_SCHEMA = [
    ("version", 4),
    ("seed", 31),
    ("palette", 5),
    ("symmetry", 4),
    ("chaos", _V5_FINE["chaos"][0]),
    ("rows", 3),
    ("n_patterns", 1),
    ("n_colors", 2),
    ("tile_size", 4),
    ("tile_variation", _V5_FINE["tile_variation"][0]),
    ("border_style", 2),
    ("mega_frac", _V5_FINE["mega_frac"][0]),
    ("plain_frac", _V5_FINE["plain_frac"][0]),
    ("quilt_stitch", 3),
    ("wonky", _V5_FINE["wonky"][0]),
    ("strippy", _V5_FINE["strippy"][0]),
    ("wash_alpha", _V5_FINE["wash_alpha"][0]),
    ("palette_2", 5),
    ("palette_mix", 5),
    ("quilt_size", 3),
]

_V5_TOTAL_BITS = sum(bits for _, bits in _V5_SCHEMA)  # 115
_V5_LEN = 20  # ceil(115 / log2(58)) = 20 chars

# rows is a 3-bit field stored as rows-14, and _pack saturates rather than
# raising — so anything generating params outside this range gets an ID that
# silently describes a different quilt. generator._PARAM_BOUNDS and
# build_site.generate_variations both derive their limits from this.
ROWS_RANGE = (14, 14 + 7)


def _pack(schema_values):
    """Pack list of (value, nbits) tuples into a single int, MSB first.

    Values are saturated to each field's [0, 2**nbits - 1] range. Masking
    instead would silently wrap an out-of-range value to an unrelated one
    (e.g. n_colors=7 -> 0 -> decodes as 3); saturation keeps the decoded
    value as close as the field allows.
    """
    n = 0
    for val, nbits in schema_values:
        hi = (1 << nbits) - 1
        n = (n << nbits) | max(0, min(int(val), hi))
    return n


def _unpack(n, schema):
    """Unpack int n using schema list of (name, nbits). Returns dict."""
    result = {}
    for name, nbits in reversed(schema):
        result[name] = n & ((1 << nbits) - 1)
        n >>= nbits
    return result


def _quantize(val, lo, step, levels):
    """Map float → 0 (off) or 1..levels (on). 0.0 → 0."""
    if val == 0.0:
        return 0
    return max(1, min(levels, round((val - lo) / step) + 1))


def _dequantize(idx, lo, step):
    """Reverse _quantize: 0 → 0.0, else lo + (idx-1)*step."""
    if idx == 0:
        return 0.0
    return round(lo + (idx - 1) * step, 4)


def _encode_wonky(val):
    """Quantize wonky float to 2-bit index (nearest of 0.0/0.02/0.04/0.06)."""
    if val == 0.0:
        return 0
    return min(3, max(1, round(val / 0.02)))


def _palette_ref(name):
    """Encode an optional secondary palette: 0 = none, else index + 1."""
    return (_V2_PALETTES.index(name) + 1) if name in _V2_PALETTES else 0


def _shared_refs(params):
    """Index fields stored the same way in V4 and V5: border, stitch, size."""
    border = params.get("border_style", "none") or "none"
    stitch = params.get("quilt_stitch") or None
    stitch_idx = (_V2_STITCH.index(stitch) + 1) if stitch in _V2_STITCH else 0
    size = params.get("quilt_size") or _V4_DEFAULT_QUILT_SIZE
    if size not in _V4_QUILT_SIZES:
        size = _V4_DEFAULT_QUILT_SIZE
    return _V2_BORDER.index(border), stitch_idx, _V4_QUILT_SIZES.index(size)


def _fine(field, value):
    """A V5 fractional field: (value as an exact multiple of its step, bits)."""
    bits, scale = _V5_FINE[field]
    return (round(value * scale), bits)


def encode(params):
    """Encode a params dict to a 20-character quilt ID string (version 5).

    >>> p = {'seed': 12345, 'palette': 'ocean breeze', 'symmetry': 'bargello',
    ...      'chaos': 0.3, 'rows': 16, 'cols': 16, 'n_patterns': 2,
    ...      'n_colors': 4, 'tile_size': 0, 'tile_variation': 0.05,
    ...      'border_style': 'none', 'mega_frac': 0.0, 'plain_frac': 0.0,
    ...      'quilt_stitch': 'sashiko_wave', 'wonky': 0.04}
    >>> qid = encode(p)
    >>> len(qid)
    20
    >>> decode(qid)['seed'], decode(qid)['symmetry'], decode(qid)['quilt_stitch']
    (12345, 'bargello', 'sashiko_wave')

    Fractional controls come back exactly — V4 rounded these to coarse steps,
    so wonky 0.037 or plain 0.15 reopened as a different quilt:

    >>> q = dict(p, wonky=0.037, plain_frac=0.15, mega_frac=0.05, strippy=0.23,
    ...          wash_alpha=0.05, palette_2='thistle', palette_mix='bluebell',
    ...          quilt_size='queen')
    >>> back = decode(encode(q))
    >>> [back[f] for f in ('wonky', 'plain_frac', 'mega_frac', 'strippy', 'wash_alpha')]
    [0.037, 0.15, 0.05, 0.23, 0.05]
    >>> back['palette_2'], back['palette_mix'], back['quilt_size']
    ('thistle', 'bluebell', 'queen')

    Older IDs still decode:

    >>> decode('6PpafDL86tkRBR')['n_colors']
    5
    >>> decode(_encode_v4(p))['wonky']
    0.04
    """
    border_idx, stitch_idx, size_idx = _shared_refs(params)
    fields = [
        (5, 4),  # version
        (params["seed"] & ((1 << 31) - 1), 31),
        (_V2_PALETTES.index(params["palette"]), 5),
        (_V2_SYMMETRY.index(params["symmetry"]), 4),
        _fine("chaos", params["chaos"]),
        (params["rows"] - 14, 3),
        (params["n_patterns"] - 1, 1),
        (params["n_colors"] - 3, 2),
        (params.get("tile_size", 0), 4),
        _fine("tile_variation", params.get("tile_variation", 0.0)),
        (border_idx, 2),
        _fine("mega_frac", params.get("mega_frac", 0.0)),
        _fine("plain_frac", params.get("plain_frac", 0.0)),
        (stitch_idx, 3),
        _fine("wonky", params.get("wonky", 0.0)),
        _fine("strippy", params.get("strippy", 0.0)),
        _fine("wash_alpha", params.get("wash_alpha", 0.0)),
        (_palette_ref(params.get("palette_2")), 5),
        (_palette_ref(params.get("palette_mix")), 5),
        (size_idx, 3),
    ]
    return _b58enc(_pack(fields), _V5_LEN)


def _encode_v4(params):
    """Encode to an 18-character V4 ID. FROZEN — kept so tests can mint V4
    IDs and prove they still decode; nothing should emit V4 any more."""
    border_idx, stitch_idx, size_idx = _shared_refs(params)
    fields = [
        (4, 4),  # version
        (params["seed"] & ((1 << 31) - 1), 31),
        (_V2_PALETTES.index(params["palette"]), 5),
        (_V2_SYMMETRY.index(params["symmetry"]), 4),
        (round(params["chaos"] * 100), 7),
        (params["rows"] - 14, 3),
        (params["n_patterns"] - 1, 1),
        (params["n_colors"] - 3, 2),
        (params.get("tile_size", 0), 4),
        (round(params.get("tile_variation", 0.0) * 100), 5),
        (border_idx, 2),
        (_quantize(params.get("mega_frac", 0.0), 0.10, 0.01, 15), 4),
        (_quantize(params.get("plain_frac", 0.0), 0.10, 0.02, 15), 4),
        (stitch_idx, 3),
        (_encode_wonky(params.get("wonky", 0.0)), 2),
        (_quantize(params.get("strippy", 0.0), 0.05, 0.05, 12), 4),
        (_quantize(params.get("wash_alpha", 0.0), 0.02, 0.02, 10), 4),
        (_palette_ref(params.get("palette_2")), 5),
        (_palette_ref(params.get("palette_mix")), 5),
        (size_idx, 3),
    ]
    return _b58enc(_pack(fields), _V4_LEN)


def _decode_shared(raw):
    """Fields V2-V5 store identically. V4-only fields fall back to their "off"
    values for V2/V3 IDs, so callers always get the same dict shape."""
    stitch_idx = raw["quilt_stitch"]
    return {
        "seed": raw["seed"],
        "palette": _V2_PALETTES[raw["palette"]],
        "symmetry": _V2_SYMMETRY[raw["symmetry"]],
        "rows": raw["rows"] + 14,
        "cols": raw["rows"] + 14,
        "n_patterns": raw["n_patterns"] + 1,
        "n_colors": raw["n_colors"] + 3,
        "tile_size": raw["tile_size"],
        "border_style": _V2_BORDER[raw["border_style"]],
        "sash_width": 0,
        "cornerstones": False,
        "color_gradient": "none",
        "quilt_stitch": _V2_STITCH[stitch_idx - 1] if stitch_idx else None,
        "palette_2": _V2_PALETTES[raw["palette_2"] - 1] if raw.get("palette_2") else None,
        "palette_mix": _V2_PALETTES[raw["palette_mix"] - 1] if raw.get("palette_mix") else None,
        "quilt_size": _V4_QUILT_SIZES[
            raw.get("quilt_size", _V4_QUILT_SIZES.index(_V4_DEFAULT_QUILT_SIZE))
        ],
    }


def _decode_v2_v3_v4(n, schema):
    """Decoder for V2/V3/V4, whose fractional fields use coarse quantization."""
    raw = _unpack(n, schema)
    return {
        **_decode_shared(raw),
        "chaos": round(raw["chaos"] / 100, 2),
        "tile_variation": round(raw["tile_variation"] / 100, 2),
        "mega_frac": _dequantize(raw["mega_frac"], 0.10, 0.01),
        "plain_frac": _dequantize(raw["plain_frac"], 0.10, 0.02),
        "wonky": _V2_WONKY[raw["wonky"]],
        "strippy": _dequantize(raw.get("strippy", 0), 0.05, 0.05),
        "wash_alpha": _dequantize(raw.get("wash_alpha", 0), 0.02, 0.02),
    }


def _from_steps(field, steps):
    """A V5 fractional field's value from its stored integer step count."""
    scale = _V5_FINE[field][1]
    return round(steps / scale, len(str(scale)) - 1)


def snap(field, value):
    """`value` rounded to what a V5 ID stores for `field` — exactly the value
    decode() returns, so a quilt rendered from the snapped value matches its ID.

    >>> snap("wonky", 0.0371), snap("plain_frac", 0.153)
    (0.037, 0.15)
    """
    return _from_steps(field, round(value * _V5_FINE[field][1]))


def _decode_v5(n):
    """Decoder for V5: fractional fields are exact multiples of their step."""
    raw = _unpack(n, _V5_SCHEMA)
    fine = {field: _from_steps(field, raw[field]) for field in _V5_FINE}
    return {**_decode_shared(raw), **fine}


def decode(qid):
    """Decode a quilt ID string back to a params dict.

    V1 (13 chars), V2/V3 (14 chars), V4 (18 chars) and V5 (20 chars) are
    supported; versions are told apart by length.

    >>> p = {'seed': 99999, 'palette': 'ocean breeze', 'symmetry': 'bargello',
    ...      'chaos': 0.55, 'rows': 16, 'cols': 16, 'n_patterns': 2,
    ...      'n_colors': 4, 'tile_size': 5, 'tile_variation': 0.1,
    ...      'border_style': 'checkerboard', 'mega_frac': 0.15, 'plain_frac': 0.2,
    ...      'quilt_stitch': 'grid', 'wonky': 0.0}
    >>> decoded = decode(encode(p))
    >>> decoded['palette']
    'ocean breeze'
    >>> decoded['symmetry']
    'bargello'
    >>> decoded['quilt_stitch']
    'grid'
    >>> abs(decoded['chaos'] - 0.55) < 0.01
    True
    >>> abs(decoded['mega_frac'] - 0.15) < 0.02
    True
    """
    n = _b58dec(qid)

    if len(qid) == _V1_LEN:
        version = n >> (_V1_TOTAL_BITS - 4)
        if version == 1:
            raw = _unpack(n, _V1_SCHEMA)
            return {
                "seed": raw["seed"],
                "palette": _V1_PALETTES[raw["palette"]],
                "symmetry": _V1_SYMMETRY[raw["symmetry"]],
                "chaos": round(raw["chaos"] / 100, 2),
                "rows": raw["rows"] + 14,
                "cols": raw["rows"] + 14,
                "n_patterns": raw["n_patterns"] + 1,
                "n_colors": raw["n_colors"] + 3,
                "tile_size": raw["tile_size"],
                "tile_variation": round(raw["tile_variation"] / 100, 2),
                "border_style": _V1_BORDER[raw["border_style"]],
                "sash_width": 5 if raw["sash_width"] else 0,
                "cornerstones": bool(raw["cornerstones"]),
                "color_gradient": _V1_GRADIENT[raw["color_gradient"]],
                "mega_frac": _dequantize(raw["mega_frac"], 0.10, 0.01),
                "plain_frac": _dequantize(raw["plain_frac"], 0.10, 0.02),
            }

    if len(qid) == _V2_LEN:
        # Try V3 first (81 bits), then V2 (80 bits)
        version = n >> (_V3_TOTAL_BITS - 4)
        if version == 3:
            return _decode_v2_v3_v4(n, _V3_SCHEMA)
        version = n >> (_V2_TOTAL_BITS - 4)
        if version == 2:
            return _decode_v2_v3_v4(n, _V2_SCHEMA)

    if len(qid) == _V4_LEN:
        if n >> (_V4_TOTAL_BITS - 4) == 4:
            return _decode_v2_v3_v4(n, _V4_SCHEMA)

    if len(qid) == _V5_LEN:
        if n >> (_V5_TOTAL_BITS - 4) == 5:
            return _decode_v5(n)

    raise ValueError(f"Unknown quilt ID version (len={len(qid)})")


def _decode_cmd(args):
    """Handle the decode subcommand."""
    if len(args) < 1:
        print("decode requires an ID argument")
        sys.exit(1)
    params = decode(args[0])
    if "--command" in args:
        parts = [
            "python quilt.py",
            f"--rows {params['rows']}",
            f"--cols {params['cols']}",
            f'--palette "{params["palette"]}"',
            f"--symmetry {params['symmetry']}",
            f"--chaos {params['chaos']}",
            f"--seed {params['seed']}",
            f"--n-patterns {params['n_patterns']}",
            f"--n-colors {params['n_colors']}",
            f"--tile-size {params['tile_size']}",
            f"--tile-variation {params['tile_variation']}",
        ]
        if params.get("border_style") and params["border_style"] != "none":
            parts.append(f"--border-style {params['border_style']}")
        if params.get("mega_frac", 0.0) > 0.0:
            parts.append(f"--mega-frac {params['mega_frac']}")
        if params.get("plain_frac", 0.0) > 0.0:
            parts.append(f"--plain-frac {params['plain_frac']}")
        parts.append("--output out.png")
        print(" \\\n  ".join(parts))
    else:
        print(json.dumps(params, indent=2))


def _cli():
    usage = """Usage:
  python quilt_id.py decode <id>           decode ID → params JSON
  python quilt_id.py decode <id> --command print quilt.py render command
  python quilt_id.py encode <params.json>  encode params file → ID
  python quilt_id.py test                  run doctests
"""
    if len(sys.argv) < 2:
        print(usage)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "decode":
        _decode_cmd(sys.argv[2:])

    elif cmd == "encode":
        if len(sys.argv) < 3:
            print("encode requires a params JSON file argument")
            sys.exit(1)
        with open(sys.argv[2], encoding="utf-8") as f:
            params = json.load(f)
        print(encode(params))

    elif cmd == "test":
        import doctest  # pylint: disable=import-outside-toplevel

        doctest.testmod(verbose=True)

    else:
        print(usage)
        sys.exit(1)


if __name__ == "__main__":
    _cli()
