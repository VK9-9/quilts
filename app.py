"""Flask webapp for active learning of quilt aesthetic preferences."""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, render_template, request, jsonify, Response

from quilt import render_quilt
from sampler import QuiltExplorer, params_to_render_kwargs

app = Flask(__name__)
explorer = QuiltExplorer()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/next")
def next_quilt():
    params = explorer.suggest_params()
    return jsonify({
        "params": params,
        "stats": explorer.stats(),
        "importance": explorer.feature_importance(),
    })


@app.route("/render")
def render():
    params = json.loads(request.args["params"])
    kwargs = params_to_render_kwargs(params)
    png_bytes = render_quilt(**kwargs)
    return Response(png_bytes, mimetype="image/png")


@app.route("/rate", methods=["POST"])
def rate():
    data = request.get_json()
    explorer.add_rating(data["params"], data["liked"])
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(debug=True, port=5555)
