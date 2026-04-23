"""Brief compliance check — v1.18.3 pure function for anti-pattern and
locked-dimension enforcement.

Pure computation: no I/O, no session state. Caller passes the brief
dict and the intended tool call; the function returns a report of
violations. Director's Phase 6 calls this before each risky tool call.

Design principles:

1. **Best-effort heuristic, not semantic understanding.** anti_patterns
   in the brief are prose. The checker does keyword-token matching
   against humanized tool-call descriptions. Won't catch every
   violation (e.g., "too muddy" → EQ cut at 300 Hz requires more
   intelligence than substring match). Does catch obvious ones
   (e.g., "bright top-end" → Hi Gain boost).

2. **Never block — always report.** The return format is a violations
   list with human-readable reason + suggestion. The caller (director)
   decides whether to proceed, ask the user, or abandon. Hard-blocking
   at this layer would crash under false positives.

3. **Empty brief passes everything.** A brief without anti_patterns or
   locked_dimensions returns ok=True for all calls — we don't want a
   fresh session to be hostile to experimentation.
"""

from __future__ import annotations

import re
from typing import Any


# ── Tool → dimension mapping ────────────────────────────────────────
# Maps MCP tool names to the creative dimension they primarily affect.
# Used for locked_dimensions enforcement. A tool can map to None
# (dimension-agnostic — e.g., undo, get_session_info) in which case no
# locked-dimension check applies.

_STRUCTURAL_TOOLS = frozenset({
    "create_scene", "delete_scene", "duplicate_scene", "set_scene_name",
    "set_scene_tempo", "set_scene_color", "fire_scene",
    "set_clip_follow_action", "set_scene_follow_action",
    "capture_and_insert_scene",
    "create_arrangement_clip", "create_native_arrangement_clip",
    "force_arrangement", "plan_arrangement",
    "transform_section", "refresh_repeated_section",
})

_RHYTHMIC_TOOLS = frozenset({
    "add_notes", "modify_notes", "remove_notes", "transpose_notes",
    "duplicate_notes", "add_arrangement_notes", "modify_arrangement_notes",
    "remove_arrangement_notes", "quantize_clip",
    "assign_clip_groove", "set_groove_params", "set_song_groove_amount",
    "apply_gesture_template",
    "generate_euclidean_rhythm", "layer_euclidean_rhythms",
    "generate_countermelody", "transform_motif",
})

_TIMBRAL_TOOLS = frozenset({
    "set_device_parameter", "batch_set_parameters",
    "load_browser_item", "find_and_load_device",
    "load_device_by_uri", "insert_device", "delete_device", "move_device",
    "toggle_device", "copy_device_state",
    "install_m4l_device",
})

_SPATIAL_TOOLS = frozenset({
    "set_track_send", "set_track_pan", "set_track_volume",
    "set_master_volume",
    "create_return_track",
    "set_track_routing",
})


def _tool_to_dimension(tool_name: str, tool_args: dict) -> str | None:
    """Map an MCP tool call to its primary creative dimension.

    Returns one of {"structural", "rhythmic", "timbral", "spatial"} or
    None if the tool is dimension-agnostic.

    Some tools (e.g., load_browser_item) are timbral EXCEPT when loading
    a device on a return track, which is spatial. The heuristic resolves
    this via track_index: negative indices indicate return tracks.
    """
    if tool_name in _STRUCTURAL_TOOLS:
        return "structural"
    if tool_name in _RHYTHMIC_TOOLS:
        return "rhythmic"
    if tool_name in _SPATIAL_TOOLS:
        return "spatial"
    if tool_name in _TIMBRAL_TOOLS:
        # load_browser_item on a return track is spatial, not timbral —
        # loading Echo/Reverb/Auto Filter on a return is send-chain work.
        track_index = tool_args.get("track_index")
        if isinstance(track_index, int) and track_index < 0 and track_index != -1000:
            return "spatial"
        return "timbral"
    return None


# ── Anti-pattern token matching ────────────────────────────────────

# Phrases that describe parameter changes indicative of "bright" moves
_BRIGHTENING_PARAM_KEYWORDS = ("hi gain", "hi freq", "high gain", "brightness",
                                "treble", "presence", "air")
# Phrases indicative of "aggressive transient" moves
_TRANSIENT_BOOST_KEYWORDS = ("transient", "attack", "punch", "snappy")
# Phrases indicative of "sidechain" moves
_SIDECHAIN_KEYWORDS = ("sidechain", "envelope follower", "ducking")
# Phrases indicative of "quantization" moves
_QUANTIZE_KEYWORDS = ("quantize", "snap", "full-grid", "perfectly quantized")


def _humanize_tool_call(tool_name: str, tool_args: dict) -> str:
    """Produce a prose description of a tool call for keyword matching.

    Best-effort — the output is not structured, just a lowercased string
    that concatenates the tool name + notable arg values.
    """
    parts = [tool_name]
    for key, val in (tool_args or {}).items():
        if isinstance(val, (str, int, float, bool)):
            parts.append(f"{key}={val}")
    return " ".join(parts).lower()


def _anti_pattern_matches(pattern: str, tool_name: str, tool_args: dict) -> bool:
    """Decide whether an anti_pattern phrase flags this tool call.

    Strategy: lowercase the pattern, pull content keywords, match against
    the humanized call + known parameter-name heuristics.
    """
    pattern_lower = pattern.lower()
    call_desc = _humanize_tool_call(tool_name, tool_args)

    # Direct substring match — cheapest first
    # Split pattern into words, check if any significant word appears
    # in the call description
    stopwords = {"the", "a", "an", "and", "or", "of", "to", "in", "on", "at", "with", "for", "/", "-"}
    pattern_tokens = [w.strip("—-./,:;") for w in re.split(r"\s+", pattern_lower)]
    pattern_tokens = [w for w in pattern_tokens if w and w not in stopwords and len(w) >= 3]

    # Check parameter-name heuristics for common anti-patterns
    if any(kw in pattern_lower for kw in ("bright", "top-end", "top end", "highs")):
        param_name = str(tool_args.get("parameter_name", "")).lower()
        value = tool_args.get("value")
        if any(bright_kw in param_name for bright_kw in _BRIGHTENING_PARAM_KEYWORDS):
            # Boosting (positive value on a gain parameter) is the violation
            if isinstance(value, (int, float)) and value > 0:
                return True

    if any(kw in pattern_lower for kw in ("transient", "aggressive transient",
                                            "transient-heavy", "crisp")):
        param_name = str(tool_args.get("parameter_name", "")).lower()
        if any(t_kw in param_name for t_kw in _TRANSIENT_BOOST_KEYWORDS):
            value = tool_args.get("value")
            if isinstance(value, (int, float)) and value > 0.5:
                return True

    if any(kw in pattern_lower for kw in ("sidechain", "pumping")):
        if tool_name == "compressor_set_sidechain":
            return True
        param_name = str(tool_args.get("parameter_name", "")).lower()
        if any(sc_kw in param_name for sc_kw in _SIDECHAIN_KEYWORDS):
            return True

    if any(kw in pattern_lower for kw in ("full-grid", "full grid",
                                            "quantized", "perfectly quantized")):
        if tool_name == "quantize_clip":
            # Quantize to tight grid (1/16 or finer, strong amount) is the violation
            return True

    # Fallback: token-level substring match
    for token in pattern_tokens:
        if token in call_desc:
            return True

    return False


# ── Public API ──────────────────────────────────────────────────────

def check_brief_compliance(
    brief: dict,
    tool_name: str,
    tool_args: dict | None = None,
) -> dict:
    """Check whether a tool call complies with the active creative brief.

    brief: compiled Creative Brief dict (may contain anti_patterns,
           locked_dimensions, reference_anchors, etc.).
    tool_name: the MCP tool about to be called.
    tool_args: the dict of arguments.

    Returns:
        {
            "ok": bool,
            "violations": [
                {
                    "rule": "anti_pattern" | "locked_dimension",
                    "detail": <pattern or dimension string>,
                    "reason": "...",
                    "suggestion": "...",
                },
                ...
            ],
        }

    Empty brief (no anti_patterns, no locked_dimensions) always returns
    ok=True with empty violations list. Best-effort heuristic — not
    semantic understanding. Caller (director Phase 6) decides whether
    to proceed, surface to user, or abandon.
    """
    tool_args = tool_args or {}
    violations: list[dict[str, Any]] = []

    # 1. Check anti_patterns
    anti_patterns = brief.get("anti_patterns", []) or []
    for pattern in anti_patterns:
        if not isinstance(pattern, str) or not pattern.strip():
            continue
        if _anti_pattern_matches(pattern, tool_name, tool_args):
            violations.append({
                "rule": "anti_pattern",
                "detail": pattern,
                "reason": (
                    f"Tool call '{tool_name}' appears to violate the "
                    f"anti_pattern '{pattern}' from the active brief."
                ),
                "suggestion": (
                    "Either (a) adjust the call to avoid this pattern, "
                    "(b) ask the user to explicitly override this "
                    "specific anti_pattern, or (c) pick a different "
                    "tool that achieves the creative goal without "
                    "triggering the avoid rule."
                ),
            })

    # 2. Check locked_dimensions
    locked_dims = brief.get("locked_dimensions", []) or []
    tool_dimension = _tool_to_dimension(tool_name, tool_args)
    if tool_dimension and tool_dimension in locked_dims:
        violations.append({
            "rule": "locked_dimension",
            "detail": tool_dimension,
            "reason": (
                f"Tool '{tool_name}' touches the '{tool_dimension}' "
                f"dimension which the user explicitly locked in this "
                f"brief."
            ),
            "suggestion": (
                f"User locked this dimension. Either (a) surface the "
                f"conflict and ask the user to unlock, or (b) pick a "
                f"tool that operates on a different dimension. "
                f"Available unlocked dimensions: "
                f"{sorted(set(['structural', 'rhythmic', 'timbral', 'spatial']) - set(locked_dims))}."
            ),
        })

    return {
        "ok": not violations,
        "violations": violations,
    }
