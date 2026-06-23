"""Active learning sampler for quilt parameter exploration.

Maintains a history of rated quilts, trains a model to predict preference,
and samples new parameters balancing exploration vs exploitation.

Two preference models run in parallel:
  - param_model: GradientBoostingClassifier on parameter vectors (fast)
  - clip_model:  LogisticRegression on CLIP image embeddings (visual)

suggest_params() uses a two-stage pipeline:
  1. param_model scores 200 random candidates → keep top 30
  2. clip_model renders those 30 at low-res, embeds, picks best predicted
"""

import json
import os
import random
import time

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression

from palettes import PALETTES
from layout import SYMMETRY_MODES
from quilt import BORDER_STYLES, QUILT_STITCH_STYLES, render_quilt
from render_params import params_to_render_kwargs

_DROP_PALETTES = {
    "storm",
    "midnight moss",
    "terracotta",
    "slate and rust",
    "coral reef",
    "autumn harvest",
    "aurora",
    "deep sea",
    "amber glow",
    "sage garden",
    "plum wine",
    "copper canyon",
    "moonstone",
    "coastal fog",
}
# Proven palettes: shown at fixed probability instead of normal rotation
_PROVEN_PALETTES = {"lavender fields": 0.50}
PALETTE_NAMES = [p[0] for p in PALETTES if p[0] not in _DROP_PALETTES]
_EXPLORE_PALETTES = [p for p in PALETTE_NAMES if p not in _PROVEN_PALETTES]
_DROP_SYMMETRY = {"flower", "emergent", "mirror", "none"}
SYMMETRY_NAMES = [s for s in SYMMETRY_MODES if s not in _DROP_SYMMETRY]
# Proven symmetries: shown at fixed probability during exploration only
_PROVEN_SYMMETRIES = {"bargello": 0.50}
_BASE_SYMMETRIES = [s for s in SYMMETRY_NAMES if s not in _PROVEN_SYMMETRIES]

# parameter ranges
PARAM_SPACE = {
    "rows": (16, 21),
    "cols": (16, 21),
    "symmetry": SYMMETRY_NAMES,
    "chaos": (0.0, 0.8),
    "palette": PALETTE_NAMES,
    "n_patterns": (2, 2),
    "n_colors": (4, 6),
    "tile_size": (4, 10),  # small tiles (1-3) disliked
    "tile_variation": (0.0, 0.3),
}

# max fraction of candidates that can use any single palette value
MAX_PALETTE_FRAC = 0.10

# block_size used when rendering candidates for CLIP scoring
_CLIP_CANDIDATE_BLOCK_SIZE = 8
# block_size used when embedding a rated quilt
_CLIP_EMBED_BLOCK_SIZE = 16
# number of top param-scored candidates to render+embed for CLIP scoring
_CLIP_TOP_N = 30


def _random_wash_direction(rng):
    """Pick a random unit-vector direction for color wash."""
    import math  # pylint: disable=import-outside-toplevel

    angle = rng.uniform(0, 2 * math.pi)
    return (round(math.cos(angle), 3), round(math.sin(angle), 3))


_DROP_STITCHES = {"crosshatch"}
_STITCH_STYLES = [s for s in QUILT_STITCH_STYLES if s not in _DROP_STITCHES]


def _weighted_stitch(rng):
    """Pick a stitch style, downweighting sashiko_asanoha."""
    weights = [0.5 if s == "sashiko_asanoha" else 1.0 for s in _STITCH_STYLES]
    return rng.choices(_STITCH_STYLES, weights=weights)[0]


def _pick_palette(rng, explore_only=False):
    """Pick a palette, giving proven palettes a fixed probability.

    If explore_only=True, only pick from exploration palettes (used for
    exploitation candidates so the model can't over-select proven winners).
    """
    if not explore_only:
        for pal, prob in _PROVEN_PALETTES.items():
            if rng.random() < prob:
                return pal
    return rng.choice(_EXPLORE_PALETTES)


def sample_random_params(rng=None, explore_only=False):
    """Sample a completely random parameter set."""
    if rng is None:
        rng = random.Random()
    rows = rng.randint(*PARAM_SPACE["rows"])
    cols = rows  # keep square
    return {
        "rows": rows,
        "cols": cols,
        "symmetry": (
            next((s for s, p in _PROVEN_SYMMETRIES.items() if rng.random() < p), None)
            or rng.choice(_BASE_SYMMETRIES)
        )
        if not explore_only
        else rng.choice(_BASE_SYMMETRIES),
        "chaos": round(rng.uniform(*PARAM_SPACE["chaos"]), 2),
        "palette": _pick_palette(rng, explore_only=explore_only),
        "n_patterns": rng.randint(*PARAM_SPACE["n_patterns"]),
        "n_colors": rng.choices([4, 5, 6], weights=[40, 45, 15])[0],
        "tile_size": rng.randint(*PARAM_SPACE["tile_size"]),
        "tile_variation": round(rng.uniform(*PARAM_SPACE["tile_variation"]), 2),
        "border_style": (
            rng.choices(
                [b for b in BORDER_STYLES if b != "stripes"],
                weights=[2.0 if b == "solid" else 1.0 for b in BORDER_STYLES if b != "stripes"],
            )[0]
            if rng.random() < 0.35
            else "none"
        ),
        "mega_frac": round(rng.uniform(0.1, 0.25), 2) if rng.random() < 0.05 else 0.0,
        "plain_frac": round(rng.uniform(0.1, 0.4), 2) if rng.random() < 0.15 else 0.0,
        "quilt_stitch": _weighted_stitch(rng) if rng.random() < 0.98 else None,
        "wash_alpha": round(rng.uniform(0.04, 0.18), 2) if rng.random() < 0.15 else 0.0,
        "palette_2": rng.choice(PALETTE_NAMES) if rng.random() < 0.05 else None,
        "palette_mix": rng.choice(PALETTE_NAMES) if rng.random() < 0.05 else None,
        "wonky": round(rng.uniform(0.02, 0.06), 3) if rng.random() < 0.10 else 0.0,
        "strippy": round(rng.uniform(0.2, 0.35), 2) if rng.random() < 0.15 else 0.0,
        "seed": rng.randint(0, 2**31),
    }


def params_to_features(params):
    """Convert a param dict to a numeric feature vector for the model."""
    features = []
    # numeric params
    features.append(params["rows"])
    features.append(params["chaos"])
    features.append(params["n_patterns"])
    features.append(params["n_colors"])
    features.append(params["tile_size"])
    features.append(params["tile_variation"])
    features.append(params.get("mega_frac", 0.0))
    features.append(params.get("plain_frac", 0.0))
    features.append(params.get("wash_alpha", 0.0))
    features.append(1.0 if params.get("quilt_stitch") else 0.0)
    features.append(1.0 if params.get("palette_2") else 0.0)
    features.append(1.0 if params.get("palette_mix") else 0.0)
    features.append(params.get("wonky", 0.0))
    features.append(params.get("strippy", 0.0))
    # one-hot border style (includes "none")
    border_names = ["none"] + BORDER_STYLES
    for b in border_names:
        features.append(1.0 if params.get("border_style", "none") == b else 0.0)
    # one-hot symmetry
    for s in SYMMETRY_NAMES:
        features.append(1.0 if params["symmetry"] == s else 0.0)
    # one-hot palette
    for p in PALETTE_NAMES:
        features.append(1.0 if params["palette"] == p else 0.0)
    return np.array(features, dtype=np.float64)


def _render_small(params, block_size):
    """Render params at the given block_size and return PNG bytes."""
    kwargs = params_to_render_kwargs(params, block_size=block_size)
    return render_quilt(**kwargs)


class QuiltExplorer:  # pylint: disable=too-many-instance-attributes
    """Active learning explorer for quilt aesthetics."""

    def __init__(self, data_path="data/ratings.json"):
        self.data_path = data_path
        # Derive companion paths from the extension only — a plain .replace()
        # would also rewrite a ".json" that appears earlier in the path.
        root = os.path.splitext(data_path)[0]
        self.embeddings_path = root + "_embeddings.npy"
        self.rounds_path = root + "_rounds.json"
        self.ratings = []
        self.embeddings = np.zeros((0, 512), dtype=np.float32)
        self.rounds = []
        self._load()
        self.model = None  # param model
        self.clip_model = None  # CLIP embedding model
        self._retrain()

    def _load(self):
        if os.path.exists(self.data_path):
            with open(self.data_path, encoding="utf-8") as f:
                self.ratings = json.load(f)
        if os.path.exists(self.embeddings_path):
            self.embeddings = np.load(self.embeddings_path)
        # Embeddings align with ratings positionally: embeddings[i] is the CLIP
        # vector for ratings[i]. More embeddings than ratings means the .npy is
        # stale (truncated/edited ratings.json, diverged backfill) — the surplus
        # rows would silently mis-pair labels, so drop them.
        if len(self.embeddings) > len(self.ratings):
            print(
                f"WARNING: {len(self.embeddings)} embeddings > {len(self.ratings)} "
                f"ratings; truncating embeddings to match."
            )
            self.embeddings = self.embeddings[: len(self.ratings)]
        if os.path.exists(self.rounds_path):
            with open(self.rounds_path, encoding="utf-8") as f:
                self.rounds = json.load(f)

    def _save(self):
        os.makedirs(os.path.dirname(self.data_path) or ".", exist_ok=True)
        with open(self.data_path, "w", encoding="utf-8") as f:
            json.dump(self.ratings, f, indent=2)

    def _save_rounds(self):
        os.makedirs(os.path.dirname(self.rounds_path) or ".", exist_ok=True)
        with open(self.rounds_path, "w", encoding="utf-8") as f:
            json.dump(self.rounds, f, indent=2)

    def start_round(self, label=None):
        """Start a new scoring round. Returns the round number."""
        num = len(self.rounds) + 1
        self.rounds.append(
            {
                "round": num,
                "label": label or f"R{num}",
                "start_index": len(self.ratings),
                "ts": time.time(),
            }
        )
        self._save_rounds()
        return num

    def _save_embeddings(self):
        np.save(self.embeddings_path, self.embeddings)

    def add_rating(self, params, liked):
        """Record a rating (liked=True/False) for a param set and embed the image."""
        self.ratings.append({"params": params, "liked": liked, "ts": time.time()})
        self._save()
        self._append_embedding(params)
        self._retrain()

    def _append_embedding(self, params):
        """Render params, embed with CLIP, append to embeddings array."""
        from clip_embed import embed_image  # pylint: disable=import-outside-toplevel

        png_bytes = _render_small(params, block_size=_CLIP_EMBED_BLOCK_SIZE)
        vec = embed_image(png_bytes)
        self.embeddings = np.vstack([self.embeddings, vec[np.newaxis, :]])
        self._save_embeddings()

    def _retrain(self):
        """Retrain both preference models on all ratings so far."""
        if len(self.ratings) < 10:
            self.model = None
            self.clip_model = None
            return
        features = np.array([params_to_features(r["params"]) for r in self.ratings])
        y = np.array([1 if r["liked"] else 0 for r in self.ratings])
        if len(set(y)) < 2:
            self.model = None
            self.clip_model = None
            return

        self.model = GradientBoostingClassifier(
            n_estimators=50,
            max_depth=3,
            random_state=42,
        )
        self.model.fit(features, y)

        # Train CLIP model on ratings that have valid (non-zero) embeddings.
        # Reset first so a prior fit is dropped if the CLIP data no longer
        # qualifies (otherwise suggest_params keeps using a stale model).
        self.clip_model = None
        # Clamp to the aligned prefix in case embeddings and ratings ever differ.
        n_emb = min(len(self.embeddings), len(y))
        if n_emb >= 10:
            emb = self.embeddings[:n_emb]
            y_emb = y[:n_emb]
            valid = np.linalg.norm(emb, axis=1) > 0
            x_valid = emb[valid]
            y_valid = y_emb[valid]
            if len(x_valid) >= 10 and len(set(y_valid)) >= 2:
                self.clip_model = LogisticRegression(max_iter=1000, C=1.0, random_state=42)
                self.clip_model.fit(x_valid, y_valid)

    def suggest_params(self, explore_prob=0.3):  # pylint: disable=too-many-locals
        """Suggest a new parameter set.

        With probability explore_prob, returns fully random params.
        Otherwise uses a two-stage pipeline:
          1. param_model pre-filters 200 candidates → top _CLIP_TOP_N
          2. clip_model renders+embeds top candidates, picks highest predicted
        Falls back to param-only if clip_model is not yet active.
        """
        rng = random.Random()

        if self.model is None or rng.random() < explore_prob:
            params = sample_random_params(rng)
            params["_source"] = "explore"
            return params

        # generate candidates with palette diversity cap
        # explore_only=True excludes proven palettes from exploitation candidates
        candidates = [sample_random_params(rng, explore_only=True) for _ in range(200)]
        max_per_palette = max(1, int(len(candidates) * MAX_PALETTE_FRAC))
        palette_counts = {}
        filtered = []
        for c in candidates:
            pal = c["palette"]
            palette_counts[pal] = palette_counts.get(pal, 0) + 1
            if palette_counts[pal] <= max_per_palette:
                filtered.append(c)
        candidates = filtered if filtered else candidates

        # stage 1: param model scores all candidates
        features = np.array([params_to_features(c) for c in candidates])
        param_probs = self.model.predict_proba(features)[:, 1]

        if self.clip_model is None:
            pick = candidates[int(np.argmax(param_probs))]
            pick["_source"] = "exploit_param"
            return pick

        # stage 2: render + embed top N, pick best by CLIP model
        top_indices = np.argsort(param_probs)[-_CLIP_TOP_N:]
        top_candidates = [candidates[i] for i in top_indices]

        png_list = [_render_small(c, block_size=_CLIP_CANDIDATE_BLOCK_SIZE) for c in top_candidates]
        from clip_embed import embed_images  # pylint: disable=import-outside-toplevel

        embs = embed_images(png_list)
        clip_probs = self.clip_model.predict_proba(embs)[:, 1]
        pick = top_candidates[int(np.argmax(clip_probs))]
        pick["_source"] = "exploit_clip"
        return pick

    def stats(self):
        """Return summary stats about ratings so far."""
        if not self.ratings:
            return {"total": 0, "liked": 0, "disliked": 0, "round": None}
        liked = sum(1 for r in self.ratings if r["liked"])
        result = {
            "total": len(self.ratings),
            "liked": liked,
            "disliked": len(self.ratings) - liked,
            "model_active": self.model is not None,
            "clip_model_active": self.clip_model is not None,
            "embeddings_count": len(self.embeddings),
        }
        if self.rounds:
            cur = self.rounds[-1]
            rnd_ratings = self.ratings[cur["start_index"] :]
            rnd_liked = sum(1 for r in rnd_ratings if r["liked"])
            result["round"] = {
                "label": cur["label"],
                "rated": len(rnd_ratings),
                "liked": rnd_liked,
            }
        else:
            result["round"] = None
        return result

    def feature_importance(self):
        """Return feature importances if param model is trained."""
        if self.model is None:
            return None
        border_names = ["none"] + BORDER_STYLES
        names = (
            [
                "rows",
                "chaos",
                "n_patterns",
                "n_colors",
                "tile_size",
                "tile_variation",
                "mega_frac",
                "plain_frac",
                "wash_alpha",
                "quilt_stitch",
                "palette_2",
                "palette_mix",
                "wonky",
                "strippy",
            ]
            + [f"brd_{b}" for b in border_names]
            + [f"sym_{s}" for s in SYMMETRY_NAMES]
            + [f"pal_{p}" for p in PALETTE_NAMES]
        )
        importances = self.model.feature_importances_
        pairs = sorted(zip(names, importances), key=lambda x: -x[1])
        return pairs
