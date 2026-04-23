"""Wonder Mode engine — pure computation, zero I/O.

Generates contextually different creative variants ranked by
taste, identity, and coherence. Each variant is built from a
real semantic move matched to the request.

PR6 adds a branch-native assembly path (generate_branch_seeds) that emits
BranchSeed objects from multiple producers — semantic_move, technique
memory, sacred-element inversion, and corpus-hint freeform seeds. The
existing generate_wonder_variants path is untouched; callers that speak
BranchSeed can consume the new function, callers that speak "variants"
keep the old one.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
from typing import Optional

from ..branches import BranchSeed, seed_from_move_id, freeform_seed

logger = logging.getLogger(__name__)


# ── Move discovery ───────────────────────────────────────────────


def discover_moves(
    request_text: str,
    taste_graph: object = None,
    active_constraints: object = None,
    candidate_domains: list[str] | None = None,
) -> list[dict]:
    """Find semantic moves relevant to the request.

    Uses keyword scoring + optional taste reranking + constraint filtering.
    Returns full move dicts including plan_template (via registry.get_move).
    """
    from ..semantic_moves import registry

    all_moves = registry.list_moves()  # returns to_dict() — no plan_template
    if not all_moves:
        return []

    request_lower = request_text.lower()
    request_words = set(request_lower.split())

    scored: list[tuple[dict, float]] = []
    for move in all_moves:
        score = 0.0
        move_words = set(move["move_id"].replace("_", " ").split())
        intent_words = set(move.get("intent", "").lower().split())
        overlap = request_words & (move_words | intent_words)
        score += len(overlap) * 0.3

        for dim in move.get("targets", {}):
            if dim in request_lower:
                score += 0.2

        if score > 0.1:
            scored.append((move, score))

    if not scored:
        return []

    # Domain filtering if provided (fall back to full list if filtering removes all)
    if candidate_domains:
        domain_filtered = [(m, s) for m, s in scored if m.get("family") in candidate_domains]
        if domain_filtered:
            scored = domain_filtered

    # Taste-based reranking if available
    if (
        taste_graph is not None
        and hasattr(taste_graph, "rank_moves")
        and hasattr(taste_graph, "evidence_count")
        and taste_graph.evidence_count > 0
    ):
        move_dicts = [m for m, _ in scored]
        ranked = taste_graph.rank_moves(move_dicts)
        taste_by_id = {m["move_id"]: m.get("taste_score", 0.5) for m in ranked}
        scored = [
            (m, kw_score * 0.6 + taste_by_id.get(m["move_id"], 0.5) * 0.4)
            for m, kw_score in scored
        ]

    scored.sort(key=lambda x: -x[1])

    # Enrich with full plan_template via get_move()
    result = []
    for move_dict, score in scored:
        full_move = registry.get_move(move_dict["move_id"])
        if full_move:
            enriched = full_move.to_full_dict()
            enriched["relevance_score"] = round(score, 3)
            result.append(enriched)

    # Filter by active constraints if any
    if (
        active_constraints is not None
        and hasattr(active_constraints, "constraints")
        and active_constraints.constraints
    ):
        try:
            from ..creative_constraints.engine import validate_plan_against_constraints
            filtered = []
            for move in result:
                plan = {"steps": [
                    {"action": step.get("tool", ""), **step}
                    for step in (move.get("plan_template") or [])
                ]}
                validation = validate_plan_against_constraints(plan, active_constraints)
                if validation["valid"]:
                    filtered.append(move)
            result = filtered
        except Exception as exc:
            # constraint filtering is optional — keep the unfiltered list
            logger.warning("constraint filtering skipped: %s", exc)

    return result


# ── Tier assignment ──────────────────────────────────────────────

_RISK_NUMERIC = {"low": 0.2, "medium": 0.5, "high": 0.8}



def _with_envelope(move: dict, tier: str) -> dict:
    """Apply novelty envelope to a move's targets and protect."""
    result = dict(move)
    targets = dict(move.get("targets", {}))
    protect = dict(move.get("protect", {}))

    if tier == "safe":
        targets = {k: round(v * 0.7, 3) for k, v in targets.items()}
    elif tier == "unexpected":
        targets = {k: round(v * 1.4, 3) for k, v in targets.items()}
        protect = {k: round(v * 0.8, 3) for k, v in protect.items()}
    # "strong" keeps targets and protect as-is

    result["targets"] = targets
    result["protect"] = protect
    return result


# ── Distinctness selection ───────────────────────────────────────


def _plan_template_shape(move: dict) -> frozenset[str]:
    """Extract the set of tool names from a move's plan_template."""
    plan = move.get("plan_template") or []
    return frozenset(step.get("tool", "") for step in plan if step.get("tool"))


def select_distinct_variants(scored_moves: list[dict]) -> list[dict]:
    """Select genuinely distinct moves for variant generation.

    Each selected move must differ from all previously selected moves by
    at least one of: move_id, family, or plan_template shape.
    Returns 0-3 moves.
    """
    if not scored_moves:
        return []

    selected: list[dict] = []
    used_ids: set[str] = set()
    used_shapes: list[tuple[str, frozenset]] = []  # (family, shape) pairs

    for move in scored_moves:
        mid = move.get("move_id", "")
        family = move.get("family", "")
        shape = _plan_template_shape(move)

        # Skip duplicate move_ids
        if mid in used_ids:
            continue

        # Check distinctness against already-selected moves
        is_distinct = True
        for sel_family, sel_shape in used_shapes:
            if family == sel_family and shape == sel_shape:
                is_distinct = False
                break

        if is_distinct:
            selected.append(move)
            used_ids.add(mid)
            used_shapes.append((family, shape))

        if len(selected) >= 3:
            break

    return selected


# ── Variant building ─────────────────────────────────────────────

_NOVELTY_LEVELS = {"safe": 0.25, "strong": 0.55, "unexpected": 0.85}
_RISK_TO_EFFECT = {"low": "preserves", "medium": "evolves", "high": "contrasts"}


def _compile_variant_plan(move_dict: dict, kernel: dict | None) -> dict | None:
    """Compile a move through the semantic compiler if possible.

    Returns CompiledPlan.to_dict() or None if no compiler is registered.
    """
    if kernel is None:
        return None

    move_id = move_dict.get("move_id", "")
    from ..semantic_moves.compiler import compile as sem_compile, _COMPILERS
    from ..semantic_moves import registry

    if move_id not in _COMPILERS:
        return None

    move_obj = registry.get_move(move_id)
    if move_obj is None:
        return None

    try:
        plan = sem_compile(move_obj, kernel)
        return plan.to_dict()
    except Exception as exc:
        logger.warning("sem_compile(%s) failed: %s", move_obj, exc)
        return None


def build_variant(
    label: str,
    move_dict: dict,
    song_brain: Optional[dict] = None,
    novelty_level: float = 0.5,
    variant_id: str = "",
    kernel: dict | None = None,
) -> dict:
    """Build a variant dict from a real move + SongBrain context.

    If kernel is provided, compiles the move through the semantic compiler
    for an executable plan. Otherwise falls back to plan_template metadata.
    """
    song_brain = song_brain or {}
    targets = move_dict.get("targets", {})
    protect = move_dict.get("protect", {})
    risk = move_dict.get("risk_level", "low")
    sacred = song_brain.get("sacred_elements", [])

    # what_changed from targets
    target_parts = [f"{dim} ({val:+.1f})" for dim, val in targets.items()]
    what_changed = f"Targets {', '.join(target_parts)}" if target_parts else "Analytical suggestion"

    # what_preserved from protect + sacred
    preserved_parts = []
    if protect:
        preserved_parts.extend(f"{dim} (threshold {thresh})" for dim, thresh in protect.items())
    if sacred:
        sacred_descs = [e.get("description", e.get("element_type", "element")) for e in sacred[:3]]
        preserved_parts.append(f"Sacred: {', '.join(sacred_descs)}")
    what_preserved = " | ".join(preserved_parts) if preserved_parts else "core elements"

    # identity_effect from risk
    identity_effect = _RISK_TO_EFFECT.get(risk, "preserves")

    # why_it_matters
    risk_label = {"low": "Low", "medium": "Moderate", "high": "High"}.get(risk, "Unknown")
    why = f"{risk_label} risk — {move_dict.get('intent', 'creative suggestion')}"
    if sacred and identity_effect == "preserves":
        why += f". Preserves {sacred[0].get('description', 'sacred elements')}"

    # Compile through semantic compiler if kernel available
    compiled = _compile_variant_plan(move_dict, kernel)
    analytical = compiled is None

    return {
        "variant_id": variant_id,
        "label": label,
        "move_id": move_dict.get("move_id", ""),
        "family": move_dict.get("family", ""),
        "intent": move_dict.get("intent", ""),
        "what_changed": what_changed,
        "what_preserved": what_preserved,
        "why_it_matters": why,
        "identity_effect": identity_effect,
        "novelty_level": novelty_level,
        "taste_fit": 0.5,
        "targets_snapshot": dict(targets),
        "compiled_plan": compiled,
        "score": 0.0,
        "rank": 0,
        "score_breakdown": {},
        "analytical_only": analytical,
        "distinctness_reason": "",
    }


def build_analytical_variant(label: str, request_text: str, novelty_level: float, variant_id: str = "") -> dict:
    """Fallback variant when no moves match — analytical only."""
    return {
        "variant_id": variant_id,
        "label": label,
        "move_id": "",
        "family": "",
        "intent": f"Analytical suggestion for: {request_text}",
        "what_changed": "No specific move matched — consider rephrasing the request",
        "what_preserved": "core elements",
        "why_it_matters": "No matching moves found — this is a directional suggestion only",
        "identity_effect": "preserves",
        "novelty_level": novelty_level,
        "taste_fit": 0.5,
        "targets_snapshot": {},
        "compiled_plan": None,
        "score": 0.0,
        "rank": 0,
        "score_breakdown": {},
        "analytical_only": True,
        "distinctness_reason": "No matching executable move — directional suggestion only",
    }


# v1.18.2 #10 fix: distinct cold-start variant seeds for empty/sparse
# sessions. Used when no semantic moves match the request. Each seed has
# a specific `what_changed` + `why_it_matters` covering a different
# starting-point family (device_creation × rhythm + device_creation ×
# harmony + mix-architecture-first). Replaces the 3-identical-generics
# degradation that v1.18.0 Test 4 surfaced.
_COLD_START_SEEDS: list[dict] = [
    {
        "label": "safe",
        "family": "device_creation",
        "intent": "Begin with a rhythmic foundation",
        "what_changed": "Load a drum kit (Drum Rack or Core Kit) on a fresh MIDI track, program a 4-bar kick-and-hat pattern",
        "what_preserved": "blank slate — first move sets the tempo and grid foundation",
        "why_it_matters": "Every track needs a rhythmic anchor before timbral or structural work. Safe starting point — drums-first is the most common composition entry.",
        "novelty_level": 0.3,
        "identity_effect": "establishes",
    },
    {
        "label": "strong",
        "family": "sound_design",
        "intent": "Begin with a harmonic source",
        "what_changed": "Load Drift or Meld on a MIDI track with a chord-stab patch (short attack, moderate release, slight detune), sketch a 2-bar chord pattern",
        "what_preserved": "tempo and key are still open to discovery — lets the harmony suggest the rhythm",
        "why_it_matters": "A harmonic source opens a different emotional palette than drums-first. Chord-first composition (Isolée / Luomo style) is less common but produces distinctive results.",
        "novelty_level": 0.55,
        "identity_effect": "establishes",
    },
    {
        "label": "unexpected",
        "family": "mix",
        "intent": "Begin with the space, not the source",
        "what_changed": "Configure return tracks BEFORE any instrument work — set up Return A with Convolution Reverb (cathedral IR) and Return B with Echo in ping-pong mode",
        "what_preserved": "the blank slate IS the canvas; the sends are the frame you'll paint into",
        "why_it_matters": "Dub techno and ambient producers (Basic Channel, Gas, Henke) build sound AROUND pre-configured sends. Unusual but genre-appropriate starting point.",
        "novelty_level": 0.85,
        "identity_effect": "establishes",
    },
]


def build_cold_start_variant(seed: dict, request_text: str, variant_id: str = "") -> dict:
    """Build a cold-start variant seed for an empty/sparse session.

    Used when no semantic moves match the request. Returns a variant with
    distinct, actionable `what_changed` / `why_it_matters` text — NOT the
    generic 'No matching moves found' fallback. Each seed covers a
    different starting-point family; together they give the user three
    genuinely distinct first-moves to choose from.

    See `_COLD_START_SEEDS` for the seed set. The variant is
    `analytical_only=True` (no compiled_plan) — turning these into
    one-click executable plans is a v1.19 enhancement.
    """
    return {
        "variant_id": variant_id,
        "label": seed["label"],
        "move_id": "",
        "family": seed["family"],
        "intent": seed["intent"],
        "what_changed": seed["what_changed"],
        "what_preserved": seed["what_preserved"],
        "why_it_matters": seed["why_it_matters"],
        "identity_effect": seed["identity_effect"],
        "novelty_level": seed["novelty_level"],
        "taste_fit": 0.5,
        "targets_snapshot": {},
        "compiled_plan": None,
        "score": 0.0,
        "rank": 0,
        "score_breakdown": {},
        "analytical_only": True,
        "distinctness_reason": f"Cold-start seed ({seed['family']}) — empty session, no moves matched",
        "cold_start": True,
    }


# ── Taste fit scoring ────────────────────────────────────────────


def compute_taste_fit(move_dict: dict, taste_graph: object = None) -> float:
    """Score how well a move fits user taste using the full TasteGraph."""
    if taste_graph is None:
        return 0.5
    if not hasattr(taste_graph, "rank_moves"):
        return 0.5
    if not hasattr(taste_graph, "evidence_count") or taste_graph.evidence_count == 0:
        return 0.5

    ranked = taste_graph.rank_moves([move_dict])
    if ranked:
        return ranked[0].get("taste_score", 0.5)
    return 0.5


# ── Ranking ──────────────────────────────────────────────────────

_IDENTITY_BASE = {"preserves": 0.9, "evolves": 0.7, "contrasts": 0.4, "resets": 0.15}


def rank_variants(
    variant_dicts: list[dict],
    song_brain: Optional[dict] = None,
    novelty_band: float = 0.5,
    taste_evidence: int = -1,
) -> list[dict]:
    """Rank variants by taste + identity + novelty + coherence."""
    song_brain = song_brain or {}
    sacred = song_brain.get("sacred_elements", [])
    identity_confidence = song_brain.get("identity_confidence", 0.5)

    weights = _select_weights(
        identity_confidence=identity_confidence,
        taste_evidence=taste_evidence,
        all_same_family=_all_same_family(variant_dicts),
    )

    move_ids = [v.get("move_id", "") for v in variant_dicts]
    all_target_dims = [set(v.get("targets_snapshot", {}).keys()) for v in variant_dicts]

    for i, v in enumerate(variant_dicts):
        taste_score = v.get("taste_fit", 0.5)

        # Identity component
        effect = v.get("identity_effect", "preserves")
        base = _IDENTITY_BASE.get(effect, 0.5)
        targets = v.get("targets_snapshot", {})
        sacred_penalty = sum(
            s.get("salience", 0.5) * 0.15
            for s in sacred
            if s.get("element_type") in targets and effect != "preserves"
        )
        identity_score = max(0.0, base - sacred_penalty)

        # Novelty — bell curve centered on user's novelty_band
        nov = v.get("novelty_level", 0.5)
        novelty_score = math.exp(-((nov - novelty_band) ** 2) / (2 * 0.15 ** 2))

        # Coherence — penalize same move_id and same target dimensions
        coherence_score = 1.0
        mid = move_ids[i]
        if mid and move_ids.count(mid) > 1:
            coherence_score -= 0.15
        if i < len(all_target_dims):
            for j, other_dims in enumerate(all_target_dims):
                if j != i and all_target_dims[i] == other_dims and all_target_dims[i]:
                    coherence_score -= 0.1
                    break
        coherence_score = max(0.0, coherence_score)

        composite = (
            taste_score * weights["taste"]
            + identity_score * weights["identity"]
            + novelty_score * weights["novelty"]
            + coherence_score * weights["coherence"]
        )

        v["score"] = round(max(0.0, min(1.0, composite)), 3)
        v["score_breakdown"] = {
            "taste": round(taste_score, 3),
            "identity": round(identity_score, 3),
            "novelty": round(novelty_score, 3),
            "coherence": round(coherence_score, 3),
            "weights": dict(weights),
        }

    variant_dicts.sort(key=lambda v: -v["score"])
    for i, v in enumerate(variant_dicts):
        v["rank"] = i + 1

    return variant_dicts


def _select_weights(
    identity_confidence: float,
    taste_evidence: int,
    all_same_family: bool,
) -> dict[str, float]:
    """Select ranking weights based on context."""
    if taste_evidence == 0:
        return {"taste": 0.00, "identity": 0.40, "novelty": 0.25, "coherence": 0.35}
    if identity_confidence > 0.7:
        return {"taste": 0.20, "identity": 0.40, "novelty": 0.10, "coherence": 0.30}
    if all_same_family:
        return {"taste": 0.25, "identity": 0.25, "novelty": 0.15, "coherence": 0.35}
    return {"taste": 0.25, "identity": 0.30, "novelty": 0.20, "coherence": 0.25}


def _all_same_family(variants: list[dict]) -> bool:
    """Check if all variants are from the same move family."""
    families = {v.get("family", "") for v in variants}
    families.discard("")
    return len(families) <= 1 and len(variants) > 1


# ── Corpus intelligence enrichment ──────────────────────────────


def _get_corpus_hints(request_text: str, diagnosis: dict | None) -> dict | None:
    """Query the corpus for creative hints relevant to the request.

    Returns a dict with emotional_recipe, genre_chain, automation_density,
    and technique_suggestions — or None if corpus is unavailable.
    """
    try:
        from ..corpus import get_corpus
    except ImportError:
        return None

    corpus = get_corpus()
    if not corpus.emotional_recipes and not corpus.genre_chains:
        return None

    hints: dict = {}
    request_lower = request_text.lower()

    # Check for emotional keywords
    _EMOTION_KEYWORDS = {
        "warm": "warmth & comfort", "cold": "tension & anxiety",
        "dark": "melancholy", "bright": "euphoria",
        "aggressive": "danger", "soft": "warmth & comfort",
        "anxious": "tension & anxiety", "nostalgic": "nostalgia",
        "vast": "vastness", "ethereal": "vastness",
        "sad": "melancholy", "happy": "euphoria",
        "tension": "tension & anxiety", "release": "euphoria",
    }
    for keyword, emotion_key in _EMOTION_KEYWORDS.items():
        if keyword in request_lower:
            recipe = corpus.suggest_for_emotion(emotion_key)
            if recipe:
                hints["emotional_recipe"] = {
                    "emotion": recipe.emotion,
                    "technique_count": len(recipe.techniques),
                    "first_techniques": [t[:100] for t in recipe.techniques[:3]],
                }
                break

    # Check for genre keywords
    _GENRE_KEYWORDS = ["dub", "techno", "minimal", "ambient", "idm", "trap",
                       "sophie", "arca", "house", "trance", "drum and bass"]
    for genre in _GENRE_KEYWORDS:
        if genre in request_lower:
            chain = corpus.get_genre_chain(genre)
            if chain:
                hints["genre_chain"] = {
                    "genre": chain.genre,
                    "devices": chain.devices[:5],
                    "description": chain.description[:120],
                }
                break

    # Check for physical model keywords
    _MATERIAL_KEYWORDS = ["water", "metal", "glass", "breath", "fire", "electric"]
    for material in _MATERIAL_KEYWORDS:
        if material in request_lower:
            model = corpus.suggest_for_material(material)
            if model:
                hints["physical_model"] = {
                    "material": model.material,
                    "devices": model.devices[:4],
                }
                break

    # Automation density from diagnosis section type
    if diagnosis:
        problem_class = diagnosis.get("problem_class", "")
        if "static" in problem_class or "flat" in problem_class:
            hints["automation_density"] = corpus.get_automation_density_for_section("peak")
        elif "breakdown" in problem_class:
            hints["automation_density"] = corpus.get_automation_density_for_section("breakdown")

    return hints if hints else None


# ── Pipeline orchestrator ────────────────────────────────────────


def generate_wonder_variants(
    request_text: str,
    diagnosis: dict | None = None,
    kernel_id: str = "",
    song_brain: dict | None = None,
    taste_graph: object = None,
    active_constraints: object = None,
    session_info: dict | None = None,
    sample_context: dict | None = None,
) -> dict:
    """Full wonder mode pipeline: discover -> select distinct -> build -> taste -> rank."""
    song_brain = song_brain or {}
    diagnosis = diagnosis or {}
    set_prefix = _wonder_id(request_text, kernel_id)

    candidate_domains = diagnosis.get("candidate_domains") or None
    moves = discover_moves(request_text, taste_graph, active_constraints, candidate_domains)
    distinct = select_distinct_variants(moves)

    labels = ["safe", "strong", "unexpected"]
    variants = []

    # Load corpus intelligence for variant enrichment
    corpus_hints = _get_corpus_hints(request_text, diagnosis)

    # Build kernel for variant compilation
    kernel = {
        "session_info": session_info or {},
        "mode": "improve",
    }
    if sample_context:
        kernel.update(sample_context)

    # Build executable variants from distinct moves
    for i, move in enumerate(distinct):
        label = labels[i]
        move_with_envelope = _with_envelope(move, label)
        v = build_variant(
            label=label,
            move_dict=move_with_envelope,
            song_brain=song_brain,
            novelty_level=_NOVELTY_LEVELS.get(label, 0.5),
            variant_id=f"{set_prefix}_{label}",
            kernel=kernel,
        )
        if taste_graph is not None:
            # Score taste on envelope-adjusted move for consistency with targets_snapshot
            v["taste_fit"] = compute_taste_fit(move_with_envelope, taste_graph)
        v["distinctness_reason"] = _explain_distinctness(move, distinct, i)
        # Enrich with corpus knowledge
        if corpus_hints:
            v["corpus_hints"] = corpus_hints
        variants.append(v)

    executable_count = len(variants)

    # v1.18.2 #10 fix: when NO executable moves matched, seed from the
    # cold-start distinct-starting-points set instead of padding with
    # identical generic analytical variants. Pre-fix, cold-start on an
    # empty session returned 3 variants all with the same generic
    # "No matching moves found" text — unhelpful to the user.
    #
    # The partial-match case (1 or 2 executable variants) still pads with
    # the generic analytical fallback because we don't want to mix real
    # move-based variants with architecture-first seeds — that would
    # confuse the presentation.
    if executable_count == 0:
        while len(variants) < 3:
            idx = len(variants)
            seed = _COLD_START_SEEDS[idx]
            v = build_cold_start_variant(
                seed=seed,
                request_text=request_text,
                variant_id=f"{set_prefix}_{seed['label']}",
            )
            variants.append(v)
    else:
        # Partial-match: pad to 3 with generic analytical variants
        while len(variants) < 3:
            idx = len(variants)
            v = build_analytical_variant(
                label=labels[idx],
                request_text=request_text,
                novelty_level=_NOVELTY_LEVELS.get(labels[idx], 0.5),
                variant_id=f"{set_prefix}_{labels[idx]}",
            )
            variants.append(v)

    novelty_band = 0.5
    taste_evidence = 0
    if taste_graph is not None and hasattr(taste_graph, "novelty_band"):
        novelty_band = taste_graph.novelty_band
        taste_evidence = getattr(taste_graph, "evidence_count", 0)

    ranked = rank_variants(
        variants,
        song_brain=song_brain,
        novelty_band=novelty_band,
        taste_evidence=taste_evidence,
    )

    degraded_reason = ""
    if executable_count == 0:
        # v1.18.2 #10: cold-start path — distinct starting-point seeds
        # rather than identical-generic padding.
        degraded_reason = (
            "No matching executable moves — cold-start variants seeded "
            "from distinct starting-point families (device_creation × 2 "
            "+ mix-architecture-first)"
        )
    elif executable_count == 1:
        degraded_reason = "Only 1 distinct executable move found"

    return {
        "mode": "wonder",
        "request": request_text,
        "variants": ranked,
        "recommended": ranked[0]["variant_id"] if ranked else "",
        "taste_evidence": taste_evidence,
        "identity_confidence": song_brain.get("identity_confidence", 0.0),
        "move_count_matched": len(moves),
        "variant_count_actual": executable_count,
        "degraded_reason": degraded_reason,
    }


def _explain_distinctness(move: dict, all_moves: list[dict], index: int) -> str:
    """Explain why this variant is different from the others."""
    family = move.get("family", "")
    other_families = {m.get("family", "") for i, m in enumerate(all_moves) if i != index}

    if family not in other_families:
        return f"Different family: {family}"
    shape = _plan_template_shape(move)
    return f"Different approach: {', '.join(sorted(shape))}"


def _wonder_id(request_text: str, kernel_id: str) -> str:
    """Deterministic variant ID prefix — no timestamp."""
    seed = json.dumps({"r": request_text, "k": kernel_id}, sort_keys=True)
    return "wm_" + hashlib.sha256(seed.encode()).hexdigest()[:10]


# ── PR6 — branch-native seed assembly ────────────────────────────────────


def _stable_seed_short_id(prefix: str, key: str) -> str:
    """Deterministic short id for a seed, no timestamp."""
    h = hashlib.sha256(f"{prefix}:{key}".encode()).hexdigest()[:10]
    return f"{prefix}_{h}"


_MOVE_NOVELTY_BY_INDEX = ("safe", "strong", "unexpected")


def generate_branch_seeds(
    request_text: str,
    kernel: Optional[dict] = None,
    song_brain: Optional[dict] = None,
    active_constraints: object = None,
    taste_graph: object = None,
    max_seeds: int = 3,
) -> list[BranchSeed]:
    """Assemble BranchSeeds from multiple creative sources.

    Branch-native companion to ``generate_wonder_variants``. Instead of
    returning pre-built variant dicts tied to moves, emits BranchSeed
    objects that can be fed to ``create_experiment_from_seeds`` or
    ``create_experiment(seeds=[...])`` directly.

    Sources (assembled in this order until max_seeds is reached):

      1. ``semantic_move`` — one seed per distinct move discovered by
         ``discover_moves`` + ``select_distinct_variants``. Novelty tier
         is assigned positionally: first move = safe, second = strong,
         third = unexpected.

      2. ``technique`` — freeform seeds built from kernel.session_memory
         entries whose category is "technique" or "success". Low-novelty
         by design (known-good).

      3. sacred-element inversion — freeform seeds that deliberately
         contrast a sacred element from ``song_brain.sacred_elements``.
         Only emitted when kernel.freshness >= 0.5. High-novelty,
         high-risk. These seeds are typically analytical until a
         producer (Wonder itself or synthesis_brain) compiles them.

      4. corpus hints — freeform seeds built from ``_get_corpus_hints``.
         Medium novelty, grounded in the corpus knowledge base.

    Distinctness rules:
      - At most one seed with each exact hypothesis (case-insensitive)
      - semantic_move seeds already pass through select_distinct_variants
        so their (family, plan_shape) distinctness is preserved

    When kernel is None, the function still works — it just skips the
    kernel-driven sources (technique memory, freshness-gated inversion).

    Does NOT include synthesis or composer seeds — those emit
    (seed, compiled_plan) pairs and must be handled by callers that
    can thread plans through. Use generate_branch_seeds_and_plans() for
    the full multi-producer assembly.
    """
    kernel = kernel or {}
    song_brain = song_brain or {}
    seeds: list[BranchSeed] = []
    used_hypotheses: set[str] = set()
    freshness = float(kernel.get("freshness", 0.5) or 0.5)

    # ── 1. semantic_move seeds ────────────────────────────────────────
    moves = discover_moves(
        request_text,
        taste_graph=taste_graph,
        active_constraints=active_constraints,
    )
    distinct_moves = select_distinct_variants(moves)

    for i, move in enumerate(distinct_moves):
        if len(seeds) >= max_seeds:
            return seeds
        label = _MOVE_NOVELTY_BY_INDEX[i] if i < len(_MOVE_NOVELTY_BY_INDEX) else "strong"
        hypothesis = move.get("intent") or f"Apply {move.get('move_id', '')}"
        seed = seed_from_move_id(
            move_id=move.get("move_id", ""),
            hypothesis=hypothesis,
            novelty_label=label,
            risk_label=move.get("risk_level", "low"),
            distinctness_reason=_explain_distinctness(move, distinct_moves, i),
        )
        seeds.append(seed)
        used_hypotheses.add(hypothesis.lower())

    # ── 2. technique seeds from session memory ────────────────────────
    session_mem = kernel.get("session_memory") or []
    for mem in session_mem:
        if len(seeds) >= max_seeds:
            return seeds
        if mem.get("category") not in ("technique", "success"):
            continue
        content = (mem.get("content") or "").strip()
        if not content:
            continue
        hyp = f"Replay: {content[:100]}"
        if hyp.lower() in used_hypotheses:
            continue
        seed = freeform_seed(
            seed_id=_stable_seed_short_id("tech", content),
            hypothesis=hyp,
            source="technique",
            novelty_label="safe",
            risk_label="low",
            distinctness_reason="recalled from session memory — known to work",
        )
        seeds.append(seed)
        used_hypotheses.add(hyp.lower())

    # ── 3. sacred-element inversion (freshness-gated) ────────────────
    if freshness >= 0.5:
        sacred = song_brain.get("sacred_elements") or []
        for s in sacred[:2]:
            if len(seeds) >= max_seeds:
                return seeds
            elem_type = s.get("element_type", "element")
            desc = s.get("description") or elem_type
            hyp = f"What if we invert {desc}?"
            if hyp.lower() in used_hypotheses:
                continue
            # Protect every OTHER sacred element — the point is to contrast
            # one of them deliberately.
            other_protected = [
                other.get("element_type", "")
                for other in sacred
                if other.get("element_type") != elem_type
            ]
            seed = freeform_seed(
                seed_id=_stable_seed_short_id("invert", elem_type),
                hypothesis=hyp,
                source="freeform",
                novelty_label="unexpected",
                risk_label="high",
                protected_qualities=[p for p in other_protected if p],
                distinctness_reason=(
                    f"deliberately contrasts the '{desc}' that baseline "
                    f"branches preserve"
                ),
            )
            seeds.append(seed)
            used_hypotheses.add(hyp.lower())

    # ── 4. corpus-hint seeds ──────────────────────────────────────────
    corpus_hints = _get_corpus_hints(request_text, song_brain.get("diagnosis"))
    if corpus_hints:
        for kind, hint in corpus_hints.items():
            if len(seeds) >= max_seeds:
                return seeds
            if not isinstance(hint, dict):
                continue
            if kind == "emotional_recipe":
                hyp = (
                    f"Apply {hint.get('emotion', 'emotional')} recipe "
                    f"({hint.get('technique_count', 0)} techniques)"
                )
            elif kind == "genre_chain":
                devices = hint.get("devices", []) or []
                hyp = (
                    f"Build {hint.get('genre', 'genre')} chain: "
                    f"{', '.join(devices[:3])}"
                )
            elif kind == "physical_model":
                devices = hint.get("devices", []) or []
                hyp = (
                    f"Model {hint.get('material', 'material')} via "
                    f"{', '.join(devices[:3])}"
                )
            else:
                continue

            if hyp.lower() in used_hypotheses:
                continue
            seed = freeform_seed(
                seed_id=_stable_seed_short_id("corpus", f"{kind}:{hyp}"),
                hypothesis=hyp,
                source="freeform",
                novelty_label="strong",
                risk_label="medium",
                distinctness_reason=f"corpus-grounded {kind.replace('_', ' ')}",
            )
            seeds.append(seed)
            used_hypotheses.add(hyp.lower())

    return seeds


def generate_branch_seeds_and_plans(
    request_text: str,
    kernel: Optional[dict] = None,
    song_brain: Optional[dict] = None,
    active_constraints: object = None,
    taste_graph: object = None,
    max_seeds: int = 3,
    synth_profiles: Optional[list] = None,
    composer_request: Optional[str] = None,
    composer_count: int = 2,
) -> tuple[list[BranchSeed], dict[str, dict]]:
    """Full multi-producer branch assembly with pre-compiled plans.

    Extends ``generate_branch_seeds`` to reach the synthesis and composer
    producers — both of which emit ``(seed, compiled_plan)`` pairs that
    cannot be expressed through the seed-only return type of the base
    function. Returns a tuple:

      (seeds, compiled_plans_by_seed_id)

    where ``compiled_plans_by_seed_id`` maps seed_id → plan dict. Seeds
    from producers that don't compile ship with their seed_id absent
    from the dict (e.g. analytical seeds, corpus hints).

    Additional inputs beyond the base function:

      synth_profiles: list of :class:`SynthProfile` objects (from
        ``synthesis_brain.analyze_synth_patch``). When non-empty, each
        profile is passed to ``propose_synth_branches`` and the returned
        pairs are merged into the output. Typically the caller fetches
        device parameters via ``ableton.send_command('get_device_parameters')``
        and builds a profile per device before calling this function.

      composer_request: natural-language composition prompt. When set,
        ``propose_composer_branches`` is invoked with it and the emitted
        pairs are merged. For composition-shaped requests, pass
        ``request_text`` here.

      composer_count: max composer branches to emit (default 2).

    Ordering matches generate_branch_seeds where sources overlap:
    semantic_move → technique → synthesis → sacred-inversion → composer
    → corpus hints. max_seeds still caps total output.
    """
    # Base seeds (semantic_move, technique, sacred-inversion, corpus)
    base_seeds = generate_branch_seeds(
        request_text=request_text,
        kernel=kernel,
        song_brain=song_brain,
        active_constraints=active_constraints,
        taste_graph=taste_graph,
        max_seeds=max_seeds,
    )

    # Copy the base seeds so we can interleave producer seeds without
    # mutating the cached list (if the caller happens to share it).
    seeds: list[BranchSeed] = list(base_seeds)
    plans_by_seed: dict[str, dict] = {}
    used_hypotheses = {s.hypothesis.lower() for s in seeds}
    budget_remaining = max(0, max_seeds - len(seeds))

    # ── synthesis producer ────────────────────────────────────────────
    if budget_remaining > 0 and synth_profiles:
        try:
            from ..synthesis_brain import propose_synth_branches
        except ImportError as exc:
            logger.warning("synthesis_brain unavailable: %s", exc)
            propose_synth_branches = None

        if propose_synth_branches is not None:
            for profile in synth_profiles:
                if budget_remaining <= 0:
                    break
                try:
                    pairs = propose_synth_branches(profile, kernel=kernel)
                except Exception as exc:
                    logger.warning(
                        "propose_synth_branches failed for %s: %s",
                        getattr(profile, "device_name", "?"),
                        exc,
                    )
                    continue
                for seed, plan in pairs:
                    if budget_remaining <= 0:
                        break
                    if seed.hypothesis.lower() in used_hypotheses:
                        continue
                    seeds.append(seed)
                    plans_by_seed[seed.seed_id] = plan
                    used_hypotheses.add(seed.hypothesis.lower())
                    budget_remaining -= 1

    # ── composer producer ────────────────────────────────────────────
    if budget_remaining > 0 and composer_request:
        try:
            from ..composer import propose_composer_branches
        except ImportError as exc:
            logger.warning("composer branch producer unavailable: %s", exc)
            propose_composer_branches = None

        if propose_composer_branches is not None:
            try:
                comp_pairs = propose_composer_branches(
                    request_text=composer_request,
                    kernel=kernel,
                    count=min(composer_count, budget_remaining),
                )
            except Exception as exc:
                logger.warning("propose_composer_branches failed: %s", exc)
                comp_pairs = []

            for seed, plan in comp_pairs:
                if budget_remaining <= 0:
                    break
                if seed.hypothesis.lower() in used_hypotheses:
                    continue
                seeds.append(seed)
                if plan:  # composer may return {} for analytical-only branches
                    plans_by_seed[seed.seed_id] = plan
                used_hypotheses.add(seed.hypothesis.lower())
                budget_remaining -= 1

    return seeds, plans_by_seed
