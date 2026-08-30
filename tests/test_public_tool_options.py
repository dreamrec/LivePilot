"""Regression tests that public options are real, not decorative knobs."""

from __future__ import annotations

from types import SimpleNamespace

from mcp_server.composer.full.apply import _validate_v2_plan
from mcp_server.sample_engine import tools as sample_tools
from mcp_server.server import _get_all_tools


def _schema(name: str) -> dict:
    tool = next(tool for tool in _get_all_tools() if tool.name == name)
    return tool.parameters


def test_removed_noop_options_are_not_advertised():
    compose = _schema("compose")["properties"]
    assert {"target_scene", "max_credits", "dry_run"}.isdisjoint(compose)

    assert "key" not in _schema("atlas_suggest")["properties"]
    assert "kernel_id" not in _schema("detect_stuckness")["properties"]


def test_search_samples_q_alias_is_callable_without_query():
    schema = _schema("search_samples")
    assert "q" in schema["properties"]
    assert "query" not in schema.get("required", [])


def test_sample_material_filter_uses_declared_type_and_filename_fallback():
    assert sample_tools._sample_material_matches(
        {"metadata": {"material_type": "vocal"}, "name": "mystery.wav"},
        "vocal",
    )
    assert sample_tools._sample_material_matches(
        {"metadata": {"material_type": "unknown"}, "name": "vinyl drum break.wav"},
        "drum_loop",
    )
    assert not sample_tools._sample_material_matches(
        {"metadata": {"material_type": "texture"}, "name": "soft drone.wav"},
        "vocal",
    )


def test_sample_workflow_role_and_section_change_search_guidance():
    result = sample_tools.plan_sample_workflow(
        SimpleNamespace(),
        search_query="dusty",
        desired_role="vocal_hook",
        section_type="breakdown",
    )

    assert result["status"] == "search_needed"
    assert result["intent"] == "vocal"
    assert result["material_type"] == "vocal"
    assert result["desired_role"] == "vocal_hook"
    assert result["section_type"] == "breakdown"
    assert any("vocal" in query.lower() for query in result["search_queries"])


def test_full_apply_rejects_abstract_events_instead_of_silently_ignoring_them():
    error = _validate_v2_plan(
        {
            "scope": "full",
            "form": [{"name": "Intro", "bars": 8}],
            "tracks": [{"name": "Bass", "variants": []}],
            "events": [{"type": "energy_rise", "bar": 7}],
        }
    )

    assert error is not None
    assert "not supported" in error
    assert "concrete" in error
