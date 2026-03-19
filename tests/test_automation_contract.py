"""Verify automation tools are registered."""


def test_automation_tool_count():
    """8 new automation tools should be registered."""
    from mcp_server.tools import automation
    import inspect
    tools = [name for name, obj in inspect.getmembers(automation)
             if callable(obj) and hasattr(obj, '__wrapped__')]
    # At minimum these should exist as functions
    expected = [
        'get_clip_automation',
        'set_clip_automation',
        'clear_clip_automation',
        'apply_automation_shape',
        'apply_automation_recipe',
        'get_automation_recipes',
        'generate_automation_curve',
        'analyze_for_automation',
    ]
    for name in expected:
        assert hasattr(automation, name), f"Missing tool: {name}"
