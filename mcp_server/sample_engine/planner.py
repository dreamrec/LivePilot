"""SamplePlanner — technique selection and plan compilation.

Pure computation. Selects the best technique for a given sample + intent,
then compiles it into a concrete sequence of MCP tool calls.
"""

from __future__ import annotations

from typing import Optional

from .models import SampleProfile, SampleIntent, SampleTechnique
from .techniques import find_techniques, get_technique


def select_technique(
    profile: SampleProfile,
    intent: SampleIntent,
    taste_graph: object = None,
    recent_techniques: Optional[list[str]] = None,
) -> Optional[SampleTechnique]:
    """Select the best technique for this sample + intent.

    Scoring: material_match(0.3) + intent_match(0.3) + philosophy_match(0.2) +
             novelty_bonus(0.1) + taste_fit(0.1)
    """
    candidates = find_techniques(
        material_type=profile.material_type,
        intent=intent.intent_type,
        philosophy=intent.philosophy if intent.philosophy != "auto" else None,
    )

    if not candidates:
        # Broaden search — try without material filter
        candidates = find_techniques(intent=intent.intent_type)

    if not candidates:
        return None

    recent = set(recent_techniques or [])

    scored: list[tuple[SampleTechnique, float]] = []
    for t in candidates:
        score = 0.0

        # Material match
        if profile.material_type in t.material_types:
            score += 0.3
        elif "any" in t.material_types or not t.material_types:
            score += 0.15

        # Intent match
        if intent.intent_type in t.intents:
            score += 0.3
        elif any(i in t.intents for i in _related_intents(intent.intent_type)):
            score += 0.15

        # Philosophy match
        if intent.philosophy == "auto" or intent.philosophy == t.philosophy or t.philosophy == "both":
            score += 0.2
        elif intent.philosophy != t.philosophy:
            score += 0.05

        # Novelty bonus
        if t.technique_id not in recent:
            score += 0.1

        scored.append((t, score))

    scored.sort(key=lambda x: -x[1])
    return scored[0][0] if scored else None


def _related_intents(intent_type: str) -> list[str]:
    """Get related intents for broader matching."""
    relations = {
        "rhythm": ["layer", "transform"],
        "texture": ["atmosphere", "transform"],
        "layer": ["melody", "rhythm"],
        "melody": ["layer", "vocal"],
        "vocal": ["melody", "texture"],
        "atmosphere": ["texture"],
        "transform": ["texture", "rhythm", "atmosphere"],
        "challenge": ["transform"],
    }
    return relations.get(intent_type, [])


def compile_sample_plan(
    profile: SampleProfile,
    intent: SampleIntent,
    target_track: Optional[int] = None,
    technique: Optional[SampleTechnique] = None,
) -> list[dict]:
    """Compile a concrete tool-call plan for sample manipulation.

    Returns list of {tool, params, description} dicts ready for execution.
    """
    if technique is None:
        technique = select_technique(profile, intent)
    if technique is None:
        return _fallback_plan(profile, intent, target_track)

    plan: list[dict] = []

    for step in technique.steps:
        compiled_step = {
            "tool": step.tool,
            "params": _resolve_params(step.params, profile, intent, target_track),
            "description": step.description,
        }
        if step.condition:
            if not _evaluate_condition(step.condition, profile, intent):
                continue
        plan.append(compiled_step)

    return plan


def _resolve_params(
    params: dict,
    profile: SampleProfile,
    intent: SampleIntent,
    target_track: Optional[int],
) -> dict:
    """Resolve template variables in technique step params."""
    resolved = dict(params)
    replacements = {
        "{file_path}": profile.file_path,
        "{track_index}": target_track if target_track is not None else 0,
        "{material_type}": profile.material_type,
        "{key}": profile.key or "",
        "{bpm}": profile.bpm or 120.0,
        "{name}": profile.name,
    }
    for k, v in resolved.items():
        if isinstance(v, str):
            for template, value in replacements.items():
                v = v.replace(template, str(value))
            resolved[k] = v
        elif v == "{track_index}":
            resolved[k] = replacements["{track_index}"]
        elif v == "{file_path}":
            resolved[k] = replacements["{file_path}"]
    return resolved


def _evaluate_condition(condition: str, profile: SampleProfile,
                        intent: SampleIntent) -> bool:
    """Evaluate a simple condition string."""
    if "material_type" in condition:
        for mt in ("vocal", "drum_loop", "instrument_loop", "one_shot",
                   "texture", "foley", "fx", "full_mix"):
            if f'material_type == "{mt}"' in condition:
                return profile.material_type == mt
    if "philosophy" in condition:
        for p in ("surgeon", "alchemist"):
            if f'philosophy == "{p}"' in condition:
                return intent.philosophy == p
    return True


def _fallback_plan(
    profile: SampleProfile,
    intent: SampleIntent,
    target_track: Optional[int],
) -> list[dict]:
    """Generic fallback when no technique matches."""
    track = target_track if target_track is not None else 0
    return [
        {"tool": "load_sample_to_simpler",
         "params": {"track_index": track, "file_path": profile.file_path},
         "description": f"Load {profile.name} into Simpler"},
        {"tool": "set_simpler_playback_mode",
         "params": {"track_index": track, "device_index": 0,
                     "playback_mode": 2 if profile.suggested_mode == "slice" else 0},
         "description": f"Set Simpler to {profile.suggested_mode} mode"},
    ]
