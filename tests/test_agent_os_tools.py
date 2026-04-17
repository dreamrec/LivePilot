"""Contract tests for Agent OS V1 MCP tools."""

import asyncio

import pytest


def _get_tool_names():
    from mcp_server.server import mcp
    tools = asyncio.run(mcp.list_tools())
    return {tool.name for tool in tools}


def test_agent_os_tools_registered():
    names = _get_tool_names()
    expected = {
        "compile_goal_vector",
        "build_world_model",
        "evaluate_move",
    }
    missing = expected - names
    assert not missing, f"Missing agent_os tools: {missing}"


class TestCompileGoalVector:
    def test_rejects_invalid_dimension(self):
        from mcp_server.tools.agent_os import compile_goal_vector
        with pytest.raises(ValueError, match="Unknown target"):
            compile_goal_vector(None, "test", {"loudness": 1.0})

    def test_rejects_invalid_mode(self):
        from mcp_server.tools.agent_os import compile_goal_vector
        with pytest.raises(ValueError, match="mode"):
            compile_goal_vector(None, "test", {"punch": 1.0}, mode="attack")

    def test_accepts_json_string_targets(self):
        from mcp_server.tools.agent_os import compile_goal_vector
        result = compile_goal_vector(None, "test", '{"punch": 0.5, "energy": 0.5}')
        assert "goal_vector" in result
        assert result["goal_vector"]["mode"] == "improve"

    def test_reports_measurable_dimensions(self):
        from mcp_server.tools.agent_os import compile_goal_vector
        result = compile_goal_vector(None, "test", {"punch": 0.3, "groove": 0.7})
        assert "punch" in result["measurable_dimensions"]
        assert "groove" in result["unmeasurable_dimensions"]


class TestEvaluateMove:
    def test_enforces_hard_rules(self):
        from mcp_server.tools.agent_os import evaluate_move
        goal = {
            "request_text": "test",
            "targets": {"weight": 1.0},
            "protect": {},
            "mode": "improve",
            "aggression": 0.5,
            "research_mode": "none",
        }
        before = {"spectrum": {"sub": 0.5, "low": 0.5}, "rms": 0.6, "peak": 0.8}
        after = {"spectrum": {"sub": 0.3, "low": 0.3}, "rms": 0.4, "peak": 0.6}
        result = evaluate_move(None, goal, before, after)
        assert result["keep_change"] is False

    def test_accepts_json_strings(self):
        import json
        from mcp_server.tools.agent_os import evaluate_move
        goal = json.dumps({
            "request_text": "test",
            "targets": {"energy": 1.0},
            "protect": {},
            "mode": "improve",
            "aggression": 0.5,
        })
        before = json.dumps({"spectrum": {"sub": 0.5}, "rms": 0.5, "peak": 0.7})
        after = json.dumps({"spectrum": {"sub": 0.5}, "rms": 0.7, "peak": 0.9})
        result = evaluate_move(None, goal, before, after)
        assert "score" in result


# ─── BUG-E6 — build_world_model vs check_flucoma consistency ────────────────


class TestBuildWorldModelFluCoMaE6:
    """BUG-E6: check_flucoma() reported flucoma_available=true (6 streams)
    while build_world_model().technical.flucoma_available returned false
    on the same session. Root cause: build_world_model read a dedicated
    'flucoma_status' cache key that the M4L bridge doesn't emit, so the
    fallback `{"flucoma_available": False}` always won. The fix derives
    availability from the same 6-stream probe check_flucoma uses."""

    def _make_ctx(self, streams_active: bool):
        from types import SimpleNamespace

        class _Cache:
            is_connected = True
            _flu_keys = {"spectral_shape", "mel_bands", "chroma",
                         "onset", "novelty", "loudness"}

            def get(self_inner, key):
                if streams_active and key in self_inner._flu_keys:
                    return {"value": [0.1] * 10}
                return None

        class _Ableton:
            def send_command(self, cmd, params=None):
                if cmd == "get_session_info":
                    return {
                        "tempo": 120, "time_signature": "4/4",
                        "track_count": 1, "return_track_count": 0,
                        "scene_count": 1,
                        "tracks": [{
                            "index": 0, "name": "A",
                            "has_midi_input": True, "has_audio_input": False,
                            "mute": False, "solo": False, "arm": False,
                        }],
                    }
                if cmd == "get_track_info":
                    return {"index": 0, "name": "A", "devices": []}
                return {}

        return SimpleNamespace(lifespan_context={
            "ableton": _Ableton(),
            "spectral": _Cache(),
        })

    def test_flucoma_available_true_when_streams_flow(self):
        """With all 6 FluCoMa stream keys populated, build_world_model must
        report flucoma_available=true — matching what check_flucoma says."""
        from mcp_server.tools.agent_os import build_world_model
        ctx = self._make_ctx(streams_active=True)
        result = build_world_model(ctx)
        technical = result.get("technical", {})
        assert technical.get("flucoma_available") is True, (
            f"BUG-E6 regressed — build_world_model says "
            f"flucoma_available={technical.get('flucoma_available')} "
            f"while streams ARE flowing. technical={technical!r}"
        )

    def test_flucoma_available_false_when_no_streams(self):
        """With no FluCoMa streams, flucoma_available must stay false."""
        from mcp_server.tools.agent_os import build_world_model
        ctx = self._make_ctx(streams_active=False)
        result = build_world_model(ctx)
        technical = result.get("technical", {})
        assert technical.get("flucoma_available") is False
