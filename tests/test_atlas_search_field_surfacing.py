"""Atlas search field surfacing — discoverability fixes from the
Granulator III silent-instrument incident (2026-05-08).

The bug: atlas_search returned only the truncated first 120 chars of
sonic_description and didn't expose `self_contained` or signature
techniques. An agent calling atlas_search saw "Three playback modes —
Classic (2 overlapping grains per stereo cha…" cut off mid-word, then
loaded Granulator III without realizing it requires a source sample.

The fix: `_surface_enriched_fields()` pulls discoverability-critical
fields from the YAML so the agent doesn't need a follow-up
atlas_device_info round-trip. Truncation widened 120 → 400 chars.
"""

from __future__ import annotations

from mcp_server.atlas import tools as atlas_tools


# ── _surface_enriched_fields direct unit tests ────────────────────────


def test_self_contained_false_is_surfaced():
    """The flag that prevents the Granulator-III bug class."""
    device = {
        "self_contained": False,
        "synthesis_type": "granular",
    }
    out = atlas_tools._surface_enriched_fields(device)
    assert out["self_contained"] is False
    assert out["synthesis_type"] == "granular"


def test_self_contained_true_is_surfaced():
    """Self-contained devices like Drift report True so callers can branch."""
    device = {
        "self_contained": True,
        "synthesis_type": "subtractive",
    }
    out = atlas_tools._surface_enriched_fields(device)
    assert out["self_contained"] is True


def test_self_contained_absent_is_omitted():
    """Devices without the field don't get a phantom default — caller
    must not assume self-contained when atlas is silent."""
    out = atlas_tools._surface_enriched_fields({})
    assert "self_contained" not in out


def test_signature_technique_first_hint_pulled():
    device = {
        "signature_techniques": [
            {
                "name": "Instant deep-minimal texture",
                "description": "Load any vocal snippet → Cloud mode, Grain Size 200-500ms → immediate organic evolving bed.",
            },
            {"name": "Other technique", "description": "..."},
        ],
    }
    out = atlas_tools._surface_enriched_fields(device)
    assert out["signature_techniques_count"] == 2
    assert "Load any vocal snippet" in out["first_technique_hint"]


def test_first_technique_falls_back_to_name_when_no_description():
    device = {
        "signature_techniques": [{"name": "Cloud-mode pad"}],
    }
    out = atlas_tools._surface_enriched_fields(device)
    assert out["first_technique_hint"] == "Cloud-mode pad"


def test_first_technique_truncation():
    long_desc = "x" * 500
    device = {
        "signature_techniques": [{"description": long_desc}],
    }
    out = atlas_tools._surface_enriched_fields(device)
    assert len(out["first_technique_hint"]) == 240


def test_use_cases_capped_at_six():
    device = {
        "use_cases": [f"case_{i}" for i in range(20)],
    }
    out = atlas_tools._surface_enriched_fields(device)
    assert len(out["use_cases"]) == 6


def test_gotchas_first_surfaced():
    device = {
        "gotchas": [
            "Cloud mode with 20 grains + 500ms size is CPU-heavy",
            "Position at 1.0 (end of sample) goes silent",
        ],
    }
    out = atlas_tools._surface_enriched_fields(device)
    assert out["gotchas_count"] == 2
    assert "CPU-heavy" in out["first_gotcha"]


def test_complexity_surfaced():
    device = {"complexity": "intermediate"}
    out = atlas_tools._surface_enriched_fields(device)
    assert out["complexity"] == "intermediate"


def test_empty_device_returns_empty():
    """No fields → no surfacing. No phantoms."""
    assert atlas_tools._surface_enriched_fields({}) == {}


def test_simulated_granulator_iii_payload():
    """End-to-end: feed a representative Granulator III enrichment and
    verify every discoverability-critical field gets surfaced."""
    device = {
        "id": "granulator_iii",
        "name": "Granulator III",
        "self_contained": False,
        "synthesis_type": "granular",
        "complexity": "intermediate",
        "use_cases": ["texture", "drone", "vocal_chop", "evolving_pad", "cloud", "atmosphere"],
        "signature_techniques": [
            {
                "name": "Instant deep-minimal texture",
                "description": "Load any vocal snippet → Cloud mode, Grain Size 200-500ms.",
            },
            {"name": "Vocal-to-chord-cloud"},
            {"name": "Real-time capture and grain"},
        ],
        "gotchas": [
            "Cloud mode with 20 grains is CPU-heavy",
            "Position at 1.0 goes silent",
        ],
    }
    out = atlas_tools._surface_enriched_fields(device)
    assert out["self_contained"] is False
    assert out["synthesis_type"] == "granular"
    assert out["complexity"] == "intermediate"
    assert out["use_cases"] == ["texture", "drone", "vocal_chop", "evolving_pad", "cloud", "atmosphere"]
    assert out["signature_techniques_count"] == 3
    assert "Load any vocal snippet" in out["first_technique_hint"]
    assert out["gotchas_count"] == 2
    assert "CPU-heavy" in out["first_gotcha"]


# ── Truncation cap ────────────────────────────────────────────────────


def test_description_cap_is_400_chars():
    """The cap was widened 120 → 400 to surface critical sentences after
    the 120-char prefix. Granulator III's full description is ~700 chars;
    400 covers the first paragraph including the sample-required mention."""
    assert atlas_tools._ATLAS_SEARCH_DESCRIPTION_CHAR_CAP == 400


# ── No regression on non-enriched fields ──────────────────────────────


def test_helper_handles_partial_enrichment_gracefully():
    """A device with only some enrichment fields shouldn't raise."""
    out = atlas_tools._surface_enriched_fields({
        "self_contained": True,
        # no synthesis_type, no use_cases, no techniques, no gotchas
    })
    assert out == {"self_contained": True}
