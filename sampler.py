"""Active learning sampler for quilt parameter exploration.

Maintains a history of rated quilts, trains a model to predict preference,
and samples new parameters balancing exploration vs exploitation.
"""
import json
import os
import random
import time

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier

from palettes import PALETTES
from layout import SYMMETRY_MODES
from quilt import BORDER_STYLES, QUILT_STITCH_STYLES

PALETTE_NAMES = [p[0] for p in PALETTES]
_DROP_SYMMETRY = {"flower", "emergent"}
SYMMETRY_NAMES = [s for s in SYMMETRY_MODES if s not in _DROP_SYMMETRY]

# parameter ranges
PARAM_SPACE = {
    "rows": (14, 19),
    "cols": (14, 19),
    "symmetry": SYMMETRY_NAMES,
    "chaos": (0.0, 0.8),
    "palette": PALETTE_NAMES,
    "n_patterns": (1, 2),
    "n_colors": (3, 4),
    "tile_size": (0, 10),       # 0 = no tiling
    "tile_variation": (0.0, 0.3),
}

# max fraction of candidates that can use any single palette value
MAX_PALETTE_FRAC = 0.10


def sample_random_params(rng=None):
    """Sample a completely random parameter set."""
    if rng is None:
        rng = random.Random()
    rows = rng.randint(*PARAM_SPACE["rows"])
    cols = rows  # keep square
    return {
        "rows": rows,
        "cols": cols,
        "symmetry": rng.choice(PARAM_SPACE["symmetry"]),
        "chaos": round(rng.uniform(*PARAM_SPACE["chaos"]), 2),
        "palette": rng.choice(PARAM_SPACE["palette"]),
        "n_patterns": rng.randint(*PARAM_SPACE["n_patterns"]),
        "n_colors": rng.randint(*PARAM_SPACE["n_colors"]),
        "tile_size": rng.randint(*PARAM_SPACE["tile_size"]),
        "tile_variation": round(rng.uniform(*PARAM_SPACE["tile_variation"]), 2),
        "border_style": rng.choice(BORDER_STYLES) if rng.random() < 0.25 else "none",
        "sash_width": 5 if rng.random() < 0.10 else 0,
        "cornerstones": rng.random() < 0.50,
        "color_gradient": "none",
        "mega_frac": round(rng.uniform(0.1, 0.25), 2) if rng.random() < 0.30 else 0.0,
        "plain_frac": round(rng.uniform(0.1, 0.4), 2) if rng.random() < 0.30 else 0.0,
        "quilt_stitch": rng.choice(QUILT_STITCH_STYLES) if rng.random() < 0.30 else None,
        "wash_alpha": round(rng.uniform(0.04, 0.18), 2) if rng.random() < 0.15 else 0.0,
        "palette_2": rng.choice(PALETTE_NAMES) if rng.random() < 0.15 else None,
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
    features.append(params.get("sash_width", 0))
    features.append(params.get("mega_frac", 0.0))
    features.append(params.get("plain_frac", 0.0))
    features.append(1.0 if params.get("cornerstones", False) else 0.0)
    features.append(params.get("wash_alpha", 0.0))
    features.append(1.0 if params.get("quilt_stitch") else 0.0)
    features.append(1.0 if params.get("palette_2") else 0.0)
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


def params_to_render_kwargs(params):
    """Convert sampled params to kwargs for render_quilt."""
    kwargs = {
        "rows": params["rows"],
        "cols": params["cols"],
        "block_size": 40,
        "symmetry": params["symmetry"],
        "chaos": params["chaos"],
        "palette_name": params["palette"],
        "seed": params["seed"],
        "output": None,  # return bytes
        "border": 15,
        "max_patterns": params["n_patterns"],
        "max_colors": params["n_colors"],
        "tile_size": params["tile_size"] if params["tile_size"] > 0 else None,
        "tile_variation": params["tile_variation"],
        "border_style": params.get("border_style", "none"),
        "sash_width": params.get("sash_width", 0),
        "color_gradient": params.get("color_gradient", "none"),
        "mega_frac": params.get("mega_frac", 0.0),
        "plain_frac": params.get("plain_frac", 0.0),
        "cornerstones": params.get("cornerstones", False),
        "quilt_stitch": params.get("quilt_stitch"),
        "wash_alpha": params.get("wash_alpha", 0.0),
        "palette_name_2": params.get("palette_2"),
    }
    if kwargs["border_style"] == "none":
        kwargs["border_style"] = None
    if kwargs["color_gradient"] == "none":
        kwargs["color_gradient"] = None
    return kwargs


class QuiltExplorer:
    """Active learning explorer for quilt aesthetics."""

    def __init__(self, data_path="ratings.json"):
        self.data_path = data_path
        self.ratings = []
        self._load()
        self.model = None
        self._retrain()

    def _load(self):
        if os.path.exists(self.data_path):
            with open(self.data_path, encoding="utf-8") as f:
                self.ratings = json.load(f)

    def _save(self):
        os.makedirs(os.path.dirname(self.data_path) or ".", exist_ok=True)
        with open(self.data_path, "w", encoding="utf-8") as f:
            json.dump(self.ratings, f, indent=2)

    def add_rating(self, params, liked):
        """Record a rating (liked=True/False) for a param set."""
        self.ratings.append({"params": params, "liked": liked, "ts": time.time()})
        self._save()
        self._retrain()

    def _retrain(self):
        """Retrain the model on all ratings so far."""
        if len(self.ratings) < 10:
            self.model = None
            return
        features = np.array([params_to_features(r["params"]) for r in self.ratings])
        y = np.array([1 if r["liked"] else 0 for r in self.ratings])
        # need at least one of each class
        if len(set(y)) < 2:
            self.model = None
            return
        self.model = GradientBoostingClassifier(
            n_estimators=50, max_depth=3, random_state=42,
        )
        self.model.fit(features, y)

    def suggest_params(self, explore_prob=0.3):
        """Suggest a new parameter set.

        With probability explore_prob, returns fully random params.
        Otherwise, generates candidates and picks the one the model
        predicts you'll like most, with a diversity cap on palette to
        prevent over-exploitation.
        """
        rng = random.Random()

        if self.model is None or rng.random() < explore_prob:
            return sample_random_params(rng)

        # generate candidates, pick best predicted (with diversity cap)
        candidates = [sample_random_params(rng) for _ in range(200)]

        # enforce palette diversity: cap per-palette count
        max_per_palette = max(1, int(len(candidates) * MAX_PALETTE_FRAC))
        palette_counts = {}
        filtered = []
        for c in candidates:
            pal = c["palette"]
            palette_counts[pal] = palette_counts.get(pal, 0) + 1
            if palette_counts[pal] <= max_per_palette:
                filtered.append(c)
        candidates = filtered if filtered else candidates

        features = np.array([params_to_features(c) for c in candidates])
        probs = self.model.predict_proba(features)[:, 1]
        best = int(np.argmax(probs))
        return candidates[best]

    def stats(self):
        """Return summary stats about ratings so far."""
        if not self.ratings:
            return {"total": 0, "liked": 0, "disliked": 0}
        liked = sum(1 for r in self.ratings if r["liked"])
        return {
            "total": len(self.ratings),
            "liked": liked,
            "disliked": len(self.ratings) - liked,
            "model_active": self.model is not None,
        }

    def feature_importance(self):
        """Return feature importances if model is trained."""
        if self.model is None:
            return None
        border_names = ["none"] + BORDER_STYLES
        names = (
            ["rows", "chaos", "n_patterns", "n_colors",
             "tile_size", "tile_variation", "sash_width", "mega_frac", "plain_frac",
             "cornerstones", "wash_alpha", "quilt_stitch", "palette_2"]
            + [f"brd_{b}" for b in border_names]
            + [f"sym_{s}" for s in SYMMETRY_NAMES]
            + [f"pal_{p}" for p in PALETTE_NAMES]
        )
        importances = self.model.feature_importances_
        pairs = sorted(zip(names, importances), key=lambda x: -x[1])
        return pairs
