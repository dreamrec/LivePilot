"""Tests for capability/degradation reporting contract."""

from mcp_server.runtime.capability import CapabilityReport, build_capability


def test_full_when_all_available():
    cap = build_capability(
        required=["session_info", "scenes", "tracks"],
        available={"session_info": True, "scenes": True, "tracks": True},
    )
    assert cap.level == "full"
    assert cap.confidence == 1.0
    assert cap.missing_sources == []


def test_fallback_when_partial():
    cap = build_capability(
        required=["session_info", "scenes", "motif_data", "tracks"],
        available={"session_info": True, "scenes": True, "motif_data": False, "tracks": True},
    )
    assert cap.level == "fallback"
    assert cap.confidence < 1.0
    assert "motif_data" in cap.missing_sources
    assert "session_info" in cap.available_sources


def test_analytical_only_when_nothing():
    cap = build_capability(
        required=["session_info", "scenes"],
        available={"session_info": False, "scenes": False},
    )
    assert cap.level == "analytical_only"
    assert cap.confidence == 0.2


def test_to_dict_includes_missing():
    cap = build_capability(
        required=["a", "b"],
        available={"a": True, "b": False},
    )
    d = cap.to_dict()
    assert d["capability"] == "fallback"
    assert "missing" in d
    assert "b" in d["missing"]


def test_to_dict_clean_when_full():
    cap = build_capability(
        required=["a"],
        available={"a": True},
    )
    d = cap.to_dict()
    assert d["capability"] == "full"
    assert "missing" not in d
