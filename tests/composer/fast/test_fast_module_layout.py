"""Verifies the fast/ package layout for v1.24."""


def test_fast_package_layout():
    from mcp_server.composer.fast.brief_builder import build_creative_brief
    from mcp_server.composer.fast.apply import apply_fast_plan
    assert callable(build_creative_brief)
    assert callable(apply_fast_plan)


def test_fast_re_exports_via_package_init():
    from mcp_server.composer.fast import build_creative_brief, apply_fast_plan
    assert callable(build_creative_brief)
    assert callable(apply_fast_plan)


def test_old_fast_py_module_does_not_exist():
    """Ensure the file-level `fast.py` was actually removed (not left as duplicate)."""
    import importlib.util
    # Should resolve to the package, not a top-level fast.py
    spec = importlib.util.find_spec("mcp_server.composer.fast")
    assert spec is not None
    assert spec.submodule_search_locations is not None, (
        "mcp_server.composer.fast should resolve to a package, not a single .py file"
    )
