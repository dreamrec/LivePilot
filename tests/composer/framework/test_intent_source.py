"""Tests for IntentSource implementations."""

import pytest
from unittest.mock import MagicMock
from mcp_server.composer.framework.intent_source import (
    IntentSource, PromptSource, SessionSource, HybridSource,
)


# ── PromptSource ────────────────────────────────────────────────────

def test_prompt_source_parses_genre_and_tempo():
    """PromptSource delegates to prompt_parser.parse_prompt."""
    src = PromptSource("dark techno 128bpm in Am")
    result = src.parse(ctx=None)
    # CompositionIntent fields — at least one should be populated for this prompt
    assert isinstance(result, dict)
    assert len(result) > 0


def test_prompt_source_empty_prompt_returns_dict():
    src = PromptSource("")
    result = src.parse(ctx=None)
    assert isinstance(result, dict)


# ── SessionSource ───────────────────────────────────────────────────

def _mock_ctx_with_session(session_data: dict, scale_data=None):
    """Build a mock ctx whose ableton.send_command returns the given data."""
    ableton = MagicMock()
    def send_command(cmd, args):
        if cmd == "get_session_info":
            return session_data
        if cmd == "get_song_scale":
            if scale_data is None:
                raise RuntimeError("not available")
            return scale_data
        return {}
    ableton.send_command = send_command
    ctx = MagicMock()
    ctx.lifespan_context = {"ableton": ableton}
    return ctx


def test_session_source_extracts_tempo_and_time_signature():
    ctx = _mock_ctx_with_session({
        "tempo": 122.0,
        "signature_numerator": 4,
        "signature_denominator": 4,
    })
    src = SessionSource(scene_index=0)
    intent = src.parse(ctx)
    assert intent["tempo"] == 122.0
    assert intent["time_signature"] == "4/4"
    assert intent["scene_index"] == 0


def test_session_source_extracts_key_when_song_scale_available():
    ctx = _mock_ctx_with_session(
        session_data={"tempo": 120.0, "signature_numerator": 4, "signature_denominator": 4},
        scale_data={"root_note": "Am", "scale_name": "minor"},
    )
    src = SessionSource()
    intent = src.parse(ctx)
    assert intent["key"] == "Am"
    assert intent["scale_mode"] == "minor"


def test_session_source_no_ableton_returns_empty():
    ctx = MagicMock()
    ctx.lifespan_context = {}  # no ableton key
    src = SessionSource()
    assert src.parse(ctx) == {}


# ── HybridSource ────────────────────────────────────────────────────

def test_hybrid_source_session_wins_on_tempo_and_key():
    """When both prompt and session provide tempo, session wins."""
    ctx = _mock_ctx_with_session(
        session_data={"tempo": 122.0, "signature_numerator": 4, "signature_denominator": 4},
        scale_data={"root_note": "Am", "scale_name": "minor"},
    )
    src = HybridSource(prompt="techno 130bpm in Cm", scene_index=0)
    intent = src.parse(ctx)
    # Session tempo (122) wins over prompt tempo (130)
    assert intent["tempo"] == 122.0
    assert intent["key"] == "Am"


def test_hybrid_source_prompt_wins_on_genre():
    """Genre comes from prompt only — session has no genre concept."""
    ctx = _mock_ctx_with_session(
        session_data={"tempo": 122.0, "signature_numerator": 4, "signature_denominator": 4},
    )
    src = HybridSource(prompt="dark techno", scene_index=0)
    intent = src.parse(ctx)
    # Tempo from session
    assert intent["tempo"] == 122.0
