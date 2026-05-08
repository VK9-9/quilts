#!/usr/bin/env python3
"""Build static quilt gallery site.

Usage:
    python build_site.py --ratings ratings.json --out docs/ --families 18 --variations 18
"""
import argparse
import json
import os
import random
import re
import shutil
from collections import Counter
from pathlib import Path

import numpy as np
from jinja2 import Environment, BaseLoader
from sklearn.cluster import KMeans

from sampler import sample_random_params, params_to_render_kwargs, PALETTE_NAMES, SYMMETRY_NAMES
from quilt import render_quilt
from quilt_id import encode, _V1_PALETTES, _V1_SYMMETRY, _V1_GRADIENT

_ACTIVE_PALETTES = set(PALETTE_NAMES)
_ENCODABLE_PALETTES = set(_V1_PALETTES)


def nearest_square(n):
    """Return the nearest perfect square to n.

    >>> nearest_square(18)
    16
    >>> nearest_square(20)
    25
    >>> nearest_square(25)
    25
    """
    root = round(n ** 0.5)
    return root * root


def _encodable(params):
    """Return True if params can be rendered and encoded as a v1 quilt ID."""
    gradient = params.get("color_gradient") or "none"
    return (params.get("palette") in _ENCODABLE_PALETTES
            and params.get("symmetry") in _V1_SYMMETRY
            and gradient in _V1_GRADIENT)


# ---------------------------------------------------------------------------
# Clustering
# ---------------------------------------------------------------------------

def load_liked(ratings_path):
    """Load liked quilts from ratings JSON, filtered to encodable params.

    Returns (params_list, indices_into_ratings) — indices are needed to
    look up CLIP embeddings from the parallel embeddings array.
    """
    with open(ratings_path, encoding="utf-8") as f:
        ratings = json.load(f)
    params, indices = [], []
    skipped = 0
    for i, r in enumerate(ratings):
        if not r["liked"]:
            continue
        if _encodable(r["params"]):
            params.append(r["params"])
            indices.append(i)
        else:
            skipped += 1
    if skipped:
        print(f"  (skipping {skipped} liked quilts with retired params)")
    return params, indices


def params_to_cluster_features(params):
    """Aesthetic-only feature vector for K-means — excludes palette so clusters
    reflect structure and composition, not just color choices."""
    features = [
        params["rows"] / 20.0,
        params["chaos"],
        params["n_patterns"] / 2.0,
        params["n_colors"] / 4.0,
        params.get("tile_size", 0) / 10.0,
        params.get("tile_variation", 0.0),
        params.get("sash_width", 0) / 5.0,
        params.get("mega_frac", 0.0),
        params.get("plain_frac", 0.0),
        1.0 if params.get("cornerstones", False) else 0.0,
    ]
    for s in SYMMETRY_NAMES:
        features.append(1.0 if params["symmetry"] == s else 0.0)
    return np.array(features, dtype=np.float64)


def load_clip_embeddings(ratings_path, indices):
    """Load CLIP embeddings for the given rating indices.

    Returns (embeddings, valid_mask) — valid_mask is False for zero-norm
    rows (retired palettes that couldn't be rendered).
    """
    emb_path = ratings_path.replace(".json", "_embeddings.npy")
    all_emb = np.load(emb_path)
    emb = all_emb[indices]
    valid = np.linalg.norm(emb, axis=1) > 0
    return emb, valid


def cluster(liked, n_families, clip_embeddings=None):
    """K-means cluster liked quilts into n_families groups.

    If clip_embeddings is provided, clusters on visual similarity.
    Otherwise clusters on hand-crafted parameter features.
    """
    if clip_embeddings is not None:
        features = clip_embeddings
    else:
        features = np.array([params_to_cluster_features(p) for p in liked])
    km = KMeans(n_clusters=n_families, random_state=42, n_init=10)
    labels = km.fit_predict(features)
    return labels, km.cluster_centers_, features


def representative(members, member_features, centroid):
    """Return the member closest to the cluster centroid."""
    dists = np.linalg.norm(member_features - centroid, axis=1)
    return members[int(np.argmin(dists))]


_CHAOS_ADJ = [
    (0.25, "Ordered"),
    (0.45, "Calm"),
    (0.62, "Lively"),
    (1.00, "Wild"),
]

_SYM_NOUN = {
    "rotational": "Spiral",
    "mirror":     "Crystal",
    "stripe":     "Ribbons",
    "partial":    "Mosaic",
    "none":       "Garden",
}

_SECONDARY = [
    ("sash",
     lambda m: sum(1 for p in m if p.get("sash_width", 0) > 0) / len(m) > 0.4,
     "Lattice"),
    ("mega",    lambda m: sum(p.get("mega_frac", 0) for p in m) / len(m) > 0.08,          "Bold"),
    ("plain",   lambda m: sum(p.get("plain_frac", 0) for p in m) / len(m) > 0.08,         "Spare"),
    ("large",   lambda m: sum(p["rows"] for p in m) / len(m) >= 17.5,                     "Grand"),
]


def family_name(members):
    """Derive an evocative name from a cluster's dominant chaos, symmetry, and traits."""
    avg_chaos = sum(p["chaos"] for p in members) / len(members)
    dominant_sym = Counter(p["symmetry"] for p in members).most_common(1)[0][0]

    adj = next(word for threshold, word in _CHAOS_ADJ if avg_chaos <= threshold)
    noun = _SYM_NOUN.get(dominant_sym, "Quilt")

    # pick first matching secondary modifier, if any
    modifier = next((word for _, test, word in _SECONDARY if test(members)), None)
    if modifier:
        return f"{modifier} {adj} {noun}"
    return f"{adj} {noun}"


def slugify(name):
    """Convert a name to a URL-safe slug."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def unique_slug(name, existing):
    """Return a slug for name that doesn't collide with existing slugs."""
    base = slugify(name)
    slug = base
    n = 2
    while slug in existing:
        slug = f"{base}-{n}"
        n += 1
    return slug


def unique_name(name, existing):
    """Return name deduplicated against existing set by appending a number.

    >>> unique_name("Lively Spiral", set())
    'Lively Spiral'
    >>> unique_name("Lively Spiral", {"Lively Spiral"})
    'Lively Spiral 2'
    >>> unique_name("Lively Spiral", {"Lively Spiral", "Lively Spiral 2"})
    'Lively Spiral 3'
    """
    result = name
    n = 2
    while result in existing:
        result = f"{name} {n}"
        n += 1
    return result


def generate_variations(symmetry, n, rng):
    """Sample n random param sets with symmetry fixed, palette free to vary."""
    variations = []
    for _ in range(n):
        while True:
            p = sample_random_params(rng)
            p["symmetry"] = symmetry
            if _encodable(p):
                break
        variations.append(p)
    return variations


def define_families(liked, n_families, n_variations, rng,  # pylint: disable=too-many-locals,too-many-arguments,too-many-positional-arguments
                    name_overrides=None, clip_embeddings=None):
    """Cluster liked quilts and define families with names, reps, and variations."""
    labels, centroids, features = cluster(liked, n_families,
                                          clip_embeddings=clip_embeddings)
    families = []
    slugs_used = set()
    names_used = set()
    name_overrides = name_overrides or {}

    for fid in range(n_families):
        idx = [i for i, l in enumerate(labels) if l == fid]
        members = [liked[i] for i in idx]
        mfeatures = features[idx]
        centroid = centroids[fid]

        auto = unique_name(family_name(members), names_used)
        names_used.add(auto)
        slug = unique_slug(auto, slugs_used)
        slugs_used.add(slug)
        name = name_overrides.get(slug, auto)

        rep = representative(members, mfeatures, centroid)
        dominant_sym = Counter(p["symmetry"] for p in members).most_common(1)[0][0]
        variations = generate_variations(dominant_sym, n_variations, rng)

        families.append({
            "name": name,
            "slug": slug,
            "rep": rep,
            "rep_id": encode(rep),
            "variations": [{"params": vp, "qid": encode(vp)} for vp in variations],
            "size": len(members),
        })

    return families


# ---------------------------------------------------------------------------
# Image rendering
# ---------------------------------------------------------------------------

def render_to_file(params, path, block_size):
    """Render a quilt to a PNG file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    kwargs = params_to_render_kwargs(params)
    kwargs["block_size"] = block_size
    kwargs["output"] = path
    render_quilt(**kwargs)


def render_images(families, out, _block_size_thumb, block_size_full):
    """Render rep and variation PNGs for all families, skipping existing files."""
    n_total = len(families) + sum(len(f["variations"]) for f in families)
    done = 0

    for fam in families:
        rep_path = str(out / "images" / "quilts" / f"{fam['rep_id']}.png")
        if not os.path.exists(rep_path):
            render_to_file(fam["rep"], rep_path, block_size_full)
        done += 1
        print(f"  [{done}/{n_total}] {fam['name']} rep")

        for v in fam["variations"]:
            qid_path = str(out / "images" / "quilts" / f"{v['qid']}.png")
            if not os.path.exists(qid_path):
                render_to_file(v["params"], qid_path, block_size_full)
            done += 1
            print(f"  [{done}/{n_total}] {fam['name']} var {v['qid']}")


# ---------------------------------------------------------------------------
# HTML templates
# ---------------------------------------------------------------------------

_INDEX_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Quilt Gallery</title>
  <style>
    body { font-family: Georgia, serif; background: #f9f5f0; margin: 0; padding: 2rem; color: #2c2c2c; }
    h1 { text-align: center; font-size: 2rem; margin-bottom: 0.4rem; }
    .subtitle { text-align: center; color: #999; margin-bottom: 2.5rem; font-size: 0.95rem; }
    .grid { display: grid; grid-template-columns: repeat({{ cols }}, 1fr); gap: 1.5rem; max-width: 1200px; margin: 0 auto; }
    .card { background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08); transition: transform 0.15s, box-shadow 0.15s; }
    .card:hover { transform: translateY(-3px); box-shadow: 0 6px 18px rgba(0,0,0,0.14); }
    .card a { text-decoration: none; color: inherit; display: block; }
    .card img { width: 100%; display: block; }
    .card-name { padding: 0.55rem 0.8rem; font-size: 0.82rem; color: #666; text-align: center; }
  </style>
</head>
<body>
  <h1>Quilt Gallery</h1>
  <p class="subtitle">{{ families|length }} families &nbsp;&middot;&nbsp; {{ total }} quilts</p>
  <div class="grid">
    {% for fam in families %}
    <div class="card">
      <a href="family/{{ fam.slug }}/">
        <img src="images/quilts/{{ fam.rep_id }}.png" alt="{{ fam.name }}" loading="lazy">
        <div class="card-name">{{ fam.name }}</div>
      </a>
    </div>
    {% endfor %}
  </div>
  <footer style="text-align:center;color:#bbb;font-size:0.75rem;margin-top:3rem;">Generated {{ generated_at }}</footer>
</body>
</html>
"""

_FAMILY_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ fam.name }} — Quilt Gallery</title>
  <style>
    body { font-family: Georgia, serif; background: #f9f5f0; margin: 0; padding: 2rem; color: #2c2c2c; }
    .back { color: #999; text-decoration: none; font-size: 0.9rem; }
    .back:hover { color: #2c2c2c; }
    h1 { font-size: 1.6rem; margin: 0.5rem 0 0.25rem; }
    .subtitle { color: #999; font-size: 0.88rem; margin-bottom: 2rem; }
    .grid { display: grid; grid-template-columns: repeat({{ cols }}, 1fr); gap: 1rem; max-width: 1200px; margin: 0 auto; }
    .card { background: white; border-radius: 6px; overflow: hidden; box-shadow: 0 2px 6px rgba(0,0,0,0.07); transition: transform 0.15s; }
    .card:hover { transform: translateY(-2px); }
    .card a { display: block; }
    .card img { width: 100%; display: block; }
  </style>
</head>
<body>
  <a class="back" href="../../">&#8592; All families</a>
  <h1>{{ fam.name }}</h1>
  <p class="subtitle">{{ fam.variations|length }} variations</p>
  <div class="grid">
    {% for v in fam.variations %}
    <div class="card">
      <a href="../../quilt/{{ v.qid }}/">
        <img src="../../images/quilts/{{ v.qid }}.png" alt="Quilt {{ v.qid }}" loading="lazy">
      </a>
    </div>
    {% endfor %}
  </div>
  <footer style="text-align:center;color:#bbb;font-size:0.75rem;margin-top:3rem;">Generated {{ generated_at }}</footer>
</body>
</html>
"""

_QUILT_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Quilt {{ qid }} — Quilt Gallery</title>
  <style>
    body { font-family: Georgia, serif; background: #f9f5f0; margin: 0; padding: 2rem;
           display: flex; flex-direction: column; align-items: center; color: #2c2c2c; }
    .back { align-self: flex-start; color: #999; text-decoration: none; font-size: 0.9rem; margin-bottom: 1.5rem; }
    .back:hover { color: #2c2c2c; }
    img { max-width: min(100%, 640px); border-radius: 4px; box-shadow: 0 4px 20px rgba(0,0,0,0.12); }
    .id-wrap { margin-top: 1.2rem; position: relative; display: inline-block; }
    .qid { font-family: monospace; font-size: 1.05rem; color: #777; cursor: default;
           border-bottom: 1px dashed #bbb; padding-bottom: 1px; }
    .tooltip { visibility: hidden; opacity: 0; transition: opacity 0.15s;
               background: #1e1e1e; color: #e8e8e8; font-size: 0.78rem; font-family: monospace;
               white-space: pre; padding: 0.7rem 1rem; border-radius: 6px;
               position: absolute; bottom: 135%; left: 50%; transform: translateX(-50%);
               z-index: 10; box-shadow: 0 4px 14px rgba(0,0,0,0.35);
               pointer-events: none; }
    .id-wrap:hover .tooltip { visibility: visible; opacity: 1; }
  </style>
</head>
<body>
  <a class="back" href="../../family/{{ family_slug }}/">&#8592; {{ family_name }}</a>
  <img src="../../images/quilts/{{ qid }}.png" alt="Quilt {{ qid }}">
  <div class="id-wrap">
    <span class="qid">{{ qid }}</span>
    <div class="tooltip">{{ params_summary }}</div>
  </div>
<script>
document.addEventListener('keydown', function(e) {
  if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
    {% if next_qid %}window.location = '../../quilt/{{ next_qid }}/';{% endif %}
  } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
    {% if prev_qid %}window.location = '../../quilt/{{ prev_qid }}/';{% endif %}
  }
});
</script>
  <footer style="text-align:center;color:#bbb;font-size:0.75rem;margin-top:3rem;">Generated {{ generated_at }}</footer>
</body>
</html>
"""


def params_summary(params):
    """Format params as a multi-line string for the quilt detail tooltip."""
    lines = [
        f"palette:    {params['palette']}",
        f"symmetry:   {params['symmetry']}",
        f"chaos:      {params['chaos']:.2f}",
        f"rows:       {params['rows']}",
        f"seed:       {params['seed']}",
    ]
    if params.get("border_style") and params["border_style"] != "none":
        lines.append(f"border:     {params['border_style']}")
    if params.get("sash_width", 0) > 0:
        cs = " + cornerstones" if params.get("cornerstones") else ""
        lines.append(f"sash:       {params['sash_width']}px{cs}")
    if params.get("mega_frac", 0.0) > 0:
        lines.append(f"mega_frac:  {params['mega_frac']:.2f}")
    if params.get("plain_frac", 0.0) > 0:
        lines.append(f"plain_frac: {params['plain_frac']:.2f}")
    return "\n".join(lines)


def render_html(families, out, n_families, n_variations):
    """Render index, family, and quilt HTML pages to out/."""
    from datetime import datetime  # pylint: disable=import-outside-toplevel
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    env = Environment(loader=BaseLoader())
    index_cols = round(n_families ** 0.5)
    family_cols = round(n_variations ** 0.5)

    # index
    tmpl = env.from_string(_INDEX_HTML)
    total = sum(len(f["variations"]) for f in families)
    (out / "index.html").write_text(
        tmpl.render(families=families, total=total, cols=index_cols,
                    generated_at=generated_at), encoding="utf-8"
    )

    # family pages
    tmpl = env.from_string(_FAMILY_HTML)
    for fam in families:
        fam_dir = out / "family" / fam["slug"]
        fam_dir.mkdir(parents=True, exist_ok=True)
        (fam_dir / "index.html").write_text(
            tmpl.render(fam=fam, cols=family_cols,
                        generated_at=generated_at), encoding="utf-8"
        )

    # quilt pages
    tmpl = env.from_string(_QUILT_HTML)
    for fam in families:
        qids = [v["qid"] for v in fam["variations"]]
        for i, v in enumerate(fam["variations"]):
            qdir = out / "quilt" / v["qid"]
            qdir.mkdir(parents=True, exist_ok=True)
            (qdir / "index.html").write_text(
                tmpl.render(
                    qid=v["qid"],
                    family_slug=fam["slug"],
                    family_name=fam["name"],
                    params_summary=params_summary(v["params"]),
                    prev_qid=qids[i - 1] if i > 0 else None,
                    next_qid=qids[i + 1] if i < len(qids) - 1 else None,
                    generated_at=generated_at,
                ),
                encoding="utf-8",
            )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():  # pylint: disable=too-many-locals,too-many-statements,too-many-branches
    """Parse CLI args and build the static gallery site."""
    parser = argparse.ArgumentParser(description="Build static quilt gallery")
    parser.add_argument("--ratings", default="ratings.json")
    parser.add_argument("--out", default="docs/")
    parser.add_argument("--families", type=int, default=18)
    parser.add_argument("--variations", type=int, default=18)
    parser.add_argument("--block-size", type=int, default=40,
                        help="Block size in px for rendered images (default: 40)")
    parser.add_argument("--seed", type=int, default=42,
                        help="RNG seed for variation sampling (default: 42)")
    parser.add_argument("--names", default="family_names.json",
                        help="JSON file mapping slug → custom name (default: family_names.json)")
    parser.add_argument("--dump-names", action="store_true",
                        help="Write auto-generated names to --names file and exit")
    parser.add_argument("--clip", action="store_true",
                        help="Cluster by CLIP visual embeddings instead of params")
    args = parser.parse_args()

    out = Path(args.out)
    # Delete everything except images/ (which is expensive to re-render)
    if out.exists():
        for item in out.iterdir():
            if item.name != "images":
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
    out.mkdir(parents=True, exist_ok=True)

    n_families = nearest_square(args.families)
    n_variations = nearest_square(args.variations)
    if n_families != args.families:
        print(f"  (--families {args.families} → {n_families} to make a square grid)")
    if n_variations != args.variations:
        print(f"  (--variations {args.variations} → {n_variations} to make a square grid)")

    liked, liked_indices = load_liked(args.ratings)
    print(f"Loaded {len(liked)} liked quilts")

    clip_emb = None
    if args.clip:
        all_emb, valid = load_clip_embeddings(args.ratings, liked_indices)
        # filter out zero-norm embeddings (retired palettes)
        valid_liked = [p for p, v in zip(liked, valid) if v]
        valid_emb = all_emb[valid]
        n_dropped = len(liked) - len(valid_liked)
        if n_dropped:
            print(f"  (dropped {n_dropped} quilts with missing CLIP embeddings)")
        liked = valid_liked
        clip_emb = valid_emb
        print(f"  Clustering on {len(clip_emb)} CLIP embeddings (512-dim)")

    rng = random.Random(args.seed)

    if args.dump_names:
        families = define_families(liked, n_families, n_variations, rng,
                                   clip_embeddings=clip_emb)
        names = {f["slug"]: f["name"] for f in families}
        with open(args.names, "w", encoding="utf-8") as f:
            json.dump(names, f, indent=2)
        for slug, name in names.items():
            print(f"  {slug:40s} → {name}")
        print(f"\nWrote {len(names)} names to {args.names}.")
        print("Edit the file, then re-run without --dump-names.")
        return

    name_overrides = {}
    if os.path.exists(args.names):
        with open(args.names, encoding="utf-8") as f:
            name_overrides = json.load(f)
        print(f"Loaded {len(name_overrides)} name overrides from {args.names}")

    families = define_families(liked, n_families, n_variations, rng,
                               name_overrides=name_overrides,
                               clip_embeddings=clip_emb)
    for fam in families:
        print(f"  {fam['name']} ({fam['size']} members) → {fam['slug']}")

    print(f"\nRendering images ({len(families)} reps + "
          f"{sum(len(f['variations']) for f in families)} variations)...")
    render_images(families, out, args.block_size, args.block_size)

    print("\nRendering HTML...")
    render_html(families, out, n_families, n_variations)

    total = sum(len(f["variations"]) for f in families)
    print(f"\nDone. {len(families)} families, {total} quilts → {out}/")
    print("Push to GitHub to deploy: git add docs/ && git commit -m 'rebuild gallery' && git push")


if __name__ == "__main__":
    main()
