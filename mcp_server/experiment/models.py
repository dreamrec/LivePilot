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
    """Captured state before or after a branch experiment.

    Pre-PR4 fields (spectrum / rms / peak / track_meters) stay the same —
    they remain the fast-path evidence when render-verify isn't available
    or wasn't opted in.

    PR4 adds render-based fields that are populated only when the
    experiment runs with render_verify=True:

      capture_path: path to the captured audio file (useful for re-analysis
                    or user audition of the branch output).
      loudness: {lufs, lra, rms, peak, crest} from analyze_loudness.
      spectral_shape: {centroid, flatness, rolloff, crest} from FluCoMa or
                      the offline analyzer.
      fingerprint: TimbralFingerprint.to_dict() extracted from the
                   captured audio.

    The fingerprint is what classify_branch_outcome reads to derive a
    real goal_progress + measurable_count instead of relying on the
    inline meter-based heuristic alone.
    """
    spectrum: Optional[dict] = None
    rms: Optional[float] = None
    peak: Optional[float] = None
    track_meters: Optional[list] = None
    timestamp_ms: int = 0
    # PR4 — render-based evidence (opt-in via render_verify flag)
    capture_path: Optional[str] = None
    loudness: Optional[dict] = None
    spectral_shape: Optional[dict] = None
    fingerprint: Optional[dict] = None  # TimbralFingerprint.to_dict()

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
        if self.capture_path is not None:
            d["capture_path"] = self.capture_path
        if self.loudness is not None:
            d["loudness"] = self.loudness
        if self.spectral_shape is not None:
            d["spectral_shape"] = self.spectral_shape
        if self.fingerprint is not None:
            d["fingerprint"] = self.fingerprint
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
            # Shortcut to the seed's producer_payload so downstream callers
            # (composer winner-commit, synthesis re-target, provenance logs)
            # don't have to reach into d["seed"]["producer_payload"] every
            # time. The full seed dict is still available for producers
            # that need other fields.
            d["producer_payload"] = dict(self.seed.producer_payload or {})
        return d


# v1.18.2 #11: composite tie-break ranking for experiment branches.
# Maps novelty_label / risk_label strings to integer ranks.
_NOVELTY_RANK: dict[str, int] = {
    "safe": 0,
    "medium": 1,       # rarely used, but accept it for robustness
    "strong": 1,
    "unexpected": 2,
    "bold": 2,         # alias in some producer outputs
}
_RISK_RANK: dict[str, int] = {
    "low": 0,
    "medium": 1,
    "high": 2,
}


def _branch_rank_key(branch: "ExperimentBranch") -> tuple:
    """Composite sort key for ExperimentSet.ranked_branches().

    Returns a tuple (-score, -novelty, risk, step_count, branch_id) such
    that Python's default ascending sort produces the desired ranking:
    higher scores first, then higher novelty at score ties, then lower
    risk under equal novelty, then simpler plans, then branch_id as a
    deterministic final tiebreak.
    """
    score = float(getattr(branch, "score", 0.0) or 0.0)
    seed = getattr(branch, "seed", None)

    if seed is not None:
        novelty_label = (seed.novelty_label or "").lower()
        risk_label = (seed.risk_label or "").lower()
    else:
        novelty_label = ""
        risk_label = ""

    novelty_rank = _NOVELTY_RANK.get(novelty_label, 1)  # middle if unknown
    risk_rank = _RISK_RANK.get(risk_label, 1)

    plan = getattr(branch, "compiled_plan", None) or {}
    step_count = int(plan.get("step_count", 0) or 0)

    branch_id = getattr(branch, "branch_id", "") or ""

    return (-score, -novelty_rank, risk_rank, step_count, branch_id)


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
        """Return evaluated branches sorted by composite rank.

        v1.18.2 #11 fix: pre-fix this was a single-key sort by score,
        which produced unstable rankings at score ties (live-verified in
        v1.18.0 Test 8 — three branches at 0.6 with no winner).

        Sort keys, in priority order:
          1. -score                     — higher score wins
          2. -novelty_rank              — higher novelty wins at score ties
                                          (creative asks reward variation)
          3. risk_rank                  — lower risk wins secondary ties
                                          (safety default under equal novelty)
          4. step_count                 — simpler plans win tertiary ties
          5. branch_id                  — deterministic final tiebreak
                                          (stable ranking across equal branches)

        Novelty labels rank: "safe"=0, "strong"=1, "unexpected"=2, "bold"=2.
        Risk labels rank: "low"=0, "medium"=1, "high"=2.
        Unknown labels default to the middle (1).
        """
        evaluated = [b for b in self.branches if b.status == "evaluated"]
        return sorted(evaluated, key=_branch_rank_key)

    # expose the key function for testing + custom rankers
    def rank_key_for(self, branch: "ExperimentBranch") -> tuple:
        """Return the composite rank key for a branch (for tie-break debugging)."""
        return _branch_rank_key(branch)

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
