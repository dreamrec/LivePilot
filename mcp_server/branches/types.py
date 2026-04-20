"""Branch-native types.

Design (see docs/specs/2026-03-17-livepilot-design.md and the branch-native
migration plan):

- Producers (Wonder, synthesis_brain, composer, technique memory) emit
  BranchSeed objects expressing creative intent. A seed carries a hypothesis,
  a source label, a distinctness reason, and novelty/risk labels — but no
  executable plan yet.
- A compiler turns a seed into a CompiledBranch by attaching a plan. For
  source="semantic_move" seeds, the existing semantic_moves.compiler is used.
  For freeform/synthesis/composer seeds, the producer supplies the plan.
- CompiledBranch is the canonical post-compilation shape. PreviewVariant
  and ExperimentBranch will migrate to thin wrappers over CompiledBranch
  in later PRs; this PR only introduces the types.

compiled_plan=None means analytical_only — the branch is a directional
suggestion with no executable path. This case already exists in Wonder
(build_analytical_variant); the branch-native schema promotes it to a
first-class concept across the whole system.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from typing import Literal, Optional


BranchSource = Literal[
    "semantic_move",  # compiled via semantic_moves.compiler
    "freeform",       # producer supplies the compiled plan directly
    "synthesis",      # from synthesis_brain (PR9+)
    "composer",       # from composer branch-native path (PR11)
    "technique",      # from technique memory replay
]
RiskLabel = Literal["low", "medium", "high"]
NoveltyLabel = Literal["safe", "strong", "unexpected"]


PRODUCER_PAYLOAD_SCHEMA_VERSION = 1


@dataclass
class BranchSeed:
    """Pre-compilation creative intent.

    Distinctness between branches is checked at seed layer — two seeds with
    the same (source, hypothesis_hash, affected_scope_hash) are not distinct.

    Fields:
      seed_id: stable identifier. For semantic_move seeds, derived from move_id.
      source: producer category.
      move_id: populated when source="semantic_move"; empty otherwise.
      hypothesis: one-line human-readable prediction of what the branch does.
      protected_qualities: dimension names the producer promises not to regress.
      affected_scope: {track_indices, device_paths, section_ids, clip_slots}.
        Session-scope information: which tracks/devices/sections the branch
        affects. Distinct from ``producer_payload`` which carries regeneration
        context.
      distinctness_reason: why this seed is different from siblings in a set.
      risk_label: execution safety tier.
      novelty_label: creative novelty tier — maps to the safe/strong/unexpected UX triptych.
      analytical_only: true ⇒ no plan will be compiled; branch is directional only.
      producer_payload: free-form dict the emitting producer populates with
        whatever it needs for regeneration / provenance / winner escalation.
        Consumers must check ``schema_version`` (defaults to 1) before reading
        specific keys so older serialized branches don't break newer readers.

        Canonical shapes per producer:
          semantic_move: {schema_version: 1}  (empty — move_id is the key)
          freeform / technique: {schema_version: 1}  (optional)
          synthesis:
            {schema_version: 1,
             device_name: "Wavetable",
             track_index: int, device_index: int,
             strategy: "osc_position_shift" | "voice_width_variant" | ...,
             topology_hint: {...}}  (used by PR4 render-verify to re-target)
          composer:
            {schema_version: 1,
             strategy: "canonical" | "energy_shift" | "layer_contrast",
             intent: {<CompositionIntent.to_dict()>}}  (used by PR3 to
             rehydrate for winner-commit escalation)
    """

    seed_id: str
    source: BranchSource
    move_id: str = ""
    hypothesis: str = ""
    protected_qualities: list[str] = field(default_factory=list)
    affected_scope: dict = field(default_factory=dict)
    distinctness_reason: str = ""
    risk_label: RiskLabel = "low"
    novelty_label: NoveltyLabel = "strong"
    analytical_only: bool = False
    producer_payload: dict = field(
        default_factory=lambda: {"schema_version": PRODUCER_PAYLOAD_SCHEMA_VERSION}
    )

    def to_dict(self) -> dict:
        d = asdict(self)
        # Guarantee schema_version in the payload even if the dict was
        # mutated to empty by a caller.
        payload = d.get("producer_payload") or {}
        if "schema_version" not in payload:
            payload = dict(payload)
            payload["schema_version"] = PRODUCER_PAYLOAD_SCHEMA_VERSION
            d["producer_payload"] = payload
        return d


@dataclass
class CompiledBranch:
    """Post-compilation branch — supersedes the move_id-locked ExperimentBranch.

    Fields:
      branch_id: stable identifier scoped to a branch set.
      seed: the originating BranchSeed (carries source, hypothesis, move_id).
      compiled_plan: execution-router-ready plan dict, or None for analytical-only.
      execution_log: per-step results after run/commit; [{tool, backend, ok, error, result}].
      before_snapshot / after_snapshot: captured session state dicts.
      evaluation: evaluator result dict; shape determined by the evaluator.
      score: composite quality score (0-1).
      status: pending | running | evaluated | committed | discarded
              | interesting_but_failed   ← PR7 will gate on this
      created_at_ms / executed_at_ms: timestamps.
    """

    branch_id: str
    seed: BranchSeed
    compiled_plan: Optional[dict] = None
    execution_log: list = field(default_factory=list)
    before_snapshot: Optional[dict] = None
    after_snapshot: Optional[dict] = None
    evaluation: Optional[dict] = None
    score: float = 0.0
    status: str = "pending"
    created_at_ms: int = 0
    executed_at_ms: int = 0

    @property
    def move_id(self) -> str:
        """Back-compat convenience — delegates to seed.move_id.

        Lets callers that currently read branch.move_id keep working once
        ExperimentBranch migrates to wrap CompiledBranch.
        """
        return self.seed.move_id

    @property
    def analytical_only(self) -> bool:
        """A branch is analytical when the seed says so OR when no plan exists."""
        return self.seed.analytical_only or self.compiled_plan is None

    def to_dict(self) -> dict:
        d = {
            "branch_id": self.branch_id,
            "seed": self.seed.to_dict(),
            "move_id": self.move_id,
            "score": self.score,
            "status": self.status,
            "analytical_only": self.analytical_only,
            "created_at_ms": self.created_at_ms,
        }
        if self.compiled_plan:
            d["step_count"] = self.compiled_plan.get("step_count", 0)
            d["summary"] = self.compiled_plan.get("summary", "")
        if self.before_snapshot is not None:
            d["before_snapshot"] = self.before_snapshot
        if self.after_snapshot is not None:
            d["after_snapshot"] = self.after_snapshot
        if self.evaluation is not None:
            d["evaluation"] = self.evaluation
        if self.execution_log:
            d["execution_log"] = self.execution_log
            d["steps_ok"] = sum(1 for e in self.execution_log if e.get("ok"))
            d["steps_failed"] = sum(1 for e in self.execution_log if not e.get("ok"))
        return d


# ── Factory helpers ──────────────────────────────────────────────────────

def _stable_seed_id(prefix: str, *parts: str) -> str:
    """Deterministic seed_id from parts — no timestamps, stable across runs."""
    seed = "|".join(str(p) for p in parts)
    return f"{prefix}_" + hashlib.sha256(seed.encode()).hexdigest()[:10]


def seed_from_move_id(
    move_id: str,
    seed_id: str = "",
    hypothesis: str = "",
    novelty_label: NoveltyLabel = "strong",
    risk_label: RiskLabel = "low",
    protected_qualities: Optional[list[str]] = None,
    distinctness_reason: str = "",
    producer_payload: Optional[dict] = None,
) -> BranchSeed:
    """Build a semantic_move seed — the baseline producer path.

    Mirrors how wonder_mode.engine.discover_moves already hands moves to
    build_variant. In later PRs, the Wonder distinctness selector will emit
    BranchSeed directly instead of move dicts.
    """
    if not seed_id:
        seed_id = _stable_seed_id("seed", "move", move_id, novelty_label)
    return BranchSeed(
        seed_id=seed_id,
        source="semantic_move",
        move_id=move_id,
        hypothesis=hypothesis or f"Apply {move_id}",
        novelty_label=novelty_label,
        risk_label=risk_label,
        protected_qualities=protected_qualities or [],
        distinctness_reason=distinctness_reason,
        producer_payload=_normalize_payload(producer_payload),
    )


def freeform_seed(
    seed_id: str,
    hypothesis: str,
    affected_scope: Optional[dict] = None,
    protected_qualities: Optional[list[str]] = None,
    distinctness_reason: str = "",
    novelty_label: NoveltyLabel = "strong",
    risk_label: RiskLabel = "medium",
    source: BranchSource = "freeform",
    producer_payload: Optional[dict] = None,
) -> BranchSeed:
    """Build a freeform seed — producer has a concrete hypothesis without a move.

    The compiled plan is attached downstream by the producer; this seed
    carries intent only. Used by synthesis_brain, composer, and any
    producer that doesn't go through semantic_moves.compiler.
    """
    return BranchSeed(
        seed_id=seed_id,
        source=source,
        hypothesis=hypothesis,
        affected_scope=affected_scope or {},
        protected_qualities=protected_qualities or [],
        distinctness_reason=distinctness_reason,
        novelty_label=novelty_label,
        risk_label=risk_label,
        producer_payload=_normalize_payload(producer_payload),
    )


def analytical_seed(
    seed_id: str,
    hypothesis: str,
    source: BranchSource = "freeform",
    protected_qualities: Optional[list[str]] = None,
    producer_payload: Optional[dict] = None,
) -> BranchSeed:
    """Build an analytical-only seed — no plan will be compiled.

    Used when a producer has a directional suggestion but no executable path:
    - Wonder fallback when no move matches (already present as
      build_analytical_variant in wonder_mode.engine).
    - Synthesis brain on opaque devices where parameter state can be read
      but safe mutations cannot be proposed yet.
    """
    return BranchSeed(
        seed_id=seed_id,
        source=source,
        hypothesis=hypothesis,
        protected_qualities=protected_qualities or [],
        analytical_only=True,
        producer_payload=_normalize_payload(producer_payload),
    )


def _normalize_payload(payload: Optional[dict]) -> dict:
    """Ensure a producer_payload always has schema_version set.

    Producers that don't care about versioning pass None / empty dict and
    get the default schema_version=PRODUCER_PAYLOAD_SCHEMA_VERSION back.
    Producers that carry their own version number have it preserved.
    """
    if not payload:
        return {"schema_version": PRODUCER_PAYLOAD_SCHEMA_VERSION}
    out = dict(payload)
    out.setdefault("schema_version", PRODUCER_PAYLOAD_SCHEMA_VERSION)
    return out
