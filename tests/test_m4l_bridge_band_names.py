"""Regression guard for T3 (sub_low band) from the 2026-04-22 handoff.

The M4L analyzer may emit either 8-band or 9-band spectrum payloads
depending on which frozen .amxd the user has loaded. The server side must
handle both without breaking: existing 8-band devices keep their names,
new 9-band devices get the sub_low key prepended.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from mcp_server.m4l_bridge import SpectralReceiver


def test_band_names_8_legacy_layout_unchanged():
    # Existing users on v1.15 and older had these exact names in this order.
    # Breaking this invariant breaks their tooling even if they haven't
    # re-frozen the .amxd — unacceptable.
    assert SpectralReceiver.BAND_NAMES_8 == [
        "sub",
        "low",
        "low_mid",
        "mid",
        "high_mid",
        "high",
        "presence",
        "air",
    ]


def test_band_names_9_prepends_sub_low():
    assert SpectralReceiver.BAND_NAMES_9[0] == "sub_low"
    # 9-band list is the 8-band list with sub_low prepended.
    assert SpectralReceiver.BAND_NAMES_9[1:] == SpectralReceiver.BAND_NAMES_8


def test_band_names_default_alias_is_9():
    # The default alias should track the new layout so callers reading
    # BAND_NAMES without a length hint get the forward-compatible set.
    assert SpectralReceiver.BAND_NAMES == SpectralReceiver.BAND_NAMES_9


def test_band_names_9_length():
    assert len(SpectralReceiver.BAND_NAMES_9) == 9


def test_band_names_8_length():
    assert len(SpectralReceiver.BAND_NAMES_8) == 8


def test_no_band_name_duplicates():
    # Duplicate names would collide in the cache dict.
    assert len(set(SpectralReceiver.BAND_NAMES_9)) == 9
    assert len(set(SpectralReceiver.BAND_NAMES_8)) == 8
