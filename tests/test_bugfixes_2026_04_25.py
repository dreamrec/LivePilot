"""Regression tests for bug fixes shipped 2026-04-25.

BUG-2026-04-25 #1: insert_rack_chain Remote Script handler did not
return `chain_index` in its response dict. The downstream caller
add_drum_rack_pad in mcp_server/tools/analyzer.py reads:

    chain_index = int(chain_result.get("chain_index",
                                        chain_result.get("index", 0)))

Both keys were absent, so chain_index defaulted to 0. This caused:
  - set_drum_chain_note(chain_0, new_pad_note) to overwrite the
    pre-existing kick chain's pad note
  - insert_device(Simpler, chain_index=0) to fail with "Device chains
    cannot have more than one instrument each" because chain 0 already
    had a Simpler

Symptom: add_drum_rack_pad worked for the FIRST pad on an empty rack
and silently corrupted state on every subsequent call.

Fix: remote_script/LivePilot/devices.py:insert_rack_chain now derives
and returns chain_index alongside chain_count.
"""

from __future__ import annotations

import os
import re


def _read_devices_source() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.dirname(here)
    path = os.path.join(repo, "remote_script", "LivePilot", "devices.py")
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _extract_insert_rack_chain_body() -> str:
    """Slice out the insert_rack_chain handler body from devices.py.

    Cannot import devices.py directly outside Ableton (`import Live`
    fails), so we slice the source text between the @register decorator
    and the next handler.
    """
    src = _read_devices_source()
    marker = '@register("insert_rack_chain")'
    start = src.index(marker)
    # Find the next @register or end-of-file
    next_marker = src.find("@register(", start + len(marker))
    end = next_marker if next_marker != -1 else len(src)
    return src[start:end]


def test_bug20260425_insert_rack_chain_returns_chain_index():
    """Response dict must include `chain_index` key — locks the contract
    that add_drum_rack_pad depends on.
    """
    body = _extract_insert_rack_chain_body()
    assert '"chain_index"' in body, (
        "insert_rack_chain response must include 'chain_index' — see "
        "BUG-2026-04-25 #1. Without it, add_drum_rack_pad falls back to "
        "chain_index=0 and overwrites the existing first chain instead "
        "of targeting the newly-inserted chain."
    )


def test_bug20260425_chain_index_derives_from_position_and_count():
    """The derivation logic must handle both append (position=-1) and
    explicit position. Append → chain_count - 1. Explicit position → N.
    """
    body = _extract_insert_rack_chain_body()
    # Look for the derivation expression. We accept any expression that
    # branches on position vs chain_count - 1; pin the structural intent
    # without over-fitting the formatting.
    has_derivation = bool(
        re.search(
            r"chain_index.*=.*position.*chain_count.*-.*1",
            body,
            flags=re.DOTALL,
        )
    )
    assert has_derivation, (
        "insert_rack_chain must derive chain_index from position + "
        "chain_count. Expected pattern: "
        "`new_chain_index = position if 0 <= position < chain_count "
        "else chain_count - 1`."
    )


def test_bug20260425_add_drum_rack_pad_caller_still_reads_chain_index():
    """The MCP-server caller in add_drum_rack_pad must read chain_index
    from the response (not just chain_count). If someone refactors the
    caller to drop the chain_index read, the fix is moot.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.dirname(here)
    path = os.path.join(repo, "mcp_server", "tools", "analyzer.py")
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    # The caller reads via chain_result.get("chain_index", ...).
    has_read = 'chain_result.get("chain_index"' in src
    assert has_read, (
        "add_drum_rack_pad must extract chain_index from the "
        "insert_rack_chain response — see BUG-2026-04-25 #1."
    )
