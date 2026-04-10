"""Hook Hunter MCP tools — 7 tools for hook and phrase intelligence.

  find_primary_hook — detect the most salient hook in the session
  rank_hook_candidates — list and rank all hook candidates
  develop_hook — suggest development strategies for a hook
  measure_hook_salience — score a specific hook's salience
  score_phrase_impact — score a section's emotional landing
  detect_payoff_failure — find where the song should deliver but doesn't
  suggest_payoff_repair — generate repair strategies for payoff failures
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

    hook_id: the hook to develop (from rank_hook_candidates)
    mode: development style — "chorus" (lift/strengthen), "variation"
          (melodic variation), "counterline" (complementary line),
          "breakdown" (stripped version), "fill" (ornamental version)

    Returns development strategies with musical explanations.
    """
    strategies = {
        "chorus": {
            "approach": "Lift and strengthen the hook for maximum impact",
            "tactics": [
                "Double the hook with an octave or harmony",
                "Add supporting harmonic movement underneath",
                "Increase rhythmic density around the hook",
                "Layer complementary textures that frame the hook",
            ],
            "identity_effect": "preserves — amplifies the core idea",
        },
        "variation": {
            "approach": "Create melodic or rhythmic variations of the hook",
            "tactics": [
                "Transpose the hook to a different register",
                "Invert or retrograde the melodic contour",
                "Apply rhythmic displacement (shift by 1/8 or 1/16)",
                "Fragment the hook — use only the first half or last half",
            ],
            "identity_effect": "evolves — develops the idea further",
        },
        "counterline": {
            "approach": "Write a complementary line that dialogues with the hook",
            "tactics": [
                "Use contrary motion — when hook goes up, counter goes down",
                "Fill rhythmic gaps in the hook with the counterline",
                "Match the harmonic context but use different intervals",
                "Use a different timbre to distinguish the counterline",
            ],
            "identity_effect": "evolves — adds depth without replacing the core",
        },
        "breakdown": {
            "approach": "Create a stripped-down version for contrast sections",
            "tactics": [
                "Remove harmony and rhythm — isolate the melodic core",
                "Use a different instrument/timbre for the stripped version",
                "Slow down or halve the rhythmic density",
                "Add space and reverb to create distance",
            ],
            "identity_effect": "preserves — the hook is still recognizable in reduced form",
        },
        "fill": {
            "approach": "Create ornamental variations for transitions and fills",
            "tactics": [
                "Add grace notes and embellishments",
                "Create a call-and-response pattern",
                "Use the hook's rhythm with new pitch material",
                "Build a riser or fill from hook fragments",
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
    """Build section data from Ableton scenes."""
    sections: list[dict] = []
    try:
        matrix = ableton.send_command("get_scene_matrix")
        for i, scene in enumerate(matrix.get("scenes", [])):
            row = matrix.get("matrix", [[]])[i] if i < len(matrix.get("matrix", [])) else []
            clip_count = sum(1 for c in row if c) if isinstance(row, list) else 0
            total_tracks = len(row) if isinstance(row, list) else 1

            sections.append({
                "id": f"scene_{i}",
                "name": scene.get("name", f"Scene {i}"),
                "label": scene.get("name", "").lower(),
                "energy": min(1.0, clip_count / max(total_tracks, 1)),
                "density": min(1.0, clip_count / max(total_tracks, 1)),
                "has_drums": True,  # assume drums present
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
    except Exception:
        pass
    return {}


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
