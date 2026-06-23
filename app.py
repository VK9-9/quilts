"""Flask webapp for active learning of quilt aesthetic preferences."""

import json
import sys
import os
import threading

sys.path.insert(0, os.path.dirname(__file__))

# pylint: disable=wrong-import-position
from flask import Flask, render_template, request, jsonify, Response
from quilt import render_quilt
from sampler import QuiltExplorer
from render_params import params_to_render_kwargs
# pylint: enable=wrong-import-position

app = Flask(__name__)
_ratings_path = sys.argv[1] if len(sys.argv) > 1 else "data/ratings.json"
explorer = QuiltExplorer(_ratings_path)

# The Flask dev server is threaded, so two requests can mutate explorer state
# (ratings list, embeddings array, model) concurrently. Serialize all mutations
# so the non-atomic in-memory updates and file writes can't interleave/corrupt.
_explorer_lock = threading.Lock()


@app.route("/")
def index():
    """Serve the rating UI."""
    return render_template("index.html")


@app.route("/next")
def next_quilt():
    """Return suggested quilt params plus model stats."""
    params = explorer.suggest_params()
    return jsonify(
        {
            "params": params,
            "stats": explorer.stats(),
            "importance": explorer.feature_importance(),
        }
    )


@app.route("/render")
def render():
    """Render a quilt PNG from params and return it."""
    raw = request.args.get("params")
    if not raw:
        return jsonify({"error": "missing params"}), 400
    try:
        params = json.loads(raw)
        kwargs = params_to_render_kwargs(params)
    except (ValueError, KeyError, TypeError) as exc:
        return jsonify({"error": f"bad params: {exc}"}), 400
    png_bytes = render_quilt(**kwargs)
    return Response(png_bytes, mimetype="image/png")


@app.route("/rate", methods=["POST"])
def rate():
    """Record a like/dislike rating for a quilt."""
    data = request.get_json()
    with _explorer_lock:
        explorer.add_rating(data["params"], data["liked"])
    return jsonify({"ok": True})


@app.route("/round", methods=["POST"])
def start_round():
    """Start a new scoring round."""
    data = request.get_json() or {}
    with _explorer_lock:
        num = explorer.start_round(label=data.get("label"))
    return jsonify({"round": num})


if __name__ == "__main__":
    # Local admin tool, but the Werkzeug debugger is an RCE console — opt in with
    # FLASK_DEBUG=1 rather than shipping it on, and never bind this to 0.0.0.0.
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1", port=5555)
