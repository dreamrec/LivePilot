"""Tests for the new branch-native types (PR1).

Structural tests only — types have no behavior beyond construction,
serialization, and property delegation. PR1 introduces no edits to
existing modules, so the surface area is the new types alone.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.branches import (
    BranchSeed,
    CompiledBranch,
    seed_from_move_id,
    freeform_seed,
    analytical_seed,
)


# ── BranchSeed ──────────────────────────────────────────────────────────

class TestBranchSeedDefaults:

    def test_required_fields(self):
        seed = BranchSeed(seed_id="s1", source="freeform")
        assert seed.seed_id == "s1"
        assert seed.source == "freeform"

    def test_empty_defaults(self):
        seed = BranchSeed(seed_id="s1", source="freeform")
        assert seed.move_id == ""
        assert seed.hypothesis == ""
        assert seed.protected_qualities == []
        assert seed.affected_scope == {}
        assert seed.distinctness_reason == ""
        assert seed.risk_label == "low"
        assert seed.novelty_label == "strong"
        assert seed.analytical_only is False

    def test_list_and_dict_defaults_are_independent(self):
        # Regression guard — mutable defaults must use field(default_factory).
        a = BranchSeed(seed_id="a", source="freeform")
        b = BranchSeed(seed_id="b", source="freeform")
        a.protected_qualities.append("brightness")
        a.affected_scope["track"] = 3
        assert b.protected_qualities == []
        assert b.affected_scope == {}

    def test_to_dict_roundtrip(self):
        seed = BranchSeed(
            seed_id="s1",
            source="synthesis",
            move_id="",
            hypothesis="Fatten Wavetable pad",
            protected_qualities=["brightness"],
            affected_scope={"track_indices": [2, 3]},
            distinctness_reason="only seed touching Wavetable",
            risk_label="medium",
            novelty_label="unexpected",
        )
        d = seed.to_dict()
        assert d["seed_id"] == "s1"
        assert d["source"] == "synthesis"
        assert d["hypothesis"] == "Fatten Wavetable pad"
        assert d["protected_qualities"] == ["brightness"]
        assert d["affected_scope"] == {"track_indices": [2, 3]}
        assert d["risk_label"] == "medium"
        assert d["novelty_label"] == "unexpected"


# ── Factory helpers ─────────────────────────────────────────────────────

class TestSeedFromMoveId:

    def test_stable_id_for_same_inputs(self):
        s1 = seed_from_move_id("make_punchier")
        s2 = seed_from_move_id("make_punchier")
        assert s1.seed_id == s2.seed_id

    def test_different_novelty_produces_different_ids(self):
        s1 = seed_from_move_id("widen_pad", novelty_label="safe")
        s2 = seed_from_move_id("widen_pad", novelty_label="unexpected")
        assert s1.seed_id != s2.seed_id

    def test_source_and_move_id_populated(self):
        seed = seed_from_move_id("make_punchier")
        assert seed.source == "semantic_move"
        assert seed.move_id == "make_punchier"

    def test_default_hypothesis_derives_from_move_id(self):
        seed = seed_from_move_id("make_punchier")
        assert seed.hypothesis == "Apply make_punchier"

    def test_overrides_respected(self):
        seed = seed_from_move_id(
            "widen_pad",
            seed_id="custom",
            hypothesis="Stretch width on the sustained pad",
            novelty_label="unexpected",
            risk_label="high",
            protected_qualities=["brightness"],
            distinctness_reason="width vs the brightness-focused sibling",
        )
        assert seed.seed_id == "custom"
        assert seed.hypothesis == "Stretch width on the sustained pad"
        assert seed.novelty_label == "unexpected"
        assert seed.risk_label == "high"
        assert "brightness" in seed.protected_qualities
        assert seed.distinctness_reason.startswith("width vs")


class TestFreeformSeed:

    def test_has_no_move_id(self):
        seed = freeform_seed(
            seed_id="alt_1",
            hypothesis="Modulate filter cutoff with audio-rate LFO",
            affected_scope={"track_indices": [3]},
        )
        assert seed.source == "freeform"
        assert seed.move_id == ""

    def test_defaults(self):
        seed = freeform_seed(seed_id="s", hypothesis="h")
        assert seed.affected_scope == {}
        assert seed.protected_qualities == []
        assert seed.risk_label == "medium"
        assert seed.novelty_label == "strong"

    def test_source_override(self):
        seed = freeform_seed(seed_id="s", hypothesis="h", source="synthesis")
        assert seed.source == "synthesis"


class TestAnalyticalSeed:

    def test_flag_set(self):
        seed = analytical_seed(
            seed_id="directional_1",
            hypothesis="Consider reducing reverb mix to tighten mids",
        )
        assert seed.analytical_only is True

    def test_source_defaults_to_freeform(self):
        seed = analytical_seed(seed_id="d", hypothesis="h")
        assert seed.source == "freeform"


# ── CompiledBranch ──────────────────────────────────────────────────────

class TestCompiledBranchAnalyticalPredicate:

    def test_analytical_when_no_plan(self):
        seed = seed_from_move_id("make_punchier")
        branch = CompiledBranch(branch_id="b1", seed=seed)
        assert branch.analytical_only is True
        assert branch.compiled_plan is None

    def test_analytical_when_seed_flagged_even_with_plan(self):
        seed = analytical_seed("s1", "directional")
        branch = CompiledBranch(
            branch_id="b1",
            seed=seed,
            compiled_plan={"steps": [], "summary": "noop"},
        )
        # Seed flag wins — analytical_only intent trumps a stray plan.
        assert branch.analytical_only is True

    def test_executable_when_plan_present_and_seed_not_flagged(self):
        seed = seed_from_move_id("make_punchier")
        branch = CompiledBranch(
            branch_id="b1",
            seed=seed,
            compiled_plan={"steps": [], "summary": "ok", "step_count": 0},
        )
        assert branch.analytical_only is False


class TestCompiledBranchMoveIdDelegation:

    def test_move_id_from_semantic_seed(self):
        seed = seed_from_move_id("widen_pad")
        branch = CompiledBranch(branch_id="b1", seed=seed)
        assert branch.move_id == "widen_pad"

    def test_move_id_empty_for_freeform_seed(self):
        seed = freeform_seed(seed_id="f", hypothesis="h")
        branch = CompiledBranch(branch_id="b1", seed=seed)
        assert branch.move_id == ""


class TestCompiledBranchToDict:

    def test_full_shape(self):
        seed = seed_from_move_id("make_punchier", hypothesis="Pump mid dynamics")
        branch = CompiledBranch(
            branch_id="b1",
            seed=seed,
            compiled_plan={
                "steps": [{"tool": "plan_mix_move"}],
                "step_count": 1,
                "summary": "pump",
            },
            execution_log=[
                {"ok": True, "tool": "plan_mix_move", "backend": "mcp_tool"},
                {"ok": False, "tool": "analyze_mix", "error": "boom"},
            ],
            score=0.72,
            status="evaluated",
            created_at_ms=111,
        )
        d = branch.to_dict()
        assert d["branch_id"] == "b1"
        assert d["move_id"] == "make_punchier"
        assert d["score"] == 0.72
        assert d["status"] == "evaluated"
        assert d["analytical_only"] is False
        assert d["step_count"] == 1
        assert d["summary"] == "pump"
        assert d["steps_ok"] == 1
        assert d["steps_failed"] == 1
        assert d["seed"]["move_id"] == "make_punchier"
        assert d["seed"]["hypothesis"] == "Pump mid dynamics"
        assert d["created_at_ms"] == 111

    def test_omits_empty_optionals(self):
        seed = seed_from_move_id("widen_pad")
        branch = CompiledBranch(branch_id="b1", seed=seed)
        d = branch.to_dict()
        assert "before_snapshot" not in d
        assert "after_snapshot" not in d
        assert "evaluation" not in d
        assert "execution_log" not in d
        assert "summary" not in d  # no compiled_plan

    def test_interesting_but_failed_status_accepted(self):
        # PR7 will introduce this status for exploration branches; PR1 just
        # ensures the field accepts the string without complaint.
        seed = seed_from_move_id("widen_pad")
        branch = CompiledBranch(
            branch_id="b1",
            seed=seed,
            status="interesting_but_failed",
        )
        assert branch.to_dict()["status"] == "interesting_but_failed"


# ── Module-level imports ────────────────────────────────────────────────

def test_public_api_exported_from_package():
    # All factory helpers and types importable from mcp_server.branches
    from mcp_server.branches import (
        BranchSeed,
        CompiledBranch,
        BranchSource,
        RiskLabel,
        NoveltyLabel,
        seed_from_move_id,
        freeform_seed,
        analytical_seed,
    )
    assert BranchSeed is not None
    assert CompiledBranch is not None
