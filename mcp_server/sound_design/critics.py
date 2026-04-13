"""Sound Design Engine critics — detect timbral issues from state data.

Five critics: static_timbre, weak_identity, masking_role,
modulation_flatness, layer_overlap.
All pure computation, zero I/O.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .models import (
    LayerStrategy,
    PatchModel,
    SoundDesignState,
    TimbralGoalVector,
)


# ── SoundDesignIssue ─────────────────────────────────────────────────


@dataclass
class SoundDesignIssue:
    """A single detected sound-design issue."""

    issue_type: str = ""
    critic: str = ""
    severity: float = 0.0
    confidence: float = 0.0
    affected_blocks: list[str] = field(default_factory=list)
    evidence: str = ""
    recommended_moves: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ── Static Timbre Critic ─────────────────────────────────────────────


def run_static_timbre_critic(
    patch: PatchModel,
    goal: TimbralGoalVector,
) -> list[SoundDesignIssue]:
    """Detect static timbre: no modulation sources, flat/lifeless sound.

    Fires when the goal asks for movement or instability but the patch
    has no LFOs and no non-default envelopes (only oscillators/filters/effects).
    """
    issues: list[SoundDesignIssue] = []

    has_lfo = any(b.block_type == "lfo" for b in patch.blocks)
    has_envelope = any(b.block_type == "envelope" for b in patch.blocks)
    has_modulation = has_lfo or has_envelope

    # If goal wants movement or instability but patch is static
    wants_movement = goal.movement > 0.1 or goal.instability > 0.1
    if wants_movement and not has_modulation and len(patch.blocks) > 0:
        severity = min(1.0, (abs(goal.movement) + abs(goal.instability)) / 2.0)
        issues.append(SoundDesignIssue(
            issue_type="static_timbre",
            critic="static_timbre",
            severity=round(severity, 3),
            confidence=0.8,
            affected_blocks=[b.device_name for b in patch.blocks],
            evidence=(
                f"Goal wants movement={goal.movement:.2f}, "
                f"instability={goal.instability:.2f} but patch has "
                f"no LFOs or modulation envelopes"
            ),
            recommended_moves=["modulation_injection"],
        ))

    # Even without explicit goal, a patch with zero modulation is flat
    if not has_modulation and not wants_movement and len(patch.blocks) > 0:
        issues.append(SoundDesignIssue(
            issue_type="no_modulation_sources",
            critic="static_timbre",
            severity=0.3,
            confidence=0.5,
            affected_blocks=[b.device_name for b in patch.blocks],
            evidence=(
                f"Patch has {len(patch.blocks)} blocks but no LFOs "
                f"or modulation envelopes — timbre will be static"
            ),
            recommended_moves=["modulation_injection"],
        ))

    return issues


# ── Weak Identity Critic ─────────────────────────────────────────────


def run_weak_identity_critic(
    patch: PatchModel,
) -> list[SoundDesignIssue]:
    """Detect weak patch identity: too few distinct blocks, generic chain.

    A patch with only one or two blocks (e.g. just an oscillator + effect)
    lacks timbral character.  Also flags chains with no filter or saturation,
    which tend to sound generic.
    """
    issues: list[SoundDesignIssue] = []

    controllable_blocks = [b for b in patch.blocks if b.controllable]
    block_types = {b.block_type for b in controllable_blocks}

    # Too few blocks for timbral identity
    if len(controllable_blocks) < 2 and len(patch.device_chain) > 0:
        issues.append(SoundDesignIssue(
            issue_type="too_few_blocks",
            critic="weak_identity",
            severity=0.5,
            confidence=0.6,
            affected_blocks=[b.device_name for b in controllable_blocks],
            evidence=(
                f"Only {len(controllable_blocks)} controllable block(s) — "
                f"patch lacks timbral sculpting potential"
            ),
            recommended_moves=["filter_contour", "source_balance"],
        ))

    # Generic chain: no filter or saturation for character
    if len(controllable_blocks) >= 2:
        has_character = "filter" in block_types or "saturation" in block_types
        if not has_character:
            issues.append(SoundDesignIssue(
                issue_type="generic_chain",
                critic="weak_identity",
                severity=0.4,
                confidence=0.5,
                affected_blocks=[b.device_name for b in controllable_blocks],
                evidence=(
                    f"Block types {sorted(block_types)} lack filter or "
                    f"saturation — chain will sound generic"
                ),
                recommended_moves=["filter_contour"],
            ))

    return issues


# ── Masking Role Critic ──────────────────────────────────────────────


def run_masking_role_critic(
    patch: PatchModel,
    layers: LayerStrategy,
) -> list[SoundDesignIssue]:
    """Detect layers overlapping in frequency role.

    Flags when the same track is assigned as both sub_anchor and
    body_layer (or other frequency-adjacent roles), or when a track's
    roles suggest it covers too wide a frequency range.
    """
    issues: list[SoundDesignIssue] = []

    # Frequency-adjacent role pairs that risk masking
    adjacent_pairs = [
        ("sub_anchor", "body_layer"),
        ("body_layer", "transient_layer"),
        ("texture_layer", "width_layer"),
    ]

    ti = patch.track_index
    assigned_roles = []
    if layers.sub_anchor == ti:
        assigned_roles.append("sub_anchor")
    if layers.body_layer == ti:
        assigned_roles.append("body_layer")
    if layers.transient_layer == ti:
        assigned_roles.append("transient_layer")
    if layers.texture_layer == ti:
        assigned_roles.append("texture_layer")
    if layers.width_layer == ti:
        assigned_roles.append("width_layer")

    for role_a, role_b in adjacent_pairs:
        if role_a in assigned_roles and role_b in assigned_roles:
            issues.append(SoundDesignIssue(
                issue_type="frequency_role_overlap",
                critic="masking_role",
                severity=0.6,
                confidence=0.7,
                affected_blocks=[],
                evidence=(
                    f"Track {ti} assigned both '{role_a}' and '{role_b}' — "
                    f"these frequency-adjacent roles risk masking each other"
                ),
                recommended_moves=["layer_split", "source_balance"],
            ))

    return issues


# ── Modulation Flatness Critic ───────────────────────────────────────


def run_modulation_flatness_critic(
    patch: PatchModel,
) -> list[SoundDesignIssue]:
    """Detect modulation flatness: no LFOs, no envelopes beyond default.

    Fires when a patch with 3+ blocks has zero dedicated modulation
    sources — the patch will sound lifeless over time.
    """
    issues: list[SoundDesignIssue] = []

    lfo_count = sum(1 for b in patch.blocks if b.block_type == "lfo")
    envelope_count = sum(1 for b in patch.blocks if b.block_type == "envelope")
    total_blocks = len(patch.blocks)

    if total_blocks >= 3 and lfo_count == 0 and envelope_count == 0:
        issues.append(SoundDesignIssue(
            issue_type="no_modulation",
            critic="modulation_flatness",
            severity=0.5,
            confidence=0.7,
            affected_blocks=[b.device_name for b in patch.blocks],
            evidence=(
                f"Patch has {total_blocks} blocks but zero LFOs and "
                f"zero modulation envelopes — sound will be static"
            ),
            recommended_moves=["modulation_injection", "envelope_shape"],
        ))

    if total_blocks >= 3 and lfo_count == 0 and envelope_count > 0:
        issues.append(SoundDesignIssue(
            issue_type="no_lfo_movement",
            critic="modulation_flatness",
            severity=0.3,
            confidence=0.6,
            affected_blocks=[b.device_name for b in patch.blocks if b.block_type != "envelope"],
            evidence=(
                f"Patch has envelopes but no LFOs — "
                f"sustained notes will lack timbral movement"
            ),
            recommended_moves=["modulation_injection"],
        ))

    return issues


# ── Layer Overlap Critic ─────────────────────────────────────────────


def run_layer_overlap_critic(
    layers: LayerStrategy,
) -> list[SoundDesignIssue]:
    """Detect when the same track serves multiple layer roles.

    A single track trying to be both sub anchor and texture layer,
    for example, will have conflicting EQ/processing needs.
    """
    issues: list[SoundDesignIssue] = []

    role_map: dict[int, list[str]] = {}
    for role_name in ("sub_anchor", "body_layer", "transient_layer",
                      "texture_layer", "width_layer"):
        track_idx = getattr(layers, role_name)
        if track_idx is not None:
            role_map.setdefault(track_idx, []).append(role_name)

    for track_idx, roles in role_map.items():
        if len(roles) > 1:
            issues.append(SoundDesignIssue(
                issue_type="multi_role_track",
                critic="layer_overlap",
                severity=min(1.0, 0.3 * len(roles)),
                confidence=0.7,
                affected_blocks=[],
                evidence=(
                    f"Track {track_idx} serves {len(roles)} layer roles: "
                    f"{roles} — conflicting processing needs"
                ),
                recommended_moves=["layer_split"],
            ))

    return issues


# ── Corpus Intelligence Critic ──────────────────────────────────────


def run_corpus_critic(
    patch: PatchModel,
    goal: TimbralGoalVector,
) -> list[SoundDesignIssue]:
    """Use the device-knowledge corpus to flag missed opportunities.

    Checks each device in the chain against the corpus for known
    techniques, parameter sweet spots, and creative possibilities
    that the current patch doesn't exploit.
    """
    try:
        from ..corpus import get_corpus
    except ImportError:
        return []

    corpus = get_corpus()
    if not corpus.emotional_recipes and not corpus.device_knowledge:
        return []  # Corpus not loaded

    issues: list[SoundDesignIssue] = []

    # Check if any device in the chain has corpus knowledge
    for block in patch.blocks:
        dk = corpus.get_device(block.device_name)
        if dk and dk.techniques and block.block_type == "oscillator":
            # Oscillator with known techniques — suggest if patch is simple
            has_character_block = any(
                b.block_type in ("saturation", "spectral")
                for b in patch.blocks
            )
            if not has_character_block and len(dk.techniques) > 2:
                issues.append(SoundDesignIssue(
                    issue_type="corpus_technique_available",
                    critic="corpus",
                    severity=0.25,
                    confidence=0.6,
                    affected_blocks=[block.device_name],
                    evidence=(
                        f"Corpus has {len(dk.techniques)} known techniques "
                        f"for {block.device_name} but chain lacks character "
                        f"processing (saturation/spectral). First technique: "
                        f"{dk.techniques[0][:80]}"
                    ),
                    recommended_moves=["modulation_injection", "filter_contour"],
                ))

    # Check if goal maps to a known emotional recipe
    emotion_map = {
        "warmth": ("warmth", goal.warmth),
        "brightness": ("euphoria", goal.brightness),
        "instability": ("tension", goal.instability),
        "softness": ("melancholy", goal.softness),
    }
    for quality, (emotion_key, goal_value) in emotion_map.items():
        if goal_value > 0.3:
            recipe = corpus.suggest_for_emotion(emotion_key)
            if recipe and recipe.techniques:
                # Check if any corpus technique device is in the chain
                chain_names_lower = {d.lower() for d in patch.device_chain}
                recipe_devices = set()
                for tech in recipe.techniques:
                    # Extract bold device names from technique strings
                    for match in re.finditer(r"\*\*(.+?)\*\*", tech):
                        recipe_devices.add(match.group(1).lower())

                missing = recipe_devices - chain_names_lower
                if missing and len(missing) <= 3:
                    issues.append(SoundDesignIssue(
                        issue_type="corpus_emotion_opportunity",
                        critic="corpus",
                        severity=0.2,
                        confidence=0.5,
                        affected_blocks=list(missing)[:3],
                        evidence=(
                            f"Goal wants {quality}={goal_value:.2f}. "
                            f"Corpus '{recipe.emotion}' recipe suggests "
                            f"devices not in chain: {', '.join(list(missing)[:3])}"
                        ),
                        recommended_moves=["filter_contour", "modulation_injection"],
                    ))

    return issues


# ── Run all critics ──────────────────────────────────────────────────


def run_all_sound_design_critics(
    state: SoundDesignState,
) -> list[SoundDesignIssue]:
    """Run all six critics and aggregate issues."""
    issues: list[SoundDesignIssue] = []
    issues.extend(run_static_timbre_critic(state.patch, state.goal))
    issues.extend(run_weak_identity_critic(state.patch))
    issues.extend(run_masking_role_critic(state.patch, state.layers))
    issues.extend(run_modulation_flatness_critic(state.patch))
    issues.extend(run_layer_overlap_critic(state.layers))
    issues.extend(run_corpus_critic(state.patch, state.goal))
    return issues
