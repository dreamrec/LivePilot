"""Tests for v1.25 atlas knowledge-surface tools (explore / audition / substitute).

These tests exercise the pure-Python implementations in
mcp_server/atlas/explore_tools.py — the @mcp.tool() wrappers in atlas/tools.py
just forward arguments, so they're covered by the contract test (test_tools_contract.py).
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from mcp_server.atlas.explore_tools import (
    audition,
    explore,
    substitute,
    _resolve_anti_tags,
)


# v1.25 — `explore` (which delegates to `AtlasResolver.resolve_for_role`) now
# unions factory atlas hits with extension_atlas overlay results. These unit
# tests scope ranking and cohort_hint inference to the FACTORY atlas only, so
# the disk-backed overlay loader must be neutralized for the duration of each
# test in this module. Stub `get_overlay_index` to return an empty index.
@pytest.fixture(autouse=True)
def _stub_overlay_index(monkeypatch):
    stub = MagicMock()
    stub.search.return_value = []
    monkeypatch.setattr(
        "mcp_server.atlas.overlays.get_overlay_index",
        lambda: stub,
    )


# ── Shared atlas stub ───────────────────────────────────────────────


def _device(
    name: str,
    *,
    uri: str = "",
    tags: list[str] | None = None,
    pack: str | None = None,
    signature_techniques: list[str] | None = None,
    category: str = "instruments",
    dev_id: str | None = None,
):
    return {
        "id": dev_id or name.lower().replace(" ", "_"),
        "name": name,
        "uri": uri or f"atlas://{name.lower().replace(' ', '_')}",
        "tags": list(tags or []),
        "character_tags": list(tags or []),
        "signature_techniques": list(signature_techniques or []),
        "pack": pack,
        "category": category,
        "enriched": bool(signature_techniques),
    }


def _make_atlas(devices: list[dict]):
    atlas = MagicMock()
    by_tag: dict[str, list[dict]] = {}
    by_pack: dict[str, list[dict]] = {}
    by_uri: dict[str, dict] = {}
    by_name: dict[str, dict] = {}
    for dev in devices:
        for tag in dev.get("character_tags", []) or dev.get("tags", []):
            by_tag.setdefault(str(tag).lower(), []).append(dev)
        if dev.get("pack"):
            by_pack.setdefault(dev["pack"], []).append(dev)
        if dev.get("uri"):
            by_uri[dev["uri"]] = dev
        if dev.get("name"):
            by_name[dev["name"].lower()] = dev
    atlas._by_tag = by_tag
    atlas._by_pack = by_pack
    atlas._by_uri = by_uri
    atlas._by_name = by_name
    atlas.lookup = lambda nid: (
        by_uri.get(nid)
        or by_name.get((nid or "").lower())
        or next((d for d in devices if d.get("id") == nid), None)
    )
    return atlas


# ── atlas_explore ───────────────────────────────────────────────────


class TestExplore:
    def test_returns_candidates_for_role(self):
        atlas = _make_atlas([_device("PunchyKick", tags=["kick"])])
        out = explore(atlas=atlas, role="kick", n=5)
        assert isinstance(out, dict)
        assert "candidates" in out
        assert len(out["candidates"]) == 1
        assert out["candidates"][0]["name"] == "PunchyKick"

    def test_no_atlas_returns_empty_with_reasoning(self):
        out = explore(atlas=None, role="kick", n=5)
        assert out["candidates"] == []
        assert "atlas not loaded" in out["reasoning"]

    def test_cohort_constraint_passes_through(self):
        atlas = _make_atlas([
            _device("InCohort", tags=["pad"], pack="pitchloop89"),
            _device("OutCohort", tags=["pad"], pack="other"),
        ])
        out = explore(atlas=atlas, role="pad", cohort_constraint=["pitchloop89"], n=5)
        names = [c["name"] for c in out["candidates"]]
        assert "InCohort" in names
        assert "OutCohort" not in names
        assert out["cohort_hint"] == "pitchloop89"

    def test_avoid_uris_excludes(self):
        atlas = _make_atlas([
            _device("PadA", uri="atlas://a", tags=["pad"]),
            _device("PadB", uri="atlas://b", tags=["pad"]),
        ])
        out = explore(atlas=atlas, role="pad", avoid_uris=["atlas://a"], n=5)
        names = [c["name"] for c in out["candidates"]]
        assert "PadA" not in names
        assert "PadB" in names

    def test_cohort_hint_inferred_when_no_constraint(self):
        atlas = _make_atlas([
            _device("DroneLabPad1", tags=["pad"], pack="drone-lab"),
            _device("DroneLabPad2", tags=["pad"], pack="drone-lab"),
            _device("OtherPad", tags=["pad"], pack="other"),
        ])
        out = explore(atlas=atlas, role="pad", n=5)
        # Most frequent pack across results should be the hint
        assert out["cohort_hint"] == "drone-lab"

    def test_candidate_dict_has_all_fields(self):
        atlas = _make_atlas([
            _device("Pad1", uri="atlas://p1", tags=["pad"], pack="pp"),
        ])
        out = explore(atlas=atlas, role="pad", n=5)
        c = out["candidates"][0]
        for key in (
            "uri", "name", "source", "score",
            "character_tags", "signature_techniques",
            "in_pack", "has_curated_adg", "reasoning",
        ):
            assert key in c, f"missing {key} in candidate"


# ── atlas_audition ──────────────────────────────────────────────────


class TestAudition:
    def test_returns_device_metadata(self):
        atlas = _make_atlas([
            _device("PitchLoop89", uri="atlas://pl89",
                    tags=["spectral", "stretch"], pack="pitchloop89"),
        ])
        out = audition(atlas=atlas, uri="atlas://pl89")
        assert out["name"] == "PitchLoop89"
        assert out["pack"] == "pitchloop89"
        assert "spectral" in out["character_tags"]

    def test_signature_techniques_loaded_from_index(self):
        # Use a device id that exists in the real device_techniques_index.json
        atlas = _make_atlas([
            _device("PitchLoop89", uri="atlas://pl89",
                    tags=["spectral"], pack="pitchloop89",
                    dev_id="pitchloop89"),
        ])
        out = audition(atlas=atlas, uri="atlas://pl89")
        # The index has entries for "pitchloop89" — at least one should surface
        assert isinstance(out["signature_techniques"], list)
        # Don't hard-assert non-empty (would couple test to index contents);
        # just confirm shape is correct
        for tech in out["signature_techniques"]:
            assert "technique" in tech
            assert "description" in tech

    def test_unknown_uri_returns_error(self):
        atlas = _make_atlas([])
        out = audition(atlas=atlas, uri="atlas://nope")
        assert "error" in out
        assert out["uri"] == "atlas://nope"

    def test_no_atlas_returns_error(self):
        out = audition(atlas=None, uri="atlas://anything")
        assert "error" in out

    def test_required_response_fields_present(self):
        atlas = _make_atlas([_device("X", uri="atlas://x", tags=["pad"])])
        out = audition(atlas=atlas, uri="atlas://x")
        for key in (
            "uri", "name", "id", "pack", "category",
            "character_tags", "signature_techniques",
            "producer_macros", "curated_adg_paths",
            "enriched", "related_demos",
        ):
            assert key in out, f"missing {key} in audition result"


# ── atlas_substitute ────────────────────────────────────────────────


class TestResolveAntiTags:
    def test_bright_resolves_excluded_and_preferred(self):
        excl, pref = _resolve_anti_tags("bright")
        assert "bright" in excl
        assert "warm" in pref

    def test_too_bright_and_harsh_aggregates(self):
        excl, pref = _resolve_anti_tags("too bright and harsh")
        assert "bright" in excl
        assert "harsh" in excl
        # both rule sets contribute
        assert any(t in pref for t in ("warm", "smooth"))

    def test_unknown_returns_empty(self):
        excl, pref = _resolve_anti_tags("xyz_nonexistent")
        assert excl == []
        assert pref == []


class TestSubstitute:
    def test_unknown_anti_tag_returns_error(self):
        atlas = _make_atlas([
            _device("PadA", uri="atlas://a", tags=["pad"]),
        ])
        out = substitute(atlas=atlas, current_uri="atlas://a", anti_tag="zzz_nonsense")
        assert "error" in out
        assert "supported_anti_tags" in out

    def test_excludes_anti_tagged_alternatives(self):
        atlas = _make_atlas([
            _device("BrightPad", uri="atlas://bright", tags=["pad", "bright"]),
            _device("WarmPad", uri="atlas://warm", tags=["pad", "warm"]),
            _device("MutedPad", uri="atlas://muted", tags=["pad", "muted"]),
        ])
        out = substitute(
            atlas=atlas,
            current_uri="atlas://bright",
            anti_tag="too bright",
            n=5,
        )
        names = [a["name"] for a in out["alternatives"]]
        # The "bright" device should not appear in alternatives
        assert "BrightPad" not in names
        # Warm/muted should both pass the filter (don't carry "bright" tag)
        assert "WarmPad" in names or "MutedPad" in names

    def test_unknown_uri_returns_error(self):
        atlas = _make_atlas([])
        out = substitute(atlas=atlas, current_uri="atlas://nope", anti_tag="bright")
        assert "error" in out

    def test_no_atlas_returns_error(self):
        out = substitute(atlas=None, current_uri="atlas://x", anti_tag="bright")
        assert "error" in out

    def test_n_truncation(self):
        devs = [_device("BrightSrc", uri="atlas://src", tags=["pad", "bright"])]
        for i in range(8):
            devs.append(_device(f"WarmPad{i}", uri=f"atlas://w{i}", tags=["pad", "warm"]))
        atlas = _make_atlas(devs)
        out = substitute(
            atlas=atlas,
            current_uri="atlas://src",
            anti_tag="too bright",
            n=3,
        )
        assert len(out["alternatives"]) == 3

    def test_response_has_full_context(self):
        atlas = _make_atlas([
            _device("Src", uri="atlas://src", tags=["pad", "bright"]),
            _device("Alt", uri="atlas://alt", tags=["pad", "warm"]),
        ])
        out = substitute(atlas=atlas, current_uri="atlas://src", anti_tag="bright")
        for key in (
            "current_uri", "current_name", "anti_tag",
            "excluded_tags", "preferred_tags",
            "alternatives", "reasoning",
        ):
            assert key in out, f"missing {key} in substitute result"
