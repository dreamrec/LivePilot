"""Hook Hunter MCP tools — 9 tools for hook and phrase intelligence.

  find_primary_hook — detect the most salient hook in the session
  rank_hook_candidates — list and rank all hook candidates
  develop_hook — suggest development strategies for a hook
  measure_hook_salience — score a specific hook's salience
  score_phrase_impact — score a section's emotional landing
  detect_payoff_failure — find where the song should deliver but doesn't
  suggest_payoff_repair — generate repair strategies for payoff failures
  detect_hook_neglect — check if a strong hook is underused across sections
  compare_phrase_impact — compare emotional impact across multiple sections
"""

from __future__ import annotations

from fastmcp import Context

from ..server import mcp
from . import analyzer


def _get_ableton(ctx: Context):
    return ctx.lifespan_context["ableton"]


def _fetch_tracks_and_scenes(ctx: Context) -> tuple[list[dict], list[dict], dict]:
    """Fetch tracks, scenes, and motif data from Ableton.

    Motif data comes from the motif engine (get_motif_graph). When available,
    it enables the analyzer's strongest path: motif recurrence and salience
    scoring. Falls back to track-name + clip-reuse heuristics when no
    motif data exists (e.g., clips have no MIDI notes).
    """
    ableton = _get_ableton(ctx)
    tracks: list[dict] = []
    scenes: list[dict] = []
    motif_data: dict = {}

    try:
        session = ableton.send_command("get_session_info", {})
        tracks = session.get("tracks", [])
    except Exception:
        pass

    try:
        matrix = ableton.send_command("get_scene_matrix")
        scenes = [
            {"name": s.get("name", f"Scene {i}"), "clips": row}
            for i, (s, row) in enumerate(
                zip(matrix.get("scenes", []), matrix.get("matrix", []))
            )
        ]
    except Exception:
        pass

    # Fetch motif data from the motif engine for salience-based hook discovery
    try:
        motif_data = ableton.send_command("get_motif_graph")
    except Exception:
        pass  # Motif graph requires notes in clips; empty dict is valid fallback

    return tracks, scenes, motif_data


@mcp.tool()
def find_primary_hook(ctx: Context) -> dict:
    """Find the most salient hook in the current session.

    Analyzes melodic motifs, distinctive rhythmic cells, and signature
    textures to identify what the track is most "about."

    Returns the primary hook with salience scores, or a note if no
    clear hook is detected.
    """
    tracks, scenes, motif_data = _fetch_tracks_and_scenes(ctx)

    hook = analyzer.find_primary_hook(tracks, motif_data, scenes)
    if hook:
        return {
            "found": True,
            **hook.to_dict(),
        }

    return {
        "found": False,
        "note": "No clear primary hook detected — consider developing a defining element",
        "suggestion": "Try creating a memorable melodic phrase, distinctive rhythm, or signature texture",
    }


@mcp.tool()
def rank_hook_candidates(ctx: Context, limit: int = 5) -> dict:
    """List and rank all hook candidates in the session.

    Returns candidates sorted by salience — a composite of memorability,
    recurrence, contrast potential, and development potential.

    limit: max candidates to return (default 5)
    """
    tracks, scenes, motif_data = _fetch_tracks_and_scenes(ctx)

    candidates = analyzer.find_hook_candidates(tracks, motif_data, scenes)
    top = candidates[:limit]

    return {
        "candidates": [c.to_dict() for c in top],
        "total_found": len(candidates),
        "shown": len(top),
    }


@mcp.tool()
def develop_hook(
    ctx: Context,
    hook_id: str = "",
    mode: str = "chorus",
) -> dict:
    """Suggest development strategies for a hook.

    hook_id: the hook to develop (from rank_hook_candidates).
             If provided, strategies are adapted to the hook's type
             (melodic, rhythmic, timbral, harmonic, textural).
    mode: development style — "chorus" (lift/strengthen), "variation"
          (melodic variation), "counterline" (complementary line),
          "breakdown" (stripped version), "fill" (ornamental version)

    Returns development strategies with musical explanations.
    """
    # Look up the actual hook to adapt strategies by type
    hook_type = "melodic"  # default
    hook_description = "the hook"
    if hook_id:
        tracks, scenes, motif_data = _fetch_tracks_and_scenes(ctx)
        candidates = analyzer.find_hook_candidates(tracks, motif_data, scenes)
        match = [c for c in candidates if c.hook_id == hook_id]
        if match:
            hook_type = match[0].hook_type
            hook_description = match[0].description

    # Type-specific focus areas
    _type_focus = {
        "melodic": {"dimension": "melodic contour and pitch", "double": "octave or harmony", "strip": "melodic core", "ornament": "grace notes and embellishments"},
        "rhythmic": {"dimension": "rhythmic pattern and groove", "double": "layered percussion or polyrhythm", "strip": "rhythmic skeleton", "ornament": "ghost notes and syncopation"},
        "timbral": {"dimension": "timbre and texture", "double": "parallel processing or layered timbres", "strip": "raw unprocessed sound", "ornament": "modulation and movement"},
        "harmonic": {"dimension": "harmonic movement and voicing", "double": "extended voicings or inversions", "strip": "root notes only", "ornament": "passing tones and suspensions"},
        "textural": {"dimension": "spatial and textural quality", "double": "stereo widening or reverb layers", "strip": "dry mono version", "ornament": "granular or delay effects"},
    }
    focus = _type_focus.get(hook_type, _type_focus["melodic"])

    strategies = {
        "chorus": {
            "approach": f"Lift and strengthen the {hook_type} hook for maximum impact",
            "tactics": [
                f"Double {hook_description} with {focus['double']}",
                f"Add supporting harmonic movement underneath the {focus['dimension']}",
                f"Increase rhythmic density around {hook_description}",
                f"Layer complementary textures that frame the {focus['dimension']}",
            ],
            "identity_effect": "preserves — amplifies the core idea",
        },
        "variation": {
            "approach": f"Create {hook_type} variations of {hook_description}",
            "tactics": [
                f"Transpose or shift the {focus['dimension']} to a different register",
                f"Invert or retrograde the {focus['dimension']}",
                "Apply rhythmic displacement (shift by 1/8 or 1/16)",
                f"Fragment {hook_description} — use only the first half or last half",
            ],
            "identity_effect": "evolves — develops the idea further",
        },
        "counterline": {
            "approach": f"Write a complementary line that dialogues with the {hook_type} hook",
            "tactics": [
                f"Use contrary motion against the {focus['dimension']}",
                f"Fill rhythmic gaps in {hook_description} with the counterline",
                "Match the harmonic context but use different intervals or timbre",
                f"Use a contrasting {hook_type} character to distinguish the counter",
            ],
            "identity_effect": "evolves — adds depth without replacing the core",
        },
        "breakdown": {
            "approach": f"Create a stripped-down version of {hook_description} for contrast",
            "tactics": [
                f"Isolate the {focus['strip']} — remove everything else",
                "Use a different instrument/timbre for the stripped version",
                "Slow down or halve the rhythmic density",
                "Add space and reverb to create distance",
            ],
            "identity_effect": "preserves — the hook is still recognizable in reduced form",
        },
        "fill": {
            "approach": f"Create ornamental variations of {hook_description} for transitions",
            "tactics": [
                f"Add {focus['ornament']}",
                "Create a call-and-response pattern",
                f"Use the hook's rhythm with new {focus['dimension']} material",
                f"Build a riser or fill from {hook_description} fragments",
            ],
            "identity_effect": "evolves — decorates without replacing",
        },
    }

    if mode not in strategies:
        return {
            "error": f"Unknown mode: {mode}",
            "available_modes": list(strategies.keys()),
        }

    strategy = strategies[mode]
    return {
        "hook_id": hook_id,
        "hook_type": hook_type,
        "hook_description": hook_description,
        "mode": mode,
        **strategy,
    }


@mcp.tool()
def measure_hook_salience(ctx: Context, hook_id: str = "") -> dict:
    """Measure the salience of a specific hook or the primary hook.

    Returns detailed scores for memorability, recurrence, contrast
    potential, and development potential.
    """
    tracks, scenes, motif_data = _fetch_tracks_and_scenes(ctx)
    candidates = analyzer.find_hook_candidates(tracks, motif_data, scenes)

    if hook_id:
        match = [c for c in candidates if c.hook_id == hook_id]
        if not match:
            return {
                "error": f"Hook {hook_id} not found",
                "available_hooks": [c.hook_id for c in candidates[:5]],
            }
        hook = match[0]
    elif candidates:
        hook = candidates[0]
    else:
        return {"error": "No hooks detected in the session"}

    return {
        **hook.to_dict(),
        "interpretation": _interpret_salience(hook),
    }


@mcp.tool()
def score_phrase_impact(
    ctx: Context,
    section_index: int = 0,
    target: str = "hook",
) -> dict:
    """Score a section's emotional impact as a musical phrase.

    Evaluates arrival strength, anticipation, contrast, groove
    continuity, and payoff balance. Phrase-level judgment outranks
    parameter-only evaluation for arrangement and transition decisions.

    section_index: which section/scene to evaluate (0-based)
    target: what it should function as — "hook", "drop", "chorus",
            "transition", or "loop"
    """
    ableton = _get_ableton(ctx)

    # Build section data from scenes
    sections = _get_section_data(ableton)
    if section_index >= len(sections):
        return {"error": f"Section index {section_index} out of range (have {len(sections)})"}

    section = sections[section_index]
    prev_section = sections[section_index - 1] if section_index > 0 else {}

    # Get song brain for context
    song_brain = _get_song_brain_dict()

    impact = analyzer.score_phrase_impact(section, target, song_brain, prev_section)
    return impact.to_dict()


@mcp.tool()
def detect_payoff_failure(ctx: Context) -> dict:
    """Detect where the song should deliver a payoff but doesn't.

    Checks chorus, drop, and hook sections for flat arrivals,
    weak contrast, missing setups, and absent hooks.

    Returns failures with severity and repair suggestions.
    """
    ableton = _get_ableton(ctx)
    sections = _get_section_data(ableton)
    song_brain = _get_song_brain_dict()

    failures = analyzer.detect_payoff_failures(sections, song_brain)

    return {
        "failures": [f.to_dict() for f in failures],
        "failure_count": len(failures),
        "overall_health": "healthy" if not failures else (
            "needs_attention" if len(failures) <= 2 else "significant_issues"
        ),
    }


@mcp.tool()
def suggest_payoff_repair(ctx: Context) -> dict:
    """Generate repair strategies for detected payoff failures.

    Runs payoff detection first, then suggests specific fixes
    for each failure.
    """
    ableton = _get_ableton(ctx)
    sections = _get_section_data(ableton)
    song_brain = _get_song_brain_dict()

    failures = analyzer.detect_payoff_failures(sections, song_brain)
    if not failures:
        return {"note": "No payoff failures detected — the song delivers where expected"}

    repairs = analyzer.suggest_payoff_repairs(failures)
    return {
        "repairs": repairs,
        "repair_count": len(repairs),
    }


# ── Helpers ───────────────────────────────────────────────────────


def _get_section_data(ableton) -> list[dict]:
    """Build section data from Ableton scenes with real energy/density/has_drums."""
    sections: list[dict] = []
    try:
        matrix = ableton.send_command("get_scene_matrix")
        scenes_list = matrix.get("scenes", [])
        matrix_rows = matrix.get("matrix", [])

        # Detect drum track indices by name
        drum_keywords = {"drum", "beat", "kick", "hat", "perc", "snare"}
        track_names = []
        # tracks may be in matrix metadata or session_info
        for ti, row_entry in enumerate(matrix_rows[0] if matrix_rows else []):
            track_names.append("")  # placeholder — we'll use scenes_list tracks if available
        # Use scene matrix track info if available
        track_info = matrix.get("tracks", [])
        drum_indices = set()
        for ti, track in enumerate(track_info):
            name_lower = track.get("name", "").lower() if isinstance(track, dict) else ""
            if any(kw in name_lower for kw in drum_keywords):
                drum_indices.add(ti)

        for i, scene in enumerate(scenes_list):
            row = matrix_rows[i] if i < len(matrix_rows) else []
            if not isinstance(row, list):
                row = []
            clip_count = sum(1 for c in row if c)
            total_tracks = max(len(row), 1)

            # has_drums: check if any drum track has a clip in this scene
            has_drums = any(
                di < len(row) and row[di]
                for di in drum_indices
            ) if drum_indices else False

            density = min(1.0, clip_count / total_tracks)
            # energy: density + drum bonus
            energy = min(1.0, density + (0.1 if has_drums else 0.0))

            sections.append({
                "id": f"scene_{i}",
                "name": scene.get("name", f"Scene {i}"),
                "label": scene.get("name", "").lower(),
                "energy": round(energy, 3),
                "density": round(density, 3),
                "has_drums": has_drums,
            })
    except Exception:
        pass

    return sections


def _get_song_brain_dict() -> dict:
    """Get current SongBrain as dict, or empty dict."""
    try:
        from ..song_brain.tools import _current_brain
        if _current_brain is not None:
            return _current_brain.to_dict()
    except Exception as _e:
        if __debug__:
            import sys
            print(f"LivePilot: SongBrain unavailable in hook_hunter: {_e}", file=sys.stderr)
    return {}


@mcp.tool()
def detect_hook_neglect(ctx: Context) -> dict:
    """Detect if a strong hook exists but is underused across sections.

    Checks whether the primary hook appears in enough sections to
    create adequate repetition and memorability. A hook that only
    appears in one section is "neglected" — it needs to recur.

    Returns neglect analysis with underused sections and suggestions.
    """
    tracks, scenes, motif_data = _fetch_tracks_and_scenes(ctx)

    hook = analyzer.find_primary_hook(tracks, motif_data, scenes)
    if not hook:
        return {
            "neglected": False,
            "note": "No primary hook detected — hook neglect N/A",
            "suggestion": "Create a defining hook before checking for neglect",
        }

    # Check per-track hook presence across scenes using scene matrix
    hook_location = hook.location if hook.location else ""
    ableton = _get_ableton(ctx)

    try:
        matrix = ableton.send_command("get_scene_matrix")
    except Exception:
        return {
            "neglected": False,
            "hook": hook.to_dict(),
            "note": "Could not fetch scene matrix to assess neglect",
        }

    scenes_list = matrix.get("scenes", [])
    matrix_rows = matrix.get("matrix", [])
    track_info = matrix.get("tracks", [])

    if not scenes_list or not hook_location:
        return {
            "neglected": False,
            "hook": hook.to_dict(),
            "note": "Insufficient section data to assess neglect",
        }

    # Find the hook's track index by matching location to track names
    hook_track_idx = None
    hook_loc_lower = hook_location.lower()
    for ti, track in enumerate(track_info):
        track_name = track.get("name", "") if isinstance(track, dict) else ""
        if track_name.lower() == hook_loc_lower or hook_loc_lower in track_name.lower():
            hook_track_idx = ti
            break

    if hook_track_idx is None:
        # Fallback: can't find the track, use density proxy
        sections = _get_section_data(ableton)
        present_count = sum(1 for s in sections if s.get("density", 0) > 0.3)
        total = max(len(sections), 1)
        return {
            "neglected": present_count / total < 0.5 and hook.salience > 0.3,
            "hook": hook.to_dict(),
            "presence_ratio": round(present_count / total, 2),
            "note": f"Could not find track '{hook_location}' — used density fallback",
        }

    # Check each scene for hook track clip presence
    present_count = 0
    absent_sections = []
    for i, scene in enumerate(scenes_list):
        scene_name = scene.get("name", f"Scene {i}")
        # Skip intro — hook absence there is normal
        if i == 0 and "intro" in scene_name.lower():
            continue

        row = matrix_rows[i] if i < len(matrix_rows) else []
        if isinstance(row, list) and hook_track_idx < len(row) and row[hook_track_idx]:
            present_count += 1
        else:
            absent_sections.append(scene_name)

    total_eligible = max(len(scenes_list) - 1, 1)  # exclude first intro
    presence_ratio = present_count / total_eligible

    neglected = presence_ratio < 0.5 and hook.salience > 0.3

    return {
        "neglected": neglected,
        "hook": hook.to_dict(),
        "hook_track": hook_location,
        "hook_track_index": hook_track_idx,
        "presence_ratio": round(presence_ratio, 2),
        "present_in_sections": present_count,
        "absent_from": absent_sections,
        "suggestion": (
            f"The hook ({hook.description}) on track '{hook_location}' only has clips in "
            f"{presence_ratio:.0%} of sections. Consider adding variations in: {', '.join(absent_sections)}"
        ) if neglected else "Hook track has clips in most sections — well-distributed",
    }


@mcp.tool()
def compare_phrase_impact(
    ctx: Context,
    section_indices: list[int] | None = None,
    target: str = "hook",
) -> dict:
    """Compare phrase-level emotional impact across multiple sections.

    Runs score_phrase_impact for each section and returns a ranked
    comparison with delta analysis between the strongest and weakest.

    section_indices: list of 0-based section indices to compare
    target: what the sections should function as — "hook", "drop",
            "chorus", "transition", or "loop"
    """
    if not section_indices or len(section_indices) < 2:
        return {"error": "Provide at least 2 section_indices to compare"}

    ableton = _get_ableton(ctx)
    sections = _get_section_data(ableton)
    song_brain = _get_song_brain_dict()

    results = []
    for idx in section_indices:
        if idx >= len(sections):
            results.append({
                "section_index": idx,
                "error": f"Index {idx} out of range (have {len(sections)} sections)",
            })
            continue

        section = sections[idx]
        prev_section = sections[idx - 1] if idx > 0 else {}
        impact = analyzer.score_phrase_impact(section, target, song_brain, prev_section)
        results.append({
            "section_index": idx,
            "section_name": section.get("name", f"Section {idx}"),
            **impact.to_dict(),
        })

    # Rank by composite impact
    valid = [r for r in results if "composite_impact" in r]
    valid.sort(key=lambda r: r.get("composite_impact", 0), reverse=True)

    # Delta analysis between best and worst
    delta = {}
    if len(valid) >= 2:
        best, worst = valid[0], valid[-1]
        delta = {
            "strongest": best["section_name"],
            "weakest": worst["section_name"],
            "composite_delta": round(
                best.get("composite_impact", 0) - worst.get("composite_impact", 0), 3
            ),
            "biggest_gap_dimension": _find_biggest_gap(best, worst),
        }

    return {
        "target": target,
        "rankings": valid,
        "delta_analysis": delta,
        "section_count": len(section_indices),
    }


def _find_biggest_gap(best: dict, worst: dict) -> str:
    """Find which impact dimension has the biggest gap between best and worst."""
    dimensions = [
        "arrival_strength", "anticipation_strength", "contrast_quality",
        "groove_continuity", "payoff_balance", "section_clarity",
    ]
    max_gap = 0.0
    max_dim = ""
    for dim in dimensions:
        gap = abs(best.get(dim, 0) - worst.get(dim, 0))
        if gap > max_gap:
            max_gap = gap
            max_dim = dim
    return max_dim


def _interpret_salience(hook) -> str:
    """Human-readable interpretation of salience score."""
    if hook.salience > 0.7:
        return "Strong hook — this is clearly the track's defining element"
    elif hook.salience > 0.4:
        return "Moderate hook — recognizable but could be developed further"
    elif hook.salience > 0.2:
        return "Emerging hook — has potential but needs more prominence"
    else:
        return "Weak hook candidate — consider strengthening or replacing"
