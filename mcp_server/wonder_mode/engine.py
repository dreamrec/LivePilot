"""Wonder Mode engine — pure computation, zero I/O.

Generates contextually different creative variants ranked by
taste, identity, and coherence. Each variant is built from a
real semantic move matched to the request.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Optional


# ── Move discovery ───────────────────────────────────────────────


def discover_moves(
    request_text: str,
    taste_graph: object = None,
    active_constraints: object = None,
) -> list[dict]:
    """Find semantic moves relevant to the request.

    Uses keyword scoring + optional taste reranking + constraint filtering.
    Returns full move dicts including compile_plan (via registry.get_move).
    """
    from ..semantic_moves import registry

    all_moves = registry.list_moves()  # returns to_dict() — no compile_plan
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

    # Enrich with full compile_plan via get_move()
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
                    for step in (move.get("compile_plan") or [])
                ]}
                validation = validate_plan_against_constraints(plan, active_constraints)
                if validation["valid"]:
                    filtered.append(move)
            result = filtered
        except Exception:
            pass  # constraint filtering is optional

    return result


# ── Tier assignment ──────────────────────────────────────────────

_RISK_NUMERIC = {"low": 0.2, "medium": 0.5, "high": 0.8}


def assign_moves_to_tiers(scored_moves: list[dict]) -> dict[str, dict]:
    """Assign moves to safe / strong / unexpected by risk profile.

    Returns dict with keys "safe", "strong", "unexpected", each
    containing a move dict with targets possibly scaled by envelope.
    Returns empty dict when no moves provided (analytical fallback).
    """
    if not scored_moves:
        return {}

    sorted_moves = sorted(
        scored_moves,
        key=lambda m: _RISK_NUMERIC.get(m.get("risk_level", "low"), 0.5),
    )

    n = len(sorted_moves)

    if n >= 3:
        return {
            "safe": _with_envelope(sorted_moves[0], "safe"),
            "strong": _with_envelope(sorted_moves[n // 2], "strong"),
            "unexpected": _with_envelope(sorted_moves[-1], "unexpected"),
        }
    elif n == 2:
        return {
            "safe": _with_envelope(sorted_moves[0], "safe"),
            "strong": _with_envelope(sorted_moves[0], "strong"),
            "unexpected": _with_envelope(sorted_moves[1], "unexpected"),
        }
    else:  # n == 1
        return {
            "safe": _with_envelope(sorted_moves[0], "safe"),
            "strong": _with_envelope(sorted_moves[0], "strong"),
            "unexpected": _with_envelope(sorted_moves[0], "unexpected"),
        }


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


# ── Variant building ─────────────────────────────────────────────

_NOVELTY_LEVELS = {"safe": 0.25, "strong": 0.55, "unexpected": 0.85}
_RISK_TO_EFFECT = {"low": "preserves", "medium": "evolves", "high": "contrasts"}


def build_variant(
    label: str,
    move_dict: dict,
    song_brain: Optional[dict] = None,
    novelty_level: float = 0.5,
    variant_id: str = "",
) -> dict:
    """Build a variant dict from a real move + SongBrain context."""
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
        "compiled_plan": move_dict.get("compile_plan"),
        "score": 0.0,
        "rank": 0,
        "score_breakdown": {},
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


# ── Pipeline orchestrator ────────────────────────────────────────


def generate_and_rank(
    request_text: str,
    kernel_id: str = "",
    song_brain: Optional[dict] = None,
    taste_graph: object = None,
    active_constraints: object = None,
) -> dict:
    """Full wonder mode pipeline: discover -> assign -> build -> taste -> rank."""
    song_brain = song_brain or {}
    set_prefix = _wonder_id(request_text, kernel_id)

    moves = discover_moves(request_text, taste_graph, active_constraints)
    tiers = assign_moves_to_tiers(moves)

    if tiers:
        variants = []
        for label, nov in [("safe", 0.25), ("strong", 0.55), ("unexpected", 0.85)]:
            move = tiers[label]
            v = build_variant(
                label=label,
                move_dict=move,
                song_brain=song_brain,
                novelty_level=nov,
                variant_id=f"{set_prefix}_{label}",
            )
            if taste_graph is not None:
                v["taste_fit"] = compute_taste_fit(move, taste_graph)
            variants.append(v)
    else:
        variants = [
            build_analytical_variant("safe", request_text, 0.25, f"{set_prefix}_safe"),
            build_analytical_variant("strong", request_text, 0.55, f"{set_prefix}_strong"),
            build_analytical_variant("unexpected", request_text, 0.85, f"{set_prefix}_unexpected"),
        ]

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

    return {
        "mode": "wonder",
        "request": request_text,
        "variants": ranked,
        "recommended": ranked[0]["variant_id"] if ranked else "",
        "taste_evidence": taste_evidence,
        "identity_confidence": song_brain.get("identity_confidence", 0.0),
        "move_count_matched": len(moves),
    }


def _wonder_id(request_text: str, kernel_id: str) -> str:
    """Deterministic variant ID prefix — no timestamp."""
    seed = json.dumps({"r": request_text, "k": kernel_id}, sort_keys=True)
    return "wm_" + hashlib.sha256(seed.encode()).hexdigest()[:10]
