"""Tests for #13 — insert_rack_chain auto-increments in_note on drum racks.

Pure-Python contract tests via the established importlib.spec_from_file_location
pattern (bypasses _Framework). Mirrors the test setup in
test_bugfixes_2026_04_22.py and test_clip_length_invariants.py.
"""

from __future__ import annotations

import importlib.util
import os


def _load_drum_helpers():
    """Import _drum_helpers.py by file path, bypassing the package __init__."""
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.dirname(here)
    path = os.path.join(repo, "remote_script", "LivePilot", "_drum_helpers.py")
    spec = importlib.util.spec_from_file_location("_drum_helpers_std", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ── Fake DrumChain shape ──────────────────────────────────────────────


class _FakeChain:
    def __init__(self, in_note):
        self.in_note = in_note


class _FakeNonDrumChain:
    """An Instrument Rack chain — has no in_note attribute."""
    pass


class _FakeRack:
    def __init__(self, chains):
        self.chains = chains


# ── Tests ─────────────────────────────────────────────────────────────


def test_first_chain_returns_36():
    """Empty drum rack — first chain gets the standard kick slot."""
    fn = _load_drum_helpers()._next_drum_chain_note
    rack = _FakeRack([])
    assert fn(rack) == 36


def test_increments_above_highest_in_note():
    """Two chains at 36 and 38 — next slot should be 39."""
    fn = _load_drum_helpers()._next_drum_chain_note
    rack = _FakeRack([_FakeChain(36), _FakeChain(38)])
    assert fn(rack) == 39


def test_handles_non_sequential_notes():
    """Chains scattered across the keyboard — return max + 1."""
    fn = _load_drum_helpers()._next_drum_chain_note
    rack = _FakeRack([_FakeChain(60), _FakeChain(36), _FakeChain(96)])
    assert fn(rack) == 97


def test_clamps_to_127():
    """Chain at the top of the MIDI range — don't overflow."""
    fn = _load_drum_helpers()._next_drum_chain_note
    rack = _FakeRack([_FakeChain(127)])
    assert fn(rack) == 127


def test_returns_none_for_non_drum_rack():
    """Instrument Rack chains have no in_note — return None to skip."""
    fn = _load_drum_helpers()._next_drum_chain_note
    rack = _FakeRack([_FakeChain(36), _FakeNonDrumChain()])
    assert fn(rack) is None


def test_handles_missing_chains_attribute():
    """Defensive: device with no `chains` at all — return 36 (empty case)."""
    fn = _load_drum_helpers()._next_drum_chain_note

    class _NoChains:
        pass

    assert fn(_NoChains()) == 36
