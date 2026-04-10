"""SongBrain builder — pure computation, zero I/O.

Constructs a SongBrain from project brain data, scene/clip analysis,
motif data, and session memory.  MCP tool wrappers call this with
pre-fetched data from Ableton.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Optional

from .models import (
    IdentityDrift,
    OpenQuestion,
    SacredElement,
    SectionPurpose,
    SongBrain,
)


# ── Main builder ──────────────────────────────────────────────────


def build_song_brain(
    session_info: dict,
    scenes: Optional[list[dict]] = None,
    tracks: Optional[list[dict]] = None,
    motif_data: Optional[dict] = None,
    composition_analysis: Optional[dict] = None,
    role_graph: Optional[dict] = None,
    recent_moves: Optional[list[dict]] = None,
    taste_graph: Optional[dict] = None,
) -> SongBrain:
    """Build a SongBrain from available session data.

    All inputs are optional — the builder degrades gracefully when
    data is missing, producing lower-confidence results.
    """
    scenes = scenes or []
    tracks = tracks or []
    motif_data = motif_data or {}
    composition_analysis = composition_analysis or {}
    role_graph = role_graph or {}
    recent_moves = recent_moves or []

    brain_id = _compute_brain_id(session_info, scenes)
    built_from: dict[str, bool] = {
        "session_info": True,
        "scenes": bool(scenes),
        "tracks": bool(tracks),
        "motif_data": bool(motif_data),
        "composition_analysis": bool(composition_analysis),
        "role_graph": bool(role_graph),
        "recent_moves": bool(recent_moves),
    }

    identity_core, identity_confidence = _infer_identity_core(
        tracks, motif_data, composition_analysis, role_graph
    )

    sacred = _detect_sacred_elements(
        tracks, motif_data, composition_analysis, role_graph
    )

    sections = _infer_section_purposes(scenes, composition_analysis)
    energy_arc = _build_energy_arc(scenes, sections)
    payoff_targets = [s.section_id for s in sections if s.is_payoff]
    open_questions = _detect_open_questions(
        sections, sacred, identity_core, tracks, composition_analysis
    )

    drift_risk = _estimate_drift_risk(recent_moves, sacred)

    return SongBrain(
        brain_id=brain_id,
        identity_core=identity_core,
        identity_confidence=identity_confidence,
        sacred_elements=sacred,
        section_purposes=sections,
        energy_arc=energy_arc,
        identity_drift_risk=drift_risk,
        payoff_targets=payoff_targets,
        open_questions=open_questions,
        built_from=built_from,
    )


# ── Identity core inference ───────────────────────────────────────


def _infer_identity_core(
    tracks: list[dict],
    motif_data: dict,
    composition: dict,
    role_graph: dict,
) -> tuple[str, float]:
    """Infer the single strongest defining idea in the session.

    Returns (description, confidence).
    """
    candidates: list[tuple[str, float]] = []

    # From motif data — most salient recurring motif
    motifs = motif_data.get("motifs", [])
    if motifs:
        top_motif = max(motifs, key=lambda m: m.get("salience", 0))
        salience = top_motif.get("salience", 0)
        if salience > 0.3:
            desc = top_motif.get("description", top_motif.get("name", "recurring motif"))
            candidates.append((f"Recurring motif: {desc}", min(0.9, salience)))

    # From composition — dominant emotional arc
    arc_type = composition.get("arc_type", "")
    if arc_type:
        candidates.append((f"Emotional arc: {arc_type}", 0.6))

    # From role graph — dominant texture
    roles = role_graph.get("roles", {})
    if roles:
        dominant = max(roles.items(), key=lambda kv: kv[1].get("weight", 0), default=None)
        if dominant:
            candidates.append((f"Dominant texture: {dominant[0]}", 0.5))

    # From track analysis — genre/style cues
    track_names = [t.get("name", "").lower() for t in tracks]
    genre_cues = _detect_genre_cues(track_names)
    if genre_cues:
        candidates.append((f"Style: {genre_cues}", 0.4))

    if not candidates:
        # Fallback: describe by track count and tempo
        return ("Emerging piece — identity not yet established", 0.2)

    best = max(candidates, key=lambda c: c[1])
    return best


def _detect_genre_cues(track_names: list[str]) -> str:
    """Simple genre/style detection from track naming patterns."""
    cue_map = {
        "808": "trap/hip-hop",
        "kick": "beat-driven",
        "pad": "atmospheric",
        "strings": "orchestral",
        "bass": "bass-forward",
        "vocal": "vocal-driven",
        "synth": "synth-based",
        "guitar": "guitar-based",
        "piano": "keys-driven",
        "ambient": "ambient",
        "drone": "drone/textural",
    }
    found = Counter()
    for name in track_names:
        for keyword, cue in cue_map.items():
            if keyword in name:
                found[cue] += 1

    if not found:
        return ""
    top = found.most_common(2)
    return ", ".join(c[0] for c in top)


# ── Sacred elements ───────────────────────────────────────────────


def _detect_sacred_elements(
    tracks: list[dict],
    motif_data: dict,
    composition: dict,
    role_graph: dict,
) -> list[SacredElement]:
    """Detect elements that should not be casually damaged.

    Conservative by default — prefer under-protecting nothing
    over over-editing the hook.
    """
    sacred: list[SacredElement] = []

    # High-salience motifs are sacred
    for motif in motif_data.get("motifs", []):
        if motif.get("salience", 0) > 0.5:
            sacred.append(SacredElement(
                element_type="motif",
                description=motif.get("description", motif.get("name", "motif")),
                location=motif.get("location", ""),
                salience=motif.get("salience", 0.6),
                confidence=0.7,
            ))

    # Lead/hook tracks from role graph
    for role_name, role_info in role_graph.get("roles", {}).items():
        if role_info.get("is_lead") or role_info.get("is_hook"):
            sacred.append(SacredElement(
                element_type="texture",
                description=f"{role_name} (lead/hook role)",
                location=role_info.get("track", ""),
                salience=0.7,
                confidence=0.6,
            ))

    # Primary groove (if clearly defined)
    groove_tracks = [
        t for t in tracks
        if any(kw in t.get("name", "").lower() for kw in ("drum", "beat", "kick", "hat", "perc"))
    ]
    if groove_tracks:
        sacred.append(SacredElement(
            element_type="groove",
            description="Primary rhythmic foundation",
            location=groove_tracks[0].get("name", "drums"),
            salience=0.6,
            confidence=0.5,
        ))

    return sacred


# ── Section purposes ──────────────────────────────────────────────


def _infer_section_purposes(
    scenes: list[dict],
    composition: dict,
) -> list[SectionPurpose]:
    """Infer what each section is trying to do emotionally."""
    sections: list[SectionPurpose] = []

    # From composition analysis if available
    comp_sections = composition.get("sections", [])
    if comp_sections:
        for sec in comp_sections:
            sections.append(SectionPurpose(
                section_id=sec.get("id", sec.get("name", "")),
                label=sec.get("label", sec.get("name", "")),
                emotional_intent=sec.get("intent", sec.get("purpose", "")),
                energy_level=sec.get("energy", 0.5),
                is_payoff=sec.get("is_payoff", False),
                confidence=0.7,
            ))
        return sections

    # Fallback: infer from scene names
    for i, scene in enumerate(scenes):
        name = scene.get("name", f"Scene {i}")
        label, intent, energy, is_payoff = _classify_scene_name(name, i, len(scenes))
        sections.append(SectionPurpose(
            section_id=f"scene_{i}",
            label=label,
            emotional_intent=intent,
            energy_level=energy,
            is_payoff=is_payoff,
            confidence=0.4,
        ))

    return sections


def _classify_scene_name(
    name: str, index: int, total: int
) -> tuple[str, str, float, bool]:
    """Classify a scene by its name into (label, intent, energy, is_payoff)."""
    name_lower = name.lower()

    patterns = {
        "intro": ("intro", "establish mood", 0.3, False),
        "verse": ("verse", "develop narrative", 0.5, False),
        "chorus": ("chorus", "deliver hook", 0.8, True),
        "drop": ("drop", "peak energy release", 0.9, True),
        "bridge": ("bridge", "contrast and transition", 0.5, False),
        "break": ("breakdown", "reduce and create anticipation", 0.3, False),
        "build": ("buildup", "create tension", 0.6, False),
        "outro": ("outro", "resolve and fade", 0.2, False),
        "hook": ("hook", "deliver memorable idea", 0.8, True),
    }

    for keyword, (label, intent, energy, payoff) in patterns.items():
        if keyword in name_lower:
            return label, intent, energy, payoff

    # Position-based fallback
    position = index / max(total - 1, 1)
    if position < 0.15:
        return "opening", "establish mood", 0.3, False
    elif position > 0.85:
        return "closing", "resolve", 0.3, False
    else:
        return "section", "develop", 0.5, False


# ── Energy arc ────────────────────────────────────────────────────


def _build_energy_arc(
    scenes: list[dict],
    sections: list[SectionPurpose],
) -> list[float]:
    """Build ordered energy levels across sections."""
    if sections:
        return [s.energy_level for s in sections]
    return [0.5] * len(scenes) if scenes else []


# ── Open questions ────────────────────────────────────────────────


def _detect_open_questions(
    sections: list[SectionPurpose],
    sacred: list[SacredElement],
    identity_core: str,
    tracks: list[dict],
    composition: dict,
) -> list[OpenQuestion]:
    """Detect unresolved creative questions about the song."""
    questions: list[OpenQuestion] = []

    # No clear identity
    if "not yet established" in identity_core.lower():
        questions.append(OpenQuestion(
            question="What is this track's defining idea?",
            domain="identity",
            priority=0.9,
        ))

    # No payoff sections
    payoffs = [s for s in sections if s.is_payoff]
    if sections and not payoffs:
        questions.append(OpenQuestion(
            question="No section is marked as a payoff/arrival — where does the song deliver?",
            domain="arrangement",
            priority=0.8,
        ))

    # Single section (loop, no form)
    if len(sections) <= 1 and len(tracks) > 2:
        questions.append(OpenQuestion(
            question="The track appears to be a single loop — is there intended form?",
            domain="arrangement",
            priority=0.7,
        ))

    # No sacred elements
    if not sacred:
        questions.append(OpenQuestion(
            question="No clearly sacred elements detected — what should be preserved?",
            domain="identity",
            priority=0.6,
        ))

    # Missing sections (common gaps)
    labels = {s.label for s in sections}
    if len(sections) > 3 and "intro" not in labels:
        questions.append(OpenQuestion(
            question="No intro section — does the track need an opening?",
            domain="arrangement",
            priority=0.4,
        ))

    return questions


# ── Drift estimation ──────────────────────────────────────────────


def _estimate_drift_risk(
    recent_moves: list[dict],
    sacred: list[SacredElement],
) -> float:
    """Estimate how much recent edits are moving the song away from itself."""
    if not recent_moves:
        return 0.0

    sacred_locations = {e.location.lower() for e in sacred if e.location}
    drift_signals = 0
    total_moves = len(recent_moves)

    for move in recent_moves:
        targets = move.get("targets", [])
        if isinstance(targets, str):
            targets = [targets]
        for target in targets:
            if target.lower() in sacred_locations:
                drift_signals += 1

    if total_moves == 0:
        return 0.0
    return min(1.0, drift_signals / max(total_moves, 1) * 2)


# ── Identity drift detection ─────────────────────────────────────


def detect_identity_drift(
    before: SongBrain,
    after: SongBrain,
) -> IdentityDrift:
    """Compare two SongBrain snapshots to detect identity drift."""
    drift = IdentityDrift()

    # Identity core change
    if before.identity_core != after.identity_core:
        drift.changed_elements.append("identity_core")
        drift.drift_score += 0.3

    # Sacred element damage
    before_sacred = {e.description for e in before.sacred_elements}
    after_sacred = {e.description for e in after.sacred_elements}
    lost = before_sacred - after_sacred
    if lost:
        drift.sacred_damage = list(lost)
        drift.drift_score += 0.2 * len(lost)

    # Energy arc shift
    if before.energy_arc and after.energy_arc:
        min_len = min(len(before.energy_arc), len(after.energy_arc))
        if min_len > 0:
            diff = sum(
                abs(before.energy_arc[i] - after.energy_arc[i])
                for i in range(min_len)
            ) / min_len
            drift.energy_arc_shift = round(diff, 3)
            drift.drift_score += diff * 0.2

    drift.drift_score = min(1.0, round(drift.drift_score, 3))

    # Recommendation
    if drift.drift_score < 0.15:
        drift.recommendation = "safe"
    elif drift.drift_score < 0.4:
        drift.recommendation = "caution"
    else:
        drift.recommendation = "rollback_suggested"

    return drift


# ── Helpers ───────────────────────────────────────────────────────


def _compute_brain_id(session_info: dict, scenes: list[dict]) -> str:
    """Deterministic brain ID from session state."""
    seed = json.dumps({
        "tempo": session_info.get("tempo"),
        "track_count": session_info.get("track_count"),
        "scene_count": len(scenes),
    }, sort_keys=True)
    return hashlib.sha256(seed.encode()).hexdigest()[:12]
