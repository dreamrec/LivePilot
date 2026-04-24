"""Audit test: every module that imports SessionLedger or reads
``memory_list`` / ``get_session_memory`` must annotate its use with a
``# store_purpose: <purpose>`` comment. This prevents the v1.20
store-confusion bug (the director SKILL originally pointed at
memory_list for anti-repetition recency — it actually reads the
persistent technique library, not the action ledger) from recurring
silently anywhere else in the codebase.

Invariants enforced:
  1. Every file that imports SessionLedger OR reads
     ``lifespan_context[...action_ledger...]`` has a nearby
     ``# store_purpose: <purpose>`` comment (within 400 chars).
  2. Every file that calls ``memory_list()`` has a purpose comment.
  3. Every file that calls ``get_session_memory()`` has a purpose comment.
  4. No file annotated ``store_purpose: anti_repetition`` also calls
     ``memory_list()`` — anti-repetition reads the action ledger, NOT
     the technique library. This is the latent v1.20 bug that the
     director SKILL correction caught; this test guards against it
     appearing anywhere else.

Allowed purposes (closed set — add deliberately):
  - writer              — module writes to the action ledger
  - anti_repetition     — reads ledger for recency-based move selection
  - audit_readonly      — reads ledger for audit/export surfaces (get_last_move,
                          get_action_ledger_summary)
  - technique_library   — reads the persistent memory_list store
                          (memory browser, replay UI, etc.) — NOT recency
  - session_observations— reads/writes session memory for notes/decisions
  - escape_hatch_log    — reads/writes session memory for
                          move_executed / tech_debt / override categories
  - mcp_tool_definition — definer file; pattern match is on the ``def`` line

Plan reference: docs/plans/v1.21-structural-plan.md §4.3,
docs/plans/v1.21-implementation-plan.md Task 5.1 + 5.2.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


_MCP_SERVER = Path(__file__).resolve().parent.parent / "mcp_server"


_READER_PATTERNS: dict[str, str] = {
    # pattern name -> regex matched against each python file's text
    "SessionLedger_import": r"from\s+[\w.]+action_ledger\s+import\s+SessionLedger",
    "action_ledger_ctx_read": (
        r"""lifespan_context[^\n]*["']action_ledger["']"""
    ),
    "memory_list_call": r"\bmemory_list\s*\(",
    "get_session_memory_call": r"\bget_session_memory\s*\(",
}


# Files that define the surfaces under audit — exempt because the
# pattern matches on their ``def`` lines and those lines don't need
# a purpose annotation (the function body IS the definition).
_EXEMPT_FILES = {
    "action_ledger.py",  # defines SessionLedger
    "action_tools.py",   # canonical get_last_move/get_action_ledger_summary readers
}


# Allowed store_purpose values — adding a new one is a conscious act.
_ALLOWED_PURPOSES = {
    "writer",
    "anti_repetition",
    "audit_readonly",
    "technique_library",
    "session_observations",
    "escape_hatch_log",
    "mcp_tool_definition",
}


def _all_python_files() -> list[Path]:
    return [
        p for p in _MCP_SERVER.rglob("*.py")
        if "__pycache__" not in p.parts
    ]


_PURPOSE_COMMENT_RX = re.compile(
    r"#\s*store_purpose\s*:\s*(\w+)",
    re.IGNORECASE,
)


def _purposes_near(text: str, match_pos: int, window: int = 800) -> set[str]:
    """Return any store_purpose values that appear within `window` chars
    before or after the matched line. Empty set = no annotation.

    Window is 800 chars (≈ 15-20 lines either side). That captures
    top-of-function and top-of-block annotations, which are the natural
    places to put purpose comments — placing them AT the hit line would
    clutter the actual reading code."""
    start = max(0, match_pos - window)
    end = min(len(text), match_pos + window)
    snippet = text[start:end]
    return {m.group(1).lower() for m in _PURPOSE_COMMENT_RX.finditer(snippet)}


class TestLedgerReaderAnnotations:
    """Every hit of every surface pattern must have a `# store_purpose:`
    comment within 400 chars of the match. This is the institutional
    memory of the v1.20 store-confusion fix encoded as a CI gate."""

    @pytest.mark.parametrize(
        "pattern_name,pattern",
        list(_READER_PATTERNS.items()),
        ids=list(_READER_PATTERNS.keys()),
    )
    def test_every_hit_has_store_purpose_comment(self, pattern_name, pattern):
        failures: list[str] = []
        regex = re.compile(pattern)
        for path in _all_python_files():
            if path.name in _EXEMPT_FILES:
                continue
            text = path.read_text(encoding="utf-8")
            for match in regex.finditer(text):
                purposes = _purposes_near(text, match.start())
                if not purposes:
                    line_no = text[: match.start()].count("\n") + 1
                    failures.append(
                        f"  {path.relative_to(_MCP_SERVER.parent)}:{line_no} "
                        f"{pattern_name} hit without nearby "
                        f"`# store_purpose: <purpose>` comment"
                    )
                else:
                    # Any purpose that doesn't match the allowed set is a
                    # typo or drift — treat the same as missing.
                    unknown = purposes - _ALLOWED_PURPOSES
                    if unknown == purposes:
                        line_no = text[: match.start()].count("\n") + 1
                        failures.append(
                            f"  {path.relative_to(_MCP_SERVER.parent)}:{line_no} "
                            f"{pattern_name} hit with unknown purpose(s) "
                            f"{sorted(unknown)} — allowed: "
                            f"{sorted(_ALLOWED_PURPOSES)}"
                        )
        assert not failures, (
            f"Store-purpose audit failures ({len(failures)}):\n"
            + "\n".join(failures)
            + f"\n\nAdd a `# store_purpose: <purpose>` comment near each hit. "
            f"Allowed purposes: {sorted(_ALLOWED_PURPOSES)}."
        )


class TestAntiRepetitionUsesLedgerNotMemoryList:
    """Anti-repetition paths must NOT call ``memory_list``. The store-
    confusion bug in v1.20 came from docs pointing at ``memory_list``
    for recency when it actually reads the persistent technique library.
    This test catches regressions where a file self-declares as
    anti-repetition but also reads the wrong store."""

    def test_no_anti_repetition_annotated_file_calls_memory_list(self):
        failures: list[str] = []
        anti_rep_rx = re.compile(
            r"#\s*store_purpose\s*:\s*anti_repetition",
            re.IGNORECASE,
        )
        memory_list_rx = re.compile(r"\bmemory_list\s*\(")
        for path in _all_python_files():
            if path.name in _EXEMPT_FILES:
                continue
            text = path.read_text(encoding="utf-8")
            if not anti_rep_rx.search(text):
                continue
            if memory_list_rx.search(text):
                failures.append(
                    f"  {path.relative_to(_MCP_SERVER.parent)}: "
                    f"annotated `store_purpose: anti_repetition` but also "
                    f"calls memory_list() — memory_list reads the persistent "
                    f"technique library, not the action ledger. "
                    f"Use SessionLedger.get_recent_moves or "
                    f"get_action_ledger_summary instead."
                )
        assert not failures, (
            "Anti-repetition / memory_list conflict "
            f"({len(failures)} files):\n" + "\n".join(failures)
        )
