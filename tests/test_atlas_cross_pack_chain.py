"""Tests for Pack-Atlas Phase F — atlas_cross_pack_chain.

All tests run without Live — they exercise the YAML loader, signal_flow parser,
and dry-run execution logic.
"""

from __future__ import annotations

import pytest
import sys
import os
from pathlib import Path

# Ensure mcp_server is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp_server.atlas.cross_pack_chain import (
    _load_workflow,
    _parse_signal_flow,
    _apply_aesthetic_overrides,
    _execute_or_dry_run,
    _KNOWN_DEVICE_FRAGMENTS,
    cross_pack_chain,
)

_CROSS_WORKFLOWS_DIR = (
    Path.home()
    / ".livepilot"
    / "atlas-overlays"
    / "packs"
    / "cross_workflows"
)


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _get_first_available_workflow_id() -> str | None:
    """Find the first actually-available workflow entity_id."""
    if not _CROSS_WORKFLOWS_DIR.exists():
        return None
    try:
        import yaml
    except ImportError:
        return None
    for f in sorted(_CROSS_WORKFLOWS_DIR.glob("*.yaml")):
        try:
            wf = yaml.safe_load(f.read_text())
            if wf and wf.get("entity_id") and wf.get("signal_flow"):
                return str(wf["entity_id"])
        except Exception:
            continue
    return None


# ─── Workflow loader ──────────────────────────────────────────────────────────


def test_load_workflow_dub_techno():
    """dub_techno_spectral_drone_bed loads correctly (both underscore and hyphen forms)."""
    wf = _load_workflow("dub_techno_spectral_drone_bed")
    if wf is None:
        pytest.skip("dub-techno workflow not available in this environment")
    assert wf.get("entity_id") == "dub_techno_spectral_drone_bed"
    assert "signal_flow" in wf
    assert len(wf["packs_used"]) >= 2


def test_load_workflow_hyphen_form():
    """Loading with hyphenated entity_id also works."""
    wf = _load_workflow("dub-techno-spectral-drone-bed")
    if wf is None:
        pytest.skip("dub-techno workflow not available")
    assert wf.get("entity_id") == "dub_techno_spectral_drone_bed"


def test_load_workflow_missing_returns_none():
    """Loading a non-existent workflow returns None."""
    wf = _load_workflow("nonexistent_workflow_xyzzy_12345")
    assert wf is None


# ─── Signal flow parser ───────────────────────────────────────────────────────


def test_parse_signal_flow_basic():
    """Basic numbered-step signal_flow parses correctly."""
    text = """1. Load Harmonic Drone Generator from Drone Lab
2. → Insert PitchLoop89 device
3. → Set Pitch A to +0.05
4. → Add Convolution Reverb"""

    steps = _parse_signal_flow(text)
    assert len(steps) == 4
    actions = [s["action"] for s in steps]
    assert "load_browser_item" in actions or "insert_device" in actions or "manual_step" in actions


def test_parse_signal_flow_list_of_strings():
    """List-of-strings format parses correctly."""
    lines = [
        "Load the Tree Tone preset",
        "Insert Bad Speaker rack",
        "Set Drive to 0.35",
    ]
    steps = _parse_signal_flow(lines)
    assert len(steps) == 3
    assert steps[0]["action"] in ("load_browser_item", "manual_step")
    assert steps[2]["action"] in ("set_device_parameter", "manual_step")


def test_parse_signal_flow_empty():
    """Empty signal_flow returns empty list."""
    assert _parse_signal_flow("") == []
    assert _parse_signal_flow(None) == []
    assert _parse_signal_flow([]) == []


def test_parse_signal_flow_dub_techno_fixture():
    """The actual dub-techno signal_flow contains >=3 parseable steps."""
    wf = _load_workflow("dub_techno_spectral_drone_bed")
    if wf is None:
        pytest.skip("dub-techno workflow not available")
    steps = _parse_signal_flow(wf["signal_flow"])
    assert len(steps) >= 3, f"Expected >=3 steps, got {len(steps)}: {steps}"

    # Must have at least one load_browser_item action
    actions = [s["action"] for s in steps]
    assert any(a == "load_browser_item" for a in actions), (
        f"Expected load_browser_item step, got actions: {actions}"
    )


def test_parse_signal_flow_verb_detection():
    """Verb detection maps correctly for known verbs."""
    cases = [
        ("Load Drone Lab preset `Earth`", "load_browser_item"),
        ("Insert PitchLoop89 effect", "insert_device"),
        ("Set Feedback A to 0.85", "set_device_parameter"),
        ("Fire `My Clip` clip", "fire_clip"),
        ("Route via send A", "set_track_send"),
    ]
    for text, expected_action in cases:
        steps = _parse_signal_flow(text)
        assert len(steps) == 1
        assert steps[0]["action"] == expected_action, (
            f"Text: {text!r} -> expected {expected_action}, got {steps[0]['action']}"
        )


# ─── Aesthetic overrides ──────────────────────────────────────────────────────


def test_aesthetic_override_target_scale():
    """target_scale inserts set_song_scale at top of steps."""
    base_steps = [
        {"step": 1, "action": "load_browser_item", "raw_text": "Load preset", "result": "dry-run"},
    ]
    overridden = _apply_aesthetic_overrides(base_steps, {"target_scale": "Fmin"})

    # Should have more steps than original
    assert len(overridden) > len(base_steps)

    # First step should be the scale override
    scale_steps = [s for s in overridden if s.get("action") == "set_song_scale"]
    assert len(scale_steps) == 1
    assert scale_steps[0]["scale"] == "Fmin"


def test_aesthetic_override_target_bpm():
    """target_bpm inserts set_tempo step."""
    base_steps = [
        {"step": 1, "action": "insert_device", "raw_text": "Add reverb", "result": "dry-run"},
    ]
    overridden = _apply_aesthetic_overrides(base_steps, {"target_bpm": 125.0})
    tempo_steps = [s for s in overridden if s.get("action") == "set_tempo"]
    assert len(tempo_steps) == 1
    assert tempo_steps[0]["value"] == 125.0


def test_aesthetic_override_none_is_passthrough():
    """None customize_aesthetic passes steps through unchanged."""
    base_steps = [
        {"step": 1, "action": "load_browser_item", "raw_text": "Load X", "result": "dry-run"},
    ]
    result = _apply_aesthetic_overrides(base_steps, None)
    assert result == base_steps


# ─── Dry-run execution ────────────────────────────────────────────────────────


def test_execute_dry_run_marks_all_steps():
    """All steps get result: 'dry-run'."""
    steps = [
        {"step": 1, "action": "load_browser_item", "raw_text": "Load X"},
        {"step": 2, "action": "insert_device", "raw_text": "Insert Y"},
    ]
    executed = _execute_or_dry_run(steps, target_track_index=-1)
    assert all(s.get("result") == "dry-run" for s in executed)


def test_execute_dry_run_annotates_track_index():
    """When target_track_index >= 0, load steps get target_track_index annotation."""
    steps = [
        {"step": 1, "action": "load_browser_item", "raw_text": "Load X"},
        {"step": 2, "action": "set_device_parameter", "raw_text": "Set Y", "value": 1.0},
    ]
    executed = _execute_or_dry_run(steps, target_track_index=2)
    load_steps = [s for s in executed if s.get("action") == "load_browser_item"]
    assert all(s.get("target_track_index") == 2 for s in load_steps)


# ─── Main cross_pack_chain function ──────────────────────────────────────────


def test_cross_pack_chain_dry_run():
    """Dry-run on ANY existing workflow produces >=3 executed steps with a load_browser_item.

    Adapts dynamically to find the first available workflow rather than hardcoding
    a specific ID.
    """
    # Try the spec's canonical workflow first
    workflow_id = "dub_techno_spectral_drone_bed"
    result = cross_pack_chain(workflow_entity_id=workflow_id, target_track_index=-1)

    if "error" in result and "not found" in result.get("error", ""):
        # Try to find any available workflow
        workflow_id = _get_first_available_workflow_id()
        if workflow_id is None:
            pytest.skip("No cross-workflow YAMLs available in this environment")
        result = cross_pack_chain(workflow_entity_id=workflow_id, target_track_index=-1)

    assert "workflow" in result, f"Missing 'workflow' key: {result}"
    assert "executed_steps" in result, f"Missing 'executed_steps' key: {result}"

    # Workflow metadata must be present
    wf = result["workflow"]
    assert wf.get("entity_id"), "workflow.entity_id should not be empty"
    assert isinstance(wf.get("packs_used", []), list)

    # Steps count
    steps = result["executed_steps"]
    assert len(steps) >= 3, (
        f"Expected >=3 executed_steps for '{workflow_id}', got {len(steps)}: {steps}"
    )

    # All steps must be dry-run
    assert all(s.get("result") == "dry-run" for s in steps), (
        "All steps should have result='dry-run'"
    )

    # At least one load_browser_item action
    actions = [s["action"] for s in steps]
    assert any(a == "load_browser_item" for a in actions), (
        f"Expected >=1 load_browser_item step, got actions: {actions}"
    )

    # Sources must have citation tag
    sources_text = " ".join(result["sources"])
    assert "[SOURCE:" in sources_text


def test_cross_pack_chain_handles_unknown_workflow():
    """Bogus workflow entity_id returns structured error with available_workflows."""
    result = cross_pack_chain(
        workflow_entity_id="xyzzy_nonexistent_workflow_abc123",
        target_track_index=-1,
    )
    assert "error" in result, "Expected error for unknown workflow"
    assert isinstance(result["error"], str)
    # Should include list of available workflows
    assert "available_workflows" in result
    assert isinstance(result["available_workflows"], list)


def test_cross_pack_chain_aesthetic_override_scale():
    """Aesthetic override with target_scale reflects Fmin in the steps."""
    result = cross_pack_chain(
        workflow_entity_id="dub_techno_spectral_drone_bed",
        target_track_index=-1,
        customize_aesthetic={"target_scale": "Fmin"},
    )

    if "error" in result and "not found" in result.get("error", ""):
        wid = _get_first_available_workflow_id()
        if wid is None:
            pytest.skip("No workflows available")
        result = cross_pack_chain(
            workflow_entity_id=wid,
            target_track_index=-1,
            customize_aesthetic={"target_scale": "Fmin"},
        )

    assert "executed_steps" in result

    # There should be a set_song_scale step with "Fmin"
    steps = result["executed_steps"]
    scale_steps = [s for s in steps if s.get("action") == "set_song_scale"]
    assert len(scale_steps) == 1, (
        f"Expected 1 set_song_scale step, got {len(scale_steps)}. "
        f"All actions: {[s.get('action') for s in steps]}"
    )
    assert scale_steps[0].get("scale") == "Fmin"


def test_cross_pack_chain_all_15_workflows_parse():
    """All 15 cross-workflow YAMLs can be loaded and parsed without errors."""
    if not _CROSS_WORKFLOWS_DIR.exists():
        pytest.skip("cross_workflows directory not available")

    try:
        import yaml
    except ImportError:
        pytest.skip("PyYAML not available")

    failed: list[str] = []
    for wf_file in sorted(_CROSS_WORKFLOWS_DIR.glob("*.yaml")):
        try:
            wf = yaml.safe_load(wf_file.read_text())
            if not wf:
                continue
            eid = str(wf.get("entity_id", wf_file.stem.replace("-", "_")))
            result = cross_pack_chain(workflow_entity_id=eid, target_track_index=-1)
            if "error" in result:
                failed.append(f"{eid}: {result['error']}")
        except Exception as exc:
            failed.append(f"{wf_file.stem}: {exc}")

    assert not failed, (
        f"The following workflows failed to parse:\n" + "\n".join(failed)
    )


def test_cross_pack_chain_boc_decayed_pad():
    """BoC decayed pad workflow loads correctly."""
    result = cross_pack_chain(
        workflow_entity_id="boc_decayed_pad",
        target_track_index=-1,
    )

    if "error" in result and "not found" in result.get("error", ""):
        pytest.skip("boc_decayed_pad workflow not available")

    assert "workflow" in result
    assert result["workflow"]["entity_id"] == "boc_decayed_pad"
    assert len(result["executed_steps"]) >= 3


# ─── BUG-INT#1 / BUG-NEW#3 regression: hint fallback ─────────────────────────


def test_hint_fallback_when_device_name_regex_fails():
    """BUG-INT#1 / BUG-NEW#3: load_browser_item steps get browser_search_hint even
    when _extract_device_name() returns None (e.g. leading-noun lines like
    'Echo with subtle wow/flutter' or 'Reverb with cathedral IR')."""
    # Construct signal_flow text that hits the fallback path:
    # no backtick/quote/TitleCase device name — just a leading known fragment.
    text = (
        "1. Echo with subtle wow/flutter\n"
        "2. Reverb with cathedral impulse response\n"
        "3. Load `GranulatorII` preset"
    )
    steps = _parse_signal_flow(text)

    # First two steps must be classified as load_browser_item (fragment in head)
    assert steps[0]["action"] == "load_browser_item", (
        f"Step 1 should be load_browser_item, got {steps[0]['action']}"
    )
    assert steps[1]["action"] == "load_browser_item", (
        f"Step 2 should be load_browser_item, got {steps[1]['action']}"
    )

    # Both must have a non-empty browser_search_hint.name_filter
    for i, step in enumerate(steps[:2]):
        hint = step.get("browser_search_hint")
        assert hint is not None, f"Step {i+1} missing browser_search_hint"
        assert hint.get("name_filter"), (
            f"Step {i+1} browser_search_hint.name_filter is empty: {hint}"
        )

    # Echo fragment maps to audio_effects
    echo_hint = steps[0].get("browser_search_hint", {})
    assert echo_hint.get("suggested_path") == "audio_effects", (
        f"Echo should map to audio_effects, got {echo_hint.get('suggested_path')}"
    )

    # Reverb fragment maps to audio_effects
    reverb_hint = steps[1].get("browser_search_hint", {})
    assert reverb_hint.get("suggested_path") == "audio_effects", (
        f"Reverb should map to audio_effects, got {reverb_hint.get('suggested_path')}"
    )


def test_hint_present_on_all_load_browser_item_steps_for_known_workflows():
    """BUG-INT#1 / BUG-NEW#3: every load_browser_item step in any loaded workflow
    should have a non-empty browser_search_hint.name_filter after the fix."""
    if not _CROSS_WORKFLOWS_DIR.exists():
        pytest.skip("cross_workflows directory not available")
    try:
        import yaml
    except ImportError:
        pytest.skip("PyYAML not available")

    missing_hint: list[str] = []
    for wf_file in sorted(_CROSS_WORKFLOWS_DIR.glob("*.yaml")):
        try:
            wf = yaml.safe_load(wf_file.read_text())
            if not wf or not wf.get("signal_flow"):
                continue
            steps = _parse_signal_flow(wf["signal_flow"])
            for step in steps:
                if step.get("action") == "load_browser_item":
                    hint = step.get("browser_search_hint", {})
                    if not hint.get("name_filter"):
                        missing_hint.append(
                            f"{wf_file.stem} step {step['step']}: {step['raw_text']!r}"
                        )
        except Exception as exc:
            missing_hint.append(f"{wf_file.stem}: {exc}")

    assert not missing_hint, (
        "The following load_browser_item steps are missing browser_search_hint.name_filter:\n"
        + "\n".join(missing_hint)
    )


# ─── BUG-NEW#2 regression: transpose no-op ────────────────────────────────────


def test_transpose_no_op_emits_manual_step():
    """BUG-NEW#2: when transpose_semitones is non-zero but no parseable pitch
    parameters exist, a manual_step override is appended."""
    # A workflow with no set_device_parameter steps (all load/manual)
    base_steps = [
        {"step": 1, "action": "load_browser_item", "raw_text": "Load Echo", "result": "dry-run"},
        {"step": 2, "action": "load_browser_item", "raw_text": "Load Reverb", "result": "dry-run"},
    ]
    result = _apply_aesthetic_overrides(base_steps, {"transpose_semitones": -3.0})

    # Should have an extra manual_step signaling the transpose
    manual_overrides = [s for s in result if s.get("action") == "manual_step"]
    assert len(manual_overrides) >= 1, (
        f"Expected >=1 manual_step, got none. Steps: {result}"
    )
    override_text = manual_overrides[-1].get("raw_text", "")
    assert "-3" in override_text or "3.0" in override_text, (
        f"Expected semitone value in raw_text, got: {override_text!r}"
    )


def test_transpose_mutates_pitch_steps_without_double_emit():
    """BUG-NEW#2: when parseable pitch params DO exist, values mutate and no
    fallback manual_step is added."""
    base_steps = [
        {
            "step": 1,
            "action": "set_device_parameter",
            "parameter_name": "Pitch A",
            "value": 0.05,
            "raw_text": "Set Pitch A to 0.05",
            "result": "dry-run",
        },
    ]
    result = _apply_aesthetic_overrides(base_steps, {"transpose_semitones": -3.0})

    # The pitch step value should be shifted
    pitch_steps = [s for s in result if s.get("action") == "set_device_parameter"]
    assert len(pitch_steps) == 1
    assert pitch_steps[0]["value"] == pytest.approx(0.05 - 3.0, abs=1e-3)

    # No fallback manual_step should have been added
    manual_overrides = [
        s for s in result
        if s.get("action") == "manual_step" and "[OVERRIDE] Transpose" in s.get("raw_text", "")
    ]
    assert len(manual_overrides) == 0, (
        f"Should not emit manual_step when pitch params were mutated: {manual_overrides}"
    )


# ─── BUG-EDGE#5 regression: non-numeric target_bpm ───────────────────────────


def test_non_numeric_target_bpm_does_not_crash():
    """BUG-EDGE#5: non-numeric target_bpm must not raise ValueError."""
    base_steps = [
        {"step": 1, "action": "load_browser_item", "raw_text": "Load Echo", "result": "dry-run"},
    ]
    # Should not raise
    result = _apply_aesthetic_overrides(base_steps, {"target_bpm": "not-a-number"})
    # No set_tempo step should be present
    tempo_steps = [s for s in result if s.get("action") == "set_tempo"]
    assert len(tempo_steps) == 0, f"Expected no set_tempo step, got: {tempo_steps}"


def test_non_numeric_target_bpm_via_cross_pack_chain():
    """BUG-EDGE#5: malformed target_bpm in cross_pack_chain does not crash."""
    result = cross_pack_chain(
        workflow_entity_id="dub_techno_spectral_drone_bed",
        target_track_index=-1,
        customize_aesthetic={"target_bpm": "not-a-number"},
    )
    # May return error for missing workflow, but must NOT be a ValueError/exception
    assert "error" in result or "executed_steps" in result, (
        f"Expected either error or executed_steps key: {result}"
    )
    # If we got steps, there must be no set_tempo step from the bogus override
    if "executed_steps" in result:
        tempo_steps = [s for s in result["executed_steps"] if s.get("action") == "set_tempo"]
        assert len(tempo_steps) == 0, (
            f"Should not have set_tempo from non-numeric BPM: {tempo_steps}"
        )
