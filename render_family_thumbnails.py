"""One-shot script: pre-render family thumbnail PNGs for the generator landing page.

Run locally and commit the output:
    python render_family_thumbnails.py
"""
from pathlib import Path
from generator import PRESETS
from sampler import params_to_render_kwargs
from quilt import render_quilt

_OUT = Path("static/generator/families")
_BLOCK_SIZE = 25  # ~400px for a 16-row quilt


def main():
    _OUT.mkdir(parents=True, exist_ok=True)
    for key, preset in PRESETS.items():
        out_path = _OUT / f"{key}.png"
        kwargs = params_to_render_kwargs(preset["params"], block_size=_BLOCK_SIZE)
        png_bytes = render_quilt(**kwargs)
        out_path.write_bytes(png_bytes)
        print(f"  {out_path}")
    print(f"Done. {len(PRESETS)} thumbnails written to {_OUT}/")


if __name__ == "__main__":
    main()
