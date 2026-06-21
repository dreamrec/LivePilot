"""Tests for AtlasManager — indexed device lookup, search, suggest, chain, compare."""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from mcp_server.atlas import AtlasManager


# ── Sample atlas fixture (3 devices) ────────────────────────────────

SAMPLE_ATLAS = {
    "meta": {
        "version": "2.0.0",
        "generated": "2026-04-13",
    },
    "devices": [
        {
            "id": "drift",
            "name": "Drift",
            "uri": "ableton:Drift",
            "category": "instrument",
            "description": "Warm analog-modeled synthesizer with two oscillators and a rich filter section",
            "tags": ["synth", "analog", "warm", "subtractive"],
            "genres": {
                "primary": ["electronic", "ambient"],
                "secondary": ["pop", "lo-fi"],
            },
            "use_cases": ["bass lines", "warm pads", "lead melodies"],
            "key_parameters": ["Osc 1 Shape", "Filter Cutoff", "Resonance"],
            "sweet_spot": "Start with Osc 1 saw, filter cutoff at 60%, resonance at 20%",
            "cpu_weight": "low",
        },
        {
            "id": "wavetable",
            "name": "Wavetable",
            "uri": "ableton:Wavetable",
            "category": "instrument",
            "description": "Modern wavetable synthesizer for evolving textures and complex timbres",
            "tags": ["synth", "wavetable", "modern", "texture"],
            "genres": {
                "primary": ["electronic", "future bass"],
                "secondary": ["pop", "cinematic"],
            },
            "use_cases": ["evolving pads", "supersaw leads", "bass design"],
            "key_parameters": ["Wavetable Position", "Sub Amount", "Filter Freq"],
            "sweet_spot": "Scan wavetable position with LFO for movement",
            "cpu_weight": "medium",
        },
        {
            "id": "compressor",
            "name": "Compressor",
            "uri": "ableton:Compressor",
            "category": "effect",
            "description": "Versatile dynamics processor for controlling levels and adding punch",
            "tags": ["dynamics", "compression", "mixing", "punch"],
            "genres": {
                "primary": ["all"],
                "secondary": [],
            },
            "use_cases": ["bus glue", "drum punch", "vocal leveling", "sidechain compression"],
            "key_parameters": ["Threshold", "Ratio", "Attack", "Release"],
            "sweet_spot": "Gentle 2:1 ratio for bus glue, 4:1+ for drums",
            "cpu_weight": "low",
        },
    ],
}


@pytest.fixture
def atlas_path(tmp_path):
    """Write sample atlas to a temp file and return its path."""
    path = tmp_path / "device_atlas.json"
    path.write_text(json.dumps(SAMPLE_ATLAS))
    return str(path)


@pytest.fixture
def atlas(atlas_path):
    """Create an AtlasManager from the sample atlas."""
    return AtlasManager(atlas_path)


# ── Loading and stats ───────────────────────────────────────────────


def test_load_device_count(atlas):
    assert atlas.device_count == 3


def test_version(atlas):
    assert atlas.version == "2.0.0"


def test_stats_structure(atlas):
    s = atlas.stats
    assert s["version"] == "2.0.0"
    assert s["device_count"] == 3
    assert s["categories"]["instrument"] == 2
    assert s["categories"]["effect"] == 1
    assert "by_id" in s["index_sizes"]
    assert "by_name" in s["index_sizes"]
    assert "by_uri" in s["index_sizes"]
    assert "by_tag" in s["index_sizes"]
    assert s["index_sizes"]["by_id"] == 3
    assert s["index_sizes"]["by_name"] == 3


# ── Lookup ──────────────────────────────────────────────────────────


def test_lookup_by_id(atlas):
    dev = atlas.lookup("drift")
    assert dev is not None
    assert dev["name"] == "Drift"


def test_lookup_by_name_case_insensitive(atlas):
    dev = atlas.lookup("DRIFT")
    assert dev is not None
    assert dev["id"] == "drift"

    dev2 = atlas.lookup("wavetable")
    assert dev2 is not None
    assert dev2["id"] == "wavetable"

    dev3 = atlas.lookup("Compressor")
    assert dev3 is not None
    assert dev3["id"] == "compressor"


def test_lookup_by_uri(atlas):
    dev = atlas.lookup("ableton:Drift")
    assert dev is not None
    assert dev["name"] == "Drift"


def test_lookup_miss_returns_none(atlas):
    assert atlas.lookup("nonexistent_device") is None
    assert atlas.lookup("") is None
    assert atlas.lookup("ableton:FakeDevice") is None


# ── Search ──────────────────────────────────────────────────────────


def test_search_by_name_exact(atlas):
    results = atlas.search("Drift")
    assert len(results) >= 1
    assert results[0]["device"]["id"] == "drift"
    # BUG-B41: exact-name match score lowered from 100 to 45 so that
    # character-tag matches can compete. Exact-name is still the
    # single strongest signal; we just no longer let it smother
    # sonic/tag matches.
    assert results[0]["score"] >= 45


def test_search_by_name_substring(atlas):
    results = atlas.search("wave")
    assert len(results) >= 1
    names = [r["device"]["name"] for r in results]
    assert "Wavetable" in names


def test_search_by_tag(atlas):
    results = atlas.search("compression")
    assert len(results) >= 1
    ids = [r["device"]["id"] for r in results]
    assert "compressor" in ids


def test_search_by_use_case(atlas):
    results = atlas.search("bass")
    assert len(results) >= 1
    # Both Drift and Wavetable have bass use cases
    ids = [r["device"]["id"] for r in results]
    assert "drift" in ids


def test_search_by_genre(atlas):
    results = atlas.search("ambient")
    assert len(results) >= 1
    ids = [r["device"]["id"] for r in results]
    assert "drift" in ids


def test_search_by_description_keyword(atlas):
    results = atlas.search("analog")
    assert len(results) >= 1
    assert results[0]["device"]["id"] == "drift"


def test_search_category_filter(atlas):
    results = atlas.search("synth", category="instrument")
    ids = [r["device"]["id"] for r in results]
    assert "compressor" not in ids
    assert len(ids) >= 1

    results_fx = atlas.search("compression", category="effect")
    ids_fx = [r["device"]["id"] for r in results_fx]
    assert "compressor" in ids_fx
    assert "drift" not in ids_fx


def test_search_limit(atlas):
    results = atlas.search("synth", limit=1)
    assert len(results) == 1


def test_search_no_results(atlas):
    results = atlas.search("zyxwvut_nonexistent")
    assert results == []


def test_search_empty_query(atlas):
    results = atlas.search("")
    assert results == []


# ── Suggest ─────────────────────────────────────────────────────────


def test_suggest_returns_ranked(atlas):
    results = atlas.suggest("bass synthesizer")
    assert len(results) >= 1
    first = results[0]
    assert "device" in first
    assert "rationale" in first
    assert "recipe" in first


def test_suggest_has_rationale(atlas):
    results = atlas.suggest("warm pads")
    assert len(results) >= 1
    for r in results:
        assert isinstance(r["rationale"], str)
        assert len(r["rationale"]) > 0


def test_suggest_has_recipe(atlas):
    results = atlas.suggest("bass")
    assert len(results) >= 1
    for r in results:
        assert isinstance(r["recipe"], dict)
        assert "energy" in r["recipe"]


def test_suggest_with_genre(atlas):
    results = atlas.suggest("synth", genre="electronic")
    assert len(results) >= 1


def test_suggest_respects_limit(atlas):
    results = atlas.suggest("synth", limit=1)
    assert len(results) == 1


def test_suggest_recipe_includes_sweet_spot(atlas):
    results = atlas.suggest("Drift")
    assert len(results) >= 1
    # Drift has a sweet_spot, so recipe should include it
    drift_results = [r for r in results if r["device"]["id"] == "drift"]
    if drift_results:
        assert "sweet_spot" in drift_results[0]["recipe"]


# ── Chain Suggest ───────────────────────────────────────────────────


def test_chain_suggest_returns_structure(atlas):
    result = atlas.chain_suggest("bass")
    assert "role" in result
    assert "genre" in result
    assert "chain" in result
    assert result["role"] == "bass"


def test_chain_suggest_has_instrument_position(atlas):
    result = atlas.chain_suggest("bass")
    chain = result["chain"]
    assert len(chain) >= 1
    # First device should be an instrument at position 0
    instrument_entries = [c for c in chain if c["device"].get("category") == "instrument"]
    assert len(instrument_entries) >= 1
    assert instrument_entries[0]["position"] == 0


def test_chain_suggest_ordered(atlas):
    result = atlas.chain_suggest("pad")
    chain = result["chain"]
    positions = [c["position"] for c in chain]
    assert positions == sorted(positions)


def test_chain_suggest_with_genre(atlas):
    result = atlas.chain_suggest("bass", genre="electronic")
    assert result["genre"] == "electronic"
    assert len(result["chain"]) >= 1


def test_chain_suggest_entries_have_reason(atlas):
    result = atlas.chain_suggest("lead")
    for entry in result["chain"]:
        assert "reason" in entry
        assert isinstance(entry["reason"], str)
        assert len(entry["reason"]) > 0


# ── Compare ─────────────────────────────────────────────────────────


def test_compare_returns_both_devices(atlas):
    result = atlas.compare("Drift", "Wavetable")
    assert "device_a" in result
    assert "device_b" in result
    assert result["device_a"]["name"] == "Drift"
    assert result["device_b"]["name"] == "Wavetable"


def test_compare_has_recommendation(atlas):
    result = atlas.compare("Drift", "Wavetable")
    assert "recommendation" in result
    assert isinstance(result["recommendation"], str)


def test_compare_with_role(atlas):
    result = atlas.compare("Drift", "Wavetable", role="bass")
    assert "recommendation" in result
    # Both have bass use cases, recommendation should mention role
    assert "bass" in result["recommendation"].lower() or "equally" in result["recommendation"].lower()


def test_compare_missing_device_a(atlas):
    result = atlas.compare("FakeDevice", "Drift")
    assert "error" in result


def test_compare_missing_device_b(atlas):
    result = atlas.compare("Drift", "FakeDevice")
    assert "error" in result


def test_compare_summary_fields(atlas):
    result = atlas.compare("Drift", "Compressor")
    for key in ("name", "category", "tags", "genres", "use_cases", "description"):
        assert key in result["device_a"]
        assert key in result["device_b"]


def test_compare_role_scoring_favors_better_match(atlas):
    # Compressor has "sidechain compression" use case, Drift doesn't mention sidechain
    result = atlas.compare("Drift", "Compressor", role="sidechain")
    assert "Compressor" in result["recommendation"]


# ── Pack index (T4 — 2026-04-22 handoff) ───────────────────────────


PACK_ATLAS = {
    "meta": {"version": "2.0.0"},
    "devices": [
        {
            "id": "harmonic_drone_generator",
            "name": "Harmonic Drone Generator",
            "uri": "ableton:HDG",
            "category": "max_for_live",
            "source": "browser",
            "pack": "Drone Lab",
            "enriched": True,
        },
        {
            "id": "pitch_hack",
            "name": "Pitch Hack",
            "uri": "ableton:PitchHack",
            "category": "audio_effects",
            "source": "browser",
            "pack": "Creative Extensions",
            "enriched": True,
        },
        {
            "id": "analog",
            "name": "Analog",
            "uri": "ableton:Analog",
            "category": "instruments",
            "source": "browser",
            "enriched": True,
            # no pack field — should fall under Core Library via heuristic
        },
        {
            "id": "random_plugin",
            "name": "Some VST",
            "uri": "vst:somevst",
            "category": "plugins",
            "source": "plugin",
            # no pack — no fallback, stays unindexed
        },
    ],
}


@pytest.fixture
def pack_atlas(tmp_path):
    path = tmp_path / "pack_atlas.json"
    path.write_text(json.dumps(PACK_ATLAS))
    return AtlasManager(str(path))


def test_by_pack_index_populated(pack_atlas):
    assert "Drone Lab" in pack_atlas._by_pack
    assert "Creative Extensions" in pack_atlas._by_pack
    # Native device with no explicit pack falls back to Core Library
    assert "Core Library" in pack_atlas._by_pack
    # Plugin without pack doesn't get indexed
    plugin_packs = [p for p, devs in pack_atlas._by_pack.items()
                    if any(d["id"] == "random_plugin" for d in devs)]
    assert plugin_packs == []


def test_pack_info_case_insensitive(pack_atlas):
    info = pack_atlas.pack_info("drone lab")
    assert info["pack"] == "Drone Lab"
    assert info["device_count"] == 1
    assert info["enriched_count"] == 1
    assert info["devices"][0]["name"] == "Harmonic Drone Generator"


def test_pack_info_miss_surfaces_available_packs(pack_atlas):
    info = pack_atlas.pack_info("Nonexistent Pack")
    assert info["device_count"] == 0
    assert "available_packs" in info
    assert "Drone Lab" in info["available_packs"]


def test_pack_info_core_library_includes_native(pack_atlas):
    info = pack_atlas.pack_info("Core Library")
    assert info["device_count"] >= 1
    names = [d["name"] for d in info["devices"]]
    assert "Analog" in names


def test_list_packs_sorted_descending(pack_atlas):
    packs = pack_atlas.list_packs()
    counts = [p["device_count"] for p in packs]
    assert counts == sorted(counts, reverse=True)


def test_pack_info_empty_string_handled(pack_atlas):
    info = pack_atlas.pack_info("")
    assert info["device_count"] == 0
    assert info["devices"] == []


def test_stats_includes_by_pack(pack_atlas):
    stats = pack_atlas.stats
    assert "by_pack" in stats["index_sizes"]
    assert stats["index_sizes"]["by_pack"] >= 2
