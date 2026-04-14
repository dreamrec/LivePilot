"""Contract tests for the rewritten composer engine.

The composer used to emit:
  - pseudo-tools like _agent_pick_best_sample and _apply_technique
  - placeholder strings like "{downloaded_path}" in params
  - invalid device_index: -1 and track_index: -1 sentinels
  - hardcoded clip_slot_index: 0 for newly created tracks

Now it must emit only real tool calls with concrete params, or drop the
layer from the plan and surface a warning.
"""

import pytest

from mcp_server.composer.engine import ComposerEngine
from mcp_server.composer.prompt_parser import parse_prompt


def _steps(result):
    """Convenience accessor for the plan's steps."""
    return result.plan


def _tool_names(result):
    return [s.get("tool", "") for s in _steps(result)]


# ── Pseudo-tool elimination ─────────────────────────────────────────────

def test_compose_plan_contains_no_pseudo_tools(tmp_path):
    """No tool name may start with an underscore — those are agent pseudo-calls."""
    # File names must match layer-planner role names (drums/bass/etc.)
    (tmp_path / "drums_tech.wav").write_bytes(b"RIFF")
    (tmp_path / "bass_sub.wav").write_bytes(b"RIFF")
    (tmp_path / "texture_air.wav").write_bytes(b"RIFF")

    engine = ComposerEngine()
    intent = parse_prompt("dark minimal techno 128bpm with organic textures")
    result = engine.compose(intent, search_roots=[tmp_path])

    for step in _steps(result):
        tool = step.get("tool", "")
        assert tool and not tool.startswith("_"), f"Pseudo-tool leaked: {tool!r}"


def test_augment_plan_contains_no_pseudo_tools(tmp_path):
    (tmp_path / "vocal.wav").write_bytes(b"RIFF")
    engine = ComposerEngine()
    result = engine.augment("add a vocal layer", search_roots=[tmp_path])

    for step in _steps(result):
        tool = step.get("tool", "")
        assert tool and not tool.startswith("_"), f"Pseudo-tool leaked: {tool!r}"


# ── Placeholder elimination ────────────────────────────────────────────

def test_compose_plan_has_no_placeholder_strings(tmp_path):
    """No param value may be a literal {placeholder} template."""
    (tmp_path / "drums_techno.wav").write_bytes(b"RIFF")
    engine = ComposerEngine()
    result = engine.compose(parse_prompt("techno 128bpm"), search_roots=[tmp_path])

    for step in _steps(result):
        for key, val in step.get("params", {}).items():
            if isinstance(val, str):
                assert "{" not in val, f"Placeholder leaked in {step.get('tool')}.{key}: {val!r}"


# ── device_index binding (no -1 sentinels) ─────────────────────────────

def test_set_device_parameter_binds_device_index_via_from_step(tmp_path):
    """set_device_parameter.device_index must be a $from_step binding, never -1."""
    (tmp_path / "drums_techno.wav").write_bytes(b"RIFF")
    engine = ComposerEngine()
    result = engine.compose(parse_prompt("techno 128bpm"), search_roots=[tmp_path])

    found_binding = False
    for step in _steps(result):
        if step.get("tool") == "set_device_parameter":
            di = step["params"].get("device_index")
            if isinstance(di, dict) and "$from_step" in di:
                found_binding = True
                assert "path" in di, f"Binding missing path: {di}"
            else:
                assert di != -1, f"set_device_parameter used -1 sentinel: {step}"

    has_processing = any(s.get("tool") == "set_device_parameter" for s in _steps(result))
    if has_processing:
        assert found_binding, "At least one processing step should bind device_index via $from_step"


def test_insert_device_emits_step_id_when_params_follow(tmp_path):
    """insert_device must carry a step_id so set_device_parameter can bind to it."""
    (tmp_path / "drums_techno.wav").write_bytes(b"RIFF")
    engine = ComposerEngine()
    result = engine.compose(parse_prompt("techno 128bpm"), search_roots=[tmp_path])

    for i, step in enumerate(_steps(result)):
        if step.get("tool") == "insert_device":
            # Is the next step a set_device_parameter on the same track?
            if i + 1 < len(_steps(result)):
                nxt = _steps(result)[i + 1]
                if nxt.get("tool") == "set_device_parameter":
                    assert "step_id" in step, \
                        f"insert_device followed by set_device_parameter needs step_id: {step}"


# ── Unresolved layers dropped + warned ─────────────────────────────────

def test_compose_drops_unresolved_layers_and_warns():
    """With no search_roots, everything is unresolved — plan must not emit
    load_sample_to_simpler steps with placeholder paths."""
    engine = ComposerEngine()
    result = engine.compose(parse_prompt("techno 128bpm"), search_roots=[])

    # Any load_sample_to_simpler must have a real path (none emitted here)
    for step in _steps(result):
        if step.get("tool") == "load_sample_to_simpler":
            fp = step["params"].get("file_path", "")
            assert fp and "{" not in fp and isinstance(fp, str), \
                f"Unresolved layer emitted with bad path: {step}"

    # Warnings must name unresolved layers
    warnings_text = " ".join(result.warnings).lower()
    assert "unresolved" in warnings_text or "no sample" in warnings_text, \
        f"Expected unresolved-layer warning; got {result.warnings}"

    # Descriptive layers are still present
    assert len(result.layers) > 0


def test_compose_keeps_resolved_layers_in_plan(tmp_path):
    """Partial resolution — one layer resolves, others don't."""
    # File name must contain a layer-planner role (drums/bass/etc.) or a query token
    (tmp_path / "drums_techno.wav").write_bytes(b"RIFF")

    engine = ComposerEngine()
    result = engine.compose(parse_prompt("techno 128bpm"), search_roots=[tmp_path])

    load_steps = [s for s in _steps(result) if s.get("tool") == "load_sample_to_simpler"]
    # At least the drums layer should have produced a concrete load step
    assert len(load_steps) >= 1, f"Expected >=1 load step; got plan: {result.plan}"
    for step in load_steps:
        fp = step["params"]["file_path"]
        assert fp.endswith(".wav")
        assert "{" not in fp


# ── Real-tool-only check ───────────────────────────────────────────────

def test_every_plan_tool_name_is_non_empty(tmp_path):
    (tmp_path / "drums_techno.wav").write_bytes(b"RIFF")
    engine = ComposerEngine()
    result = engine.compose(parse_prompt("techno 128bpm"), search_roots=[tmp_path])
    for step in _steps(result):
        assert step.get("tool", "").strip(), f"Empty tool name: {step}"


# ── Dry-run path still works ───────────────────────────────────────────

def test_get_plan_dry_run_path():
    """get_plan is the explicit dry-run preview. Should return a dict with plan shape."""
    engine = ComposerEngine()
    plan = engine.get_plan(parse_prompt("techno 128bpm"))
    assert "plan" in plan
    assert "layers" in plan
    assert "warnings" in plan
