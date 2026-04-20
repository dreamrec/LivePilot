"""Composer branch producer — emit section-hypothesis BranchSeeds.

PR11 adds a branch-native entry point alongside the existing compose()
pipeline. Instead of a single deterministic layer plan, callers can
request N distinct compositional hypotheses and audition them via
create_experiment(seeds=..., compiled_plans=...).

Design:
  A composer branch is a CompositionIntent + variant_strategy. Three
  canned strategies are shipped in PR11:

    "canonical"     — intent unchanged, layer plan uses genre defaults
    "energy_shift"  — intent.energy inverted around 0.5 (dense ⇄ sparse)
    "layer_contrast" — one role swapped in the layer plan (e.g. bass
                       role replaced with pad-anchor, or percussion
                       stripped to emphasize melodic content)

Seeds carry source="composer". Each branch produces a pre-compiled
plan through the existing ComposerEngine.compose() pipeline so
run_experiment respects the plans without re-compiling. Later PRs
can add more strategies (key-shift, section-reorder, tempo-halftime).
"""

from __future__ import annotations

import hashlib
from typing import Optional

from ..branches import BranchSeed, freeform_seed
from .prompt_parser import parse_prompt, CompositionIntent
from .layer_planner import plan_layers, plan_sections
from .engine import ComposerEngine, CompositionResult


# Strategy registry — each function takes an intent and returns (modified
# intent, distinctness_reason, novelty_label, risk_label).
def _strategy_canonical(intent: CompositionIntent):
    return (
        intent,
        "baseline composition with genre defaults",
        "safe",
        "low",
    )


def _strategy_energy_shift(intent: CompositionIntent):
    new = CompositionIntent(
        genre=intent.genre,
        sub_genre=intent.sub_genre,
        mood=intent.mood,
        tempo=intent.tempo,
        key=intent.key,
        descriptors=list(intent.descriptors),
        explicit_elements=list(intent.explicit_elements),
        energy=round(1.0 - intent.energy, 2),
        layer_count=intent.layer_count,
        duration_bars=intent.duration_bars,
    )
    direction = "denser" if new.energy > intent.energy else "sparser"
    return (
        new,
        f"energy shifted from {intent.energy:.1f} → {new.energy:.1f} ({direction})",
        "strong",
        "low",
    )


def _strategy_layer_contrast(intent: CompositionIntent):
    new = CompositionIntent(
        genre=intent.genre,
        sub_genre=intent.sub_genre,
        mood=intent.mood,
        tempo=intent.tempo,
        key=intent.key,
        descriptors=list(intent.descriptors),
        # Force the layer planner to drop "bass" as an anchor role by adding
        # "pad" explicitly to explicit_elements and not asking for a bass.
        explicit_elements=list(intent.explicit_elements) + ["pad_anchor", "no_bass"],
        energy=intent.energy,
        layer_count=intent.layer_count,
        duration_bars=intent.duration_bars,
    )
    return (
        new,
        "layer contrast — pad anchor instead of bass line",
        "unexpected",
        "medium",
    )


_STRATEGIES = [
    ("canonical", _strategy_canonical),
    ("energy_shift", _strategy_energy_shift),
    ("layer_contrast", _strategy_layer_contrast),
]


def _short_id(prefix: str, key: str) -> str:
    h = hashlib.sha256(f"{prefix}:{key}".encode()).hexdigest()[:10]
    return f"{prefix}_{h}"


def propose_composer_branches(
    request_text: str,
    kernel: Optional[dict] = None,
    count: int = 2,
    search_roots: Optional[list] = None,
) -> list[tuple[BranchSeed, dict]]:
    """Emit composer-source branch seeds with pre-compiled plans.

    request_text: the natural-language composition prompt.
    kernel: optional SessionKernel dict — reads ``freshness`` to gate
      whether high-novelty strategies (layer_contrast) are included.
    count: desired number of branches (clamped to 1..len(_STRATEGIES)).
    search_roots: optional list of directory paths for sample resolution,
      threaded to ComposerEngine.compose().

    Returns a list of (BranchSeed, compiled_plan_dict) tuples. Each plan
    is a dict with {"steps": [...], "step_count": N, "summary": "..."}
    compatible with run_experiment.
    """
    kernel = kernel or {}
    freshness = float(kernel.get("freshness", 0.5) or 0.5)

    intent = parse_prompt(request_text)

    # Gate high-novelty strategies on freshness.
    if freshness < 0.4:
        strategies = [_STRATEGIES[0]]  # canonical only
    elif freshness < 0.7:
        strategies = _STRATEGIES[:2]   # canonical + energy_shift
    else:
        strategies = _STRATEGIES       # all three

    count = max(1, min(count, len(strategies)))
    results: list[tuple[BranchSeed, dict]] = []

    for name, strategy_fn in strategies[:count]:
        try:
            variant_intent, reason, novelty, risk = strategy_fn(intent)
            plan = _build_section_hypothesis_plan(variant_intent, name)

            seed = freeform_seed(
                seed_id=_short_id(f"cmp_{name}", request_text),
                hypothesis=f"Composer branch ({name}): {reason}",
                source="composer",
                novelty_label=novelty,
                risk_label=risk,
                distinctness_reason=reason,
                # PR3 — carry the variant intent + strategy so commit_experiment
                # can rehydrate and run the full ComposerEngine.compose()
                # pipeline on the winner instead of committing the scaffold.
                producer_payload={
                    "strategy": name,
                    "intent": variant_intent.to_dict(),
                    "request_text": request_text,
                    "reason": reason,
                },
            )
            results.append((seed, plan))
        except Exception as exc:
            # Don't let one strategy's failure kill the rest.
            import logging
            logging.getLogger(__name__).warning(
                "composer strategy %s failed: %s", name, exc
            )
            continue

    return results


async def escalate_composer_branch(
    producer_payload: dict,
    search_roots: Optional[list] = None,
    splice_client: object = None,
    browser_client: object = None,
    max_credits: int = 10,
) -> dict:
    """Run the full ComposerEngine.compose() pipeline on a committed
    composer branch, using the CompositionIntent captured in the seed's
    producer_payload at emit time.

    Returns a dict with:
      ok: bool
      plan: list of executable steps (the full resolved plan, not the
            scaffolding the branch was auditioned with)
      step_count: int
      layer_count: int
      resolved_samples: dict (role → local_path)
      warnings: list (unresolved layers, missing samples, etc.)
      error: str (when ok=False)

    When ok=False, callers should fall back to committing the scaffold
    plan instead of dropping the branch — the scaffolding is still
    useful as a track/scene skeleton the user can populate manually.

    This function is async because ComposerEngine.compose() is async
    (it awaits Splice / filesystem sample resolution).
    """
    import logging
    logger = logging.getLogger(__name__)

    schema_version = producer_payload.get("schema_version") if producer_payload else None
    intent_dict = (producer_payload or {}).get("intent")

    if not intent_dict:
        return {
            "ok": False,
            "error": (
                "Composer branch producer_payload missing 'intent'. "
                "This branch was likely emitted before PR3/v2 and cannot "
                "be escalated — commit the scaffold plan instead."
            ),
        }

    # Rehydrate CompositionIntent from the payload dict. Tolerate unknown
    # keys by only pulling the fields CompositionIntent understands — older
    # schemas may have fewer fields, newer may have more.
    try:
        intent_fields = {
            k: v for k, v in intent_dict.items()
            if k in (
                "genre", "sub_genre", "mood", "tempo", "key",
                "descriptors", "explicit_elements", "energy",
                "layer_count", "duration_bars",
            )
        }
        intent = CompositionIntent(**intent_fields)
    except Exception as exc:
        return {
            "ok": False,
            "error": (
                f"Failed to rehydrate CompositionIntent from producer_payload "
                f"(schema_version={schema_version}): {exc}"
            ),
        }

    engine = ComposerEngine()
    try:
        result: CompositionResult = await engine.compose(
            intent=intent,
            dry_run=False,
            max_credits=max_credits,
            search_roots=search_roots or [],
            splice_client=splice_client,
            browser_client=browser_client,
        )
    except Exception as exc:
        return {
            "ok": False,
            "error": f"ComposerEngine.compose() raised: {exc}",
        }

    # Fallback when no layers resolved — explicit signal so callers can
    # fall back to the scaffold instead of silently shipping an empty
    # plan.
    if not result.plan or len(result.layers) == 0:
        return {
            "ok": False,
            "error": (
                "ComposerEngine.compose() produced zero executable layers. "
                "Sample resolution likely failed — check Splice credits, "
                "filesystem roots, or browser connectivity. Falling back "
                "to scaffold commit is the correct action."
            ),
            "warnings": list(result.warnings),
            "resolved_samples": dict(result.resolved_samples),
        }

    return {
        "ok": True,
        "plan": list(result.plan),
        "step_count": len(result.plan),
        "layer_count": len(result.layers),
        "resolved_samples": dict(result.resolved_samples),
        "credits_estimated": result.credits_estimated,
        "warnings": list(result.warnings),
        "intent_used": intent.to_dict(),
    }


def _build_section_hypothesis_plan(intent: CompositionIntent, strategy_name: str) -> dict:
    """Build a lightweight, executable plan from an intent.

    Uses the synchronous planning primitives (plan_layers, plan_sections)
    to generate a scaffolding plan: set_tempo + create_midi_track per layer
    with sensible names and colors. Sample resolution is deferred —
    callers that want samples loaded should either hand the branch to
    commit_experiment after auditioning, or re-run ComposerEngine.compose()
    on the winning intent.

    Returns a dict with {"steps", "step_count", "summary"}.
    """
    layers = plan_layers(intent)
    sections = plan_sections(intent)

    steps: list[dict] = []

    # Step 1: tempo — only when intent.tempo is set. Remote transport
    # handler takes "tempo" (not "bpm") — see transport.py:set_tempo.
    if intent.tempo and intent.tempo > 0:
        steps.append({
            "tool": "set_tempo",
            "params": {"tempo": float(intent.tempo)},
        })

    # Step 2: one create_midi_track per layer role — the skeleton every
    # subsequent composition step builds on.
    for idx, layer in enumerate(layers):
        name = getattr(layer, "role", f"layer_{idx}")
        steps.append({
            "tool": "create_midi_track",
            "params": {"name": str(name)},
        })

    # Step 3: one create_scene + set_scene_name per section. Remote
    # create_scene handler only accepts "index" — see scenes.py:create_scene.
    # Section labels land via set_scene_name after creation. step_id +
    # $from_step binding resolves the new scene index so parallel branches
    # with different section counts don't step on each other.
    for s_idx, section in enumerate(sections):
        if isinstance(section, dict):
            sec_name = section.get("name", f"Section {s_idx + 1}")
        else:
            sec_name = f"Section {s_idx + 1}"
        create_step_id = f"create_scene_{s_idx}"
        steps.append({
            "tool": "create_scene",
            "step_id": create_step_id,
            "params": {"index": -1},  # -1 ⇒ append at end
        })
        steps.append({
            "tool": "set_scene_name",
            "params": {
                "scene_index": {"$from_step": create_step_id, "path": "index"},
                "name": str(sec_name),
            },
        })

    summary = (
        f"{strategy_name}: {intent.genre or 'auto-genre'} @ "
        f"{intent.tempo or 'auto-tempo'} bpm, energy {intent.energy:.1f} — "
        f"{len(layers)} layers, {len(sections)} sections"
    )
    return {
        "steps": steps,
        "step_count": len(steps),
        "summary": summary,
    }
