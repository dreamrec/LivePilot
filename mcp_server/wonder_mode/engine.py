"""Wonder Mode engine — pure computation, zero I/O.

Generates novelty-aware creative variants and ranks them using
taste + identity + phrase impact.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Optional

from ..preview_studio.models import PreviewVariant


# ── Wonder variant generation ─────────────────────────────────────


def generate_wonder_variants(
    request_text: str,
    kernel_id: str,
    song_brain: Optional[dict] = None,
    taste_graph: Optional[dict] = None,
    available_moves: Optional[list[dict]] = None,
) -> list[PreviewVariant]:
    """Generate wonder-mode variants with elevated novelty.

    Creates three conceptually distinct branches:
    - safe: identity-preserving, taste-aligned
    - strong: musically assertive, moderate novelty
    - unexpected: surprising but sacred-element-respecting
    """
    song_brain = song_brain or {}
    taste_graph = taste_graph or {}
    available_moves = available_moves or []
    now = int(time.time() * 1000)

    sacred = song_brain.get("sacred_elements", [])
    sacred_text = ", ".join(
        e.get("description", "") for e in sacred[:3]
    ) if sacred else "core musical elements"
    identity = song_brain.get("identity_core", "the track's defining character")

    set_prefix = _wonder_id(request_text, kernel_id)

    variants = [
        PreviewVariant(
            variant_id=f"{set_prefix}_safe",
            label="safe",
            intent=f"Stay close to {identity} while addressing: {request_text}",
            novelty_level=0.25,
            identity_effect="preserves",
            what_preserved=f"All sacred elements: {sacred_text}",
            what_changed="Minimal — refines within existing boundaries",
            why_it_matters="Zero risk to what's working. Good when the track is fragile.",
            taste_fit=_taste_fit(0.25, taste_graph),
            move_id=available_moves[0].get("move_id", "") if available_moves else "",
            created_at_ms=now,
        ),
        PreviewVariant(
            variant_id=f"{set_prefix}_strong",
            label="strong",
            intent=f"Push {identity} forward with conviction: {request_text}",
            novelty_level=0.55,
            identity_effect="evolves",
            what_preserved=f"Core identity and {sacred_text}",
            what_changed="Assertive move — adds new energy without breaking identity",
            why_it_matters="Best default pick — meaningful impact with controlled risk.",
            taste_fit=_taste_fit(0.55, taste_graph),
            move_id=available_moves[1].get("move_id", "") if len(available_moves) > 1 else "",
            created_at_ms=now,
        ),
        PreviewVariant(
            variant_id=f"{set_prefix}_unexpected",
            label="unexpected",
            intent=f"Surprise — reframe {identity} through a new lens: {request_text}",
            novelty_level=0.85,
            identity_effect="contrasts",
            what_preserved=f"Respects {sacred_text} but recontextualizes them",
            what_changed="High novelty — introduces something genuinely new",
            why_it_matters="May unlock a direction you wouldn't have found otherwise.",
            taste_fit=_taste_fit(0.85, taste_graph),
            move_id=available_moves[2].get("move_id", "") if len(available_moves) > 2 else "",
            created_at_ms=now,
        ),
    ]

    return variants


# ── Ranking ───────────────────────────────────────────────────────


def rank_wonder_variants(
    variants: list[PreviewVariant],
    song_brain: Optional[dict] = None,
    taste_graph: Optional[dict] = None,
    phrase_impacts: Optional[list[dict]] = None,
) -> list[dict]:
    """Rank wonder variants by taste + identity + impact.

    Rewards novelty that doesn't destroy identity. Penalizes fake
    diversity (variants that differ only in magnitude, not concept).
    """
    song_brain = song_brain or {}
    taste_graph = taste_graph or {}
    phrase_impacts = phrase_impacts or []

    scored: list[dict] = []
    for v in variants:
        # Taste component
        taste_score = v.taste_fit

        # Identity component — preserves > evolves > contrasts > resets
        identity_scores = {
            "preserves": 0.9,
            "evolves": 0.75,
            "contrasts": 0.5,
            "resets": 0.2,
        }
        identity_score = identity_scores.get(v.identity_effect, 0.5)

        # Novelty component — reward difference from center, penalize extremes
        novelty_reward = v.novelty_level * 0.6  # reward novelty
        identity_penalty = 0.0
        if v.identity_effect == "resets":
            identity_penalty = 0.3
        elif v.identity_effect == "contrasts" and v.novelty_level > 0.9:
            identity_penalty = 0.1

        # Impact component (from phrase impacts if available)
        impact_score = 0.5
        matching_impact = [p for p in phrase_impacts if p.get("variant_id") == v.variant_id]
        if matching_impact:
            impact_score = matching_impact[0].get("composite_impact", 0.5)

        composite = (
            taste_score * 0.25
            + identity_score * 0.3
            + novelty_reward * 0.2
            + impact_score * 0.25
            - identity_penalty
        )

        v.score = round(max(0.0, min(1.0, composite)), 3)

        scored.append({
            "variant_id": v.variant_id,
            "label": v.label,
            "score": v.score,
            "taste_fit": v.taste_fit,
            "novelty_level": v.novelty_level,
            "identity_effect": v.identity_effect,
            "intent": v.intent,
            "what_preserved": v.what_preserved,
            "why_it_matters": v.why_it_matters,
        })

    scored.sort(key=lambda s: s["score"], reverse=True)
    return scored


# ── Helpers ───────────────────────────────────────────────────────


def _wonder_id(request_text: str, kernel_id: str) -> str:
    seed = json.dumps({"r": request_text, "k": kernel_id, "w": True}, sort_keys=True)
    return "wm_" + hashlib.sha256(seed.encode()).hexdigest()[:10]


def _taste_fit(novelty: float, taste_graph: dict) -> float:
    """Estimate taste fit based on user boldness preferences."""
    boldness = taste_graph.get("transition_boldness", 0.5)
    fx_intensity = taste_graph.get("fx_intensity", 0.5)
    avg_boldness = (boldness + fx_intensity) / 2
    fit = 1.0 - abs(novelty - avg_boldness) * 0.6
    return round(max(0.0, min(1.0, fit)), 3)
