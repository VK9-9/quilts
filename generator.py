"""Public-facing quilt generator webapp.

Routes:
    GET /               Families landing page (preset style cards)
    GET /create         Param editor with live preview
    GET /render         Render quilt PNG from query params
    GET /download       Same as /render but as file download
"""

import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(__file__))

# pylint: disable=wrong-import-position
from flask import Flask, render_template, request, Response, has_request_context
from quilt import render_quilt, BORDER_STYLES as _QUILT_BORDER_STYLES
from quilt_id import encode, decode, _V2_PALETTES, _V2_SYMMETRY, _V2_STITCH
from render_params import params_to_render_kwargs
# pylint: enable=wrong-import-position

app = Flask(__name__)

# Build info — captured once at import time
# Railway sets RAILWAY_GIT_COMMIT_SHA; fall back to local git
_COMMIT = os.environ.get("RAILWAY_GIT_COMMIT_SHA", "")[:7]
if not _COMMIT:
    try:
        _COMMIT = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        _COMMIT = "unknown"
_BUILD_TIME = (
    __import__("datetime")
    .datetime.now(__import__("datetime").timezone.utc)
    .strftime("%Y-%m-%d %H:%M UTC")
)


# Deployed instance, for the dev-only "view this page on prod" link.
_PROD_BASE = "https://quilty.up.railway.app"
_LOCAL_HOSTS = ("localhost", "127.0.0.1", "0.0.0.0")


def _prod_equivalent_url():
    """When served from a local host, the same path+query on the prod instance.

    Returns None in prod (or outside a request) so the link only appears in dev.
    """
    if not has_request_context() or request.host.split(":")[0] not in _LOCAL_HOSTS:
        return None
    path = request.full_path
    if path.endswith("?"):  # full_path appends a bare "?" when there's no query
        path = path[:-1]
    return _PROD_BASE + path


@app.context_processor
def _inject_build_info():
    return {
        "build_commit": _COMMIT,
        "build_time": _BUILD_TIME,
        "prod_link": _prod_equivalent_url(),
    }


PALETTE_NAMES = _V2_PALETTES
SYMMETRY_NAMES = _V2_SYMMETRY
BORDER_STYLES = ["none"] + _QUILT_BORDER_STYLES
STITCH_STYLES = ["none"] + _V2_STITCH

# ---------------------------------------------------------------------------
# Preset families — shown as cards on the landing page.
# Seeds are fixed so thumbnails are stable/reproducible.
# ---------------------------------------------------------------------------
PRESETS = {
    "bargello-calm": {
        "name": "Bargello — Calm",
        "description": "Gentle undulating waves in soft lavender",
        "params": {
            "palette": "lavender fields",
            "symmetry": "bargello",
            "chaos": 0.15,
            "rows": 16,
            "n_colors": 4,
            "tile_size": 6,
            "tile_variation": 0.1,
            "border_style": "none",
            "mega_frac": 0.0,
            "plain_frac": 0.0,
            "quilt_stitch": "grid",
            "wonky": 0.0,
            "seed": 1001,
        },
    },
    "bargello-bold": {
        "name": "Bargello — Bold",
        "description": "High-contrast waves with deep indigo tones",
        "params": {
            "palette": "indigo dye",
            "symmetry": "bargello",
            "chaos": 0.55,
            "rows": 18,
            "n_colors": 4,
            "tile_size": 5,
            "tile_variation": 0.15,
            "border_style": "solid",
            "mega_frac": 0.0,
            "plain_frac": 0.0,
            "quilt_stitch": "diagonal",
            "wonky": 0.0,
            "seed": 1002,
        },
    },
    "mirror-geometric": {
        "name": "Mirror — Geometric",
        "description": "Clean four-fold reflection with ocean tones",
        "params": {
            "palette": "ocean breeze",
            "symmetry": "mirror",
            "chaos": 0.30,
            "rows": 16,
            "n_colors": 4,
            "tile_size": 7,
            "tile_variation": 0.1,
            "border_style": "none",
            "mega_frac": 0.0,
            "plain_frac": 0.0,
            "quilt_stitch": "sashiko_wave",
            "wonky": 0.0,
            "seed": 1003,
        },
    },
    "rotational-lively": {
        "name": "Rotational — Lively",
        "description": "Spinning energy with wildflower colours",
        "params": {
            "palette": "wildflower",
            "symmetry": "rotational",
            "chaos": 0.55,
            "rows": 16,
            "n_colors": 4,
            "tile_size": 6,
            "tile_variation": 0.2,
            "border_style": "none",
            "mega_frac": 0.0,
            "plain_frac": 0.0,
            "quilt_stitch": "grid",
            "wonky": 0.0,
            "seed": 1004,
        },
    },
    "stripe-serene": {
        "name": "Stripe — Serene",
        "description": "Calm banded layout in northern lights palette",
        "params": {
            "palette": "northern lights",
            "symmetry": "stripe",
            "chaos": 0.20,
            "rows": 16,
            "n_colors": 4,
            "tile_size": 8,
            "tile_variation": 0.05,
            "border_style": "none",
            "mega_frac": 0.0,
            "plain_frac": 0.0,
            "quilt_stitch": "diagonal",
            "wonky": 0.0,
            "seed": 1005,
        },
    },
    "flower-medallion": {
        "name": "Flower — Medallion",
        "description": "Centred bloom radiating outward in cherry blossom",
        "params": {
            "palette": "cherry blossom",
            "symmetry": "flower",
            "chaos": 0.40,
            "rows": 16,
            "n_colors": 4,
            "tile_size": 6,
            "tile_variation": 0.1,
            "border_style": "none",
            "mega_frac": 0.0,
            "plain_frac": 0.0,
            "quilt_stitch": "sashiko_asanoha",
            "wonky": 0.0,
            "seed": 1006,
        },
    },
    "emergent-wild": {
        "name": "Emergent — Wild",
        "description": "Macro patterns emerge from coordinated block rotations",
        "params": {
            "palette": "wisteria",
            "symmetry": "emergent",
            "chaos": 0.70,
            "rows": 18,
            "n_colors": 4,
            "tile_size": 5,
            "tile_variation": 0.2,
            "border_style": "none",
            "mega_frac": 0.0,
            "plain_frac": 0.0,
            "quilt_stitch": "grid",
            "wonky": 0.0,
            "seed": 1007,
        },
    },
    "improv-wonky": {
        "name": "Improv — Wonky",
        "description": "Modern improv quilting with jittered vertices",
        "params": {
            "palette": "thistle",
            "symmetry": "none",
            "chaos": 0.60,
            "rows": 16,
            "n_colors": 4,
            "tile_size": 6,
            "tile_variation": 0.15,
            "border_style": "none",
            "mega_frac": 0.0,
            "plain_frac": 0.0,
            "quilt_stitch": "diagonal",
            "wonky": 0.05,
            "seed": 1008,
        },
    },
}

_RENDER_BLOCK_SIZE = 36  # ~576px for a 16-row quilt
_DOWNLOAD_BLOCK_SIZE = 72  # ~1152px for download

QUILT_SIZES = {
    "throw": (50, 65, 'Throw (50" x 65")'),
    "twin": (65, 85, 'Twin (65" x 85")'),
    "queen": (85, 108, 'Queen (85" x 108")'),
    "king": (110, 108, 'King (110" x 108")'),
    "sq6": (72, 72, 'Square 6\' (72" x 72")'),
    "sq8": (96, 96, 'Square 8\' (96" x 96")'),
    "sq10": (120, 120, 'Square 10\' (120" x 120")'),
}


# Hard server-side bounds on numeric render params. The HTML controls cap these
# client-side, but the endpoints are public so the raw query string is untrusted:
# an unbounded rows/tile_size/strippy inflates the cairo surface to gigapixels
# and OOMs the worker. (lo, hi) per key; values are clamped, not rejected.
_PARAM_BOUNDS = {
    "rows": (14, 21),
    "n_colors": (3, 6),
    "tile_size": (0, 12),
    "tile_variation": (0.0, 0.5),
    "chaos": (0.0, 1.0),
    "mega_frac": (0.0, 0.5),
    "plain_frac": (0.0, 0.5),
    "wonky": (0.0, 0.1),
    "strippy": (0.0, 0.6),
    "wash_alpha": (0.0, 0.3),
    "seed": (0, 2**31 - 1),
}

# Default value for every control the /create UI binds. This is the single
# source of truth: the query-string parser falls back to it, and complete_params()
# fills it in for callers whose param dict has holes.
_DEFAULTS = {
    "palette": "lavender fields",
    "symmetry": "bargello",
    "chaos": 0.3,
    "rows": 16,
    "n_patterns": 2,
    "n_colors": 4,
    "tile_size": 6,
    "tile_variation": 0.1,
    "border_style": "none",
    "mega_frac": 0.0,
    "plain_frac": 0.0,
    "quilt_stitch": None,
    "wonky": 0.0,
    "strippy": 0.0,
    "wash_alpha": 0.0,
    "palette_2": None,
    "palette_mix": None,
    "quilt_size": "sq8",
    "seed": 42,
}


def _cols_for(rows, size_key):
    """Column count that gives `rows` the aspect ratio of the named quilt size."""
    size_w, size_h, _ = QUILT_SIZES.get(size_key, QUILT_SIZES[_DEFAULTS["quilt_size"]])
    return round(rows * size_w / size_h)


def complete_params(params):
    """Fill in any control missing from `params` and derive cols.

    Presets omit the advanced controls, and decode() can only return what the
    quilt-ID schema carries, so both arrive here with holes. Every control the
    template binds needs a real value: Jinja renders a missing key as the empty
    string, and an empty value on an <input type=range> is resolved by the
    browser to the slider midpoint — which silently turned an absent strippy
    into strippy=0.3 on every preset and shared-ID page load.
    """
    full = dict(_DEFAULTS)
    full.update(params)
    full["cols"] = _cols_for(full["rows"], full["quilt_size"])
    return full


def _params_from_request(defaults=None):
    """Parse quilt params from query string, falling back to defaults."""
    a = request.args
    base = defaults or {}

    def _get(key, cast):
        v = a.get(key)
        if v is not None:
            try:
                v = cast(v)
            except (ValueError, TypeError):
                v = base.get(key, _DEFAULTS[key])
        else:
            v = base.get(key, _DEFAULTS[key])
        lo_hi = _PARAM_BOUNDS.get(key)
        if lo_hi is not None and isinstance(v, (int, float)):
            v = max(lo_hi[0], min(v, lo_hi[1]))
        return v

    def _choice(key, valid):
        v = a.get(key, base.get(key, _DEFAULTS[key]))
        return v if v in valid else _DEFAULTS[key]

    stitch = _choice("quilt_stitch", STITCH_STYLES)
    if stitch == "none":
        stitch = None

    rows = _get("rows", int)
    size_key = _choice("quilt_size", QUILT_SIZES)
    return {
        "palette": _choice("palette", PALETTE_NAMES),
        "symmetry": _choice("symmetry", SYMMETRY_NAMES),
        "chaos": _get("chaos", float),
        "rows": rows,
        "cols": _cols_for(rows, size_key),
        "quilt_size": size_key,
        "n_patterns": _DEFAULTS["n_patterns"],
        "n_colors": _get("n_colors", int),
        "tile_size": _get("tile_size", int),
        "tile_variation": _get("tile_variation", float),
        "border_style": _choice("border_style", BORDER_STYLES),
        "mega_frac": _get("mega_frac", float),
        "plain_frac": _get("plain_frac", float),
        "quilt_stitch": stitch,
        "wonky": _get("wonky", float),
        "strippy": _get("strippy", float),
        "wash_alpha": _get("wash_alpha", float),
        "palette_2": a.get("palette_2", base.get("palette_2")) or None,
        "palette_mix": a.get("palette_mix", base.get("palette_mix")) or None,
        "seed": _get("seed", int),
    }


def _render_png(params, block_size):
    """Render params to PNG bytes at the given block_size."""
    kwargs = params_to_render_kwargs(params, block_size=block_size)
    return render_quilt(**kwargs)


@app.route("/")
def index():
    """Families landing page."""
    return render_template("generator/index.html", presets=PRESETS)


def _create_params():
    """Resolve the params the /create editor should open with.

    Three sources, in priority order: an explicit quilt ID, a named preset,
    then the query string. The first two are partial — neither carries every
    control — so both go through complete_params().
    """
    qid = request.args.get("id")
    if qid:
        try:
            return complete_params(decode(qid))
        except (ValueError, KeyError, IndexError):
            pass

    preset_key = request.args.get("preset")
    if preset_key in PRESETS:
        return complete_params(PRESETS[preset_key]["params"])

    return _params_from_request()


@app.route("/create")
def create():
    """Param editor page."""
    return render_template(
        "generator/create.html",
        params=_create_params(),
        palette_names=PALETTE_NAMES,
        symmetry_names=SYMMETRY_NAMES,
        border_styles=BORDER_STYLES,
        stitch_styles=STITCH_STYLES,
        quilt_sizes=QUILT_SIZES,
    )


@app.route("/render")
def render():
    """Render quilt PNG from query params."""
    params = _params_from_request()
    try:
        qid = encode(params)
    except (ValueError, KeyError):
        qid = "unknown"
    png_bytes = _render_png(params, _RENDER_BLOCK_SIZE)
    return Response(
        png_bytes, mimetype="image/png", headers={"Cache-Control": "no-store", "X-Quilt-Id": qid}
    )


@app.route("/download")
def download():
    """Render high-res quilt PNG as file download."""
    params = _params_from_request()
    try:
        qid = encode(params)
    except (ValueError, KeyError):
        qid = "unknown"
    png_bytes = _render_png(params, _DOWNLOAD_BLOCK_SIZE)
    return Response(
        png_bytes,
        mimetype="image/png",
        headers={
            "Content-Disposition": f'attachment; filename="quilt-{qid}.png"',
            "Cache-Control": "no-store",
        },
    )


@app.route("/pattern")
def pattern():
    """Generate PDF sewing pattern for the current quilt."""
    # Imported lazily: reportlab is ~17 MB and is only needed by this route,
    # so it stays out of every worker's baseline footprint.
    from pattern_pdf import generate_pattern_pdf  # pylint: disable=import-outside-toplevel

    params = _params_from_request()
    try:
        qid = encode(params)
    except (ValueError, KeyError):
        qid = "unknown"
    size_key = request.args.get("quilt_size", "sq8")
    size_w, size_h, _ = QUILT_SIZES.get(size_key, QUILT_SIZES["sq8"])
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        generate_pattern_pdf(params, tmp_path, quilt_w=size_w, quilt_h=size_h)
        with open(tmp_path, "rb") as f:
            pdf_bytes = f.read()
    finally:
        os.unlink(tmp_path)
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="pattern-{qid}.pdf"',
            "Cache-Control": "no-store",
        },
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    # Default debug off: this app is public, and the Werkzeug debugger exposes an
    # RCE console. Opt in locally with FLASK_DEBUG=1. (Production runs gunicorn,
    # which ignores this block, but never ship debug=True in source.)
    debug = os.environ.get("FLASK_DEBUG") == "1"
    app.run(debug=debug, port=port)
