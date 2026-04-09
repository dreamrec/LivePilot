"""Experiment branch data models.

An ExperimentBranch represents one trial of a semantic move against the
current session state. Multiple branches form an experiment set that can
be compared and ranked.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional


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
    """One trial branch in an experiment set."""
    branch_id: str
    name: str
    move_id: str
    source_kernel_id: str = ""
    status: str = "pending"  # pending | running | evaluated | committed | discarded

    # Compiled plan for this branch
    compiled_plan: Optional[dict] = None

    # Captured snapshots
    before_snapshot: Optional[BranchSnapshot] = None
    after_snapshot: Optional[BranchSnapshot] = None

    # Evaluation results
    evaluation: Optional[dict] = None
    score: float = 0.0

    # Metadata
    created_at_ms: int = 0
    executed_at_ms: int = 0

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
