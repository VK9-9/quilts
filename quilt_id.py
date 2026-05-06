#!/usr/bin/env python3
"""Compact identifier for quilt parameter sets.

Encodes all parameters needed to reproduce a quilt into a short base58 string.
The version field (top 4 bits) selects the decode schema, so new params can be
added in future versions without breaking existing IDs.

Version 1: 76 bits → 13 base58 characters
    version(4) seed(31) palette(4) symmetry(3) chaos(7) rows(3)
    n_patterns(1) n_colors(1) tile_size(4) tile_variation(5)
    border_style(2) sash_width(1) cornerstones(1) color_gradient(1)
    mega_frac(4) plain_frac(4)

To add parameters in a future round: define _V2_SCHEMA with the new fields,
add a version==2 branch in decode(), and update encode() to write version 2.
Old version-1 IDs will still decode correctly via the version==1 branch.

Usage:
    from quilt_id import encode, decode
    qid = encode(params)          # e.g. "3xKm7pRt2nWqA"
    params = decode(qid)
"""

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
    "autumn harvest", "ocean breeze", "wildflower", "farmhouse",
    "winter sky", "stained glass", "indigo dye", "deep sea",
    "plum and gold", "storm", "northern lights",
]

# Active symmetry modes (3 bits → max 7 entries)
_V1_SYMMETRY = ["none", "mirror", "rotational", "stripe", "partial"]

_V1_BORDER   = ["none", "solid", "checkerboard", "piano_keys"]  # 2 bits
_V1_GRADIENT = ["none", "diagonal"]                              # 1 bit

# Bit layout — total must equal _V1_TOTAL_BITS
_V1_SCHEMA = [
    ("version",        4),
    ("seed",          31),
    ("palette",        4),
    ("symmetry",       3),
    ("chaos",          7),  # 0–80 representing 0.00–0.80 in steps of 0.01
    ("rows",           3),  # offset 14: stored as rows-14, range 0–5
    ("n_patterns",     1),  # offset 1: stored as n_patterns-1
    ("n_colors",       1),  # offset 3: stored as n_colors-3
    ("tile_size",      4),  # 0–10
    ("tile_variation", 5),  # 0–30 representing 0.00–0.30 in steps of 0.01
    ("border_style",   2),
    ("sash_width",     1),  # 0=off, 1=5px
    ("cornerstones",   1),
    ("color_gradient", 1),
    ("mega_frac",      4),  # 0=off, 1–15 → 0.10–0.24 in steps of 0.01
    ("plain_frac",     4),  # 0=off, 1–15 → 0.10–0.38 in steps of 0.02
]

_V1_TOTAL_BITS = sum(bits for _, bits in _V1_SCHEMA)  # 76
_V1_LEN = 13   # ceil(76 / log2(58)) = 13 chars


def _pack(schema_values):
    """Pack list of (value, nbits) tuples into a single int, MSB first."""
    n = 0
    for val, nbits in schema_values:
        n = (n << nbits) | (val & ((1 << nbits) - 1))
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


def encode(params):
    """Encode a params dict to a 13-character quilt ID string.

    >>> p = {'seed': 12345, 'palette': 'ocean breeze', 'symmetry': 'partial',
    ...      'chaos': 0.3, 'rows': 16, 'cols': 16, 'n_patterns': 2,
    ...      'n_colors': 4, 'tile_size': 0, 'tile_variation': 0.05,
    ...      'border_style': 'none', 'sash_width': 0, 'cornerstones': False,
    ...      'color_gradient': 'none', 'mega_frac': 0.0, 'plain_frac': 0.0}
    >>> qid = encode(p)
    >>> len(qid)
    13
    >>> decode(qid)['seed']
    12345
    >>> decode(qid)['palette']
    'ocean breeze'
    """
    border   = params.get("border_style",   "none") or "none"
    gradient = params.get("color_gradient", "none") or "none"

    fields = [
        (1,                                                            4),  # version
        (params["seed"] & ((1 << 31) - 1),                           31),
        (_V1_PALETTES.index(params["palette"]),                        4),
        (_V1_SYMMETRY.index(params["symmetry"]),                       3),
        (round(params["chaos"] * 100),                                 7),
        (params["rows"] - 14,                                          3),
        (params["n_patterns"] - 1,                                     1),
        (params["n_colors"] - 3,                                       1),
        (params.get("tile_size", 0),                                   4),
        (round(params.get("tile_variation", 0.0) * 100),               5),
        (_V1_BORDER.index(border),                                     2),
        (1 if params.get("sash_width", 0) > 0 else 0,                 1),
        (1 if params.get("cornerstones", False) else 0,                1),
        (_V1_GRADIENT.index(gradient),                                 1),
        (_quantize(params.get("mega_frac",  0.0), 0.10, 0.01, 15),    4),
        (_quantize(params.get("plain_frac", 0.0), 0.10, 0.02, 15),    4),
    ]
    return _b58enc(_pack(fields), _V1_LEN)


def decode(qid):
    """Decode a quilt ID string back to a params dict.

    >>> p = {'seed': 99999, 'palette': 'farmhouse', 'symmetry': 'mirror',
    ...      'chaos': 0.55, 'rows': 14, 'cols': 14, 'n_patterns': 1,
    ...      'n_colors': 3, 'tile_size': 5, 'tile_variation': 0.1,
    ...      'border_style': 'checkerboard', 'sash_width': 5,
    ...      'cornerstones': True, 'color_gradient': 'diagonal',
    ...      'mega_frac': 0.15, 'plain_frac': 0.2}
    >>> decoded = decode(encode(p))
    >>> decoded['palette']
    'farmhouse'
    >>> decoded['sash_width']
    5
    >>> decoded['cornerstones']
    True
    >>> abs(decoded['chaos'] - 0.55) < 0.01
    True
    >>> abs(decoded['mega_frac'] - 0.15) < 0.02
    True
    """
    n = _b58dec(qid)
    version = n >> (_V1_TOTAL_BITS - 4)

    if version == 1:
        raw = _unpack(n, _V1_SCHEMA)
        return {
            "seed":           raw["seed"],
            "palette":        _V1_PALETTES[raw["palette"]],
            "symmetry":       _V1_SYMMETRY[raw["symmetry"]],
            "chaos":          round(raw["chaos"] / 100, 2),
            "rows":           raw["rows"] + 14,
            "cols":           raw["rows"] + 14,
            "n_patterns":     raw["n_patterns"] + 1,
            "n_colors":       raw["n_colors"] + 3,
            "tile_size":      raw["tile_size"],
            "tile_variation": round(raw["tile_variation"] / 100, 2),
            "border_style":   _V1_BORDER[raw["border_style"]],
            "sash_width":     5 if raw["sash_width"] else 0,
            "cornerstones":   bool(raw["cornerstones"]),
            "color_gradient": _V1_GRADIENT[raw["color_gradient"]],
            "mega_frac":      _dequantize(raw["mega_frac"],  0.10, 0.01),
            "plain_frac":     _dequantize(raw["plain_frac"], 0.10, 0.02),
        }

    raise ValueError(f"Unknown quilt ID version: {version}")


def _cli():
    import sys
    import json

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
        if len(sys.argv) < 3:
            print("decode requires an ID argument")
            sys.exit(1)
        params = decode(sys.argv[2])
        if "--command" in sys.argv:
            parts = [
                "python quilt.py",
                f"--rows {params['rows']}",
                f"--cols {params['cols']}",
                f"--palette \"{params['palette']}\"",
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
            if params.get("sash_width", 0) > 0:
                parts.append(f"--sash-width {params['sash_width']}")
            if params.get("cornerstones"):
                parts.append("--cornerstones")
            if params.get("mega_frac", 0.0) > 0.0:
                parts.append(f"--mega-frac {params['mega_frac']}")
            if params.get("plain_frac", 0.0) > 0.0:
                parts.append(f"--plain-frac {params['plain_frac']}")
            parts.append("--output out.png")
            print(" \\\n  ".join(parts))
        else:
            print(json.dumps(params, indent=2))

    elif cmd == "encode":
        if len(sys.argv) < 3:
            print("encode requires a params JSON file argument")
            sys.exit(1)
        with open(sys.argv[2], encoding="utf-8") as f:
            params = json.load(f)
        print(encode(params))

    elif cmd == "test":
        import doctest
        doctest.testmod(verbose=True)

    else:
        print(usage)
        sys.exit(1)


if __name__ == "__main__":
    _cli()
