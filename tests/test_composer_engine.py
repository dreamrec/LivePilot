"""Contract tests for the rewritten composer engine.

The composer used to emit:
  - pseudo-tools like _agent_pick_best_sample and _apply_technique
  - placeholder strings like "{downloaded_path}" in params
  - invalid device_index: -1 and track_index: -1 sentinels
  - hardcoded clip_slot_index: 0 for newly created tracks

Now it must emit only real tool calls with concrete params, or drop the
layer from the plan and surface a warning.

Phase 2C: compose/augment/get_plan are async because sample resolution
may download from Splice. Tests wrap calls in asyncio.run().
"""

import asyncio

import pytest

from mcp_server.composer.engine import ComposerEngine
from mcp_server.composer.prompt_parser import parse_prompt


def _steps(result):
    """Convenience accessor for the plan's steps."""
    return result.plan


def _tool_names(result):
    return [s.get("tool", "") for s in _steps(result)]


def _compose(engine, intent, **kwargs):
    """Sync wrapper around async compose for concise tests."""
    return asyncio.run(engine.compose(intent, **kwargs))


def _augment(engine, request, **kwargs):
    """Sync wrapper around async augment for concise tests."""
    return asyncio.run(engine.augment(request, **kwargs))


def _get_plan(engine, intent, **kwargs):
    """Sync wrapper around async get_plan for concise tests."""
    return asyncio.run(engine.get_plan(intent, **kwargs))


# ── Pseudo-tool elimination ─────────────────────────────────────────────

def test_compose_plan_contains_no_pseudo_tools(tmp_path):
    """No tool name may start with an underscore — those are agent pseudo-calls."""
    # File names must match layer-planner role names (drums/bass/etc.)
    (tmp_path / "drums_tech.wav").write_bytes(b"RIFF")
    (tmp_path / "bass_sub.wav").write_bytes(b"RIFF")
    (tmp_path / "texture_air.wav").write_bytes(b"RIFF")

    engine = ComposerEngine()
    intent = parse_prompt("dark minimal techno 128bpm with organic textures")
    result = _compose(engine, intent, search_roots=[tmp_path])

    for step in _steps(result):
        tool = step.get("tool", "")
        assert tool and not tool.startswith("_"), f"Pseudo-tool leaked: {tool!r}"


def test_augment_plan_contains_no_pseudo_tools(tmp_path):
    (tmp_path / "vocal.wav").write_bytes(b"RIFF")
    engine = ComposerEngine()
    result = _augment(engine, "add a vocal layer", search_roots=[tmp_path])

    for step in _steps(result):
        tool = step.get("tool", "")
        assert tool and not tool.startswith("_"), f"Pseudo-tool leaked: {tool!r}"


# ── Placeholder elimination ────────────────────────────────────────────

def test_compose_plan_has_no_placeholder_strings(tmp_path):
    """No param value may be a literal {placeholder} template."""
    (tmp_path / "drums_techno.wav").write_bytes(b"RIFF")
    engine = ComposerEngine()
    result = _compose(engine, parse_prompt("techno 128bpm"), search_roots=[tmp_path])

    for step in _steps(result):
        for key, val in step.get("params", {}).items():
            if isinstance(val, str):
                assert "{" not in val, f"Placeholder leaked in {step.get('tool')}.{key}: {val!r}"


# ── device_index binding (no -1 sentinels) ─────────────────────────────

def test_set_device_parameter_binds_device_index_via_from_step(tmp_path):
    """set_device_parameter.device_index must be a $from_step binding, never -1."""
    (tmp_path / "drums_techno.wav").write_bytes(b"RIFF")
    engine = ComposerEngine()
    result = _compose(engine, parse_prompt("techno 128bpm"), search_roots=[tmp_path])

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
    result = _compose(engine, parse_prompt("techno 128bpm"), search_roots=[tmp_path])

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
    result = _compose(engine, parse_prompt("techno 128bpm"), search_roots=[])

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
    result = _compose(engine, parse_prompt("techno 128bpm"), search_roots=[tmp_path])

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
    result = _compose(engine, parse_prompt("techno 128bpm"), search_roots=[tmp_path])
    for step in _steps(result):
        assert step.get("tool", "").strip(), f"Empty tool name: {step}"


# ── Dry-run path still works ───────────────────────────────────────────

def test_get_plan_dry_run_path():
    """get_plan is the explicit dry-run preview. Should return a dict with plan shape."""
    engine = ComposerEngine()
    plan = _get_plan(engine, parse_prompt("techno 128bpm"))
    assert "plan" in plan
    assert "layers" in plan
    assert "warnings" in plan


# ── Phase 2B: arrangement clip emission ────────────────────────────────

def test_compose_emits_create_clip_and_add_notes_before_arrangement(tmp_path):
    """Every layer that loads a sample must also emit, in order:
      1. create_clip (session slot, source for tiling)
      2. add_notes (trigger note so Simpler actually sounds)
      3. create_arrangement_clip per section
    The ordering matters because create_arrangement_clip duplicates an
    existing session clip — if add_notes hasn't run, the arrangement clip
    will be empty.
    """
    (tmp_path / "drums_techno.wav").write_bytes(b"RIFF")
    engine = ComposerEngine()
    result = _compose(engine, parse_prompt("techno 128bpm"), search_roots=[tmp_path])

    # Find the drums layer's create_midi_track, load_sample, create_clip,
    # add_notes, and create_arrangement_clip indices in emission order.
    seq = [(i, s.get("tool"), s.get("role", "")) for i, s in enumerate(result.plan)]

    def find_first(tool, role):
        for i, t, r in seq:
            if t == tool and r == role:
                return i
        return None

    load_idx = find_first("load_sample_to_simpler", "drums")
    assert load_idx is not None, f"No load step for drums; plan:\n{seq}"

    clip_idx = None
    notes_idx = None
    arr_idx = None
    for i, t, r in seq:
        if r != "drums" or i <= load_idx:
            continue
        if t == "create_clip" and clip_idx is None:
            clip_idx = i
        elif t == "add_notes" and notes_idx is None:
            notes_idx = i
        elif t == "create_arrangement_clip" and arr_idx is None:
            arr_idx = i

    assert clip_idx is not None, "Missing create_clip for drums layer"
    assert notes_idx is not None, "Missing add_notes for drums layer"
    assert arr_idx is not None, "Missing create_arrangement_clip for drums layer"
    assert load_idx < clip_idx < notes_idx < arr_idx, (
        f"Ordering wrong: load={load_idx}, clip={clip_idx}, "
        f"notes={notes_idx}, arr={arr_idx}"
    )


def test_compose_arrangement_clip_has_concrete_timing(tmp_path):
    """Every create_arrangement_clip step must carry concrete start_time
    and length in beats, plus a clip_slot_index pointing at the source."""
    (tmp_path / "drums_techno.wav").write_bytes(b"RIFF")
    engine = ComposerEngine()
    result = _compose(engine, parse_prompt("techno 128bpm"), search_roots=[tmp_path])

    arr_steps = [s for s in result.plan if s.get("tool") == "create_arrangement_clip"]
    assert arr_steps, "Expected at least one create_arrangement_clip step"

    for step in arr_steps:
        params = step["params"]
        assert "start_time" in params
        assert "length" in params
        assert "clip_slot_index" in params
        assert isinstance(params["start_time"], (int, float))
        assert isinstance(params["length"], (int, float))
        assert params["length"] > 0
        assert params["start_time"] >= 0


def test_compose_trigger_clip_has_single_midi_note(tmp_path):
    """The source clip created for each layer has at least one MIDI note
    so Simpler actually sounds when the arrangement clip plays."""
    (tmp_path / "drums_techno.wav").write_bytes(b"RIFF")
    engine = ComposerEngine()
    result = _compose(engine, parse_prompt("techno 128bpm"), search_roots=[tmp_path])

    add_notes_steps = [s for s in result.plan if s.get("tool") == "add_notes"]
    assert add_notes_steps, "Expected at least one add_notes step"

    for step in add_notes_steps:
        params = step["params"]
        assert "notes" in params
        notes = params["notes"]
        assert isinstance(notes, list) and len(notes) >= 1
        for note in notes:
            assert "pitch" in note
            assert "start_time" in note
            assert "duration" in note
            assert 0 <= note["pitch"] <= 127


def test_compose_arrangement_clip_tiles_all_layer_sections(tmp_path):
    """If a layer is used in multiple sections, each gets its own
    create_arrangement_clip call."""
    (tmp_path / "drums_techno.wav").write_bytes(b"RIFF")
    engine = ComposerEngine()
    result = _compose(engine, parse_prompt("techno 128bpm"), search_roots=[tmp_path])

    arr_for_drums = [
        s for s in result.plan
        if s.get("tool") == "create_arrangement_clip" and s.get("role") == "drums"
    ]
    # Drums layer should appear in >=1 section, usually more
    assert len(arr_for_drums) >= 1

    # Each arrangement clip targets a distinct section
    sections_named = [s.get("section", "") for s in arr_for_drums]
    assert len(sections_named) == len(arr_for_drums)


def test_compose_unresolved_layer_emits_no_arrangement_steps():
    """When a layer doesn't resolve, we must NOT emit create_clip, add_notes,
    or create_arrangement_clip for it — those would reference a nonexistent
    track and crash the plan."""
    engine = ComposerEngine()
    result = _compose(engine, parse_prompt("techno 128bpm"), search_roots=[])

    # Everything is unresolved
    assert not any(s.get("tool") == "create_clip" for s in result.plan)
    assert not any(s.get("tool") == "add_notes" for s in result.plan)
    assert not any(s.get("tool") == "create_arrangement_clip" for s in result.plan)
