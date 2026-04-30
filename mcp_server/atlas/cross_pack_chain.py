"""Pack-Atlas Phase F — Cross-Pack Chain Executor.

Execute a cross_pack_workflow recipe step-by-step by parsing its signal_flow
field into structured executable actions.

Real YAML schema (discovered 2026-04-27):
  entity_id: dub_techno_spectral_drone_bed
  entity_type: cross_pack_workflow
  name: Dub Techno Spectral Drone Bed
  description: ...
  packs_used: [drone-lab, pitchloop89, convolution-reverb]
  devices_used: [harmonic_drone_generator, pitchloop89, convolution_reverb]
  signal_flow: |-
    1. <step text>
    2. → <step text>
    ...
  when_to_reach: ...
  gotcha: ...
  avoid: ...

signal_flow is a multi-line string with numbered steps. Steps beginning with
"→" are continuation steps (chained into the previous device).

All workflow execution in Phase F is DRY-RUN only. Live execution is gated
on an active Remote Script connection.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# ─── Paths ────────────────────────────────────────────────────────────────────

_CROSS_WORKFLOWS_DIR = (
    Path.home()
    / ".livepilot"
    / "atlas-overlays"
    / "packs"
    / "cross_workflows"
)

# ─── Slug normalization ───────────────────────────────────────────────────────


def _normalize_slug(workflow_entity_id: str) -> str:
    """Normalize entity_id: convert underscores to hyphens for filename lookup,
    or hyphens to underscores for entity_id matching.

    The YAML files use hyphens in filenames but entity_id fields use underscores.
    """
    return workflow_entity_id.replace("_", "-")


def _entity_id_to_filename(workflow_entity_id: str) -> str:
    """Convert entity_id (underscores) to filename (hyphens)."""
    return _normalize_slug(workflow_entity_id) + ".yaml"


# ─── Workflow loader ──────────────────────────────────────────────────────────


def _load_workflow(workflow_entity_id: str) -> dict | None:
    """Load a cross-pack workflow YAML.

    Handles normalization:
    - Try hyphenated filename: dub-techno-spectral-drone-bed.yaml
    - Try underscore filename: dub_techno_spectral_drone_bed.yaml
    - Try entity_id field match across all YAMLs

    Returns the parsed YAML dict, or None if not found.
    """
    if not _CROSS_WORKFLOWS_DIR.exists():
        return None

    try:
        import yaml
    except ImportError:
        return None

    # Try hyphenated filename first
    hyphen_name = _entity_id_to_filename(workflow_entity_id)
    hyphen_path = _CROSS_WORKFLOWS_DIR / hyphen_name
    if hyphen_path.exists():
        try:
            return yaml.safe_load(hyphen_path.read_text())
        except Exception:
            return None

    # Try underscore filename (some might be stored with underscores)
    under_name = workflow_entity_id.replace("-", "_") + ".yaml"
    under_path = _CROSS_WORKFLOWS_DIR / under_name
    if under_path.exists():
        try:
            return yaml.safe_load(under_path.read_text())
        except Exception:
            return None

    # Scan all YAMLs for matching entity_id field
    for wf_file in sorted(_CROSS_WORKFLOWS_DIR.glob("*.yaml")):
        try:
            wf = yaml.safe_load(wf_file.read_text())
            if wf and str(wf.get("entity_id", "")) == workflow_entity_id:
                return wf
            # Also check hyphen/underscore variants
            eid = str(wf.get("entity_id", ""))
            if eid.replace("_", "-") == workflow_entity_id.replace("_", "-"):
                return wf
        except Exception:
            continue

    return None


# ─── Signal flow parser ───────────────────────────────────────────────────────

# Verb → action mapping for signal_flow step parsing.
# Each entry is (list_of_verb_strings, action).
# Verb strings are matched with `in text_lower` — they MUST include a trailing
# space so that substring-of-word matches (e.g. "chain" inside "Sidechain") are
# avoided.  For the routing semantic, require "chain to " or "chain into " so
# that "Sidechain" and "master-bus chain" are not caught.
_VERB_TO_ACTION: list[tuple[list[str], str]] = [
    # Load / open / import
    (["load ", "open ", "import ", "place "], "load_browser_item"),
    # Insert / add
    (["insert ", "add ", "drop "], "insert_device"),
    # Set / tweak / configure / adjust
    (["set ", "tweak ", "configure ", "adjust ", "tune ", "dial ", "use "], "set_device_parameter"),
    # Automate
    (["automate ", "modulate ", "lfo "], "set_device_parameter"),
    # Fire / play / trigger / activate
    (["fire ", "play ", "trigger ", "activate ", "launch "], "fire_clip"),
    # Chain / route / send / feed — require "chain to"/"chain into" to avoid
    # matching "Sidechain" or "master-bus chain"
    (["chain to ", "chain into ", "route ", "feed ", "send to "], "set_track_send"),
    # Anything else
]

# Known device name fragments that indicate a "load" step even without a load verb.
# Used when a step begins with a noun (device name) rather than a verb.
_KNOWN_DEVICE_FRAGMENTS: list[str] = [
    "harmonic drone generator",
    "pitchloop89",
    "convolution reverb",
    "auto filter",
    "tree tone",
    "bad speaker",
    "reverb",
    "delay",
    "echo",
    "saturator",
    "granulator",
    "sampler",
    "simpler",
    "operator",
    "drift",
    "wavetable",
]

# BUG-INT#1 / BUG-NEW#3: Fragments that map to a more specific suggested_path
# rather than the broad "sounds" default.  If a fragment appears in this dict,
# its path is used instead.  Native Ableton audio-effect fragments use
# "audio_effects"; instrument/synth fragments use "instruments".
_FRAGMENT_TO_SUGGESTED_PATH: dict[str, str] = {
    "echo": "audio_effects",
    "reverb": "audio_effects",
    "convolution reverb": "audio_effects",
    "delay": "audio_effects",
    "auto filter": "audio_effects",
    "saturator": "audio_effects",
    "granulator": "instruments",
    "sampler": "instruments",
    "simpler": "instruments",
    "operator": "instruments",
    "drift": "instruments",
    "wavetable": "instruments",
    "harmonic drone generator": "instruments",
    "tree tone": "instruments",
}

# Patterns to extract device/clip names from step text
_DEVICE_EXTRACT_PATTERNS: list[re.Pattern] = [
    re.compile(r"`([^`]+)`"),                          # backtick-quoted names
    re.compile(r'"([^"]+)"'),                          # double-quoted names
    re.compile(r"'([^']+)'"),                          # single-quoted names
    re.compile(r"\b([A-Z][A-Za-z0-9\s\-]+(?:Reverb|Delay|Filter|Loop|Echo|Generator|Device|89))\b"),
]


def _classify_step_verb(text_lower: str) -> str:
    """Classify a signal_flow step text into an action type.

    Handles three patterns:
      - verb-first        ("Load HDG from...")
      - noun-first        ("Harmonic Drone Generator (Drone Lab) tuned to...")
      - pack-prefix-first ("Inspired by Nature `tree_tone` on a sustained Cmaj7...")
        → BUG-F2#4: pack-name prefix shadows device-name match. Fix by
          checking the device fragment anywhere in the first 80 chars
          rather than only at the start.
    """
    for verbs, action in _VERB_TO_ACTION:
        for verb in verbs:
            if verb in text_lower:
                return action

    # Noun-first device mentions — startswith first (cheap), then in-prefix substring
    for fragment in _KNOWN_DEVICE_FRAGMENTS:
        if text_lower.startswith(fragment) or text_lower.startswith("→ " + fragment):
            return "load_browser_item"

    # Pack-prefix or quoted device-name pattern — substring search in first 80 chars.
    # Catches "Inspired by Nature `tree_tone`...", "Lost and Found `Bad Speaker`...".
    # Underscore-normalize so `tree_tone` matches the `tree tone` fragment.
    head = text_lower[:80].replace("_", " ")
    for fragment in _KNOWN_DEVICE_FRAGMENTS:
        if fragment in head:
            return "load_browser_item"

    return "manual_step"


def _extract_device_name(text: str) -> str | None:
    """Try to extract a device or clip name from step text."""
    for pattern in _DEVICE_EXTRACT_PATTERNS:
        m = pattern.search(text)
        if m:
            return m.group(1).strip()
    return None


def _extract_numeric_value(text: str) -> float | None:
    """Extract the first numeric value from text (for set_device_parameter).

    Requires a word/whitespace/sign boundary before the digit so that digits
    embedded in device names (e.g. 'PitchLoop89') are not matched.
    """
    m = re.search(r"(?<![A-Za-z\d])([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)", text)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return None


def _extract_parameter_name(text: str) -> str | None:
    """Extract a parameter name from step text.

    Looks for patterns like "Pitch A +0.05", "Feedback A ... 0.85",
    "Drive 0.3-0.4", "LFO at 0.1Hz".
    """
    # Pattern: "Parameter Name value" where Parameter Name is Title Case words
    # or backtick-quoted
    param_patterns = [
        re.compile(r"`([^`]+)`\s+[-+]?[\d.]+"),          # `Pitch A` +0.05
        re.compile(r"\b((?:[A-Z][a-zA-Z]+\s+){1,3})[-+]?[\d.]"),  # Pitch A 0.05
        re.compile(r"\b([A-Z][a-zA-Z]+(?:\s+[A-Z])?)\s+(?:at\s+)?[-+]?[\d.]"),
    ]
    for pattern in param_patterns:
        m = pattern.search(text)
        if m:
            name = m.group(1).strip()
            # Filter out generic English words that aren't parameter names
            if name not in ("Set", "Use", "Load", "Add", "With", "For", "The", "A", "An"):
                return name
    return None


def _parse_signal_flow(signal_flow: str | list | None) -> list[dict]:
    """Parse the signal_flow field into structured action steps.

    Handles three formats:
    1. Multi-line string with numbered steps (most common in corpus)
    2. List of strings
    3. List of dicts

    Each output step:
    {
        step: int,
        action: str,         # load_browser_item | insert_device | set_device_parameter
                             # fire_clip | set_track_send | manual_step
        device_name: str?,
        parameter_name: str?,
        value: float?,
        raw_text: str,
        result: "dry-run"
    }
    """
    if not signal_flow:
        return []

    # Normalize to a list of raw text strings
    raw_lines: list[str] = []

    if isinstance(signal_flow, str):
        # Split on numbered steps: "1.", "2.", etc.
        # Also handle continuation lines starting with "→" or "->"
        for line in signal_flow.splitlines():
            line = line.strip()
            if not line:
                continue
            # Split compound steps that have mid-line "→" (e.g. "HDG ... → fire clip")
            # Lines that START with digits+dot are the main step; any "→" within
            # the line after the first segment is a sub-step.
            # Only split if the line doesn't START with "→" (those are handled below)
            if not line.lstrip().startswith("→"):
                # Strip the leading step number to get the content
                content = re.sub(r"^\d+[.)]\s*", "", line).strip()
                # Split on mid-line "→" markers to produce sub-steps,
                # but ONLY when the arrow is NOT inside parentheses.
                # Strategy: mask text inside (...) before splitting, then restore.
                masked = re.sub(r"\([^)]*\)", lambda m: "(" + "X" * (len(m.group(0)) - 2) + ")", content)
                split_positions = [m.start() for m in re.finditer(r"\s+→\s+", masked)]
                if split_positions:
                    # Reconstruct sub_parts using original content at split positions
                    parts: list[str] = []
                    prev = 0
                    for pos in split_positions:
                        # Find the actual end of the arrow in original (lengths match)
                        arrow_m = re.search(r"\s+→\s+", content[pos:])
                        if arrow_m:
                            parts.append(content[prev:pos].strip())
                            prev = pos + arrow_m.end()
                    parts.append(content[prev:].strip())
                    if len(parts) > 1:
                        raw_lines.append(parts[0])
                        for sub in parts[1:]:
                            raw_lines.append("→ " + sub)
                        continue
                # No split happened — fall through with number-stripped content
                raw_lines.append(content)
                continue
            raw_lines.append(line)

    elif isinstance(signal_flow, list):
        for item in signal_flow:
            if isinstance(item, str):
                raw_lines.append(item.strip())
            elif isinstance(item, dict):
                # Dict item — convert to text representation
                text = item.get("text") or item.get("description") or str(item)
                raw_lines.append(text.strip())
    else:
        # Fallback: stringify
        raw_lines = [str(signal_flow)]

    # Parse each line into a structured step
    steps: list[dict] = []
    step_counter = 0

    for line in raw_lines:
        if not line:
            continue

        # Strip leading step number (e.g. "1." or "1)")
        clean = re.sub(r"^\d+[.)]\s*", "", line).strip()
        # Strip leading "→" or "->"
        clean = re.sub(r"^[→\->]+\s*", "", clean).strip()

        if not clean:
            continue

        step_counter += 1
        clean_lower = clean.lower()

        action = _classify_step_verb(clean_lower)
        device_name = _extract_device_name(clean)
        param_name = None
        value = None

        if action == "set_device_parameter":
            param_name = _extract_parameter_name(clean)
            value = _extract_numeric_value(clean)
            if not param_name and device_name:
                # The "device_name" might actually be the parameter
                param_name = device_name
                device_name = None

        step: dict = {
            "step": step_counter,
            "action": action,
            "raw_text": line,
            "result": "dry-run",
        }

        # BUG-INT#1 / BUG-NEW#3: if the regex-based extractor returned None for a
        # load_browser_item step (e.g. "Echo with subtle wow/flutter" has no
        # backtick/quote/TitleCase device name), fall back to scanning the first
        # 80 chars of the line for any known device fragment and use that as the
        # name_filter.
        if action == "load_browser_item" and device_name is None:
            head = clean_lower[:80].replace("_", " ")
            for fragment in _KNOWN_DEVICE_FRAGMENTS:
                if fragment in head:
                    device_name = fragment  # lower-case is fine for name_filter
                    break

        if device_name:
            step["device_name"] = device_name
            # Consistency with extract_chain + pack_aware_compose: every
            # load_browser_item step gets a browser_search_hint the executor
            # can pass to search_browser to resolve the runtime FileId-keyed
            # URI. Cross-pack workflows have no pack context (the YAML names
            # the device by free-form prose), so suggested_path defaults to
            # the broadest browser category.
            if action == "load_browser_item":
                # Use a more precise suggested_path if the fragment is a known
                # native audio-effect or instrument (BUG-INT#1 / BUG-NEW#3).
                hint_name = device_name
                hint_path = _FRAGMENT_TO_SUGGESTED_PATH.get(
                    device_name.lower(), "sounds"
                )
                step["browser_search_hint"] = {
                    "name_filter": hint_name,
                    "suggested_path": hint_path,
                }
        if param_name:
            step["parameter_name"] = param_name
        if value is not None:
            step["value"] = value

        steps.append(step)

    return steps


# ─── Aesthetic overrides ──────────────────────────────────────────────────────


def _apply_aesthetic_overrides(
    steps: list[dict],
    customize_aesthetic: dict | None,
) -> list[dict]:
    """Apply aesthetic customizations to parsed steps.

    Currently handles:
    - target_scale: inserts a set_song_scale step at the top
    - target_bpm: inserts a set_tempo step at the top
    - transpose_semitones: adjusts any numeric pitch values

    For pitch transposition, imports Phase C's transplant logic.
    """
    if not customize_aesthetic:
        return steps

    overrides: list[dict] = []

    # Scale override
    target_scale = customize_aesthetic.get("target_scale", "")
    if target_scale:
        overrides.append({
            "step": 0,
            "action": "set_song_scale",
            "scale": target_scale,
            "raw_text": f"[OVERRIDE] Set scale to {target_scale}",
            "result": "dry-run",
            "comment": f"Aesthetic override: target_scale={target_scale} [SOURCE: agent-inference]",
        })

    # BPM override
    # BUG-EDGE#5: guard against non-numeric target_bpm (e.g. "not-a-number" string)
    target_bpm = customize_aesthetic.get("target_bpm")
    if target_bpm is not None:
        try:
            bpm_val = float(target_bpm)
            overrides.append({
                "step": 0,
                "action": "set_tempo",
                "value": bpm_val,
                "raw_text": f"[OVERRIDE] Set BPM to {target_bpm}",
                "result": "dry-run",
                "comment": f"Aesthetic override: target_bpm={target_bpm} [SOURCE: agent-inference]",
            })
        except (ValueError, TypeError):
            pass  # malformed target_bpm — skip silently

    # Transpose override for pitch-related parameter steps
    transpose_st = customize_aesthetic.get("transpose_semitones")
    if transpose_st is not None:
        try:
            st = float(transpose_st)
            mutated_count = 0
            for i, step in enumerate(steps):
                if step.get("action") == "set_device_parameter":
                    pname = (step.get("parameter_name") or "").lower()
                    if any(k in pname for k in ("pitch", "note", "transpose", "tune")):
                        if step.get("value") is not None:
                            step = dict(step)  # copy
                            step["value"] = round(step["value"] + st, 3)
                            step["comment"] = (
                                f"Pitch transposed by {st:+.1f} semitones "
                                f"[SOURCE: agent-inference]"
                            )
                            steps[i] = step  # write copy back into list
                            mutated_count += 1

            # BUG-NEW#2: if no numeric pitch steps were found to mutate, emit a
            # manual_step so the caller knows the transpose was requested but
            # couldn't be applied automatically.
            if st != 0 and mutated_count == 0:
                sign = "+" if st > 0 else ""
                steps.append({
                    "step": len(steps) + 1,
                    "action": "manual_step",
                    "raw_text": f"[OVERRIDE] Transpose {sign}{st} semitones",
                    "comment": (
                        "No numeric pitch parameters were parsed from this workflow's "
                        "signal_flow. Apply the transpose manually after loading the chain. "
                        "[SOURCE: agent-inference]"
                    ),
                    "result": "dry-run",
                })
        except (TypeError, ValueError):
            pass

    # Renumber: overrides go first (negative step numbers), then original
    for i, ov in enumerate(overrides):
        ov["step"] = -(len(overrides) - i)  # -N, -(N-1), ..., -1

    return overrides + steps


# ─── Dry-run executor ─────────────────────────────────────────────────────────


def _execute_or_dry_run(
    steps: list[dict],
    target_track_index: int,
) -> list[dict]:
    """For Phase F, all execution is dry-run only.

    Marks each step result: "dry-run". If target_track_index >= 0,
    adds a target_track annotation to device-loading steps.
    """
    executed: list[dict] = []
    for step in steps:
        out = dict(step)
        out["result"] = "dry-run"
        if target_track_index >= 0:
            if out.get("action") in ("load_browser_item", "insert_device"):
                out["target_track_index"] = target_track_index
        executed.append(out)
    return executed


# ─── Main entry point ─────────────────────────────────────────────────────────


def cross_pack_chain(
    workflow_entity_id: str,
    target_track_index: int = -1,
    customize_aesthetic: dict | None = None,
) -> dict:
    """Execute (dry-run) a cross-pack workflow recipe step-by-step.

    Called by the MCP tool wrapper in tools.py.

    Parameters
    ----------
    workflow_entity_id : str
        Entity ID from the cross_pack_workflow namespace.
        E.g. "dub_techno_spectral_drone_bed", "boc_decayed_pad".
        Hyphens and underscores are interchangeable.

    target_track_index : int
        -1 = dry run (all steps marked result: "dry-run").
        >= 0 = target existing track (Phase F ships dry-run only for both modes).

    customize_aesthetic : dict, optional
        Optional overrides. Supported keys:
        - "target_scale": str (e.g. "Fmin") — inserts set_song_scale step
        - "target_bpm": float — inserts set_tempo step
        - "transpose_semitones": float — adjusts numeric pitch parameter values

    Returns
    -------
    dict with keys:
        workflow: {entity_id, name, packs_used, description, when_to_reach, gotcha}
        executed_steps: list of action dicts with result: "dry-run"
        warnings: list of caution strings
        sources: citation list
        error: (only on failure) error message
    """
    # ── 1. Load workflow ──────────────────────────────────────────────────────
    wf = _load_workflow(workflow_entity_id)

    if wf is None:
        # List available workflows for helpful error message
        available: list[str] = []
        if _CROSS_WORKFLOWS_DIR.exists():
            for f in sorted(_CROSS_WORKFLOWS_DIR.glob("*.yaml")):
                # Return the entity_id (underscore form) not the filename
                eid = f.stem.replace("-", "_")
                available.append(eid)

        return {
            "error": (
                f"Cross-pack workflow '{workflow_entity_id}' not found. "
                f"Check ~/.livepilot/atlas-overlays/packs/cross_workflows/."
            ),
            "available_workflows": available,
            "hint": (
                "Entity IDs use underscores (e.g. 'dub_techno_spectral_drone_bed'). "
                "Filenames use hyphens (dub-techno-spectral-drone-bed.yaml). "
                "Both forms are accepted."
            ),
            "sources": [],
        }

    # ── 2. Parse signal_flow ──────────────────────────────────────────────────
    signal_flow_raw = wf.get("signal_flow", "")
    parsed_steps = _parse_signal_flow(signal_flow_raw)

    warnings: list[str] = []

    if not parsed_steps:
        warnings.append(
            f"signal_flow field is empty or could not be parsed for "
            f"'{workflow_entity_id}'. The workflow YAML may need updating."
        )

    # ── 3. Apply aesthetic overrides ──────────────────────────────────────────
    if customize_aesthetic:
        parsed_steps = _apply_aesthetic_overrides(parsed_steps, customize_aesthetic)

    # ── 4. Execute (dry-run) ──────────────────────────────────────────────────
    executed_steps = _execute_or_dry_run(parsed_steps, target_track_index)

    # ── 5. Warn about gotchas ─────────────────────────────────────────────────
    gotcha = wf.get("gotcha", "")
    avoid = wf.get("avoid", "")
    if gotcha:
        warnings.append(f"Gotcha: {gotcha}")
    if avoid:
        warnings.append(f"Avoid: {avoid}")

    # ── 6. Build return shape ─────────────────────────────────────────────────
    workflow_meta = {
        "entity_id": wf.get("entity_id", workflow_entity_id),
        "name": wf.get("name", ""),
        "packs_used": wf.get("packs_used", []),
        "devices_used": wf.get("devices_used", []),
        "description": wf.get("description", ""),
        "when_to_reach": wf.get("when_to_reach", ""),
        "gotcha": gotcha,
    }

    return {
        "workflow": workflow_meta,
        "executed_steps": executed_steps,
        "warnings": warnings,
        "sources": [
            f"cross_pack_workflow body.signal_flow [SOURCE: cross_pack_workflow.yaml]",
            f"agent-inference: verb parsing + action classification [SOURCE: agent-inference]",
        ],
    }
