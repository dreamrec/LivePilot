"""Verifies the full/ package layout for v1.24."""


def test_full_package_layout():
    from mcp_server.composer.full.engine import ComposerEngine
    from mcp_server.composer.full.layer_planner import LayerSpec
    from mcp_server.composer.full.apply import apply_full_plan
    assert callable(apply_full_plan)
    assert ComposerEngine is not None


def test_full_re_exports_via_package_init():
    from mcp_server.composer.full import ComposerEngine, apply_full_plan
    assert ComposerEngine is not None
    assert callable(apply_full_plan)


def test_full_subpackage_exists_and_contains_moved_modules():
    """Ensure the full/ package was created and the moved modules live there."""
    import importlib.util
    # The new canonical locations must resolve
    spec_engine = importlib.util.find_spec("mcp_server.composer.full.engine")
    spec_layer = importlib.util.find_spec("mcp_server.composer.full.layer_planner")
    spec_apply = importlib.util.find_spec("mcp_server.composer.full.apply")
    assert spec_engine is not None, "mcp_server.composer.full.engine not found"
    assert spec_layer is not None, "mcp_server.composer.full.layer_planner not found"
    assert spec_apply is not None, "mcp_server.composer.full.apply not found"

    # Backward-compat shims must also resolve (old tests depend on them)
    spec_old_engine = importlib.util.find_spec("mcp_server.composer.engine")
    spec_old_layer = importlib.util.find_spec("mcp_server.composer.layer_planner")
    assert spec_old_engine is not None, "backward-compat shim composer/engine.py missing"
    assert spec_old_layer is not None, "backward-compat shim composer/layer_planner.py missing"
