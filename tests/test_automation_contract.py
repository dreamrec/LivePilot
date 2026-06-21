"""Verify automation tools are registered."""


def test_automation_tool_count():
    """10 automation tools should be registered as module-level functions."""
    from mcp_server.tools import automation

    expected = [
        'get_clip_automation',
        'set_clip_automation',
        'clear_clip_automation',
        'apply_automation_shape',
        'apply_automation_recipe',
        'get_automation_recipes',
        'generate_automation_curve',
        'analyze_for_automation',
        'record_parameter_automation_realtime',
        'set_arrangement_automation_via_session_record',
    ]
    for name in expected:
        assert hasattr(automation, name), f"Missing tool: {name}"
        assert callable(getattr(automation, name)), f"Not callable: {name}"
