"""Integration test: the creative-director SKILL.md Phase 6 decision
table must stay in sync with the registered semantic moves.

This prevents doc drift — a common failure mode after v1.19 when the
SKILL and registry accumulated separately. Every NEW move in the
decision table must exist as a registered semantic move; conversely,
every v1.20 move must appear in the table so Phase 6 is actually the
default surface for it.

The test parses the SKILL.md Phase 6 decision table by regex and
compares against the registry.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import mcp_server.semantic_moves  # noqa: F401 — triggers registrations
from mcp_server.semantic_moves import registry


_REPO_ROOT = Path(__file__).resolve().parent.parent
_SKILL_MD = _REPO_ROOT / "livepilot" / "skills" / "livepilot-creative-director" / "SKILL.md"
_PHASE6_DOC = _REPO_ROOT / "livepilot" / "skills" / "livepilot-creative-director" / "references" / "phase-6-execution.md"


# The 10 v1.20 moves — source of truth for the decision table.
V1_20_MOVES: frozenset[str] = frozenset({
    # routing
    "build_send_chain",
    "configure_send_architecture",
    "set_track_routing",
    # device-mutation
    "configure_device",
    "remove_device",
    # content
    "load_chord_source",
    "create_drum_rack_pad",
    # metadata
    "configure_groove",
    "set_scene_metadata",
    "set_track_metadata",
})


def _skill_md_text() -> str:
    assert _SKILL_MD.exists(), f"SKILL.md not found at {_SKILL_MD}"
    return _SKILL_MD.read_text(encoding="utf-8")


def _phase6_ref_text() -> str:
    assert _PHASE6_DOC.exists(), f"phase-6-execution.md not found at {_PHASE6_DOC}"
    return _PHASE6_DOC.read_text(encoding="utf-8")


def _extract_decision_table_move_ids(text: str) -> set[str]:
    """Extract move_ids from the Phase 6 decision table.

    Looks for backtick-quoted identifiers that also appear in the
    registry. Markdown table cells can wrap identifiers in backticks;
    we filter to those that match a real registered move.
    """
    all_registered = set(registry._REGISTRY.keys())
    # All backtick-quoted tokens
    candidates = re.findall(r"`([a-zA-Z_][a-zA-Z_0-9]*)`", text)
    return {c for c in candidates if c in all_registered}


class TestDirectorMoveCoverage:
    def test_all_v1_20_moves_appear_in_skill_md(self):
        """Every new move must be name-dropped somewhere in SKILL.md
        Phase 6 — otherwise the director can't discover it."""
        text = _skill_md_text()
        mentioned = _extract_decision_table_move_ids(text)
        missing = V1_20_MOVES - mentioned
        assert not missing, (
            f"v1.20 moves not mentioned in SKILL.md Phase 6: {sorted(missing)}. "
            "Add each to the decision table or reference them in the text."
        )

    def test_all_v1_20_moves_have_full_contract_in_phase6_ref(self):
        """Every new move must have a full contract in
        phase-6-execution.md — seed_args shape, steps, risk, family."""
        text = _phase6_ref_text()
        mentioned = _extract_decision_table_move_ids(text)
        missing = V1_20_MOVES - mentioned
        assert not missing, (
            f"v1.20 moves missing full contract in phase-6-execution.md: "
            f"{sorted(missing)}"
        )

    def test_skill_md_phase6_mentions_escape_hatch(self):
        """Phase 6 MUST document the escape hatch policy — otherwise
        the phased-cutover intent is lost and agents don't know what
        to do for uncovered patterns."""
        text = _skill_md_text()
        assert "escape hatch" in text.lower() or "escape_hatch" in text.lower(), (
            "SKILL.md Phase 6 has no 'escape hatch' mention. "
            "The v1.20 phased cutover requires explicit hatch documentation."
        )

    def test_skill_md_phase6_mandates_both_memory_categories_for_hatch(self):
        """Escape hatch requires BOTH move_executed AND tech_debt logs.
        Collapsing them into one breaks the contract — they serve
        different consumers (anti-repetition vs release planning)."""
        text = _skill_md_text()
        assert "move_executed" in text, "SKILL.md missing move_executed category reference"
        assert "tech_debt" in text, "SKILL.md missing tech_debt category reference"

    def test_skill_md_phase6_documents_apply_semantic_move_as_default(self):
        text = _skill_md_text()
        # Phase 6 should call out apply_semantic_move as the preferred path.
        assert "apply_semantic_move" in text, (
            "SKILL.md Phase 6 never mentions apply_semantic_move — the v1.20 "
            "default execution surface."
        )
        # And should also reference commit_experiment as the other default.
        assert "commit_experiment" in text

    def test_phase6_ref_documents_affordance_integration(self):
        """phase-6-execution.md must explain how affordance presets
        feed into configure_device's param_overrides — otherwise v1.21's
        preset library has no integration path."""
        text = _phase6_ref_text()
        assert "affordance" in text.lower(), (
            "phase-6-execution.md doesn't explain affordance integration"
        )
        assert "configure_device" in text
        assert "param_overrides" in text


class TestRegistryMatchesDecisionTable:
    def test_no_decision_table_entry_without_registered_move(self):
        """Every move_id mentioned in SKILL.md Phase 6 as a v1.20+ entry
        must be registered. Catches SKILL-ahead-of-code doc drift."""
        text = _skill_md_text()
        # Parse the table row by row for any entry marked NEW
        all_registered = set(registry._REGISTRY.keys())
        for match in re.finditer(
            r"`([a-zA-Z_][a-zA-Z_0-9]*)`[^|]*\| NEW", text
        ):
            move_id = match.group(1)
            assert move_id in all_registered, (
                f"SKILL.md Phase 6 marks `{move_id}` as NEW but no such "
                f"move is registered. Either register it or update the table."
            )

    def test_every_registered_v1_20_move_has_compiler(self):
        """No v1.20 move should fall through to the 'no compiler' warning."""
        from mcp_server.semantic_moves import compiler as move_compiler
        for move_id in V1_20_MOVES:
            move = registry.get_move(move_id)
            assert move is not None, f"v1.20 move {move_id} not registered"
            plan = move_compiler.compile(move, {"seed_args": {}, "session_info": {}, "mode": "improve"})
            fallback = [w for w in plan.warnings if "No compiler" in w]
            assert not fallback, f"{move_id}: {fallback}"
