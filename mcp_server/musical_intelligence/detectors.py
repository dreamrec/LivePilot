"""Musical intelligence detectors — pure computation, no I/O.

Each detector takes session data dicts and returns structured findings.
These feed into arrangement, transition, and diagnostic workflows.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Optional


# ═══════════════════════════════════════════════════════════════════════
# Repetition Fatigue
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class FatigueReport:
    """Report on repetition fatigue across the arrangement."""
    fatigue_level: float = 0.0  # 0 = fresh, 1 = extremely fatigued
    issues: list[dict] = field(default_factory=list)
    section_staleness: dict[str, float] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "fatigue_level": round(self.fatigue_level, 3),
            "issue_count": len(self.issues),
            "issues": self.issues,
            "section_staleness": self.section_staleness,
            "recommendations": self.recommendations,
        }


def detect_repetition_fatigue(
    scenes: list[dict],
    motif_graph: Optional[dict] = None,
) -> FatigueReport:
    """Detect repetition fatigue from scene/clip data.

    Analyzes:
    - How many scenes share the same clips (pattern reuse)
    - Motif overuse from motif_graph if available
    - Density stability (everything at same level = fatiguing)

    scenes: list of scene dicts with clip names per track
    motif_graph: optional output from get_motif_graph
    """
    report = FatigueReport()

    if not scenes:
        return report

    # 1. Clip reuse across scenes
    clip_usage = Counter()
    for scene in scenes:
        clips = scene.get("clips", [])
        if isinstance(clips, list):
            for clip in clips:
                name = clip.get("name", "") if isinstance(clip, dict) else str(clip)
                if name:
                    clip_usage[name] += 1

    overused = {name: count for name, count in clip_usage.items() if count >= 3}
    if overused:
        report.issues.append({
            "type": "clip_overuse",
            "severity": min(0.8, len(overused) * 0.15),
            "detail": f"{len(overused)} clip(s) used 3+ times",
            "clips": dict(overused),
        })

    # 2. Scene similarity (how many scenes have identical clip sets)
    scene_fingerprints = []
    for scene in scenes:
        clips = scene.get("clips", [])
        names = sorted(
            (c.get("name", "") if isinstance(c, dict) else str(c))
            for c in (clips if isinstance(clips, list) else [])
            if (c.get("name", "") if isinstance(c, dict) else str(c))
        )
        scene_fingerprints.append(tuple(names))

    duplicate_scenes = sum(
        1 for i, fp in enumerate(scene_fingerprints)
        if fp and scene_fingerprints.index(fp) != i
    )
    if duplicate_scenes > 0:
        report.issues.append({
            "type": "duplicate_scenes",
            "severity": min(0.7, duplicate_scenes * 0.2),
            "detail": f"{duplicate_scenes} scene(s) are identical to earlier ones",
        })

    # 3. Motif fatigue from motif_graph
    if motif_graph:
        motifs = motif_graph.get("motifs", [])
        num_sections = max(1, len(scenes))
        for motif in motifs:
            fatigue_risk = motif.get("fatigue_risk", 0)
            recurrence = motif.get("recurrence", 0)

            # Motif appearing in >60% of sections = fatigue signal
            if recurrence > 0.6 and num_sections >= 3:
                adjusted_fatigue = max(fatigue_risk, recurrence * 0.8)
                report.issues.append({
                    "type": "motif_overuse",
                    "severity": round(adjusted_fatigue, 3),
                    "detail": f"Motif {motif.get('name', motif.get('motif_id', '?'))} appears in {recurrence:.0%} of sections",
                    "motif_id": motif.get("motif_id", motif.get("name", "")),
                    "evidence": "motif_recurrence",
                })
            elif fatigue_risk > 0.6:
                report.issues.append({
                    "type": "motif_overuse",
                    "severity": fatigue_risk,
                    "detail": f"Motif {motif.get('motif_id', '?')} fatigue risk {fatigue_risk:.2f}",
                    "motif_id": motif.get("motif_id"),
                })

    # 4. Section staleness (per named scene)
    for i, scene in enumerate(scenes):
        name = scene.get("name", f"Scene {i}")
        if not name:
            continue
        clips = scene.get("clips", [])
        clip_names = [
            (c.get("name", "") if isinstance(c, dict) else "")
            for c in (clips if isinstance(clips, list) else [])
        ]
        reuse_count = sum(clip_usage.get(n, 0) for n in clip_names if n)
        total = max(1, len([n for n in clip_names if n]))
        staleness = min(1.0, (reuse_count / total - 1) * 0.3) if total else 0
        report.section_staleness[name] = round(max(0, staleness), 3)

    # Overall fatigue level
    if report.issues:
        report.fatigue_level = min(1.0, sum(i["severity"] for i in report.issues) / max(1, len(report.issues)))

    # Recommendations
    if report.fatigue_level > 0.5:
        report.recommendations.append("Add variation clips to overused patterns")
        report.recommendations.append("Use transform_motif (inversion, retrograde) to refresh stale melodic ideas")
    if duplicate_scenes > 1:
        report.recommendations.append("Create unique clip variations for duplicate scenes")
    if report.fatigue_level > 0.3:
        report.recommendations.append("Add perlin automation for organic movement within loops")

    return report


# ═══════════════════════════════════════════════════════════════════════
# Role Conflict Detection
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class RoleConflict:
    """A detected conflict where multiple tracks compete for the same musical role."""
    role: str
    tracks: list[dict]  # [{index, name}]
    severity: float = 0.0
    recommendation: str = ""

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "tracks": self.tracks,
            "severity": round(self.severity, 3),
            "recommendation": self.recommendation,
        }


def detect_role_conflicts(
    tracks: list[dict],
    role_fn=None,
) -> list[RoleConflict]:
    """Detect tracks competing for the same musical role.

    Roles that should be unique: sub_anchor (only 1 bass), foreground (only 1 lead),
    transient_anchor (only 1 main drum track).

    tracks: list of track dicts with at least 'name' and 'index'
    role_fn: optional function(track_name) -> role_str
    """
    if role_fn is None:
        from ..semantic_moves.resolvers import infer_role
        role_fn = infer_role

    # Group tracks by role
    role_groups: dict[str, list[dict]] = defaultdict(list)
    for track in tracks:
        name = track.get("name", "")
        role = role_fn(name)
        if role != "unknown":
            role_groups[role].append({
                "index": track.get("index", 0),
                "name": name,
            })

    # Roles that should be unique (1 track only)
    UNIQUE_ROLES = {
        "bass": ("Sub/bass conflict — multiple bass tracks compete for the low end",
                 "Consider merging bass parts or using EQ to give each a distinct range"),
        "lead": ("Lead conflict — multiple foreground melodies compete for attention",
                 "Mute one lead or use arrangement to alternate them across sections"),
        "drums": ("Drum conflict — multiple drum tracks may mask each other's transients",
                  "Layer drum parts into one Drum Rack or pan them apart"),
    }

    conflicts = []
    for role, (desc, rec) in UNIQUE_ROLES.items():
        group = role_groups.get(role, [])
        if len(group) > 1:
            severity = min(0.9, 0.3 + (len(group) - 1) * 0.2)
            conflicts.append(RoleConflict(
                role=role,
                tracks=group,
                severity=severity,
                recommendation=rec,
            ))

    # Check for missing essential roles
    essential = {"bass", "drums"}
    for role in essential:
        if role not in role_groups:
            conflicts.append(RoleConflict(
                role=role,
                tracks=[],
                severity=0.3,
                recommendation=f"No {role} track detected — the mix may lack foundation",
            ))

    return conflicts


# ═══════════════════════════════════════════════════════════════════════
# Section Purpose Inference
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class SectionPurpose:
    """Inferred musical purpose of a section/scene."""
    name: str
    purpose: str  # setup | tension | payoff | contrast | release | outro | unknown
    energy: float = 0.0  # 0-1
    density: float = 0.0  # 0-1 (how many tracks are active)
    confidence: float = 0.5

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "purpose": self.purpose,
            "energy": round(self.energy, 3),
            "density": round(self.density, 3),
            "confidence": round(self.confidence, 3),
        }


def infer_section_purposes(
    scenes: list[dict],
    total_tracks: int = 6,
) -> list[SectionPurpose]:
    """Infer the musical purpose of each scene based on density and position.

    Uses heuristics:
    - Low density at start → setup/intro
    - Increasing density → tension/build
    - Maximum density → payoff/drop
    - Sudden density drop → contrast/breakdown
    - Low density at end → release/outro
    - Decreasing density → outro/dissolve

    scenes: list of scene dicts with name and clip count
    total_tracks: total track count for density calculation
    """
    if not scenes:
        return []

    # Calculate density for each scene
    densities = []
    for scene in scenes:
        clips = scene.get("clips", [])
        if isinstance(clips, list):
            active = sum(1 for c in clips
                        if isinstance(c, dict) and c.get("state") not in ("empty", None))
        else:
            active = 0
        density = active / max(1, total_tracks)
        densities.append(density)

    results = []
    n = len(scenes)

    for i, scene in enumerate(scenes):
        name = scene.get("name", f"Scene {i}")
        density = densities[i]
        position = i / max(1, n - 1)  # 0 = first, 1 = last

        # Density change from previous
        prev_density = densities[i - 1] if i > 0 else 0
        density_delta = density - prev_density

        # Infer purpose
        if position < 0.15 and density < 0.5:
            purpose = "setup"
            confidence = 0.7
        elif density_delta > 0.2:
            purpose = "tension"
            confidence = 0.6
        elif density >= 0.8:
            purpose = "payoff"
            confidence = 0.65
        elif density_delta < -0.3:
            purpose = "contrast"
            confidence = 0.6
        elif position > 0.8 and density < 0.5:
            purpose = "release"
            confidence = 0.65
        elif position > 0.85 and density_delta < 0:
            purpose = "outro"
            confidence = 0.6
        else:
            purpose = "development"
            confidence = 0.4

        results.append(SectionPurpose(
            name=name,
            purpose=purpose,
            energy=density,
            density=density,
            confidence=confidence,
        ))

    return results


# ═══════════════════════════════════════════════════════════════════════
# Emotional Arc Scoring
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class ArcScore:
    """Score for the overall emotional arc of the arrangement."""
    arc_clarity: float = 0.0     # How clear is the build → climax → resolve?
    contrast: float = 0.0        # How different are sections from each other?
    payoff_strength: float = 0.0  # Does the climax feel earned?
    resolution: float = 0.0      # Does the ending resolve tension?
    issues: list[str] = field(default_factory=list)

    @property
    def overall(self) -> float:
        return round(
            (self.arc_clarity + self.contrast + self.payoff_strength + self.resolution) / 4, 3
        )

    def to_dict(self) -> dict:
        return {
            "overall": self.overall,
            "arc_clarity": round(self.arc_clarity, 3),
            "contrast": round(self.contrast, 3),
            "payoff_strength": round(self.payoff_strength, 3),
            "resolution": round(self.resolution, 3),
            "issues": self.issues,
        }


def score_emotional_arc(sections: list[SectionPurpose]) -> ArcScore:
    """Score the emotional arc from inferred section purposes.

    Checks for:
    - Build before payoff (tension should precede climax)
    - Variety of purposes (not all the same energy level)
    - Resolution at the end (shouldn't end at peak tension)
    - Clear climax point (should have at least one payoff section)
    """
    score = ArcScore()

    if not sections:
        score.issues.append("No sections to analyze")
        return score

    purposes = [s.purpose for s in sections]
    energies = [s.energy for s in sections]

    # Arc clarity: do we have a clear build → peak → resolve shape?
    has_setup = "setup" in purposes
    has_tension = "tension" in purposes
    has_payoff = "payoff" in purposes
    has_release = "release" in purposes or "outro" in purposes

    clarity_points = sum([has_setup, has_tension, has_payoff, has_release])
    score.arc_clarity = clarity_points / 4

    if not has_payoff:
        score.issues.append("No clear climax/payoff section")
    if not has_setup and not has_tension:
        score.issues.append("No build — payoff arrives without anticipation")

    # Contrast: how different are sections?
    if len(energies) >= 2:
        energy_range = max(energies) - min(energies)
        score.contrast = min(1.0, energy_range * 1.5)
        if energy_range < 0.2:
            score.issues.append("Low contrast — sections are too similar in energy")
    else:
        score.contrast = 0.0

    # Payoff strength: does tension precede the peak?
    if has_payoff:
        payoff_idx = purposes.index("payoff")
        if payoff_idx > 0 and sections[payoff_idx - 1].energy < sections[payoff_idx].energy:
            score.payoff_strength = 0.8
        else:
            score.payoff_strength = 0.4
            score.issues.append("Payoff doesn't feel earned — no energy build before it")
    else:
        score.payoff_strength = 0.0

    # Resolution: does energy decrease at the end?
    if len(energies) >= 3:
        final_energy = energies[-1]
        peak_energy = max(energies)
        if final_energy < peak_energy * 0.7:
            score.resolution = 0.8
        elif final_energy < peak_energy:
            score.resolution = 0.5
        else:
            score.resolution = 0.2
            score.issues.append("No resolution — ending at or near peak energy")
    else:
        score.resolution = 0.3

    return score
