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
import subprocess
import time

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression

from palettes import PALETTES
from layout import SYMMETRY_MODES
from quilt import BORDER_STYLES, QUILT_STITCH_STYLES, render_quilt
from render_params import params_to_render_kwargs


def _atomic_write_json(path, obj):
    """Write JSON to a temp file then atomically replace, so an interrupted
    write (or a concurrent reader) never leaves a truncated/corrupt file."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)
    os.replace(tmp, path)


# Palettes retired from sampling but still defined in palettes.py, so old
# ratings that used them still render. Names already deleted from palettes.py
# don't belong here — they can't be sampled either way, and listing them
# implied they still existed. test_palette_consistency pins that.
_DROP_PALETTES = {
    "storm",
    "midnight moss",
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

# Numeric ranges sample_random_params draws from. Categorical choices are not
# listed here: they moved to _EXPLORE_PALETTES / _BASE_SYMMETRIES / _STITCH_STYLES
# when proven-winner handling landed, and leaving stale copies here described a
# parameter space that wasn't the one being sampled.
PARAM_SPACE = {
    "rows": (16, 21),
    "chaos": (0.0, 0.8),
    "n_patterns": (2, 2),
    "tile_size": (4, 10),  # small tiles (1-3) disliked
    "tile_variation": (0.0, 0.3),
    # Optional features: the range drawn from when FEATURE_PROBS switches it on.
    "mega_frac": (0.1, 0.25),
    "plain_frac": (0.1, 0.4),
    "wash_alpha": (0.04, 0.18),
    "wonky": (0.02, 0.06),
    "strippy": (0.2, 0.35),
}

# Chance each optional feature is switched on in a random sample. Named here
# rather than inline in sample_random_params so current_policy() can snapshot
# them into each round — reconstructing what distribution generated a round
# shouldn't take git archaeology.
FEATURE_PROBS = {
    "border_style": 0.35,
    "mega_frac": 0.05,
    "plain_frac": 0.15,
    "quilt_stitch": 0.98,
    "wash_alpha": 0.15,
    "palette_2": 0.05,
    "palette_mix": 0.05,
    "wonky": 0.10,
    "strippy": 0.15,
}

# Relative weights for n_colors (all palettes have 6).
N_COLORS_WEIGHTS = {4: 40, 5: 45, 6: 15}

# Chance suggest_params returns a fully random (explore) sample.
EXPLORE_PROB = 0.3
# Random candidates the param model scores per exploit suggestion.
_N_CANDIDATES = 200

# max fraction of candidates that can use any single palette value
MAX_PALETTE_FRAC = 0.10

# Train both models on ratings from this round onward, not on all history.
#
# Rounds 1-13 come from a different generative space and a differently
# calibrated rater: quilt stitching did not exist until R7, so R1-R6 (1914
# ratings, 35% of history at R22) have none, and they are the untuned rounds
# with 20-38% like rates against 75% for the stitch era. That makes
# "quilt_stitch == 0" a near-perfect proxy for "rated before R7" rather than a
# statement about stitching, and it took 0.70 of the param model's feature
# importance — in a feature that is constant at prediction time, since the
# sampler now stitches 98% of candidates, and so cannot rank two live
# candidates against each other at all.
#
# Walk-forward validation over R18-R22 (train on everything before a round,
# predict that round), mean AUC:
#
#   train from   param model   CLIP model
#   all history      0.554        0.598
#   R7+              0.570        0.601
#   R11+             0.577        0.606
#   R14+             0.605        0.620   <- best for both
#   R17+             0.603        0.580
#
# Re-derive this as rounds accumulate: the floor trades era-consistency against
# sample size, and R17+ already loses to R14+ on CLIP for want of data.
_TRAIN_FROM_ROUND = 14
# Below this, the window is worse than the confound it removes — fall back to
# everything rather than fit on a handful of rows.
_MIN_TRAINING_RATINGS = 200

# block_size used when rendering candidates for CLIP scoring
_CLIP_CANDIDATE_BLOCK_SIZE = 8
# block_size used when embedding a rated quilt
_CLIP_EMBED_BLOCK_SIZE = 16
# number of top param-scored candidates to render+embed for CLIP scoring
_CLIP_TOP_N = 30


_PARAM_MODEL_KWARGS = {"n_estimators": 50, "max_depth": 3, "random_state": 42}
_CLIP_MODEL_KWARGS = {"max_iter": 1000, "C": 1.0, "random_state": 42}


_DROP_STITCHES = {"crosshatch"}
# Sampling weight per stitch style; anything not dropped defaults to 1.0.
_STITCH_WEIGHTS = {
    s: {"sashiko_asanoha": 0.5}.get(s, 1.0) for s in QUILT_STITCH_STYLES if s not in _DROP_STITCHES
}
_DROP_BORDERS = {"stripes"}
_BORDER_WEIGHTS = {b: {"solid": 2.0}.get(b, 1.0) for b in BORDER_STYLES if b not in _DROP_BORDERS}


def _weighted_choice(rng, weights):
    """Draw one key of `weights` with probability proportional to its value."""
    return rng.choices(list(weights), weights=list(weights.values()))[0]


def _maybe(rng, feature, draw, off):
    """Return draw() with probability FEATURE_PROBS[feature], else `off`.

    The gate is drawn before the value, matching the inline
    `draw() if rng.random() < p else off` this replaced — the order is part of
    the seed → params mapping.
    """
    return draw() if rng.random() < FEATURE_PROBS[feature] else off


def _uniform(rng, feature, digits=2):
    """Draw a rounded value from PARAM_SPACE[feature]."""
    return round(rng.uniform(*PARAM_SPACE[feature]), digits)


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
        "chaos": _uniform(rng, "chaos"),
        "palette": _pick_palette(rng, explore_only=explore_only),
        "n_patterns": rng.randint(*PARAM_SPACE["n_patterns"]),
        "n_colors": _weighted_choice(rng, N_COLORS_WEIGHTS),
        "tile_size": rng.randint(*PARAM_SPACE["tile_size"]),
        "tile_variation": _uniform(rng, "tile_variation"),
        "border_style": _maybe(
            rng, "border_style", lambda: _weighted_choice(rng, _BORDER_WEIGHTS), "none"
        ),
        "mega_frac": _maybe(rng, "mega_frac", lambda: _uniform(rng, "mega_frac"), 0.0),
        "plain_frac": _maybe(rng, "plain_frac", lambda: _uniform(rng, "plain_frac"), 0.0),
        "quilt_stitch": _maybe(
            rng, "quilt_stitch", lambda: _weighted_choice(rng, _STITCH_WEIGHTS), None
        ),
        "wash_alpha": _maybe(rng, "wash_alpha", lambda: _uniform(rng, "wash_alpha"), 0.0),
        "palette_2": _maybe(rng, "palette_2", lambda: rng.choice(PALETTE_NAMES), None),
        "palette_mix": _maybe(rng, "palette_mix", lambda: rng.choice(PALETTE_NAMES), None),
        "wonky": _maybe(rng, "wonky", lambda: _uniform(rng, "wonky", digits=3), 0.0),
        "strippy": _maybe(rng, "strippy", lambda: _uniform(rng, "strippy"), 0.0),
        "seed": rng.randint(0, 2**31),
    }


_NUMERIC_FEATURES = [
    ("rows", 0),
    ("chaos", 0.0),
    ("n_patterns", 0),
    ("n_colors", 0),
    ("tile_size", 0),
    ("tile_variation", 0.0),
    ("mega_frac", 0.0),
    ("plain_frac", 0.0),
    ("wash_alpha", 0.0),
    ("wonky", 0.0),
    ("strippy", 0.0),
]
_FLAG_FEATURES = ["quilt_stitch", "palette_2", "palette_mix"]
# Categorical params that get one-hot encoded, and the currently-samplable
# values for each. build_feature_vocab widens these with whatever the ratings
# history actually contains.
_CATEGORICAL_BASE = {
    "border_style": ["none"] + BORDER_STYLES,
    "symmetry": list(SYMMETRY_MODES),
    "palette": [p[0] for p in PALETTES],
}


def build_feature_vocab(ratings=()):
    """Build the one-hot vocabulary, covering history as well as the live space.

    _retrain fits on every rating ever recorded, so the encoder has to be able
    to represent values that have since been retired from sampling — or deleted
    from palettes.py outright, which is true of 25 palettes in the current
    history. Encoding over only the samplable set collapsed all of them into a
    single all-zero block: 27% of ratings landed there, and because values get
    retired precisely for underperforming, that block carried a 27% like rate
    against 65% for everything else. That taught the model a large, uniformly
    negative bucket it can never meet again at prediction time, biased the base
    rate the predicted probabilities are calibrated against, and made every
    palette indicator partly encode "not retired" rather than "liked".

    Values are sorted so the encoding depends only on the vocabulary's contents,
    not on dict or file ordering.
    """
    vocab = {}
    for key, base in _CATEGORICAL_BASE.items():
        seen = {r["params"].get(key) for r in ratings}
        vocab[key] = sorted(set(base) | {v for v in seen if v is not None})
    return vocab


def params_to_features(params, vocab=None):
    """Convert a param dict to a numeric feature vector for the model.

    `vocab` must be the same mapping used for every other row in a fit — pass
    the one build_feature_vocab returned for the training set.
    """
    vocab = vocab if vocab is not None else build_feature_vocab()
    features = [params.get(name, default) for name, default in _NUMERIC_FEATURES]
    features += [1.0 if params.get(name) else 0.0 for name in _FLAG_FEATURES]
    for key in _CATEGORICAL_BASE:
        # border_style is the one categorical whose "off" state is a real value
        # rather than an absent key, so normalise None to it.
        actual = params.get(key)
        if key == "border_style" and actual is None:
            actual = "none"
        features += [1.0 if actual == v else 0.0 for v in vocab[key]]
    return np.array(features, dtype=np.float64)


_CATEGORICAL_PREFIXES = {"border_style": "brd", "symmetry": "sym", "palette": "pal"}


def feature_names(vocab=None):
    """Names matching params_to_features' output, for reporting importances."""
    vocab = vocab if vocab is not None else build_feature_vocab()
    names = [name for name, _default in _NUMERIC_FEATURES] + list(_FLAG_FEATURES)
    for key in _CATEGORICAL_BASE:
        names += [f"{_CATEGORICAL_PREFIXES[key]}_{v}" for v in vocab[key]]
    return names


def current_policy():
    """Snapshot of everything that shapes what the scorer shows, as plain JSON.

    start_round stores this on each round so "what distribution generated
    round N" is a lookup rather than archaeology. The R22 post-mortem needed
    that: quilt_stitch's 0.70 importance turned out to be a time confound
    (stitching didn't exist before R7), and nothing recorded when the
    generative space had changed.
    """
    return {
        "param_space": {k: list(v) for k, v in PARAM_SPACE.items()},
        "feature_probs": dict(FEATURE_PROBS),
        "n_colors_weights": {str(k): v for k, v in N_COLORS_WEIGHTS.items()},
        "border_weights": dict(_BORDER_WEIGHTS),
        "stitch_weights": dict(_STITCH_WEIGHTS),
        "drop_palettes": sorted(_DROP_PALETTES),
        "drop_symmetry": sorted(_DROP_SYMMETRY),
        "proven_palettes": dict(_PROVEN_PALETTES),
        "proven_symmetries": dict(_PROVEN_SYMMETRIES),
        "explore_prob": EXPLORE_PROB,
        "n_candidates": _N_CANDIDATES,
        "max_palette_frac": MAX_PALETTE_FRAC,
        "clip_top_n": _CLIP_TOP_N,
        "clip_candidate_block_size": _CLIP_CANDIDATE_BLOCK_SIZE,
        "clip_embed_block_size": _CLIP_EMBED_BLOCK_SIZE,
        "train_from_round": _TRAIN_FROM_ROUND,
        "min_training_ratings": _MIN_TRAINING_RATINGS,
        "param_model": dict(_PARAM_MODEL_KWARGS),
        "clip_model": dict(_CLIP_MODEL_KWARGS),
    }


def _git_commit():
    """Short HEAD sha, suffixed "-dirty" if the tree has uncommitted changes.

    The policy dict can't capture renderer or layout changes, which shift what
    a seed looks like just as much, so a round also records the code version.
    None when git isn't available.
    """
    here = os.path.dirname(os.path.abspath(__file__))

    def git(*args):
        return subprocess.check_output(
            ["git", *args], cwd=here, stderr=subprocess.DEVNULL, text=True
        ).strip()

    try:
        sha = git("rev-parse", "--short", "HEAD")
        dirty = git("status", "--porcelain", "--untracked-files=no")
    except (OSError, subprocess.SubprocessError):
        return None
    return sha + ("-dirty" if dirty else "")


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
        # One-hot vocabulary for the current fit. Rebuilt on every retrain so a
        # newly-seen palette widens it, and held on the instance so scoring a
        # candidate encodes identically to how the training rows were encoded.
        self.vocab = build_feature_vocab()
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
        _atomic_write_json(self.data_path, self.ratings)

    def _save_rounds(self):
        _atomic_write_json(self.rounds_path, self.rounds)

    def start_round(self, label=None):
        """Start a new scoring round. Returns the round number.

        Records the sampling policy and code version alongside the boundary
        (see current_policy). Rounds started before this was added have
        neither key: absent means unknown, not "same as now".
        """
        num = len(self.rounds) + 1
        self.rounds.append(
            {
                "round": num,
                "label": label or f"R{num}",
                "start_index": len(self.ratings),
                "ts": time.time(),
                "commit": _git_commit(),
                "policy": current_policy(),
            }
        )
        self._save_rounds()
        return num

    def _save_embeddings(self):
        # Write to a temp file then atomically replace, so an interrupted save
        # (or a concurrent reader) never sees a half-written array.
        tmp = self.embeddings_path + ".tmp.npy"
        np.save(tmp, self.embeddings)
        os.replace(tmp, self.embeddings_path)

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

    def training_start(self):
        """First rating index to train on — see _TRAIN_FROM_ROUND.

        Falls back to 0 when the round log doesn't reach that far or the window
        would leave too little to fit on, so a fresh install still trains.
        """
        start = next(
            (r["start_index"] for r in self.rounds if r.get("round") == _TRAIN_FROM_ROUND),
            0,
        )
        if len(self.ratings) - start < _MIN_TRAINING_RATINGS:
            return 0
        return start

    def _retrain(self):
        """Retrain both preference models on the current training window."""
        start = self.training_start()
        window = self.ratings[start:]
        # Vocabulary describes the training distribution, so values that only
        # appear before the window don't occupy permanently-zero columns.
        self.vocab = build_feature_vocab(window)
        if len(window) < 10:
            self.model = None
            self.clip_model = None
            return
        features = np.array([params_to_features(r["params"], self.vocab) for r in window])
        y = np.array([1 if r["liked"] else 0 for r in window])
        if len(set(y)) < 2:
            self.model = None
            self.clip_model = None
            return

        self.model = GradientBoostingClassifier(**_PARAM_MODEL_KWARGS)
        self.model.fit(features, y)

        # Train CLIP model on ratings that have valid (non-zero) embeddings.
        # Reset first so a prior fit is dropped if the CLIP data no longer
        # qualifies (otherwise suggest_params keeps using a stale model).
        self.clip_model = None
        # Clamp to the aligned prefix in case embeddings and ratings ever differ.
        n_emb = min(len(self.embeddings) - start, len(y))
        if n_emb >= 10:
            emb = self.embeddings[start : start + n_emb]
            y_emb = y[:n_emb]
            valid = np.linalg.norm(emb, axis=1) > 0
            x_valid = emb[valid]
            y_valid = y_emb[valid]
            if len(x_valid) >= 10 and len(set(y_valid)) >= 2:
                self.clip_model = LogisticRegression(**_CLIP_MODEL_KWARGS)
                self.clip_model.fit(x_valid, y_valid)

    def suggest_params(self, explore_prob=EXPLORE_PROB):  # pylint: disable=too-many-locals
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
        candidates = [sample_random_params(rng, explore_only=True) for _ in range(_N_CANDIDATES)]
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
        features = np.array([params_to_features(c, self.vocab) for c in candidates])
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
        start = self.training_start()
        result = {
            "total": len(self.ratings),
            "liked": liked,
            "disliked": len(self.ratings) - liked,
            "model_active": self.model is not None,
            "clip_model_active": self.clip_model is not None,
            "embeddings_count": len(self.embeddings),
            "trained_on": len(self.ratings) - start,
            "train_from_round": _TRAIN_FROM_ROUND if start else 1,
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
        names = feature_names(self.vocab)
        importances = self.model.feature_importances_
        return sorted(zip(names, importances), key=lambda x: -x[1])
