"""Preview Studio engine — pure computation, zero I/O.

Creates, compares, and ranks preview variants using the creative triptych
pattern (safe / strong / unexpected).
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Optional

from .models import PreviewSet, PreviewVariant


# ── In-memory store ───────────────────────────────────────────────

_preview_sets: dict[str, PreviewSet] = {}
_MAX_PREVIEW_SETS = 20


def get_preview_set(set_id: str) -> Optional[PreviewSet]:
    return _preview_sets.get(set_id)


def store_preview_set(ps: PreviewSet) -> None:
    _preview_sets[ps.set_id] = ps
    # Evict oldest sets if over limit
    while len(_preview_sets) > _MAX_PREVIEW_SETS:
        oldest_key = next(iter(_preview_sets))
        del _preview_sets[oldest_key]


# ── Creation ──────────────────────────────────────────────────────


def create_preview_set(
    request_text: str,
    kernel_id: str,
    strategy: str = "creative_triptych",
    available_moves: Optional[list[dict]] = None,
    song_brain: Optional[dict] = None,
    taste_graph: Optional[dict] = None,
) -> PreviewSet:
    """Create a preview set with variant slots.

    For creative_triptych, generates 3 variants: safe, strong, unexpected.
    Each variant gets a move_id from available_moves ranked by novelty.
    """
    set_id = _compute_set_id(request_text, kernel_id)
    now = int(time.time() * 1000)

    moves = available_moves or []
    song_brain = song_brain or {}
    taste_graph = taste_graph or {}

    if strategy == "creative_triptych":
        variants = _build_triptych(request_text, moves, song_brain, taste_graph, set_id, now)
    elif strategy == "binary":
        variants = _build_binary(request_text, moves, song_brain, set_id, now)
    else:
        variants = _build_triptych(request_text, moves, song_brain, taste_graph, set_id, now)

    ps = PreviewSet(
        set_id=set_id,
        request_text=request_text,
        strategy=strategy,
        source_kernel_id=kernel_id,
        variants=variants,
        created_at_ms=now,
    )
    store_preview_set(ps)
    return ps


def _build_triptych(
    request_text: str,
    moves: list[dict],
    song_brain: dict,
    taste_graph: dict,
    set_id: str,
    now: int,
) -> list[PreviewVariant]:
    """Build safe / strong / unexpected variants."""
    identity = song_brain.get("identity_core", "")
    sacred = [e.get("description", "") for e in song_brain.get("sacred_elements", [])]
    sacred_text = ", ".join(sacred[:3]) if sacred else "core elements"

    profiles = [
        {
            "label": "safe",
            "novelty": 0.2,
            "intent": f"Close to current identity, minimal risk. {request_text}",
            "identity_effect": "preserves",
            "what_preserved": f"Preserves {sacred_text}",
            "why_it_matters": "Low risk — good when identity is fragile",
        },
        {
            "label": "strong",
            "novelty": 0.5,
            "intent": f"Musically assertive approach. {request_text}",
            "identity_effect": "evolves",
            "what_preserved": f"Maintains {sacred_text} while pushing forward",
            "why_it_matters": "Best balance of impact and safety",
        },
        {
            "label": "unexpected",
            "novelty": 0.8,
            "intent": f"Surprising but taste-filtered. {request_text}",
            "identity_effect": "contrasts",
            "what_preserved": f"Respects {sacred_text} but reframes context",
            "why_it_matters": "High novelty — may unlock a new direction",
        },
    ]

    variants = []
    for i, profile in enumerate(profiles):
        # Pick a move if available
        move_id = ""
        compiled_plan = None
        if moves and i < len(moves):
            move_id = moves[i].get("move_id", "")
            compiled_plan = moves[i].get("plan_template")

        variants.append(PreviewVariant(
            variant_id=f"{set_id}_{profile['label']}",
            label=profile["label"],
            intent=profile["intent"],
            novelty_level=profile["novelty"],
            identity_effect=profile["identity_effect"],
            what_preserved=profile["what_preserved"],
            why_it_matters=profile["why_it_matters"],
            move_id=move_id,
            compiled_plan=compiled_plan,
            taste_fit=_estimate_taste_fit(profile["novelty"], taste_graph),
            created_at_ms=now,
        ))

    return variants


def _build_binary(
    request_text: str,
    moves: list[dict],
    song_brain: dict,
    set_id: str,
    now: int,
) -> list[PreviewVariant]:
    """Build simple A/B comparison."""
    return [
        PreviewVariant(
            variant_id=f"{set_id}_a",
            label="option_a",
            intent=f"Primary approach: {request_text}",
            novelty_level=0.3,
            identity_effect="preserves",
            move_id=moves[0].get("move_id", "") if moves else "",
            created_at_ms=now,
        ),
        PreviewVariant(
            variant_id=f"{set_id}_b",
            label="option_b",
            intent=f"Alternative approach: {request_text}",
            novelty_level=0.6,
            identity_effect="evolves",
            move_id=moves[1].get("move_id", "") if len(moves) > 1 else "",
            created_at_ms=now,
        ),
    ]


# ── Comparison ────────────────────────────────────────────────────


def compare_variants(
    preview_set: PreviewSet,
    criteria: Optional[dict] = None,
) -> dict:
    """Compare variants within a preview set and rank them."""
    criteria = criteria or {}
    weight_taste = criteria.get("taste_weight", 0.3)
    weight_novelty = criteria.get("novelty_weight", 0.2)
    weight_identity = criteria.get("identity_weight", 0.5)

    rankings = []
    for v in preview_set.variants:
        # Score components
        taste_score = v.taste_fit
        novelty_score = 1.0 - abs(v.novelty_level - 0.5) * 2  # bell curve around 0.5
        identity_score = _identity_effect_score(v.identity_effect)

        composite = (
            taste_score * weight_taste
            + novelty_score * weight_novelty
            + identity_score * weight_identity
        )
        v.score = round(composite, 3)

        rankings.append({
            "variant_id": v.variant_id,
            "label": v.label,
            "score": v.score,
            "taste_fit": v.taste_fit,
            "novelty_level": v.novelty_level,
            "identity_effect": v.identity_effect,
            "summary": v.intent,
            "what_preserved": v.what_preserved,
            "why_it_matters": v.why_it_matters,
        })

    rankings.sort(key=lambda r: r["score"], reverse=True)

    comparison = {
        "rankings": rankings,
        "recommended": rankings[0]["variant_id"] if rankings else "",
        "criteria_used": {
            "taste_weight": weight_taste,
            "novelty_weight": weight_novelty,
            "identity_weight": weight_identity,
        },
    }

    preview_set.comparison = comparison
    preview_set.status = "compared"
    return comparison


def commit_variant(preview_set: PreviewSet, variant_id: str) -> Optional[PreviewVariant]:
    """Mark a variant as committed and discard others."""
    chosen = None
    for v in preview_set.variants:
        if v.variant_id == variant_id:
            v.status = "committed"
            chosen = v
        else:
            v.status = "discarded"

    if chosen:
        preview_set.committed_variant_id = variant_id
        preview_set.status = "committed"

    return chosen


def discard_set(set_id: str) -> bool:
    """Discard an entire preview set."""
    ps = _preview_sets.pop(set_id, None)
    if ps:
        ps.status = "discarded"
        for v in ps.variants:
            v.status = "discarded"
        return True
    return False


# ── Helpers ───────────────────────────────────────────────────────


def _compute_set_id(request_text: str, kernel_id: str) -> str:
    seed = json.dumps({"request": request_text, "kernel": kernel_id}, sort_keys=True)
    return "ps_" + hashlib.sha256(seed.encode()).hexdigest()[:10]


def _estimate_taste_fit(novelty: float, taste_graph: dict) -> float:
    """Estimate how well a novelty level fits user taste."""
    boldness = taste_graph.get("transition_boldness", 0.5)
    # Users who like boldness prefer higher novelty
    fit = 1.0 - abs(novelty - boldness) * 0.5
    return round(max(0.0, min(1.0, fit)), 3)


def _identity_effect_score(effect: str) -> float:
    """Score identity effects — preserves is safest."""
    return {
        "preserves": 0.9,
        "evolves": 0.7,
        "contrasts": 0.4,
        "resets": 0.2,
    }.get(effect, 0.5)
