"""One-shot script: pre-render family thumbnail PNGs for the generator landing page.

Run locally and commit the output:
    python render_family_thumbnails.py

Params go through generator.complete_params() — the same filling the /create
page does — so a card's thumbnail always matches the quilt you land on when
you click it.
"""

from pathlib import Path
from generator import PRESETS, complete_params
from render_params import params_to_render_kwargs
from quilt import render_quilt

_OUT = Path("static/generator/families")
_BLOCK_SIZE = 25  # ~400px for a 16-row quilt


def main():
    """Render all preset family thumbnails to static/generator/families/."""
    _OUT.mkdir(parents=True, exist_ok=True)
    for key, preset in PRESETS.items():
        out_path = _OUT / f"{key}.png"
        kwargs = params_to_render_kwargs(complete_params(preset["params"]), _BLOCK_SIZE)
        png_bytes = render_quilt(**kwargs)
        out_path.write_bytes(png_bytes)
        print(f"  {out_path}")
    print(f"Done. {len(PRESETS)} thumbnails written to {_OUT}/")


if __name__ == "__main__":
    main()
