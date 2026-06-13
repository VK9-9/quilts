"""Flask webapp for active learning of quilt aesthetic preferences."""

import json
import sys
import os

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
    params = json.loads(request.args["params"])
    kwargs = params_to_render_kwargs(params)
    png_bytes = render_quilt(**kwargs)
    return Response(png_bytes, mimetype="image/png")


@app.route("/rate", methods=["POST"])
def rate():
    """Record a like/dislike rating for a quilt."""
    data = request.get_json()
    explorer.add_rating(data["params"], data["liked"])
    return jsonify({"ok": True})


@app.route("/round", methods=["POST"])
def start_round():
    """Start a new scoring round."""
    data = request.get_json() or {}
    num = explorer.start_round(label=data.get("label"))
    return jsonify({"round": num})


if __name__ == "__main__":
    app.run(debug=True, port=5555)
