"""Safety Kernel — policy enforcement layer for LivePilot.

Pure Python, zero I/O.  Validates proposed actions against policies
before they execute.  MCP tool wrappers call ``check_action_safety``
before executing mutations.

Policies
--------
* **Blocked** — bulk-destructive operations that are never safe to run
  automatically (delete_all_tracks, clear_all_automation, …).
* **Confirm required** — single-item destructive ops where the user
  should be prompted before proceeding.
* **Scope check** — mutations affecting more than 5 tracks at once
  are flagged as *caution*.
* **Capability gating** — when the runtime is in *read_only* mode,
  all mutations are blocked.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional


# ── Data types ─────────────────────────────────────────────────────

@dataclass
class SafetyCheck:
    """Result of evaluating a proposed action against safety policies."""

    action: str                       # what was proposed
    allowed: bool                     # can it proceed?
    risk_level: str                   # "safe", "caution", "blocked"
    reason: str                       # why blocked / cautioned
    requires_confirmation: bool       # should we ask the user first?

    def to_dict(self) -> dict:
        return asdict(self)


# ── Policy sets ────────────────────────────────────────────────────

BLOCKED_ACTIONS: set[str] = {
    "delete_all_tracks",
    "delete_all_clips",
    "delete_all_scenes",
    "clear_all_automation",
    "reset_all_devices",
}

CONFIRM_REQUIRED_ACTIONS: set[str] = {
    "delete_track",
    "delete_clip",
    "delete_scene",
    "flatten_track",
    "replace_simpler_sample",
}

# Read-only prefixes — any action starting with one of these is a read.
_READ_ONLY_PREFIXES = (
    "get_",
    "analyze_",
    "identify_",
    "detect_",
    "check_",
    "search_",
    "compare_",
    "read_",
    "classify_",
    "find_",
    "walk_",
    "list_",
    "export_",
    "extract_",
    "build_world_model",
    "compile_goal_vector",
    "evaluate_",
    "memory_list",
    "memory_get",
    "memory_recall",
)

# Explicit safe actions (full list for fast-path lookup).
SAFE_ACTIONS: set[str] = {
    "get_session_info",
    "get_track_info",
    "get_notes",
    "get_device_parameters",
    "get_master_spectrum",
    "get_master_rms",
    "get_detected_key",
    "get_clip_info",
    "get_scenes_info",
    "get_arrangement_clips",
    "get_arrangement_notes",
    "get_clip_automation",
    "get_automation_recipes",
    "get_browser_tree",
    "get_browser_items",
    "get_return_tracks",
    "get_master_track",
    "get_mix_snapshot",
    "get_track_routing",
    "get_track_meters",
    "get_master_meters",
    "get_device_info",
    "get_device_presets",
    "get_rack_chains",
    "get_freeze_status",
    "get_scene_matrix",
    "get_playing_clips",
    "get_cue_points",
    "get_hidden_parameters",
    "get_automation_state",
    "get_display_values",
    "get_warp_markers",
    "get_clip_file_path",
    "get_simpler_slices",
    "get_spectral_shape",
    "get_mel_spectrum",
    "get_chroma",
    "get_onsets",
    "get_novelty",
    "get_momentary_loudness",
    "get_recent_actions",
    "get_session_diagnostics",
    "get_plugin_parameters",
    "get_plugin_presets",
    "analyze_harmony",
    "analyze_composition",
    "analyze_loudness",
    "analyze_spectrum_offline",
    "analyze_midi_file",
    "analyze_for_automation",
    "analyze_outcomes",
    "identify_scale",
    "detect_theory_issues",
    "compare_to_reference",
    "read_audio_metadata",
    "check_flucoma",
    "search_browser",
    "classify_progression",
    "find_voice_leading_path",
    "walk_device_tree",
    "build_world_model",
    "compile_goal_vector",
    "evaluate_move",
    "evaluate_composition_move",
    "memory_list",
    "memory_get",
    "memory_recall",
    "extract_piano_roll",
    "export_clip_midi",
    "get_section_graph",
    "get_phrase_grid",
    "get_harmony_field",
    "get_transition_analysis",
    "get_section_outcomes",
    "get_motif_graph",
    "get_technique_card",
    "get_emotional_arc",
    "get_style_tactics",
    "research_technique",
    "get_capability_state",
    "get_action_ledger_summary",
    "get_last_move",
    "get_taste_profile",
    "evaluate_with_fabric",
    "get_anti_preferences",
    "get_promotion_candidates",
    "analyze_mix",
    "get_mix_issues",
    "get_mix_summary",
    "get_masking_report",
    "analyze_sound_design",
    "get_sound_design_issues",
    "get_patch_model",
    "analyze_transition",
    "score_transition",
    "build_reference_profile",
    "analyze_reference_gaps",
    "check_translation",
    "get_translation_issues",
    "get_performance_state",
    "get_performance_safe_moves",
    "get_project_brain_summary",
}


# ── Scope limits per capability mode ──────────────────────────────

_MAX_SCOPE: dict[str, dict] = {
    "normal":             {"max_tracks": 0},        # 0 = unlimited
    "measured_degraded":  {"max_tracks": 3},
    "judgment_only":      {"max_tracks": 1},
    "read_only":          {"max_tracks": 0},        # mutations blocked entirely
}

_WIDE_SCOPE_THRESHOLD = 5   # tracks


# ── Public API ─────────────────────────────────────────────────────

def is_read_only_action(action: str) -> bool:
    """Return True if *action* is a non-mutating read/query."""
    if action in SAFE_ACTIONS:
        return True
    return action.startswith(_READ_ONLY_PREFIXES)


def get_max_safe_scope(capability_mode: str) -> dict:
    """Return the maximum allowed scope for *capability_mode*.

    Keys:
      max_tracks — 0 means unlimited.
    """
    return dict(_MAX_SCOPE.get(capability_mode, _MAX_SCOPE["normal"]))


def check_action_safety(
    action: str,
    scope: Optional[dict] = None,
    capability_state: Optional[dict] = None,
) -> SafetyCheck:
    """Validate a proposed action against safety policies.

    Parameters
    ----------
    action:
        Tool / command name (e.g. ``"delete_track"``).
    scope:
        Optional dict describing what the action will affect.
        Recognised key: ``track_count`` (int).
    capability_state:
        Optional dict with at least a ``"mode"`` key
        (``"normal"``, ``"read_only"``, …).

    Returns
    -------
    SafetyCheck
    """
    scope = scope or {}
    capability_state = capability_state or {}
    mode = capability_state.get("mode", "normal")

    # 1. Blocked actions — always refused.
    if action in BLOCKED_ACTIONS:
        return SafetyCheck(
            action=action,
            allowed=False,
            risk_level="blocked",
            reason=f"'{action}' is a bulk-destructive operation and is blocked by policy.",
            requires_confirmation=False,
        )

    # 2. Capability gating — read_only blocks all mutations.
    if mode == "read_only" and not is_read_only_action(action):
        return SafetyCheck(
            action=action,
            allowed=False,
            risk_level="blocked",
            reason="System is in read_only mode — mutations are not allowed.",
            requires_confirmation=False,
        )

    # 3. Scope-based gating for degraded modes.
    track_count = scope.get("track_count", 1)
    max_scope = get_max_safe_scope(mode)
    max_tracks = max_scope["max_tracks"]
    if max_tracks > 0 and track_count > max_tracks and not is_read_only_action(action):
        return SafetyCheck(
            action=action,
            allowed=False,
            risk_level="blocked",
            reason=(
                f"Scope ({track_count} tracks) exceeds limit for "
                f"'{mode}' mode (max {max_tracks})."
            ),
            requires_confirmation=False,
        )

    # 4. Wide-scope caution (normal mode).
    if track_count > _WIDE_SCOPE_THRESHOLD and not is_read_only_action(action):
        return SafetyCheck(
            action=action,
            allowed=True,
            risk_level="caution",
            reason=(
                f"Action affects {track_count} tracks (> {_WIDE_SCOPE_THRESHOLD}). "
                "Proceed with caution."
            ),
            requires_confirmation=True,
        )

    # 5. Confirm-required actions.
    if action in CONFIRM_REQUIRED_ACTIONS:
        return SafetyCheck(
            action=action,
            allowed=True,
            risk_level="caution",
            reason=f"'{action}' is destructive — user confirmation recommended.",
            requires_confirmation=True,
        )

    # 6. Explicitly safe / read-only.
    if is_read_only_action(action):
        return SafetyCheck(
            action=action,
            allowed=True,
            risk_level="safe",
            reason="Read-only action — always safe.",
            requires_confirmation=False,
        )

    # 7. Default — allow but note it's a mutation.
    return SafetyCheck(
        action=action,
        allowed=True,
        risk_level="safe",
        reason="Action permitted by policy.",
        requires_confirmation=False,
    )


def check_batch_safety(actions: list[dict]) -> list[SafetyCheck]:
    """Check a batch of proposed actions.

    Each element should be a dict with at least an ``"action"`` key,
    plus optional ``"scope"`` and ``"capability_state"`` keys.

    Returns one :class:`SafetyCheck` per input, in the same order.
    """
    results: list[SafetyCheck] = []
    for entry in actions:
        action = entry.get("action", "")
        scope = entry.get("scope")
        cap = entry.get("capability_state")
        results.append(check_action_safety(action, scope, cap))
    return results
