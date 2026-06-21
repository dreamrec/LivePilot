"""Tests for the Plugin Knowledge Engine — Phase 2.1-2.4 detector + manual flow,
plus Phase 3 + 4 packet builders.

Detection runs against synthetic plugin bundle layouts in tmp_path so tests
are hermetic. Live integration with the user's actual plugin folder is
out-of-scope for CI (machine-specific).
"""

from __future__ import annotations

import json
import plistlib
from pathlib import Path

import pytest

from mcp_server.user_corpus.plugin_engine import (
    DetectedPlugin,
    detect_installed_plugins,
    discover_manuals_for_plugin,
    extract_manual_text,
    build_research_targets,
    build_synthesis_brief,
)
from mcp_server.user_corpus.plugin_engine.detector import (
    _identify_vst3, _identify_au, _identify_vst2,
)
from mcp_server.user_corpus.plugin_engine.manual import (
    ManualCandidate, _score_candidate, _detect_sections,
)


# ─── VST3 detector ───────────────────────────────────────────────────────────


def test_vst3_with_moduleinfo(tmp_path):
    bundle = tmp_path / "Diva.vst3"
    (bundle / "Contents" / "Resources").mkdir(parents=True)
    (bundle / "Contents" / "Resources" / "moduleinfo.json").write_text(json.dumps({
        "Name": "Diva",
        "Vendor": "u-he",
        "Version": "1.4.5",
        "URL": "https://u-he.com/products/diva/",
        "Classes": [{"CID": "ABCDEF01", "Name": "Diva", "Vendor": "u-he"}],
    }))
    plugin = _identify_vst3(bundle)
    assert plugin is not None
    assert plugin.format == "VST3"
    assert plugin.name == "Diva"
    assert plugin.vendor == "u-he"
    assert plugin.version == "1.4.5"
    assert plugin.unique_id == "ABCDEF01"
    assert plugin.plugin_id == "u-he-diva"


def test_vst3_without_moduleinfo_falls_back_to_plist(tmp_path):
    """Pre-3.7 VST3 bundles have no moduleinfo.json — use Info.plist."""
    bundle = tmp_path / "OldPlugin.vst3"
    (bundle / "Contents").mkdir(parents=True)
    plist = {
        "CFBundleIdentifier": "com.someVendor.OldPlugin",
        "CFBundleShortVersionString": "0.9.1",
    }
    with (bundle / "Contents" / "Info.plist").open("wb") as fh:
        plistlib.dump(plist, fh)
    plugin = _identify_vst3(bundle)
    assert plugin is not None
    assert plugin.vendor == "Somevendor"  # title-case from "somevendor"
    assert plugin.version == "0.9.1"


# ─── AU detector ─────────────────────────────────────────────────────────────


def test_au_vendor_from_audiocomponents_name(tmp_path):
    """AudioComponents[0].name has 'Vendor: Plugin' format — split it."""
    bundle = tmp_path / "Massive.component"
    (bundle / "Contents").mkdir(parents=True)
    plist = {
        "CFBundleIdentifier": "com.native-instruments.Massive",
        "CFBundleShortVersionString": "1.5.7",
        "AudioComponents": [{
            "name": "Native Instruments: Massive",
            "manufacturer": 1313812816,  # 4-char code
            "subtype": 1297301571,
            "type": 1635085685,
            "description": "Massive",
        }],
    }
    with (bundle / "Contents" / "Info.plist").open("wb") as fh:
        plistlib.dump(plist, fh)
    plugin = _identify_au(bundle)
    assert plugin is not None
    assert plugin.format == "AU"
    assert plugin.vendor == "Native Instruments"
    assert plugin.name == "Massive"
    assert plugin.version == "1.5.7"


def test_au_vendor_falls_back_to_bundle_id(tmp_path):
    """When AudioComponents.name has no colon, use CFBundleIdentifier."""
    bundle = tmp_path / "Some.component"
    (bundle / "Contents").mkdir(parents=True)
    plist = {
        "CFBundleIdentifier": "com.fabfilter.proq3",
        "CFBundleShortVersionString": "3.20",
        "AudioComponents": [{
            "name": "ProQ3",
            "manufacturer": 1179726626,
            "subtype": 1380078899,
            "type": 1635085685,
        }],
    }
    with (bundle / "Contents" / "Info.plist").open("wb") as fh:
        plistlib.dump(plist, fh)
    plugin = _identify_au(bundle)
    assert plugin is not None
    assert plugin.vendor == "Fabfilter"  # title-case from bundle id "fabfilter"


def test_au_vendor_falls_back_to_copyright(tmp_path):
    """When neither name-split nor bundle-id work, parse the copyright string."""
    bundle = tmp_path / "ValhallaFreqEcho.component"
    (bundle / "Contents").mkdir(parents=True)
    plist = {
        "NSHumanReadableCopyright": "Copyright © 2024 Valhalla DSP, LLC. All rights reserved.",
        "CFBundleShortVersionString": "1.2.8",
        "AudioComponents": [{
            "name": "ValhallaFreqEcho",
            "manufacturer": 1182427504,
        }],
    }
    with (bundle / "Contents" / "Info.plist").open("wb") as fh:
        plistlib.dump(plist, fh)
    plugin = _identify_au(bundle)
    assert plugin is not None
    assert plugin.vendor and "Valhalla" in plugin.vendor


def test_au_4char_code_only_fallback(tmp_path):
    """Last resort — return the 4-char manufacturer code when nothing else works."""
    bundle = tmp_path / "Mystery.component"
    (bundle / "Contents").mkdir(parents=True)
    plist = {
        "AudioComponents": [{"name": "Mystery", "manufacturer": 1397772120}],
    }
    with (bundle / "Contents" / "Info.plist").open("wb") as fh:
        plistlib.dump(plist, fh)
    plugin = _identify_au(bundle)
    assert plugin is not None
    # 1397772120 → "TDM!" via big-endian decode
    assert plugin.vendor and len(plugin.vendor) == 4


# ─── VST2 detector ───────────────────────────────────────────────────────────


def test_vst2_ccnk_header(tmp_path):
    """VST2 reads the 'CcnK' chunk for plugin code + program name."""
    plugin_path = tmp_path / "MyVST.vst"
    plugin_path.parent.mkdir(parents=True, exist_ok=True)
    # Build a minimal CcnK header: magic + 12 bytes + plugin_code + 8 bytes + name
    head = b"CcnK"
    head += b"\x00" * 12
    head += b"SRMA"  # plugin code
    head += b"\x00" * 8
    name_bytes = b"My Patch Name" + b"\x00" * (32 - 13)
    head += name_bytes
    plugin_path.write_bytes(head)
    plugin = _identify_vst2(plugin_path)
    assert plugin is not None
    assert plugin.format == "VST2"
    assert plugin.unique_id == "SRMA"


# ─── Manual scoring ──────────────────────────────────────────────────────────


def test_scoring_rejects_log_files(tmp_path):
    """log.txt should never count as a manual."""
    p = tmp_path / "log.txt"
    p.write_text("a" * 30000)  # 30KB
    assert _score_candidate(p, location_score=2) is None


def test_scoring_rejects_cache_files(tmp_path):
    p = tmp_path / "cache.txt"
    p.write_text("x" * 30000)
    assert _score_candidate(p, location_score=2) is None


def test_scoring_rejects_files_in_logs_dir(tmp_path):
    """Even an innocent-looking .pdf in logs/ should be rejected."""
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    p = logs_dir / "innocent.pdf"
    p.write_text("x" * 30000)
    assert _score_candidate(p, location_score=2) is None


def test_scoring_accepts_pdf_with_manual_in_name(tmp_path):
    p = tmp_path / "Diva-User-Manual.pdf"
    p.write_bytes(b"x" * 50000)
    cand = _score_candidate(p, location_score=4)
    assert cand is not None
    assert cand.name_score >= 2.0


def test_scoring_rejects_unhinted_txt_at_low_location_score(tmp_path):
    """A plain .txt with no hint at low-priority location → rejected."""
    p = tmp_path / "notes.txt"
    p.write_text("x" * 5000)
    assert _score_candidate(p, location_score=2) is None


def test_scoring_accepts_pdf_in_bundle_resources(tmp_path):
    """A .pdf inside the bundle (location_score=5) is accepted even without name hint."""
    p = tmp_path / "doc.pdf"
    p.write_bytes(b"x" * 20000)
    cand = _score_candidate(p, location_score=5)
    assert cand is not None


# ─── Section detection ──────────────────────────────────────────────────────


def test_section_detection_finds_known_keywords():
    text = """
INTRODUCTION

Welcome to the plugin.

PARAMETERS

The Cutoff dial sets...

MODULATION

Three LFOs are provided.

EFFECTS

Built-in chorus, delay, and reverb.
"""
    sections = _detect_sections(text)
    titles = [s["title"] for s in sections]
    assert any("PARAMETERS" in t for t in titles)
    assert any("MODULATION" in t for t in titles)


def test_section_detection_handles_markdown_headings():
    text = "# Overview\n\nText.\n\n## Parameters\n\nDial details.\n\n## Modulation\n\n..."
    sections = _detect_sections(text)
    # markdown variants captured
    assert len(sections) >= 2


# ─── Phase 3 + 4 packet builders ─────────────────────────────────────────────


def test_research_targets_minimum_shape(tmp_path):
    p = DetectedPlugin(
        plugin_id="vendor-plugin", name="Plugin", vendor="Vendor",
        format="VST3", version="1.0", bundle_path="/tmp/Plugin.vst3",
        unique_id=None,
    )
    targets = build_research_targets(p)
    assert targets["plugin_id"] == "vendor-plugin"
    assert "research_targets" in targets
    assert len(targets["research_targets"]) >= 3
    types = {t["type"] for t in targets["research_targets"]}
    assert "manual_alt" in types
    assert "technique_corpus" in types
    assert "comparison" in types
    assert targets["local_manual_present"] is False
    assert targets["next_step_tool"] == "corpus_emit_synthesis_briefs"


def test_research_targets_with_local_manual():
    from mcp_server.user_corpus.plugin_engine.manual import ManualExtraction
    p = DetectedPlugin(
        plugin_id="x-y", name="Y", vendor="X", format="VST3",
        version="1.0", bundle_path="/tmp/Y.vst3", unique_id=None,
    )
    extr = ManualExtraction(
        plugin_id="x-y", source_path="/tmp/manual.pdf",
        source_kind="pdf", text="The plugin sounds like ...",
        char_count=24,
    )
    targets = build_research_targets(p, extr)
    assert targets["local_manual_present"] is True
    # Even with a local manual, manual_alt query is still emitted (for verification)
    types = [t["type"] for t in targets["research_targets"]]
    assert "manual_alt" in types
    # fetch_top_n is reduced when local manual already present
    manual_alt = next(t for t in targets["research_targets"] if t["type"] == "manual_alt")
    assert manual_alt["fetch_top_n"] == 1


def test_synthesis_brief_shape():
    p = DetectedPlugin(
        plugin_id="vendor-plugin", name="Plugin", vendor="Vendor",
        format="VST3", version="1.0", bundle_path="/tmp/Plugin.vst3",
        unique_id=None,
    )
    brief = build_synthesis_brief(p)
    assert brief["plugin_id"] == "vendor-plugin"
    assert "synthesis_inputs" in brief
    assert "synthesis_schema" in brief
    # All expected schema fields present
    schema = brief["synthesis_schema"]
    for field in ("sonic_fingerprint", "reach_for", "avoid",
                  "key_techniques", "parameter_glossary",
                  "comparable_plugins", "genre_affinity",
                  "producer_anchors"):
        assert field in schema, f"Schema missing field: {field}"
    assert brief["output_path"].endswith("identity.yaml")


# ─── End-to-end against synthetic plugin folder ─────────────────────────────


def test_detect_installed_plugins_against_fake_folder(tmp_path):
    """Build a fake plugin folder + verify the detector walks + identifies.

    Pass use_auval=False so the test doesn't pull the system's actual AU
    inventory — keeps the test hermetic and machine-independent.
    """
    vst3_dir = tmp_path / "VST3"
    vst3_dir.mkdir()
    (vst3_dir / "Demo.vst3" / "Contents" / "Resources").mkdir(parents=True)
    (vst3_dir / "Demo.vst3" / "Contents" / "Resources" / "moduleinfo.json").write_text(
        json.dumps({"Name": "Demo", "Vendor": "TestVendor", "Version": "1.0"})
    )

    paths = [(vst3_dir, "VST3")]
    detected = detect_installed_plugins(paths=paths, use_auval=False)
    assert len(detected) == 1
    assert detected[0].name == "Demo"
    assert detected[0].vendor == "TestVendor"
    assert detected[0].format == "VST3"


def test_discover_manuals_finds_pdf_in_bundle(tmp_path):
    """A manual.pdf inside the bundle's Resources should be the top candidate."""
    bundle = tmp_path / "Plugin.vst3"
    res = bundle / "Contents" / "Resources"
    res.mkdir(parents=True)
    manual = res / "User-Manual.pdf"
    manual.write_bytes(b"x" * 100000)  # 100KB

    plugin = DetectedPlugin(
        plugin_id="x-plugin", name="Plugin", vendor="X",
        format="VST3", version="1.0", bundle_path=str(bundle),
        unique_id=None,
    )
    cands = discover_manuals_for_plugin(plugin)
    assert len(cands) >= 1
    top = cands[0]
    assert top.path == str(manual)
    assert top.location_score == 5  # inside bundle is highest
