"""Experiment branch data models.

An ExperimentBranch represents one trial against the current session state.

Pre-PR3 every branch was tied to a semantic_move (positional required
``move_id``). PR3 widens this: a branch may now be built from any
:class:`mcp_server.branches.BranchSeed` — semantic_move, freeform,
synthesis, composer, or technique. The ``move_id`` field is retained as
an optional convenience that mirrors ``seed.move_id`` for back-compat with
callers that read ``branch.move_id`` directly.

Multiple branches form an experiment set that can be compared and ranked.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional

from ..branches import BranchSeed


@dataclass
class BranchSnapshot:
    """Captured state before or after a branch experiment."""
    spectrum: Optional[dict] = None
    rms: Optional[float] = None
    peak: Optional[float] = None
    track_meters: Optional[list] = None
    timestamp_ms: int = 0

    def to_dict(self) -> dict:
        d = {}
        if self.spectrum is not None:
            d["spectrum"] = self.spectrum
        if self.rms is not None:
            d["rms"] = self.rms
        if self.peak is not None:
            d["peak"] = self.peak
        if self.track_meters is not None:
            d["track_meters"] = self.track_meters
        d["timestamp_ms"] = self.timestamp_ms
        return d


@dataclass
class ExperimentBranch:
    """One trial branch in an experiment set.

    move_id is retained as an optional convenience (empty for freeform /
    synthesis / composer seeds) so pre-PR3 callers that read
    ``branch.move_id`` directly keep working. The authoritative source of
    branch intent is ``seed`` when present.
    """
    branch_id: str
    name: str
    # PR3 — was a required positional; now defaults to "" for seeds whose
    # source is not "semantic_move". When seed is present, move_id mirrors
    # seed.move_id (populated by ExperimentBranch.from_seed).
    move_id: str = ""
    source_kernel_id: str = ""
    status: str = "pending"  # pending | running | evaluated | committed | discarded | interesting_but_failed

    # Compiled plan for this branch. Pre-PR3 this was always filled in at
    # run_experiment time. Post-PR3, freeform / synthesis / composer producers
    # MAY pre-populate it on the seed path; run_experiment respects a
    # pre-existing plan and only compiles when it's None.
    compiled_plan: Optional[dict] = None

    # Captured snapshots
    before_snapshot: Optional[BranchSnapshot] = None
    after_snapshot: Optional[BranchSnapshot] = None

    # Evaluation results
    evaluation: Optional[dict] = None
    score: float = 0.0

    # Execution log — per-step results from the async router. Non-empty when
    # a branch has been run through run_branch or committed via commit_branch.
    # Each entry: {tool, backend, ok, error, result}. Surfaced on to_dict()
    # so callers can see exactly which steps succeeded or failed.
    execution_log: list = field(default_factory=list)

    # Metadata
    created_at_ms: int = 0
    executed_at_ms: int = 0

    # PR3 — branch-native seed. None for legacy move-only branches built via
    # the bare constructor; populated when built through from_seed() or via
    # create_experiment_from_seeds.
    seed: Optional[BranchSeed] = None

    @classmethod
    def from_seed(
        cls,
        seed: BranchSeed,
        branch_id: str,
        name: str = "",
        source_kernel_id: str = "",
        compiled_plan: Optional[dict] = None,
        created_at_ms: int = 0,
    ) -> "ExperimentBranch":
        """Construct an ExperimentBranch from a BranchSeed.

        ``move_id`` is mirrored from ``seed.move_id`` (empty for freeform /
        synthesis / composer / technique seeds). When ``compiled_plan`` is
        provided, the producer has already compiled — run_experiment will
        skip compilation for this branch. When None, compilation defers to
        the semantic_moves.compiler at run time and only succeeds for
        source="semantic_move" seeds.
        """
        default_name = (
            f"Branch ({seed.source}:{seed.move_id or seed.seed_id[:8]})"
        )
        return cls(
            branch_id=branch_id,
            name=name or default_name,
            move_id=seed.move_id,
            source_kernel_id=source_kernel_id,
            status="pending",
            compiled_plan=compiled_plan,
            created_at_ms=created_at_ms,
            seed=seed,
        )

    def to_dict(self) -> dict:
        d = {
            "branch_id": self.branch_id,
            "name": self.name,
            "move_id": self.move_id,
            "status": self.status,
            "score": self.score,
            "created_at_ms": self.created_at_ms,
        }
        if self.compiled_plan:
            d["step_count"] = self.compiled_plan.get("step_count", 0)
            d["summary"] = self.compiled_plan.get("summary", "")
        if self.before_snapshot:
            d["before_snapshot"] = self.before_snapshot.to_dict()
        if self.after_snapshot:
            d["after_snapshot"] = self.after_snapshot.to_dict()
        if self.evaluation:
            d["evaluation"] = self.evaluation
        if self.execution_log:
            d["execution_log"] = self.execution_log
            d["steps_ok"] = sum(1 for e in self.execution_log if e.get("ok"))
            d["steps_failed"] = sum(1 for e in self.execution_log if not e.get("ok"))
        if self.seed is not None:
            d["seed"] = self.seed.to_dict()
            d["branch_source"] = self.seed.source
            d["analytical_only"] = (
                self.seed.analytical_only or self.compiled_plan is None
            )
        return d


@dataclass
class ExperimentSet:
    """A collection of branches being compared for one request."""
    experiment_id: str
    request_text: str
    branches: list[ExperimentBranch] = field(default_factory=list)
    status: str = "open"  # open | evaluated | committed | discarded
    winner_branch_id: Optional[str] = None
    created_at_ms: int = 0

    @property
    def branch_count(self) -> int:
        return len(self.branches)

    def get_branch(self, branch_id: str) -> Optional[ExperimentBranch]:
        for b in self.branches:
            if b.branch_id == branch_id:
                return b
        return None

    def ranked_branches(self) -> list[ExperimentBranch]:
        """Return branches sorted by score descending."""
        evaluated = [b for b in self.branches if b.status == "evaluated"]
        return sorted(evaluated, key=lambda b: -b.score)

    def to_dict(self) -> dict:
        return {
            "experiment_id": self.experiment_id,
            "request_text": self.request_text,
            "status": self.status,
            "branch_count": self.branch_count,
            "branches": [b.to_dict() for b in self.branches],
            "winner_branch_id": self.winner_branch_id,
            "ranking": [
                {"branch_id": b.branch_id, "name": b.name, "score": b.score}
                for b in self.ranked_branches()
            ],
        }
