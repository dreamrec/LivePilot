"""Tests for v1.21's commit_experiment auto-ledger-write contract.

Mirrors the v1.20 TestApplySemanticMoveLedgerWrite shape at
``tests/test_apply_semantic_move_args.py``. Pins that commit_experiment
in the success path writes a LedgerEntry — engine tag discriminated by
branch SOURCE (not escalation success), move_class from seed family,
actions per executed step (from execution_log), kept based on failure
count, ledger_entry_id returned in the response.

Reference implementation (the pattern being mirrored):
    mcp_server/semantic_moves/tools.py::apply_semantic_move (commit 0b3489b)

Target of this contract:
    mcp_server/experiment/tools.py::commit_experiment (v1.21 addition)

Plan reference: docs/plans/v1.21-structural-plan.md §4.1,
docs/plans/v1.21-implementation-plan.md Task 2.1,
docs/plans/v1.21-impl-status.md §4 (line-number verification).
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Optional

import pytest

from mcp_server.runtime.action_ledger import SessionLedger


# ── Fake experiment + branch + seed scaffolding ──────────────────────────────
#
# Real commit_experiment reads ``target.status``, ``target.seed``,
# ``target.compiled_plan``, ``target.evaluation``, ``target.name``.
# Real ``engine.get_experiment(eid)`` returns an ExperimentSet with
# ``get_branch(branch_id)``. These fakes provide exactly that shape —
# no more — so the unit tests stay focused on the ledger-write contract.


class _FakeSeed:
    def __init__(
        self,
        source: str = "wonder",
        family: str = "mix",
        producer_payload: Optional[dict] = None,
    ):
        self.source = source
        self.family = family
        self.producer_payload = producer_payload


class _FakeBranch:
    def __init__(
        self,
        branch_id: str = "b1",
        name: str = "test branch",
        seed: Optional[_FakeSeed] = None,
        status: str = "evaluated",
        compiled_plan: Optional[dict] = None,
    ):
        self.branch_id = branch_id
        self.name = name
        # Default seed is non-composer, mix family — explicit default keeps
        # the two-step pattern straight: name the default in _FakeSeed, pass
        # a custom one when the test cares about engine/family.
        self.seed = seed if seed is not None else _FakeSeed()
        self.status = status
        self.compiled_plan = compiled_plan or {
            "steps": [
                {"tool": "set_track_volume", "params": {"track_index": 0, "volume": 0.7}},
                {"tool": "set_track_volume", "params": {"track_index": 1, "volume": 0.6}},
            ],
            "step_count": 2,
        }
        self.evaluation: Optional[dict] = None
        self.score: float = 0.0


class _FakeExperiment:
    def __init__(
        self,
        experiment_id: str = "exp1",
        branch: Optional[_FakeBranch] = None,
    ):
        self.experiment_id = experiment_id
        self._branch = branch or _FakeBranch()

    def get_branch(self, branch_id: str):
        if self._branch.branch_id == branch_id:
            return self._branch
        return None


class _MinimalAbleton:
    def send_command(self, cmd, params=None):
        return {"ok": True}


# ── Default commit_branch_async result — shape lifted from engine.py:361 ─────

_DEFAULT_COMMIT_RESULT = {
    "committed": True,
    "branch_id": "b1",
    "branch_name": "test branch",
    "steps_executed": 2,
    "steps_failed": 0,
    "status": "committed",
    "score": 0.8,
    "execution_log": [
        {"tool": "set_track_volume", "backend": "remote_command", "ok": True, "result": {}},
        {"tool": "set_track_volume", "backend": "remote_command", "ok": True, "result": {}},
    ],
}


@pytest.fixture
def make_ctx(monkeypatch):
    """Factory fixture that builds a ctx with mocked ableton + experiment
    engine + composer escalator.

    Usage:
        ctx, exp, branch = make_ctx()                        # defaults
        ctx, exp, branch = make_ctx(branch=custom_branch)    # override branch
        ctx, exp, branch = make_ctx(commit_result=custom)    # override dispatch
    """

    def _factory(
        branch: Optional[_FakeBranch] = None,
        commit_result: Optional[dict] = None,
    ):
        branch = branch or _FakeBranch()
        experiment = _FakeExperiment(branch=branch)

        ctx = SimpleNamespace(
            lifespan_context={
                "ableton": _MinimalAbleton(),
                "m4l": None,
                "mcp_dispatch": {},
            },
        )

        # Patch engine.get_experiment + engine.commit_branch_async
        from mcp_server.experiment import engine
        monkeypatch.setattr(engine, "get_experiment", lambda eid: experiment)

        result = (
            dict(commit_result) if commit_result is not None
            else dict(_DEFAULT_COMMIT_RESULT)
        )
        result.setdefault("branch_id", branch.branch_id)
        result.setdefault("branch_name", branch.name)

        async def _fake_commit(*args, **kwargs):
            return result

        monkeypatch.setattr(engine, "commit_branch_async", _fake_commit)

        # Patch composer.escalate_composer_branch so composer-sourced
        # branches' engine tag can be exercised without invoking the real
        # composer pipeline. ``ok: False`` makes commit_experiment fall
        # through to committing the scaffold — exactly the path the
        # "engine tag reflects SOURCE, not escalation success" assertion
        # needs to exercise.
        try:
            from mcp_server import composer as composer_pkg
        except ImportError:
            composer_pkg = None

        async def _fake_escalate(**kwargs):
            return {"ok": False, "error": "test harness", "warnings": []}

        if composer_pkg is not None and hasattr(
            composer_pkg, "escalate_composer_branch"
        ):
            monkeypatch.setattr(
                composer_pkg, "escalate_composer_branch", _fake_escalate
            )

        return ctx, experiment, branch

    return _factory


# ── Tests ────────────────────────────────────────────────────────────────────


class TestCommitExperimentLedgerWrite:
    """v1.21: commit_experiment writes a LedgerEntry after a successful
    commit. Shape mirrors ``apply_semantic_move``'s ledger pattern (v1.20
    commit 0b3489b). Key difference from apply: engine_tag reflects branch
    SOURCE, not escalation success — a composer-sourced branch that fell
    back to the scaffold is still an ``engine="composer"`` commit, because
    the escalation-success detail is captured in
    ``target.evaluation["composer_escalation"]`` and the engine tag
    doubling up on that would be noise for anti-repetition filters."""

    def test_commit_populates_ledger(self, make_ctx):
        from mcp_server.experiment.tools import commit_experiment
        ctx, exp, branch = make_ctx()
        result = asyncio.run(commit_experiment(
            ctx, exp.experiment_id, branch.branch_id,
        ))
        assert result.get("committed") is True, result
        ledger: SessionLedger = ctx.lifespan_context["action_ledger"]
        last = ledger.get_last_move()
        assert last is not None, (
            "ledger should contain the just-committed experiment"
        )

    def test_engine_tag_experiment_for_non_composer_branch(self, make_ctx):
        from mcp_server.experiment.tools import commit_experiment
        seed = _FakeSeed(source="wonder", family="mix")
        branch = _FakeBranch(seed=seed)
        ctx, exp, _ = make_ctx(branch=branch)
        asyncio.run(commit_experiment(
            ctx, exp.experiment_id, branch.branch_id,
        ))
        last = ctx.lifespan_context["action_ledger"].get_last_move()
        assert last.engine == "experiment", (
            f"expected engine=experiment for non-composer branch, got {last.engine!r}"
        )

    def test_engine_tag_composer_for_composer_sourced_branch(self, make_ctx):
        """Composer-sourced branches tag as engine=composer regardless of
        escalation-success outcome. The fake escalator returns ok=False,
        so this exercises the fallback path — proving the tag comes from
        seed.source, not from the escalation outcome."""
        from mcp_server.experiment.tools import commit_experiment
        seed = _FakeSeed(
            source="composer",
            family="arrangement",
            producer_payload={"intent": "dummy"},  # triggers escalation path
        )
        branch = _FakeBranch(seed=seed)
        ctx, exp, _ = make_ctx(branch=branch)
        asyncio.run(commit_experiment(
            ctx, exp.experiment_id, branch.branch_id,
        ))
        last = ctx.lifespan_context["action_ledger"].get_last_move()
        assert last.engine == "composer", (
            "composer-sourced branch must tag as engine=composer "
            "regardless of escalation-success outcome"
        )

    def test_move_class_from_seed_family(self, make_ctx):
        from mcp_server.experiment.tools import commit_experiment
        seed = _FakeSeed(source="wonder", family="sound_design")
        branch = _FakeBranch(seed=seed)
        ctx, exp, _ = make_ctx(branch=branch)
        asyncio.run(commit_experiment(
            ctx, exp.experiment_id, branch.branch_id,
        ))
        last = ctx.lifespan_context["action_ledger"].get_last_move()
        assert last.move_class == "sound_design"

    def test_records_each_successful_step(self, make_ctx):
        """Default _DEFAULT_COMMIT_RESULT has 2 ok steps in execution_log;
        ledger should carry 2 action entries (one per ok row)."""
        from mcp_server.experiment.tools import commit_experiment
        ctx, exp, branch = make_ctx()
        asyncio.run(commit_experiment(
            ctx, exp.experiment_id, branch.branch_id,
        ))
        last = ctx.lifespan_context["action_ledger"].get_last_move()
        assert len(last.actions) == 2, (
            f"expected 2 actions (matching 2 ok execution_log entries), "
            f"got {len(last.actions)}: {last.actions!r}"
        )

    def test_kept_true_when_all_steps_ok(self, make_ctx):
        from mcp_server.experiment.tools import commit_experiment
        ctx, exp, branch = make_ctx()
        asyncio.run(commit_experiment(
            ctx, exp.experiment_id, branch.branch_id,
        ))
        last = ctx.lifespan_context["action_ledger"].get_last_move()
        assert last.kept is True
        assert last.score == 1.0, (
            f"expected score=1.0 (2/2 ok), got {last.score}"
        )

    def test_response_includes_ledger_entry_id(self, make_ctx):
        """Callers correlate the MCP response with the ledger entry via
        the returned ledger_entry_id — same pattern as apply_semantic_move."""
        from mcp_server.experiment.tools import commit_experiment
        ctx, exp, branch = make_ctx()
        result = asyncio.run(commit_experiment(
            ctx, exp.experiment_id, branch.branch_id,
        ))
        assert "ledger_entry_id" in result, (
            f"expected ledger_entry_id in response, got keys: {sorted(result.keys())}"
        )
        ledger = ctx.lifespan_context["action_ledger"]
        assert ledger.get_entry(result["ledger_entry_id"]) is not None

    def test_commit_on_rejected_branch_does_NOT_write_ledger(self, make_ctx):
        """Rejected / analytical / failed branches short-circuit before
        commit_branch_async is called. No ledger write should happen on
        these pre-commit-rejection paths."""
        from mcp_server.experiment.tools import commit_experiment
        branch = _FakeBranch(status="rejected")
        ctx, exp, _ = make_ctx(branch=branch)
        result = asyncio.run(commit_experiment(
            ctx, exp.experiment_id, branch.branch_id,
        ))
        assert "error" in result, (
            "rejected-branch guard should surface an error response"
        )
        # Either no action_ledger was populated OR it's empty — the
        # functional assertion is "no move recorded."
        ledger = ctx.lifespan_context.get("action_ledger") or SessionLedger()
        assert ledger.get_last_move() is None

    def test_ledger_write_failure_does_not_fail_commit(self, make_ctx, monkeypatch):
        """Simulate SessionLedger.start_move raising — commit must still
        return the normal success payload (just without ledger_entry_id).
        The ledger write is best-effort and its failure must NEVER abort
        a committed experiment."""
        from mcp_server.experiment.tools import commit_experiment

        def _boom(self, *a, **kw):
            raise RuntimeError("simulated ledger failure")

        monkeypatch.setattr(SessionLedger, "start_move", _boom)

        ctx, exp, branch = make_ctx()
        result = asyncio.run(commit_experiment(
            ctx, exp.experiment_id, branch.branch_id,
        ))
        assert result.get("committed") is True, (
            f"ledger failure must not fail the commit; got: {result}"
        )
        assert "ledger_entry_id" not in result, (
            "when the ledger write fails, ledger_entry_id must be absent"
        )
