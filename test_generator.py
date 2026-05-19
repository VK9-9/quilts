"""Tests for generator.py — Flask webapp routes and param parsing."""
import pytest
from generator import app, PRESETS, _params_to_render_kwargs


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# --- _params_to_render_kwargs ---

class TestParamsToRenderKwargs:

    def test_basic_conversion(self):
        params = {
            "palette": "ocean breeze", "symmetry": "bargello",
            "chaos": 0.3, "rows": 16, "cols": 16, "n_patterns": 2,
            "n_colors": 4, "tile_size": 6, "tile_variation": 0.1,
            "border_style": "none", "sash_width": 0, "cornerstones": False,
            "color_gradient": "none", "mega_frac": 0.0, "plain_frac": 0.0,
            "quilt_stitch": "grid", "wonky": 0.0, "seed": 42,
        }
        kwargs = _params_to_render_kwargs(params, block_size=36)
        assert kwargs["rows"] == 16
        assert kwargs["block_size"] == 36
        assert kwargs["palette_name"] == "ocean breeze"
        assert kwargs["output"] is None  # always returns bytes
        assert kwargs["border_style"] is None  # "none" → None
        assert kwargs["color_gradient"] is None  # "none" → None

    def test_tile_size_zero_becomes_none(self):
        params = {
            "palette": "ocean breeze", "symmetry": "none",
            "chaos": 0.3, "rows": 16, "cols": 16, "n_patterns": 2,
            "n_colors": 4, "tile_size": 0, "tile_variation": 0.1,
            "border_style": "solid", "seed": 42,
        }
        kwargs = _params_to_render_kwargs(params)
        assert kwargs["tile_size"] is None

    def test_border_style_solid_preserved(self):
        params = {
            "palette": "ocean breeze", "symmetry": "none",
            "chaos": 0.3, "rows": 16, "cols": 16, "n_patterns": 2,
            "n_colors": 4, "tile_size": 6, "tile_variation": 0.1,
            "border_style": "solid", "seed": 42,
        }
        kwargs = _params_to_render_kwargs(params)
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
            "seed": 12345, "palette": "ocean breeze", "symmetry": "bargello",
            "chaos": 0.3, "rows": 16, "cols": 16, "n_patterns": 2,
            "n_colors": 4, "tile_size": 5, "tile_variation": 0.1,
            "border_style": "none", "mega_frac": 0.0, "plain_frac": 0.0,
            "quilt_stitch": "grid", "wonky": 0.0,
        }
        qid = encode(params)
        resp = client.get(f"/create?id={qid}")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "ocean breeze" in html

    def test_create_with_invalid_quilt_id(self, client):
        resp = client.get("/create?id=invalid!!!")
        assert resp.status_code == 200  # falls back to defaults


class TestRenderRoute:

    def test_render_returns_png(self, client):
        resp = client.get("/render?seed=42&symmetry=bargello&palette=ocean+breeze&rows=4")
        assert resp.status_code == 200
        assert resp.content_type == "image/png"
        assert resp.data[:8] == b'\x89PNG\r\n\x1a\n'

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


class TestParamParsing:

    def test_invalid_int_falls_back(self, client):
        resp = client.get("/render?seed=42&symmetry=bargello&palette=ocean+breeze&rows=abc")
        assert resp.status_code == 200  # "abc" can't parse as int → uses default

    def test_stitch_none_string(self, client):
        resp = client.get(
            "/render?seed=42&symmetry=bargello&palette=ocean+breeze"
            "&rows=4&quilt_stitch=none"
        )
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
            assert p["palette"] in _V2_PALETTES, \
                f"Preset {key} palette '{p['palette']}' not in V2 palettes"
            assert p["symmetry"] in _V2_SYMMETRY, \
                f"Preset {key} symmetry '{p['symmetry']}' not in V2 symmetries"

    def test_all_presets_renderable(self, client):
        """Each preset should produce a valid PNG via /render."""
        for key, preset in PRESETS.items():
            params = preset["params"]
            qs = "&".join(f"{k}={v}" for k, v in params.items()
                         if k not in ("cornerstones",))
            resp = client.get(f"/render?{qs}")
            assert resp.status_code == 200, f"Preset {key} failed to render"
            assert resp.data[:8] == b'\x89PNG\r\n\x1a\n'
