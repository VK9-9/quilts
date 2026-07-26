# Generator Webapp — Product Design & Code Plan

## Goal
A public-facing quilt generator deployed on Railway. Users browse style families,
pick one, then tweak params interactively to create a custom quilt they can download.
Totally separate from `app.py` (the private scoring webapp).

## File Layout
```
generator.py            Flask app (new)
templates/
  generator/
    index.html          Families landing page
    create.html         Param editor + live preview
static/
  generator/
    families/           Pre-rendered family thumbnails (PNG, ~400px)
      bargello-calm.png
      mirror-lively.png
      ... (8-12 presets)
Procfile                web: gunicorn generator:app
nixpacks.toml           system deps: libcairo2-dev pkg-config
```

## Routes

### `GET /`
Families landing page. Shows a grid of preset style cards.
Each card: thumbnail image, name, short description.
Clicking navigates to `/create?preset=<name>`.

### `GET /create`
Param editor. Query params:
- `preset=<name>` — load preset defaults (from PRESETS dict)
- `id=<quilt_id>` — load from encoded V2 quilt ID (for share links)
- All individual params as fallback (palette, symmetry, chaos, etc.)

Page layout: sidebar (controls) + main (quilt image).
Image is an `<img>` tag pointing to `/render?<params>`.
Controls update the URL and the img src on change.

### `GET /render`
Renders quilt PNG from query params, returns image/png.
Params: palette, symmetry, chaos, rows, tile_size, tile_variation,
        border_style, n_colors, mega_frac, plain_frac,
        quilt_stitch, wonky, seed
Defaults applied for missing params.

### `GET /download`
Same as /render but with Content-Disposition: attachment header.

## Preset Families (8 cards on landing page)
Pre-rendered thumbnails committed to static/generator/families/.

| preset name        | symmetry    | chaos | palette          | notes             |
|--------------------|-------------|-------|------------------|-------------------|
| bargello-calm      | bargello    | 0.15  | lavender fields  | gentle waves      |
| bargello-bold      | bargello    | 0.55  | indigo dye       | high contrast     |
| mirror-geometric   | mirror      | 0.30  | ocean breeze     | clean reflection  |
| rotational-lively  | rotational  | 0.55  | wildflower       | spinning energy   |
| stripe-calm        | stripe      | 0.20  | northern lights  | serene bands      |
| flower-medallion   | flower      | 0.40  | cherry blossom   | centered bloom    |
| emergent-wild      | emergent    | 0.70  | wisteria         | macro patterns    |
| improv-wonky       | none        | 0.60  | thistle          | wonky=0.05        |

Each preset is a full params dict in PRESETS dict in generator.py.
Seeds are hardcoded so thumbnails are stable/reproducible.

## Controls (sidebar)
Group into sections:

### Style
- Symmetry: dropdown (all 8 modes)
- Palette: dropdown (all 17 palettes)
- Colors: radio 3 / 4

### Structure
- Chaos: slider 0–0.80, step 0.05
- Grid size: slider 14–20 rows
- Tile size: slider 2–10
- Tile variation: slider 0–0.30, step 0.05

### Details
- Border: dropdown (none / solid / checkerboard / piano_keys)
- Stitch: dropdown (none / grid / diagonal / sashiko_wave / sashiko_asanoha)
- Wonky: checkbox (off / subtle 0.03 / strong 0.05)
- Mega blocks: checkbox + slider 10–25%
- Plain frac: checkbox + slider 10–40%

### Seed
- Number input + "Randomize" button

### Actions
- "Download PNG" button (links to /download?<params>)
- "Copy share link" button (encodes to V2 quilt ID, copies /create?id=<qid> to clipboard)

## UI Behavior
- Every control change: update URL query string (replaceState, no page reload) +
  update `<img src>` to `/render?<params>`. Browser shows loading state naturally.
- Image is ~600px rendered server-side, full-res download via /download.
- No JS framework — vanilla JS only. Form state lives in URL params.
- Render is blocking (Cairo is fast, ~200ms), no async needed.

## Rendering
generator.py imports `render_quilt` and `params_to_render_kwargs` from existing code.
`/render` parses individual query params (not JSON blob like app.py) for cleaner URLs.

```python
def _params_from_request():
    a = request.args
    return {
        "palette":        a.get("palette", "lavender fields"),
        "symmetry":       a.get("symmetry", "bargello"),
        "chaos":          float(a.get("chaos", 0.3)),
        "rows":           int(a.get("rows", 16)),
        "cols":           int(a.get("rows", 16)),
        "n_patterns":     2,
        "n_colors":       int(a.get("n_colors", 4)),
        "tile_size":      int(a.get("tile_size", 6)),
        "tile_variation": float(a.get("tile_variation", 0.1)),
        "border_style":   a.get("border_style", "none"),
        "sash_width":     0,
        "cornerstones":   False,
        "color_gradient": "none",
        "mega_frac":      float(a.get("mega_frac", 0.0)),
        "plain_frac":     float(a.get("plain_frac", 0.0)),
        "quilt_stitch":   a.get("quilt_stitch") or None,
        "wonky":          float(a.get("wonky", 0.0)),
        "seed":           int(a.get("seed", 42)),
    }
```

## Railway Deployment

### Procfile
```
web: gunicorn generator:app --bind 0.0.0.0:$PORT --workers 2
```

### nixpacks.toml
```toml
[phases.setup]
aptPkgs = ["libcairo2-dev", "pkg-config", "libgirepository1.0-dev"]
```

### requirements additions
- gunicorn (add to requirements.txt)
- flask already present

Railway auto-detects nixpacks.toml for system deps.
No file storage needed — renders are ephemeral, download is on-demand.

## Pre-rendering Thumbnails
Script `render_family_thumbnails.py` (run once locally, commit PNGs):
```python
for name, preset in PRESETS.items():
    png = render_quilt(**params_to_render_kwargs(preset), size=400)
    Path(f"static/generator/families/{name}.png").write_bytes(png)
```
PNGs committed to git so Railway doesn't need to render them at startup.

## Implementation Order
1. `generator.py` — Flask app with /render and /download routes + PRESETS dict
2. `render_family_thumbnails.py` — one-shot script to generate PNGs
3. `templates/generator/create.html` — editor page with sidebar + img tag
4. `templates/generator/index.html` — families landing page
5. `Procfile` + `nixpacks.toml` — Railway config
6. Add `gunicorn` to requirements.txt
7. Test locally, commit, push branch, connect to Railway

## Open Questions (decide before/during build)
- Image size for /render endpoint: 600px? 800px? (affects latency)
- Should /create?id=<qid> support V1 IDs too? (probably yes, decode handles it)
- Render timeout on Railway — if Cairo is slow on cold start, may need to bump
