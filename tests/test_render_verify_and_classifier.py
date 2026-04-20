"""Tests for render-based verification + fingerprint→classifier wiring (PR4/5).

Covers:
  - BranchSnapshot serializes the new render-verify fields (capture_path,
    loudness, spectral_shape, fingerprint)
  - derive_goal_progress_from_fingerprint: signed vs unsigned progress
  - classify_branch_outcome accepts fingerprint_diff and derives
    measurable_count / goal_progress when the caller didn't supply them
  - Targeted diffs score positive when moving in the target direction
  - Empty / noise-floor diffs contribute zero measurable_count

PR4's run_experiment wiring is integration-tested via mocking the capture
path; end-to-end capture_audio testing requires a running Ableton + M4L
bridge and is out of scope for unit tests.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.evaluation.policy import (
    classify_branch_outcome,
    derive_goal_progress_from_fingerprint,
)
from mcp_server.experiment.models import BranchSnapshot


# ── BranchSnapshot shape ─────────────────────────────────────────────────


class TestBranchSnapshotFields:

    def test_fingerprint_field_defaults_none(self):
        snap = BranchSnapshot()
        assert snap.fingerprint is None
        assert snap.capture_path is None
        assert snap.loudness is None
        assert snap.spectral_shape is None

    def test_to_dict_omits_absent_render_fields(self):
        snap = BranchSnapshot(rms=0.2, peak=0.5)
        d = snap.to_dict()
        assert "fingerprint" not in d
        assert "capture_path" not in d
        assert "loudness" not in d
        assert "spectral_shape" not in d
        assert d["rms"] == 0.2

    def test_to_dict_includes_present_render_fields(self):
        snap = BranchSnapshot(
            capture_path="/tmp/capture.wav",
            loudness={"integrated_lufs": -14.3, "lra_lu": 3.5},
            spectral_shape={"centroid": 1800, "flatness": 0.12},
            fingerprint={"brightness": 0.4, "warmth": 0.2},
        )
        d = snap.to_dict()
        assert d["capture_path"] == "/tmp/capture.wav"
        assert d["loudness"]["integrated_lufs"] == -14.3
        assert d["spectral_shape"]["centroid"] == 1800
        assert d["fingerprint"]["brightness"] == 0.4


# ── Fingerprint diff → goal progress derivation ─────────────────────────


class TestDeriveGoalProgress:

    def test_empty_diff_returns_zero(self):
        progress, count = derive_goal_progress_from_fingerprint({})
        assert progress == 0.0
        assert count == 0

    def test_noise_floor_diffs_not_counted(self):
        # Diffs under 0.02 epsilon are dropped as noise.
        diff = {"brightness": 0.005, "warmth": -0.01, "bite": 0.015}
        progress, count = derive_goal_progress_from_fingerprint(diff)
        assert count == 0
        assert progress == 0.0

    def test_untargeted_diff_counts_magnitude_as_progress(self):
        diff = {"brightness": 0.4, "warmth": -0.3}
        progress, count = derive_goal_progress_from_fingerprint(diff)
        assert count == 2
        # Unsigned magnitude * 0.5 contribution: 0.4 * 0.5 + 0.3 * 0.5 = 0.35
        assert 0.3 < progress < 0.4

    def test_targeted_positive_direction_scores_positive(self):
        diff = {"brightness": 0.4, "warmth": -0.3}
        target = {"brightness": 0.5, "warmth": 0.0, "bite": 0.0}
        progress, count = derive_goal_progress_from_fingerprint(diff, target=target)
        # Only "brightness" is targeted; warmth target is 0. Direction
        # of brightness target (+1) * diff (+0.4) = +0.4 progress.
        assert count == 1
        assert progress > 0.3

    def test_targeted_wrong_direction_scores_negative(self):
        diff = {"brightness": 0.4, "warmth": -0.3}
        # Target wanted DARKER (negative brightness), branch went brighter.
        target = {"brightness": -0.5}
        progress, count = derive_goal_progress_from_fingerprint(diff, target=target)
        assert count == 1
        assert progress < 0  # moved wrong direction

    def test_target_with_zero_dimension_is_ignored(self):
        # "warmth" target = 0 means caller didn't care; the diff's warmth
        # movement shouldn't contribute to measurable_count.
        diff = {"brightness": 0.5, "warmth": 0.4}
        target = {"brightness": 0.5, "warmth": 0.0}
        progress, count = derive_goal_progress_from_fingerprint(diff, target=target)
        assert count == 1  # only brightness counted


# ── Classifier integration ──────────────────────────────────────────────


class TestClassifierFingerprintIntegration:

    def test_fingerprint_diff_makes_unmeasurable_case_measurable(self):
        # Without fingerprint_diff: measurable_count=0 means rule 1 defers
        # and score < 0.4 still forces undo (PR7 classifier change). But
        # with a fingerprint_diff, the classifier derives measurable_count
        # and goal_progress — now it's evaluated on real evidence.
        diff = {"brightness": 0.3, "warmth": 0.2}
        target = {"brightness": 0.5, "warmth": 0.3}
        outcome = classify_branch_outcome(
            score=0.6,
            fingerprint_diff=diff,
            timbral_target=target,
        )
        # Derived positive progress, positive score → keep.
        assert outcome.status == "keep"

    def test_caller_supplied_measurable_inputs_take_precedence(self):
        # When the caller passes measurable_count explicitly, the classifier
        # uses that and does NOT derive from fingerprint. Keeps back-compat.
        diff = {"brightness": 0.4}
        outcome = classify_branch_outcome(
            score=0.6,
            measurable_count=5,       # explicit
            target_count=5,
            goal_progress=-2.0,       # explicit negative
            fingerprint_diff=diff,     # present but ignored
        )
        # goal_progress < 0 with measurable_count > 0 → rule 3 failure.
        assert outcome.status == "undo"

    def test_fingerprint_diff_wrong_direction_with_low_score_undoes(self):
        # Branch moved away from the target AND score is below threshold.
        diff = {"brightness": 0.5}
        target = {"brightness": -0.8}
        outcome = classify_branch_outcome(
            score=0.35,
            fingerprint_diff=diff,
            timbral_target=target,
        )
        # Derived goal_progress is negative, score < 0.4 threshold.
        # Status: undo (technical mode).
        assert outcome.status == "undo"
        assert outcome.keep_change is False

    def test_fingerprint_evidence_interesting_but_failed_in_exploration(self):
        # Same wrong-direction case, but exploration mode retains for audit.
        diff = {"brightness": 0.5}
        target = {"brightness": -0.8}
        outcome = classify_branch_outcome(
            score=0.35,
            fingerprint_diff=diff,
            timbral_target=target,
            exploration_rules=True,
        )
        assert outcome.status == "interesting_but_failed"

    def test_no_fingerprint_diff_preserves_pre_pr4_behavior(self):
        # Without fingerprint_diff, the classifier does what it did
        # pre-PR4 — scores alone + meter heuristics.
        outcome = classify_branch_outcome(score=0.2)
        assert outcome.status == "undo"

    def test_protection_violation_still_trumps_fingerprint_evidence(self):
        # Safety invariant from PR7: protection violation always forces
        # undo regardless of fingerprint diff or exploration mode.
        diff = {"brightness": 0.8}  # big positive move
        target = {"brightness": 0.5}
        outcome = classify_branch_outcome(
            score=0.9,
            protection_violated=True,
            fingerprint_diff=diff,
            timbral_target=target,
            exploration_rules=True,
        )
        assert outcome.status == "undo"
        assert any("protected" in f.lower() for f in outcome.failure_reasons)
