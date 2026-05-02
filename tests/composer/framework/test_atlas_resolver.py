"""Tests for AtlasResolver — v1.25 hybrid knowledge surface (Phase 1.1)."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from mcp_server.composer.framework.atlas_resolver import (
    AtlasAnchors,
    AtlasCandidate,
    AtlasResolver,
    BANNED_DEFAULT_MELODIC,
    OPAQUE_M4L_FOR_PAD,
)


# v1.25 — `resolve_for_role` now unions factory atlas hits with extension_atlas
# overlay results (packs/demo_project + all-namespace passes). These unit tests
# scope ranking math to the FACTORY atlas only, so the disk-backed overlay
# loader must be neutralized — otherwise real corpus content contaminates
# expected-candidate counts and ranking expectations. Stub `get_overlay_index`
# to return an empty index for every test in this module.
@pytest.fixture(autouse=True)
def _stub_overlay_index(monkeypatch):
    stub = MagicMock()
    stub.search.return_value = []
    monkeypatch.setattr(
        "mcp_server.atlas.overlays.get_overlay_index",
        lambda: stub,
    )


# ── Atlas stub builder ─────────────────────────────────────────────


def _device(
    name: str,
    *,
    uri: str = "",
    tags: list[str] | None = None,
    character_tags: list[str] | None = None,
    signature_techniques: list[str] | None = None,
    pack: str | None = None,
    has_curated_adg: bool = False,
    genres: dict | None = None,
) -> dict:
    """Fixture-builder for a device dict matching atlas YAML shape."""
    return {
        "id": name.lower().replace(" ", "_"),
        "name": name,
        "uri": uri or f"query:Synths#Synth/{name.replace(' ', '%20')}",
        "tags": list(tags or []),
        "character_tags": list(character_tags or tags or []),
        "signature_techniques": list(signature_techniques or []),
        "pack": pack,
        "has_curated_adg": has_curated_adg,
        "genres": genres or {},
        "enriched": bool(signature_techniques or character_tags),
    }


def _make_atlas(devices: list[dict]):
    """Build a minimal atlas object with _by_tag / _by_genre / _by_pack indexes."""
    atlas = MagicMock()
    by_tag: dict[str, list[dict]] = {}
    by_genre: dict[str, list[dict]] = {}
    by_pack: dict[str, list[dict]] = {}
    for dev in devices:
        for tag in dev.get("character_tags", []) or dev.get("tags", []):
            by_tag.setdefault(str(tag).lower(), []).append(dev)
        genres = dev.get("genres") or {}
        for genre in genres.get("primary", []):
            by_genre.setdefault(str(genre).lower(), []).append(dev)
        for genre in genres.get("secondary", []):
            by_genre.setdefault(str(genre).lower(), []).append(dev)
        if dev.get("pack"):
            by_pack.setdefault(dev["pack"], []).append(dev)
    atlas._by_tag = by_tag
    atlas._by_genre = by_genre
    atlas._by_pack = by_pack
    atlas.lookup = lambda nid: next(
        (d for d in devices if d.get("name") == nid or d.get("uri") == nid or d.get("id") == nid),
        None,
    )
    return atlas


# ── Ranking math ───────────────────────────────────────────────────


class TestRankingMath:
    def test_tag_match_baseline_returns_candidate(self):
        atlas = _make_atlas([_device("PunchyKick", tags=["kick"])])
        r = AtlasResolver(atlas=atlas)
        c = r.resolve_for_role(role="kick", n=5)
        assert len(c) == 1
        assert 0.0 < c[0].score <= 1.0
        assert c[0].name == "PunchyKick"

    def test_signature_technique_boost_overrides_baseline(self):
        atlas = _make_atlas([
            _device("PadA", tags=["pad"], signature_techniques=["spectral_stretch_drone"]),
            _device("PadB", tags=["pad"]),
        ])
        r = AtlasResolver(atlas=atlas)
        c = r.resolve_for_role(role="pad", mood="spectral warped", n=5)
        names = [x.name for x in c]
        assert names.index("PadA") < names.index("PadB")

    def test_curated_adg_boosts_above_bare(self):
        atlas = _make_atlas([
            _device("BareSynth", tags=["pad"], has_curated_adg=False),
            _device("CuratedSynth", tags=["pad"], has_curated_adg=True),
        ])
        r = AtlasResolver(atlas=atlas)
        c = r.resolve_for_role(role="pad", n=5)
        names = [x.name for x in c]
        assert names.index("CuratedSynth") < names.index("BareSynth")

    def test_section_one_banned_melodic_default_penalized(self):
        """§1: Drift penalized for pad role when mood doesn't say 'analog'."""
        atlas = _make_atlas([
            _device("Drift", tags=["pad", "synth"]),
            _device("PitchLoop89", tags=["pad", "spectral"]),
        ])
        r = AtlasResolver(atlas=atlas)
        c = r.resolve_for_role(role="pad", mood="dreamy", n=5)
        names = [x.name for x in c]
        assert names.index("PitchLoop89") < names.index("Drift")

    def test_banned_default_allowed_when_mood_has_analog(self):
        """§1 carve-out: 'analog subtractive' lifts the Drift penalty."""
        atlas = _make_atlas([
            _device("Drift", tags=["pad", "synth"]),
            _device("PitchLoop89", tags=["pad"]),
        ])
        r = AtlasResolver(atlas=atlas)
        c = r.resolve_for_role(role="pad", mood="analog subtractive warm", n=5)
        drift = next(x for x in c if x.name == "Drift")
        assert drift.score >= 0.5

    def test_opaque_m4l_pad_penalized(self):
        atlas = _make_atlas([
            _device("Poli", tags=["pad", "m4l"]),
            _device("PitchLoop89", tags=["pad"]),
        ])
        r = AtlasResolver(atlas=atlas)
        c = r.resolve_for_role(role="pad", n=5)
        names = [x.name for x in c]
        assert names.index("PitchLoop89") < names.index("Poli")

    def test_anti_repeat_penalty_via_recent_uris(self):
        atlas = _make_atlas([
            _device("FreshSynth", uri="atlas://fresh", tags=["pad"]),
            _device("RecentSynth", uri="atlas://recent", tags=["pad"]),
        ])
        r = AtlasResolver(atlas=atlas, recent_uris={"atlas://recent"})
        c = r.resolve_for_role(role="pad", n=5)
        names = [x.name for x in c]
        assert names.index("FreshSynth") < names.index("RecentSynth")

    def test_caller_supplied_avoid_list_penalizes(self):
        atlas = _make_atlas([
            _device("Wanted", tags=["pad"]),
            _device("Avoided", tags=["pad"]),
        ])
        r = AtlasResolver(atlas=atlas)
        c = r.resolve_for_role(role="pad", avoid=["Avoided"], n=5)
        names = [x.name for x in c]
        assert names.index("Wanted") < names.index("Avoided")


class TestResolveForRole:
    def test_n_truncation_limits_results(self):
        atlas = _make_atlas([_device(f"Pad{i}", tags=["pad"]) for i in range(10)])
        r = AtlasResolver(atlas=atlas)
        c = r.resolve_for_role(role="pad", n=3)
        assert len(c) == 3

    def test_cohort_constraint_filters_to_packs(self):
        atlas = _make_atlas([
            _device("CohortPad", tags=["pad"], pack="pitchloop89"),
            _device("OutsidePad", tags=["pad"], pack="other-pack"),
        ])
        r = AtlasResolver(atlas=atlas)
        c = r.resolve_for_role(role="pad", cohort_constraint=["pitchloop89"], n=5)
        names = [x.name for x in c]
        assert "CohortPad" in names
        assert "OutsidePad" not in names

    def test_excluded_uris_removes_candidates(self):
        atlas = _make_atlas([
            _device("PadA", uri="atlas://a", tags=["pad"]),
            _device("PadB", uri="atlas://b", tags=["pad"]),
        ])
        r = AtlasResolver(atlas=atlas)
        c = r.resolve_for_role(role="pad", excluded_uris={"atlas://a"}, n=5)
        names = [x.name for x in c]
        assert "PadA" not in names
        assert "PadB" in names

    def test_empty_atlas_returns_empty_list(self):
        atlas = _make_atlas([])
        r = AtlasResolver(atlas=atlas)
        c = r.resolve_for_role(role="pad", n=5)
        assert c == []

    def test_unknown_role_falls_back_to_role_string_as_tag(self):
        atlas = _make_atlas([_device("WeirdRoleDevice", tags=["weird_role"])])
        r = AtlasResolver(atlas=atlas)
        c = r.resolve_for_role(role="weird_role", n=5)
        assert len(c) >= 1

    def test_no_atlas_returns_empty(self):
        r = AtlasResolver(atlas=None)
        c = r.resolve_for_role(role="pad", n=5)
        assert c == []


class TestCandidateShape:
    def test_candidate_carries_required_fields(self):
        atlas = _make_atlas([
            _device(
                "PadA", uri="atlas://a", tags=["pad"],
                signature_techniques=["sig1"], pack="pp",
            )
        ])
        r = AtlasResolver(atlas=atlas)
        c = r.resolve_for_role(role="pad", n=5)
        a = c[0]
        assert a.uri == "atlas://a"
        assert a.name == "PadA"
        assert a.source == "atlas"
        assert 0.0 <= a.score <= 1.0
        assert isinstance(a.character_tags, list)
        assert "sig1" in a.signature_techniques
        assert a.in_pack == "pp"
        assert a.reasoning


class TestResolveAnchorsFallback:
    """Anchor resolution must degrade gracefully when pack_aware_compose unavailable.

    Full integration with pack_aware_compose tested in
    test_atlas_resolver_anchors_integration.py.
    """

    def test_anchors_returns_object_when_pack_aware_compose_errors(self, monkeypatch):
        atlas = _make_atlas([])

        def _fake_compose(**kwargs):
            return {"error": "fake outage", "status": "error"}

        monkeypatch.setattr(
            "mcp_server.atlas.pack_aware_compose.pack_aware_compose",
            _fake_compose,
        )
        r = AtlasResolver(atlas=atlas)
        anchors = r.resolve_anchors(brief_text="anything")
        assert isinstance(anchors, AtlasAnchors)
        assert anchors.pack_cohort == []
        assert "error" in anchors.reasoning.lower() or "outage" in anchors.reasoning.lower()

    def test_anchors_passes_through_pack_aware_compose_cohort(self, monkeypatch):
        atlas = _make_atlas([])

        def _fake_compose(**kwargs):
            return {
                "brief_analysis": {
                    "primary_aesthetic": "dub-techno-spectral",
                    "secondary_aesthetics": ["ambient"],
                    "anchor_producers": ["robert_henke"],
                    "anchor_genres": ["dub_techno"],
                    "pack_cohort": ["pitchloop89", "convolution-reverb"],
                },
                "pack_cohort": ["pitchloop89", "convolution-reverb"],
                "track_proposal": [
                    {"role": "harmonic-foundation", "preset": "pitchloop89/spectral_drone"},
                    {"role": "rhythmic-driver", "preset": "drum-essentials/dub_kit"},
                ],
                "warnings": [],
            }

        monkeypatch.setattr(
            "mcp_server.atlas.pack_aware_compose.pack_aware_compose",
            _fake_compose,
        )
        r = AtlasResolver(atlas=atlas)
        anchors = r.resolve_anchors(
            brief_text="dub-techno spectral henke",
            genre="dub_techno",
            mood="spectral",
            artist_refs=["Henke"],
        )
        assert anchors.primary_pack == "pitchloop89"
        assert "convolution-reverb" in anchors.pack_cohort
        assert anchors.primary_aesthetic == "dub-techno-spectral"
        assert "robert_henke" in anchors.anchor_producers
        # Coarse role 'harmonic-foundation' should map to fine role 'pad'
        assert anchors.cohort_uris.get("pad") == "pitchloop89/spectral_drone"
        # Coarse role 'rhythmic-driver' should map to drums (kick/snare/hat)
        assert anchors.cohort_uris.get("kick") == "drum-essentials/dub_kit"
