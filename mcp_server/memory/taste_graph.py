"""TasteGraph — extended taste model for personalized move ranking.

Builds on the existing TasteMemoryStore and AntiMemoryStore to add:
- Move family scoring (which semantic move families does the user prefer?)
- Device affinities (which synths, effects, and kits resonate?)
- Novelty band (how experimental vs. conservative does the user want to be?)
- Evidence tracking (what decisions informed each inference?)

The TasteGraph is the bridge between "what moves are available" and
"what moves does THIS user want." It powers rank_moves_by_taste.

Pure computation — no I/O. Updated from outcome data.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class MoveFamilyScore:
    """How much a user favors a semantic move family."""
    family: str       # mix, arrangement, transition, sound_design
    score: float = 0.0  # -1 to 1 (negative = dislikes, positive = prefers)
    kept_count: int = 0
    undone_count: int = 0
    last_updated_ms: int = 0

    def to_dict(self) -> dict:
        return {
            "family": self.family,
            "score": round(self.score, 3),
            "kept_count": self.kept_count,
            "undone_count": self.undone_count,
        }


@dataclass
class DeviceAffinity:
    """How much a user likes a particular device or device class."""
    device_name: str
    affinity: float = 0.0  # -1 to 1
    use_count: int = 0
    last_used_ms: int = 0

    def to_dict(self) -> dict:
        return {
            "device_name": self.device_name,
            "affinity": round(self.affinity, 3),
            "use_count": self.use_count,
        }


@dataclass
class TasteGraph:
    """Extended taste model for personalized ranking.

    Combines dimension preferences, move family scores, device affinities,
    and novelty tolerance into a single queryable model.
    """
    # Core dimension preferences (from existing TasteMemoryStore)
    dimension_weights: dict[str, float] = field(default_factory=dict)

    # Dimension avoidances (from AntiMemoryStore)
    dimension_avoidances: dict[str, str] = field(default_factory=dict)

    # Move family preferences
    move_family_scores: dict[str, MoveFamilyScore] = field(default_factory=dict)

    # Device preferences
    device_affinities: dict[str, DeviceAffinity] = field(default_factory=dict)

    # PR8 — per-goal-mode novelty bands. Canonical source of truth.
    # Keys are goal modes ("improve", "explore", or any string a caller
    # supplies). novelty_band (below, as a property) reads/writes
    # novelty_bands["improve"] — one storage, two access paths.
    novelty_bands: dict = field(
        default_factory=lambda: {"improve": 0.5, "explore": 0.5}
    )

    # PR8 — when True, rank_moves returns uniform taste scores (0.5) to
    # bypass taste filtering during branch generation. Callers flip this
    # for fresh / surprise-me mode so novelty survives to post-hoc ranking.
    bypass_taste_in_generation: bool = False

    # Total evidence count (how many decisions informed this graph)
    evidence_count: int = 0
    last_updated_ms: int = 0

    @property
    def novelty_band(self) -> float:
        """Legacy flat novelty band — mirrors novelty_bands["improve"].

        Kept for back-compat with callers that set/read novelty_band
        directly. Setting this property writes through to the bands dict
        so there's no dual source of truth.
        """
        return self.novelty_bands.get("improve", 0.5)

    @novelty_band.setter
    def novelty_band(self, value: float) -> None:
        self.novelty_bands["improve"] = float(value)

    def to_dict(self) -> dict:
        return {
            "dimension_weights": self.dimension_weights,
            "dimension_avoidances": self.dimension_avoidances,
            "move_family_scores": {
                k: v.to_dict() for k, v in self.move_family_scores.items()
            },
            "device_affinities": {
                k: v.to_dict()
                for k, v in sorted(
                    self.device_affinities.items(),
                    key=lambda x: -x[1].affinity,
                )[:10]  # Top 10 only
            },
            # novelty_band kept for legacy consumers that read it directly;
            # novelty_bands is the canonical per-goal-mode shape going forward.
            "novelty_band": round(self.novelty_band, 3),
            "novelty_bands": {k: round(v, 3) for k, v in self.novelty_bands.items()},
            "bypass_taste_in_generation": self.bypass_taste_in_generation,
            "evidence_count": self.evidence_count,
        }

    # ── Update methods ───────────────────────────────────────────────

    # Persistent store reference (set by build_taste_graph when available)
    _persistent_store: object = None

    def record_move_outcome(
        self, move_id: str, family: str, kept: bool, score: float = 0.0
    ) -> None:
        """Update taste from a kept/undone semantic move."""
        now = int(time.time() * 1000)

        if family not in self.move_family_scores:
            self.move_family_scores[family] = MoveFamilyScore(family=family)

        fam = self.move_family_scores[family]
        if kept:
            fam.score = min(1.0, fam.score + 0.1)
            fam.kept_count += 1
        else:
            fam.score = max(-1.0, fam.score - 0.12)
            fam.undone_count += 1
        fam.last_updated_ms = now

        self.evidence_count += 1
        self.last_updated_ms = now

        # Write-back to persistent store
        if self._persistent_store is not None:
            try:
                self._persistent_store.record_move_outcome(move_id, family, kept, score)
            except Exception as exc:
                logger.debug("record_move_outcome failed: %s", exc)
                pass  # persistence is best-effort

    def record_device_use(self, device_name: str, positive: bool = True) -> None:
        """Update device affinity from usage."""
        now = int(time.time() * 1000)

        if device_name not in self.device_affinities:
            self.device_affinities[device_name] = DeviceAffinity(
                device_name=device_name
            )

        dev = self.device_affinities[device_name]
        dev.use_count += 1
        if positive:
            dev.affinity = min(1.0, dev.affinity + 0.05)
        else:
            dev.affinity = max(-1.0, dev.affinity - 0.08)
        dev.last_used_ms = now

        self.evidence_count += 1
        self.last_updated_ms = now

    def update_novelty_from_experiment(
        self, chose_bold: bool, goal_mode: str = "improve",
    ) -> None:
        """Shift novelty band for a given goal mode based on experiment choices.

        PR8: goal_mode defaults to "improve" so legacy callers land on the
        same band they updated before. Pass "explore" to shift the
        exploration-mode band without touching improve-mode preference.
        (novelty_band is a property view over novelty_bands["improve"], so
        improve-mode updates automatically surface there too.)
        """
        current = self.novelty_bands.get(goal_mode, 0.5)
        if chose_bold:
            new_val = min(1.0, current + 0.05)
        else:
            new_val = max(0.0, current - 0.05)
        self.novelty_bands[goal_mode] = new_val

    # ── Ranking ──────────────────────────────────────────────────────

    def rank_moves(
        self,
        move_specs: list[dict],
        goal_mode: str = "improve",
    ) -> list[dict]:
        """Rank a list of semantic move dicts by taste fit.

        Each move dict should have: move_id, family, targets, risk_level.
        Returns the same dicts with added 'taste_score' field, sorted desc.

        PR8 additions:
          goal_mode (str, default "improve"): which novelty band to use for
            risk alignment. "improve" respects the user's conservative history;
            "explore" uses the explore-mode band so past timid choices don't
            punish surprise-me branch generation.
          bypass_taste_in_generation (instance flag): when True, every move
            scores a uniform 0.5. Used during branch generation so taste
            doesn't prune novelty before the user has a chance to audition.
            Ranking order is preserved from input when this flag is on.
        """
        if self.bypass_taste_in_generation:
            return [dict(move, taste_score=0.5) for move in move_specs]

        # Read the band for the requested mode. Falls back to the improve
        # band (via self.novelty_band property) when the mode is unknown.
        novelty_band = self.novelty_bands.get(goal_mode, self.novelty_band)

        ranked = []
        for move in move_specs:
            taste_score = 0.5  # Neutral baseline

            # Family preference
            family = move.get("family", "")
            fam_score = self.move_family_scores.get(family)
            if fam_score:
                taste_score += fam_score.score * 0.3

            # Dimension alignment
            targets = move.get("targets", {})
            for dim, weight in targets.items():
                dim_pref = self.dimension_weights.get(dim, 0.0)
                taste_score += dim_pref * weight * 0.2

            # Anti-preference penalty
            for dim in targets:
                if dim in self.dimension_avoidances:
                    taste_score -= 0.3

            # Novelty/risk alignment (PR8: per-mode band)
            risk = move.get("risk_level", "low")
            risk_val = {"low": 0.2, "medium": 0.5, "high": 0.8}.get(risk, 0.5)
            novelty_match = 1.0 - abs(risk_val - novelty_band)
            taste_score += novelty_match * 0.1

            # Clamp
            taste_score = max(0.0, min(1.0, taste_score))

            result = dict(move)
            result["taste_score"] = round(taste_score, 3)
            ranked.append(result)

        ranked.sort(key=lambda x: -x["taste_score"])
        return ranked

    def explain(self) -> dict:
        """Generate a human-readable explanation of taste inferences."""
        explanations = []

        # Top move families
        top_families = sorted(
            self.move_family_scores.values(),
            key=lambda f: -f.score,
        )[:3]
        for fam in top_families:
            if fam.score > 0.1:
                explanations.append(
                    f"Prefers {fam.family} moves (score {fam.score:.2f}, "
                    f"{fam.kept_count} kept, {fam.undone_count} undone)"
                )
            elif fam.score < -0.1:
                explanations.append(
                    f"Tends to reject {fam.family} moves (score {fam.score:.2f})"
                )

        # Novelty
        if self.novelty_band > 0.65:
            explanations.append("Prefers experimental/bold approaches")
        elif self.novelty_band < 0.35:
            explanations.append("Prefers conservative/safe approaches")

        # Top devices
        top_devs = sorted(
            self.device_affinities.values(),
            key=lambda d: -d.affinity,
        )[:3]
        for dev in top_devs:
            if dev.affinity > 0.1 and dev.use_count >= 2:
                explanations.append(
                    f"Likes {dev.device_name} (used {dev.use_count}x)"
                )

        # Avoidances
        for dim, direction in self.dimension_avoidances.items():
            explanations.append(f"Avoids {direction} {dim}")

        return {
            "evidence_count": self.evidence_count,
            "novelty_band": round(self.novelty_band, 3),
            "explanations": explanations,
        }

# ── Builder ──────────────────────────────────────────────────────────────────


def build_taste_graph(
    taste_store=None,   # TasteMemoryStore
    anti_store=None,    # AntiMemoryStore
    persistent_store=None,  # PersistentTasteStore (optional)
) -> TasteGraph:
    """Build a TasteGraph from existing memory stores.

    When persistent_store is provided, hydrates move_family_scores,
    device_affinities, and novelty_band from disk — these survive
    server restart.
    """
    graph = TasteGraph()

    # Session-scoped dimensions (in-memory)
    if taste_store:
        for dim in taste_store.get_taste_dimensions():
            if dim.evidence_count > 0:
                graph.dimension_weights[dim.name] = dim.value

    if anti_store:
        for pref in anti_store.get_anti_preferences():
            graph.dimension_avoidances[pref.dimension] = pref.direction

    # Persistent state (from disk)
    if persistent_store is not None:
        persisted = persistent_store.get_all()

        # Move family scores
        for move_id, outcome in persisted.get("move_outcomes", {}).items():
            family = outcome.get("family", "")
            if family and family not in graph.move_family_scores:
                from .taste_graph import MoveFamilyScore
                graph.move_family_scores[family] = MoveFamilyScore(family=family)
            if family:
                fam = graph.move_family_scores[family]
                fam.kept_count += outcome.get("kept_count", 0)
                fam.undone_count += outcome.get("undone_count", 0)
                total = fam.kept_count + fam.undone_count
                if total > 0:
                    fam.score = round((fam.kept_count - fam.undone_count) / total, 3)

        # Novelty band — migrate from flat float if present, OR read
        # per-mode dict if newer persistence format has it (PR8).
        persisted_band = persisted.get("novelty_band", 0.5)
        persisted_bands = persisted.get("novelty_bands")
        if isinstance(persisted_bands, dict) and persisted_bands:
            graph.novelty_bands = {
                k: float(v) for k, v in persisted_bands.items() if isinstance(v, (int, float))
            }
            # Ensure both canonical keys are present with sensible defaults.
            graph.novelty_bands.setdefault("improve", persisted_band)
            graph.novelty_bands.setdefault("explore", persisted_band)
            graph.novelty_band = graph.novelty_bands["improve"]
        else:
            graph.novelty_band = persisted_band
            graph.novelty_bands = {"improve": persisted_band, "explore": persisted_band}

        # Device affinities
        for dev_name, dev_data in persisted.get("device_affinities", {}).items():
            from .taste_graph import DeviceAffinity

            graph.device_affinities[dev_name] = DeviceAffinity(
                device_name=dev_name,
                affinity=dev_data.get("affinity", 0.0),
                use_count=dev_data.get("use_count", 0),
            )

        # Evidence count
        graph.evidence_count = max(
            graph.evidence_count, persisted.get("evidence_count", 0)
        )

        # Dimension weights from persistent store (merged, session takes precedence)
        for dim, val in persisted.get("dimension_weights", {}).items():
            if dim not in graph.dimension_weights:
                graph.dimension_weights[dim] = val

        # Anti-preferences from persistent store
        for anti in persisted.get("anti_preferences", []):
            dim = anti.get("dimension", "")
            direction = anti.get("direction", "")
            if dim and dim not in graph.dimension_avoidances:
                graph.dimension_avoidances[dim] = direction

    # Attach persistent store for write-back
    graph._persistent_store = persistent_store

    return graph
