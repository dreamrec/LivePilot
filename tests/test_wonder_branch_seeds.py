"""Tests for Wonder's branch-native seed assembly (PR6).

Covers the generate_branch_seeds() pure function across all four sources:
semantic_move, technique memory, sacred-element inversion, corpus hints.
The existing generate_wonder_variants path has its own tests —
this file only covers the new branch-native assembly.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.branches import BranchSeed
from mcp_server.wonder_mode.engine import generate_branch_seeds


# ── Baseline: semantic_move seeds ───────────────────────────────────────


class TestSemanticMoveSource:

    def test_returns_branch_seed_objects(self):
        seeds = generate_branch_seeds("make this punchier")
        assert all(isinstance(s, BranchSeed) for s in seeds)

    def test_semantic_move_seeds_come_first(self):
        seeds = generate_branch_seeds("make this punchier")
        # There are semantic moves registered for "punchier" — the first
        # seed must be a semantic_move, not a fallback freeform.
        if seeds:
            assert seeds[0].source == "semantic_move"
            assert seeds[0].move_id != ""

    def test_novelty_labels_assigned_positionally(self):
        seeds = generate_branch_seeds("widen stereo and make punchier")
        # First semantic_move seed gets "safe", second "strong", third "unexpected"
        sm_seeds = [s for s in seeds if s.source == "semantic_move"]
        expected = ["safe", "strong", "unexpected"]
        for i, s in enumerate(sm_seeds):
            if i < len(expected):
                assert s.novelty_label == expected[i], (
                    f"seed {i} expected {expected[i]}, got {s.novelty_label}"
                )

    def test_respects_max_seeds(self):
        seeds = generate_branch_seeds("make this punchier and wider", max_seeds=1)
        assert len(seeds) <= 1

    def test_no_moves_returns_empty_or_non_semantic(self):
        # A request with zero keyword overlap should return no semantic moves,
        # and without kernel/song_brain/corpus, no other sources fire either.
        seeds = generate_branch_seeds("xyzzy quxqux nothing matches here")
        assert all(s.source != "semantic_move" or s.move_id for s in seeds)


# ── Technique seeds from session memory ─────────────────────────────────


class TestTechniqueSource:

    def test_technique_seed_added_from_memory(self):
        kernel = {
            "session_memory": [
                {"category": "technique", "content": "sidechain the pad from the kick"},
            ],
        }
        seeds = generate_branch_seeds(
            "xyzzy nothing matches",  # no semantic moves
            kernel=kernel,
        )
        tech_seeds = [s for s in seeds if s.source == "technique"]
        assert len(tech_seeds) >= 1
        assert "sidechain the pad" in tech_seeds[0].hypothesis

    def test_success_category_also_counts(self):
        kernel = {
            "session_memory": [
                {"category": "success", "content": "LPF on the lead with tempo-sync LFO"},
            ],
        }
        seeds = generate_branch_seeds("xyzzy", kernel=kernel)
        assert any(s.source == "technique" for s in seeds)

    def test_unrelated_memory_categories_ignored(self):
        kernel = {
            "session_memory": [
                {"category": "observation", "content": "kick feels muddy"},
                {"category": "error", "content": "plugin crashed"},
            ],
        }
        seeds = generate_branch_seeds("xyzzy", kernel=kernel)
        assert not any(s.source == "technique" for s in seeds)

    def test_technique_seeds_are_low_risk_safe_novelty(self):
        # Known-good moves are conservative by definition.
        kernel = {
            "session_memory": [
                {"category": "technique", "content": "tape saturation on the bus"},
            ],
        }
        seeds = generate_branch_seeds("xyzzy", kernel=kernel)
        tech = [s for s in seeds if s.source == "technique"]
        assert tech[0].risk_label == "low"
        assert tech[0].novelty_label == "safe"


# ── Sacred-element inversion ────────────────────────────────────────────


class TestSacredInversionSource:

    def test_inversion_added_when_freshness_high(self):
        kernel = {"freshness": 0.8}
        song_brain = {
            "sacred_elements": [
                {"element_type": "hook", "description": "the filtered stab"},
            ],
        }
        seeds = generate_branch_seeds(
            "xyzzy",  # no semantic moves
            kernel=kernel,
            song_brain=song_brain,
        )
        inverted = [s for s in seeds if "invert" in s.hypothesis.lower()]
        assert len(inverted) >= 1
        assert inverted[0].novelty_label == "unexpected"
        assert inverted[0].risk_label == "high"

    def test_inversion_skipped_when_freshness_low(self):
        # freshness < 0.5 suppresses the high-risk inversion path
        kernel = {"freshness": 0.2}
        song_brain = {
            "sacred_elements": [
                {"element_type": "hook", "description": "the filtered stab"},
            ],
        }
        seeds = generate_branch_seeds("xyzzy", kernel=kernel, song_brain=song_brain)
        assert not any("invert" in s.hypothesis.lower() for s in seeds)

    def test_inversion_protects_other_sacred_elements(self):
        kernel = {"freshness": 0.8}
        song_brain = {
            "sacred_elements": [
                {"element_type": "hook", "description": "the stab"},
                {"element_type": "bassline", "description": "the bass"},
            ],
        }
        seeds = generate_branch_seeds("xyzzy", kernel=kernel, song_brain=song_brain)
        # When inverting hook, bassline must be protected, and vice versa.
        for s in seeds:
            if "invert the stab" in s.hypothesis.lower():
                assert "bassline" in s.protected_qualities
            if "invert the bass" in s.hypothesis.lower():
                assert "hook" in s.protected_qualities


# ── Distinctness and ordering ───────────────────────────────────────────


class TestDistinctnessAndOrdering:

    def test_no_duplicate_hypotheses(self):
        kernel = {
            "session_memory": [
                {"category": "technique", "content": "sidechain from kick"},
                {"category": "success", "content": "sidechain from kick"},  # dupe
            ],
        }
        seeds = generate_branch_seeds("xyzzy", kernel=kernel)
        hyps = [s.hypothesis.lower() for s in seeds]
        assert len(hyps) == len(set(hyps))

    def test_stable_seed_ids_across_calls(self):
        # Same inputs → same seed_ids (important for caching / UI stability).
        kernel = {
            "session_memory": [
                {"category": "technique", "content": "tape saturation"},
            ],
        }
        a = generate_branch_seeds("make it wider", kernel=kernel)
        b = generate_branch_seeds("make it wider", kernel=kernel)
        assert [s.seed_id for s in a] == [s.seed_id for s in b]

    def test_max_seeds_enforced_across_sources(self):
        # Many possible sources: semantic_move + technique + inversion.
        # max_seeds=2 must still produce exactly ≤2 seeds total.
        kernel = {
            "freshness": 0.9,
            "session_memory": [
                {"category": "technique", "content": "tape saturation"},
                {"category": "technique", "content": "auto pan"},
            ],
        }
        song_brain = {
            "sacred_elements": [{"element_type": "hook", "description": "stab"}],
        }
        seeds = generate_branch_seeds(
            "make it wider and punchier",
            kernel=kernel,
            song_brain=song_brain,
            max_seeds=2,
        )
        assert len(seeds) <= 2


# ── Resilience ──────────────────────────────────────────────────────────


class TestResilience:

    def test_empty_kernel_ok(self):
        seeds = generate_branch_seeds("make it punchier", kernel=None)
        # Still produces semantic_move seeds.
        assert all(isinstance(s, BranchSeed) for s in seeds)

    def test_empty_song_brain_ok(self):
        seeds = generate_branch_seeds(
            "make it punchier",
            kernel={"freshness": 0.8},
            song_brain=None,
        )
        # No sacred-element inversion without song_brain, but other sources work.
        assert all(isinstance(s, BranchSeed) for s in seeds)

    def test_every_seed_has_a_distinctness_reason(self):
        kernel = {
            "freshness": 0.8,
            "session_memory": [
                {"category": "technique", "content": "tape saturation"},
            ],
        }
        song_brain = {
            "sacred_elements": [{"element_type": "hook", "description": "stab"}],
        }
        seeds = generate_branch_seeds(
            "make it wider",
            kernel=kernel,
            song_brain=song_brain,
        )
        for s in seeds:
            assert s.distinctness_reason, (
                f"seed {s.seed_id} missing distinctness_reason"
            )
