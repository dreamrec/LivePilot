"""Browser load_browser_item atlas-aware preflight tests.

The bug: load_browser_item("query:Synths#Granulator III") loaded the
instrument silently — Granulator III without a sample produces no
audio, and nothing in the load response warned that follow-up was
needed.

The fix: _atlas_preflight_for_load() looks up the loaded device in
the atlas and returns a structured warning when self_contained=false.
The result dict gets an `atlas_preflight` block the agent can act on.
"""

from __future__ import annotations

from mcp_server.tools import browser


class _FakeAtlas:
    """Minimal AtlasManager substitute for testing the preflight helper."""

    def __init__(self, entries: dict[str, dict]):
        self.entries = entries

    def lookup(self, name_or_id: str):
        # Match by name or id (case-insensitive)
        key = (name_or_id or "").lower().strip()
        for k, v in self.entries.items():
            if k.lower() == key or v.get("name", "").lower() == key:
                return v
        return None


def _install_fake_atlas(monkeypatch, entries: dict[str, dict]):
    """Patch mcp_server.atlas.get_atlas to return a fake atlas."""
    fake = _FakeAtlas(entries)

    import mcp_server.atlas as atlas_module
    monkeypatch.setattr(atlas_module, "get_atlas", lambda: fake)
    return fake


# ── Self-contained → no preflight warning ─────────────────────────────


def test_no_preflight_when_self_contained_true(monkeypatch):
    _install_fake_atlas(monkeypatch, {
        "drift": {
            "id": "drift", "name": "Drift",
            "enriched": True,
            "self_contained": True,
        }
    })
    assert browser._atlas_preflight_for_load("Drift") is None


def test_no_preflight_when_self_contained_field_absent(monkeypatch):
    """Self-contained-by-default for atlas entries without the explicit
    flag — don't fire false-positive warnings on non-enriched devices."""
    _install_fake_atlas(monkeypatch, {
        "operator": {
            "id": "operator", "name": "Operator",
            "enriched": True,
            # no self_contained field
        }
    })
    assert browser._atlas_preflight_for_load("Operator") is None


def test_no_preflight_when_device_not_in_atlas(monkeypatch):
    _install_fake_atlas(monkeypatch, {})
    assert browser._atlas_preflight_for_load("Some 3rd-Party VST") is None


def test_no_preflight_when_device_name_empty(monkeypatch):
    _install_fake_atlas(monkeypatch, {})
    assert browser._atlas_preflight_for_load("") is None
    assert browser._atlas_preflight_for_load(None) is None  # type: ignore[arg-type]


def test_no_preflight_when_atlas_unavailable(monkeypatch):
    """Atlas not loaded → preflight returns None silently, never raises."""
    import mcp_server.atlas as atlas_module
    monkeypatch.setattr(atlas_module, "get_atlas", lambda: None)
    assert browser._atlas_preflight_for_load("Granulator III") is None


def test_no_preflight_when_atlas_lookup_raises(monkeypatch):
    """Atlas lookup error → preflight returns None silently."""
    class _BoomAtlas:
        def lookup(self, *a, **kw):
            raise RuntimeError("atlas exploded")
    import mcp_server.atlas as atlas_module
    monkeypatch.setattr(atlas_module, "get_atlas", lambda: _BoomAtlas())
    assert browser._atlas_preflight_for_load("Granulator III") is None


def test_no_preflight_for_unenriched_entry(monkeypatch):
    """Enrichment is required — can't trust self_contained on unenriched."""
    _install_fake_atlas(monkeypatch, {
        "weird_3rd_party": {
            "id": "weird_3rd_party", "name": "Weird 3rd Party",
            "enriched": False,
            "self_contained": False,  # ignored — no enrichment
        }
    })
    assert browser._atlas_preflight_for_load("Weird 3rd Party") is None


# ── Self-contained=false → preflight fires ────────────────────────────


def test_preflight_fires_for_granulator_iii(monkeypatch):
    """The canonical case this fix prevents."""
    _install_fake_atlas(monkeypatch, {
        "granulator_iii": {
            "id": "granulator_iii", "name": "Granulator III",
            "enriched": True,
            "self_contained": False,
            "synthesis_type": "granular",
            "signature_techniques": [
                {
                    "name": "Instant deep-minimal texture",
                    "description": "Load any vocal snippet → Cloud mode, Grain Size 200-500ms.",
                }
            ],
        }
    })
    out = browser._atlas_preflight_for_load("Granulator III")
    assert out is not None
    assert out["self_contained"] is False
    assert out["device_id"] == "granulator_iii"
    assert "not self-contained" in out["warning"]
    assert "source sample or real-time audio capture" in out["warning"]
    assert "search_browser" in out["warning"]
    assert "Granulator III" in out["warning"]
    assert "Load any vocal snippet" in out["first_technique_hint"]


def test_preflight_fires_for_vector_grain(monkeypatch):
    """Same self_contained=false case, different device — confirm the
    preflight isn't Granulator-specific."""
    _install_fake_atlas(monkeypatch, {
        "vector_grain": {
            "id": "vector_grain", "name": "Vector Grain",
            "enriched": True,
            "self_contained": False,
            "synthesis_type": "granular",
        }
    })
    out = browser._atlas_preflight_for_load("Vector Grain")
    assert out is not None
    assert out["self_contained"] is False
    assert out["device_id"] == "vector_grain"
    assert "Vector Grain" in out["warning"]


def test_preflight_handles_missing_techniques(monkeypatch):
    """Some self_contained=false entries may not have signature_techniques.
    Don't crash — just produce empty hint."""
    _install_fake_atlas(monkeypatch, {
        "minimal_sampler": {
            "id": "minimal_sampler", "name": "Minimal Sampler",
            "enriched": True,
            "self_contained": False,
        }
    })
    out = browser._atlas_preflight_for_load("Minimal Sampler")
    assert out is not None
    assert out["self_contained"] is False
    assert out["first_technique_hint"] == ""


def test_preflight_truncates_long_technique_descriptions(monkeypatch):
    """Don't blow up the response with a 5KB technique description."""
    _install_fake_atlas(monkeypatch, {
        "verbose_grain": {
            "id": "verbose_grain", "name": "Verbose Grain",
            "enriched": True,
            "self_contained": False,
            "signature_techniques": [{"description": "x" * 1000}],
        }
    })
    out = browser._atlas_preflight_for_load("Verbose Grain")
    assert out is not None
    assert len(out["first_technique_hint"]) == 240


def test_preflight_lookup_handles_id_or_name(monkeypatch):
    """The atlas should resolve "Granulator III" or "granulator_iii" to
    the same entry — _FakeAtlas mimics this. The helper just passes the
    device_name through."""
    _install_fake_atlas(monkeypatch, {
        "granulator_iii": {
            "id": "granulator_iii", "name": "Granulator III",
            "enriched": True,
            "self_contained": False,
        }
    })
    out = browser._atlas_preflight_for_load("Granulator III")
    assert out is not None
