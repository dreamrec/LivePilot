"""Smoke tests for atlas_macro_fingerprint (Pack-Atlas Phase D).

Tests run purely on filesystem sidecars — no Ableton session required.
All assertions use real corpus data from
~/.livepilot/atlas-overlays/packs/_preset_parses/.
"""
from __future__ import annotations

import pathlib
import pytest


# Skip the whole module if the sidecar corpus isn't present
PRESET_PARSES_ROOT = (
    pathlib.Path.home()
    / ".livepilot"
    / "atlas-overlays"
    / "packs"
    / "_preset_parses"
)
pytestmark = pytest.mark.skipif(
    not PRESET_PARSES_ROOT.exists(),
    reason="Preset sidecar corpus not present at ~/.livepilot/atlas-overlays/packs/_preset_parses/",
)


def _find_sidecar_stem(pack_slug: str, keyword: str) -> str | None:
    """Locate a sidecar stem containing keyword in its filename (case-insensitive)."""
    pack_dir = PRESET_PARSES_ROOT / pack_slug
    if not pack_dir.is_dir():
        return None
    for p in sorted(pack_dir.glob("*.json")):
        if keyword.lower() in p.stem.lower():
            return p.stem
    return None


# ─── Test 1: Main corpus source — finds ≥3 matches, all ≥0.4 ─────────────────

def test_macro_fingerprint_named_source():
    """Source preset with named macros returns ≥3 matches all above threshold.

    Uses a drone-lab laboratory instrument rack that has 6 producer-named
    macros (Filter Control, Movement, Low Cut, Attack, Release, Chorus).
    Top matches must come from the instrument_rack class and include cross-pack
    results. All returned matches must be at or above the 0.4 similarity floor.
    [SOURCE: adg-parse]
    """
    stem = _find_sidecar_stem("drone-lab", "razor-wire-drone")
    if stem is None:
        pytest.skip("drone-lab/razor-wire-drone sidecar not found")

    from mcp_server.atlas.tools import atlas_macro_fingerprint

    result = atlas_macro_fingerprint(
        ctx=None,
        source_pack_slug="drone-lab",
        source_preset_path=stem,
        top_k=5,
    )

    assert "error" not in result, f"Tool returned error: {result.get('error')}"
    assert len(result["matches"]) >= 3, (
        f"Expected ≥3 matches, got {len(result['matches'])}"
    )
    for m in result["matches"]:
        assert m["similarity_score"] >= 0.4, (
            f"Match {m['preset_name']} has score {m['similarity_score']} < 0.4"
        )

    # Source block must be well-formed
    src = result["source"]
    assert src["pack_slug"] == "drone-lab"
    assert src["fingerprint_strength"] in ("strong", "moderate", "weak")
    assert len(src["macros_named"]) >= 3

    # Top match must be from a known aesthetic-adjacent pack
    top = result["matches"][0]
    known_adjacent_packs = {
        "drone-lab", "mood-reel", "inspired-by-nature-by-dillon-bastan",
        "glitch-and-wash", "synth-essentials", "beat-tools",
        "punch-and-tilt", "creative-extensions",
    }
    assert top["pack_slug"] in known_adjacent_packs, (
        f"Top match pack '{top['pack_slug']}' not in expected adjacent packs"
    )

    # Sources citation must be present
    assert result["sources"]
    assert any("adg-parse" in s for s in result["sources"])


# ─── Test 2: Cross-pack match — spectral/dub-techno rationale ────────────────

def test_macro_fingerprint_cross_pack_match():
    """Spectral audio effect rack source returns cross-pack matches with
    'spectral' or 'dub-techno' in the rationale prose for at least one result.

    Uses drone-lab's Partial Discord (AudioEffectGroupDevice with 'Spectral Amount'
    macro) as source, filtered to AudioEffectGroupDevice candidates.
    Proves synonym matching bridges cross-pack vocabulary.
    [SOURCE: adg-parse]
    """
    stem = _find_sidecar_stem(
        "drone-lab", "partial-discord"
    )
    if stem is None:
        pytest.skip("drone-lab/partial-discord sidecar not found")

    from mcp_server.atlas.tools import atlas_macro_fingerprint

    result = atlas_macro_fingerprint(
        ctx=None,
        source_pack_slug="drone-lab",
        source_preset_path=stem,
        rack_class_filter="AudioEffectGroupDevice",
        top_k=8,
    )

    assert "error" not in result, f"Tool returned error: {result.get('error')}"
    assert len(result["matches"]) >= 1, (
        "Expected ≥1 cross-pack audio effect rack match"
    )

    # At least one match must have spectral or dub-techno in rationale
    rationales = [m["rationale"].lower() for m in result["matches"]]
    assert any(
        "spectral" in r or "dub-techno" in r for r in rationales
    ), (
        f"No rationale mentions 'spectral' or 'dub-techno'. Got: {rationales}"
    )

    # Cross-pack: at least one match outside drone-lab
    cross_pack = [m for m in result["matches"] if m["pack_slug"] != "drone-lab"]
    assert cross_pack, "Expected at least one cross-pack match"


# ─── Test 3: Weak source is rejected with informative error ─────────────────

def test_macro_fingerprint_rejects_weak_source():
    """Source preset with <3 producer-named macros returns an error dict
    with an informative message, not a low-quality match list.

    Uses an inspired-by-nature preset where all macros use default 'Macro N'
    names — fingerprint is empty, below the min_named_macros floor.
    [SOURCE: adg-parse]
    """
    # Find an inspired-by-nature sidecar with only default macro names
    stem = _find_sidecar_stem(
        "inspired-by-nature-by-dillon-bastan", "brutal-feedback"
    )
    if stem is None:
        # Try any preset in the pack with all-default macro names
        pack_dir = PRESET_PARSES_ROOT / "inspired-by-nature-by-dillon-bastan"
        if not pack_dir.is_dir():
            pytest.skip("inspired-by-nature pack sidecar dir not found")
        import json
        stem = None
        for p in sorted(pack_dir.glob("*.json")):
            d = json.loads(p.read_text())
            named = [
                m for m in d.get("macros", [])
                if m.get("name", "") and not m["name"].startswith("Macro ")
            ]
            if len(named) == 0:
                stem = p.stem
                break
        if stem is None:
            pytest.skip("No all-default-macro preset found for weak-source test")

    from mcp_server.atlas.tools import atlas_macro_fingerprint

    result = atlas_macro_fingerprint(
        ctx=None,
        source_pack_slug="inspired-by-nature-by-dillon-bastan",
        source_preset_path=stem,
        min_named_macros=3,
    )

    assert "error" in result, (
        f"Expected an error for weak source but got matches: {result}"
    )
    # Error message must be specific, not generic
    error_text = result["error"].lower()
    assert "producer-named" in error_text or "named macro" in error_text, (
        f"Error message not descriptive enough: {result['error']}"
    )
    # Must include suggestion on how to recover
    assert "suggestion" in result or "hint" in result or "suggestion" in result, (
        "Error response should include a 'suggestion' key"
    )


# ─── Test 4: Missing sidecar returns informative error ───────────────────────

def test_macro_fingerprint_missing_sidecar():
    """Requesting a nonexistent sidecar returns an error with a helpful hint."""
    from mcp_server.atlas.tools import atlas_macro_fingerprint

    result = atlas_macro_fingerprint(
        ctx=None,
        source_pack_slug="drone-lab",
        source_preset_path="this-preset-does-not-exist",
    )

    assert "error" in result
    assert "drone-lab" in result["error"] or "Sidecar not found" in result["error"]
    # Should include a hint listing available files
    assert "hint" in result


# ─── Test 5: No source params returns usage error ────────────────────────────

def test_macro_fingerprint_no_source_params():
    """Calling with no source params returns a descriptive error."""
    from mcp_server.atlas.tools import atlas_macro_fingerprint

    result = atlas_macro_fingerprint(ctx=None)

    assert "error" in result
    assert "source_pack_slug" in result["error"] or "Provide either" in result["error"]


# ─── Test 6: Unit-level synonym canonicalization ─────────────────────────────

def test_synonym_canonicalization():
    """Known synonym variants must collapse to the same canonical key."""
    from mcp_server.atlas.macro_fingerprint import _canonicalize_macro_name

    pairs = [
        ("Filter Control", "filter_cutoff"),
        ("filter freq",     "filter_cutoff"),
        ("Filter Cutoff",   "filter_cutoff"),
        ("Cutoff",          "filter_cutoff"),
        ("Movement",        "movement"),
        ("LFO Amount",      "lfo_amount"),
        ("Reverb",          "reverb"),
        ("Space",           "reverb"),
        ("Attack",          "attack"),
        ("Release",         "release"),
        ("Chorus",          "chorus"),
        ("Drive",           "drive"),
    ]
    for raw, expected in pairs:
        got = _canonicalize_macro_name(raw)
        assert got == expected, (
            f"_canonicalize_macro_name({raw!r}) = {got!r}, expected {expected!r}"
        )


# ─── Test 7: Performance — full scan < 2 seconds ────────────────────────────

def test_macro_fingerprint_performance():
    """Full corpus scan completes under 2 seconds (p95 requirement from spec)."""
    import time

    stem = _find_sidecar_stem("drone-lab", "razor-wire-drone")
    if stem is None:
        pytest.skip("drone-lab/razor-wire-drone sidecar not found")

    # Clear lru_cache to force re-read for this timing test
    from mcp_server.atlas.macro_fingerprint import _load_preset_sidecar
    _load_preset_sidecar.cache_clear()

    from mcp_server.atlas.tools import atlas_macro_fingerprint

    t0 = time.monotonic()
    result = atlas_macro_fingerprint(
        ctx=None,
        source_pack_slug="drone-lab",
        source_preset_path=stem,
        top_k=8,
    )
    elapsed = time.monotonic() - t0

    assert "error" not in result, f"Tool error during perf test: {result.get('error')}"
    assert elapsed < 2.0, (
        f"Full corpus scan took {elapsed:.2f}s — exceeds 2s p95 target"
    )


# ─── Test 8: BUG-EDGE#1 — string top_k/min_named_macros/similarity_threshold ──

def test_macro_fingerprint_string_top_k():
    """BUG-EDGE#1: top_k='10' must not raise TypeError: slice indices must be integers."""
    from mcp_server.atlas.tools import atlas_macro_fingerprint

    # This must not crash even with no corpus present; an error dict is fine
    result = atlas_macro_fingerprint(
        ctx=None,
        source_pack_slug="drone-lab",
        source_preset_path="nonexistent-preset-for-type-test",
        top_k="10",
    )
    # Must return a dict, not raise TypeError
    assert isinstance(result, dict)


def test_macro_fingerprint_string_min_named_macros():
    """BUG-EDGE#1: min_named_macros='3' must not raise TypeError."""
    from mcp_server.atlas.tools import atlas_macro_fingerprint

    result = atlas_macro_fingerprint(
        ctx=None,
        source_pack_slug="drone-lab",
        source_preset_path="nonexistent-preset-for-type-test",
        min_named_macros="3",
    )
    assert isinstance(result, dict)


def test_macro_fingerprint_string_similarity_threshold():
    """BUG-EDGE#1: similarity_threshold='0.5' must not raise TypeError."""
    from mcp_server.atlas.tools import atlas_macro_fingerprint

    result = atlas_macro_fingerprint(
        ctx=None,
        source_pack_slug="drone-lab",
        source_preset_path="nonexistent-preset-for-type-test",
        similarity_threshold="0.5",
    )
    assert isinstance(result, dict)
