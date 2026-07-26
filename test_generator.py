"""Tests for generator.py — Flask webapp routes and param parsing."""

import re

import pytest
from generator import app, PRESETS
from quilt import render_quilt
from render_params import params_to_render_kwargs


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# --- params_to_render_kwargs ---


class TestParamsToRenderKwargs:
    def test_basic_conversion(self):
        params = {
            "palette": "ocean breeze",
            "symmetry": "bargello",
            "chaos": 0.3,
            "rows": 16,
            "cols": 16,
            "n_patterns": 2,
            "n_colors": 4,
            "tile_size": 6,
            "tile_variation": 0.1,
            "border_style": "none",
            "mega_frac": 0.0,
            "plain_frac": 0.0,
            "quilt_stitch": "grid",
            "wonky": 0.0,
            "seed": 42,
        }
        kwargs = params_to_render_kwargs(params, block_size=36)
        assert kwargs["rows"] == 16
        assert kwargs["block_size"] == 36
        assert kwargs["palette_name"] == "ocean breeze"
        assert kwargs["output"] is None  # always returns bytes
        assert kwargs["border_style"] is None  # "none" → None

    def test_tile_size_zero_becomes_none(self):
        params = {
            "palette": "ocean breeze",
            "symmetry": "none",
            "chaos": 0.3,
            "rows": 16,
            "cols": 16,
            "n_patterns": 2,
            "n_colors": 4,
            "tile_size": 0,
            "tile_variation": 0.1,
            "border_style": "solid",
            "seed": 42,
        }
        kwargs = params_to_render_kwargs(params)
        assert kwargs["tile_size"] is None

    def test_border_style_solid_preserved(self):
        params = {
            "palette": "ocean breeze",
            "symmetry": "none",
            "chaos": 0.3,
            "rows": 16,
            "cols": 16,
            "n_patterns": 2,
            "n_colors": 4,
            "tile_size": 6,
            "tile_variation": 0.1,
            "border_style": "solid",
            "seed": 42,
        }
        kwargs = params_to_render_kwargs(params)
        assert kwargs["border_style"] == "solid"


# --- Routes ---


class TestIndexRoute:
    def test_index_returns_200(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_index_contains_preset_names(self, client):
        resp = client.get("/")
        html = resp.data.decode()
        for key, preset in PRESETS.items():
            assert preset["name"] in html

    def test_index_has_build_info(self, client):
        resp = client.get("/")
        html = resp.data.decode()
        assert "UTC" in html  # build_time contains UTC


class TestCreateRoute:
    def test_create_default(self, client):
        resp = client.get("/create")
        assert resp.status_code == 200

    def test_create_with_preset(self, client):
        resp = client.get("/create?preset=bargello-calm")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "lavender fields" in html

    def test_create_with_invalid_preset(self, client):
        resp = client.get("/create?preset=nonexistent")
        assert resp.status_code == 200  # falls back to defaults

    def test_create_with_quilt_id(self, client):
        from quilt_id import encode

        params = {
            "seed": 12345,
            "palette": "ocean breeze",
            "symmetry": "bargello",
            "chaos": 0.3,
            "rows": 16,
            "cols": 16,
            "n_patterns": 2,
            "n_colors": 4,
            "tile_size": 5,
            "tile_variation": 0.1,
            "border_style": "none",
            "mega_frac": 0.0,
            "plain_frac": 0.0,
            "quilt_stitch": "grid",
            "wonky": 0.0,
        }
        qid = encode(params)
        resp = client.get(f"/create?id={qid}")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "ocean breeze" in html

    def test_create_with_invalid_quilt_id(self, client):
        resp = client.get("/create?id=invalid!!!")
        assert resp.status_code == 200  # falls back to defaults


class TestCreateControlsAlwaysBound:
    """Every control the editor renders must carry a real value on every entry path.

    Jinja renders a missing key as "", and the HTML value-sanitization algorithm
    resolves an empty <input type=range> value to the slider midpoint. Presets and
    decoded quilt IDs both omit the advanced controls, so this used to silently open
    every preset and shared-ID page at strippy=0.3 / wash_alpha=0.1.
    """

    def _entry_urls(self):
        from quilt_id import encode

        qid = encode(
            {
                "seed": 12345,
                "palette": "ocean breeze",
                "symmetry": "bargello",
                "chaos": 0.3,
                "rows": 16,
                "cols": 16,
                "n_patterns": 2,
                "n_colors": 4,
                "tile_size": 5,
                "tile_variation": 0.1,
                "border_style": "none",
                "mega_frac": 0.0,
                "plain_frac": 0.0,
                "quilt_stitch": "grid",
                "wonky": 0.0,
            }
        )
        return ["/create", f"/create?id={qid}"] + [f"/create?preset={k}" for k in PRESETS]

    @staticmethod
    def _range_values(html):
        return dict(re.findall(r'<input type="range" id="(\w+)"[^>]*?value="([^"]*)"', html, re.S))

    def test_every_range_input_has_a_numeric_value(self, client):
        for url in self._entry_urls():
            html = client.get(url).data.decode()
            values = self._range_values(html)
            assert values, f"{url}: no range inputs found — did the template change?"
            for name, raw in values.items():
                assert raw != "", f"{url}: range input '{name}' rendered an empty value"
                float(raw)  # raises if the browser would reject it

    def test_advanced_controls_default_to_off(self, client):
        """A preset or ID that says nothing about strippy/wash must open at zero."""
        for url in self._entry_urls():
            values = self._range_values(client.get(url).data.decode())
            assert float(values["strippy"]) == 0.0, f"{url}: strippy defaulted on"
            assert float(values["wash_alpha"]) == 0.0, f"{url}: wash_alpha defaulted on"

    def test_quilt_size_selection_round_trips(self, client):
        for size_key in ["throw", "queen", "sq10"]:
            html = client.get(f"/create?quilt_size={size_key}").data.decode()
            selected = re.findall(r'<option value="(\w+)" selected>', html)
            assert size_key in selected, f"quilt_size={size_key} not selected in the editor"

    def test_rows_slider_covers_the_encodable_range(self, client):
        """Slider bounds, server clamp, and the quilt-ID field must agree."""
        from generator import _PARAM_BOUNDS

        html = client.get("/create").data.decode()
        lo, hi = re.search(r'id="rows" min="(\d+)" max="(\d+)"', html).groups()
        assert (int(lo), int(hi)) == _PARAM_BOUNDS["rows"]


class TestRenderRoute:
    def test_render_returns_png(self, client):
        resp = client.get("/render?seed=42&symmetry=bargello&palette=ocean+breeze&rows=4")
        assert resp.status_code == 200
        assert resp.content_type == "image/png"
        assert resp.data[:8] == b"\x89PNG\r\n\x1a\n"

    def test_render_no_cache(self, client):
        resp = client.get("/render?seed=42&symmetry=bargello&palette=ocean+breeze&rows=4")
        assert resp.headers.get("Cache-Control") == "no-store"

    def test_render_returns_quilt_id(self, client):
        resp = client.get("/render?seed=42&symmetry=bargello&palette=ocean+breeze&rows=4")
        qid = resp.headers.get("X-Quilt-Id")
        assert qid is not None
        assert len(qid) == 14  # V2 encoding

    def test_render_with_params(self, client):
        resp = client.get(
            "/render?seed=42&symmetry=bargello&palette=lavender+fields"
            "&rows=4&n_colors=3&tile_size=4&chaos=0.5"
        )
        assert resp.status_code == 200


class TestDownloadRoute:
    def test_download_returns_png(self, client):
        resp = client.get("/download?seed=42&symmetry=bargello&palette=ocean+breeze&rows=4")
        assert resp.status_code == 200
        assert resp.content_type == "image/png"

    def test_download_has_filename(self, client):
        resp = client.get("/download?seed=42&symmetry=bargello&palette=ocean+breeze&rows=4")
        cd = resp.headers.get("Content-Disposition", "")
        assert "attachment" in cd
        assert "quilt-" in cd
        assert ".png" in cd


class TestPatternRoute:
    def test_pattern_returns_pdf(self, client):
        resp = client.get("/pattern?seed=42&symmetry=rotational&palette=ocean+breeze&rows=4")
        assert resp.status_code == 200
        assert resp.content_type == "application/pdf"
        assert resp.data[:5] == b"%PDF-"

    def test_pattern_has_filename(self, client):
        resp = client.get("/pattern?seed=42&symmetry=rotational&palette=ocean+breeze&rows=4")
        cd = resp.headers.get("Content-Disposition", "")
        assert "attachment" in cd
        assert "pattern-" in cd
        assert ".pdf" in cd

    def test_pattern_bargello(self, client):
        resp = client.get("/pattern?seed=42&symmetry=bargello&palette=ocean+breeze&rows=4")
        assert resp.status_code == 200
        assert resp.data[:5] == b"%PDF-"

    def test_pattern_with_quilt_size(self, client):
        resp = client.get(
            "/pattern?seed=42&symmetry=rotational&palette=ocean+breeze&rows=4&quilt_size=throw"
        )
        assert resp.status_code == 200


class TestParamParsing:
    def test_invalid_int_falls_back(self, client):
        resp = client.get("/render?seed=42&symmetry=bargello&palette=ocean+breeze&rows=abc")
        assert resp.status_code == 200  # "abc" can't parse as int → uses default

    def test_stitch_none_string(self, client):
        resp = client.get(
            "/render?seed=42&symmetry=bargello&palette=ocean+breeze&rows=4&quilt_stitch=none"
        )
        assert resp.status_code == 200

    def test_advanced_params_parsed(self, client):
        resp = client.get(
            "/render?seed=42&symmetry=bargello&palette=ocean+breeze"
            "&rows=4&wash_alpha=0.1&palette_2=wildflower&palette_mix=wisteria"
        )
        assert resp.status_code == 200

    def test_huge_rows_clamped(self, client):
        """Unbounded rows must not OOM the worker — params are clamped server-side."""
        from generator import _params_from_request

        with app.test_request_context("/render?rows=100000&strippy=1e9&tile_size=99999"):
            params = _params_from_request()
        assert params["rows"] <= 21
        assert params["tile_size"] <= 12
        assert params["strippy"] <= 0.6

    def test_invalid_palette_falls_back(self, client):
        """An unknown palette must not 500 (and must not leak the palette list)."""
        resp = client.get("/render?seed=42&rows=4&palette=definitely+not+a+palette")
        assert resp.status_code == 200

    def test_invalid_symmetry_falls_back(self, client):
        resp = client.get("/render?seed=42&rows=4&symmetry=bogus")
        assert resp.status_code == 200


class TestPresets:
    def test_all_presets_have_required_keys(self):
        for key, preset in PRESETS.items():
            assert "name" in preset, f"Preset {key} missing name"
            assert "description" in preset, f"Preset {key} missing description"
            assert "params" in preset, f"Preset {key} missing params"

    def test_all_preset_params_have_palette(self):
        from quilt_id import _V2_PALETTES, _V2_SYMMETRY

        for key, preset in PRESETS.items():
            p = preset["params"]
            assert p["palette"] in _V2_PALETTES, (
                f"Preset {key} palette '{p['palette']}' not in V2 palettes"
            )
            assert p["symmetry"] in _V2_SYMMETRY, (
                f"Preset {key} symmetry '{p['symmetry']}' not in V2 symmetries"
            )

    def test_all_presets_renderable(self, client):
        """Each preset should produce a valid PNG via /render."""
        for key, preset in PRESETS.items():
            params = preset["params"]
            qs = "&".join(f"{k}={v}" for k, v in params.items())
            resp = client.get(f"/render?{qs}")
            assert resp.status_code == 200, f"Preset {key} failed to render"
            assert resp.data[:8] == b"\x89PNG\r\n\x1a\n"

    def test_presets_render_through_the_thumbnail_path(self):
        """render_family_thumbnails.py must be able to rebuild every card.

        It renders preset params directly rather than via the request parser, so
        a preset missing a key params_to_render_kwargs requires (cols, n_patterns)
        broke the script silently — the committed PNGs simply went stale.
        """
        from generator import complete_params

        for key, preset in PRESETS.items():
            kwargs = params_to_render_kwargs(complete_params(preset["params"]), 8)
            assert kwargs["cols"] > 0, f"Preset {key} produced no cols"
            assert render_quilt(**kwargs)[:8] == b"\x89PNG\r\n\x1a\n"

    def test_thumbnail_matches_the_create_page(self, client):
        """A card's image and the page it links to must be the same quilt."""
        from generator import complete_params

        for key, preset in PRESETS.items():
            landed = client.get(f"/create?preset={key}").data.decode()
            values = dict(
                re.findall(r'<input type="range" id="(\w+)"[^>]*?value="([^"]*)"', landed, re.S)
            )
            thumb_params = complete_params(preset["params"])
            for control, raw in values.items():
                assert float(raw) == pytest.approx(float(thumb_params[control])), (
                    f"Preset {key}: card renders {control}="
                    f"{thumb_params[control]} but /create opens at {raw}"
                )
