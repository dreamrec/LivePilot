"""Schema checks for complex MCP tool payloads."""

from __future__ import annotations

import json


def _tool_schema(name: str) -> dict:
    from mcp_server.server import _get_all_tools

    tools = {tool.name: tool for tool in _get_all_tools()}
    return tools[name].parameters


def _array_variant(prop: dict) -> dict:
    if prop.get("type") == "array":
        return prop
    for variant in prop.get("anyOf", []):
        if isinstance(variant, dict) and variant.get("type") == "array":
            return variant
    raise AssertionError(f"No array variant found in schema: {json.dumps(prop, indent=2)}")


def test_add_notes_schema_exposes_note_shape():
    schema = _tool_schema("add_notes")
    notes_prop = schema["properties"]["notes"]
    array_variant = _array_variant(notes_prop)
    assert array_variant["items"]["$ref"] == "#/$defs/NoteSpec"

    note_spec = schema["$defs"]["NoteSpec"]["properties"]
    assert note_spec["pitch"]["anyOf"] == [{"type": "integer"}, {"type": "string"}]
    assert note_spec["start_time"]["anyOf"] == [{"type": "number"}, {"type": "string"}]
    assert note_spec["duration"]["anyOf"] == [{"type": "number"}, {"type": "string"}]


def test_set_clip_automation_schema_exposes_point_shape():
    schema = _tool_schema("set_clip_automation")
    points_prop = schema["properties"]["points"]
    array_variant = _array_variant(points_prop)
    assert array_variant["items"]["$ref"] == "#/$defs/AutomationPoint"

    point_spec = schema["$defs"]["AutomationPoint"]["properties"]
    assert point_spec["time"]["anyOf"] == [{"type": "number"}, {"type": "string"}]
    assert point_spec["value"]["anyOf"] == [{"type": "number"}, {"type": "string"}]
