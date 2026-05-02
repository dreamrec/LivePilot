"""Regression guards: NO form templates in the framework.

The framework provides VOCABULARY (descriptive). The LLM provides FORM
(creative). Anything that constrains FORM to a predetermined skeleton —
section sequences, bar counts, variant taxonomies, drop placements — is
a regression and must be rejected at code review.

These tests scan the codebase mechanically and FAIL if anyone re-introduces
a form-template registry.
"""

import pkgutil


# Banned registry names — uppercase Python identifiers that historically
# encoded form (section sequences with bar counts).
BANNED_REGISTRY_NAMES = {
    "STYLE_TEMPLATES",
    "FORM_TEMPLATES",
    "GENRE_FORMS",
    "ARRANGEMENT_TEMPLATES",
    "SECTION_TEMPLATES",
    "TRACK_FORM_REGISTRY",
}


def test_no_form_template_registries_in_composer():
    """No module under mcp_server.composer defines a form-template dict."""
    import mcp_server.composer as pkg
    for mod_info in pkgutil.walk_packages(pkg.__path__, prefix="mcp_server.composer."):
        try:
            mod = __import__(mod_info.name, fromlist=[""])
        except ImportError:
            continue
        leaks = {n for n in dir(mod) if n in BANNED_REGISTRY_NAMES}
        assert not leaks, (
            f"{mod_info.name} re-introduced banned form-template registry: {leaks}. "
            f"Form templates are forbidden in v1.24+ — see plan + CLAUDE.md §design principle."
        )


def test_no_form_template_registries_in_tools():
    """No module under mcp_server.tools defines a form-template dict either.

    The historical STYLE_TEMPLATES lived in _planner_engine.py — this guard
    ensures it's gone.
    """
    import mcp_server.tools as pkg
    for mod_info in pkgutil.walk_packages(pkg.__path__, prefix="mcp_server.tools."):
        try:
            mod = __import__(mod_info.name, fromlist=[""])
        except ImportError:
            continue
        leaks = {n for n in dir(mod) if n in BANNED_REGISTRY_NAMES}
        assert not leaks, (
            f"{mod_info.name} re-introduced banned form-template registry: {leaks}."
        )


def test_no_fixed_variant_taxonomy_constants_anywhere():
    """No module-level uppercase constants encoding fixed variant taxonomies."""
    BANNED_VARIANT_CONSTANTS = {
        "BUILD_VARIANT", "FILL_VARIANT", "BREAK_VARIANT", "ALT_PEAK_VARIANT",
        "DROP_VARIANT", "BREAKDOWN_VARIANT", "INTRO_VARIANT", "OUTRO_VARIANT",
    }
    for parent_pkg_name in ("mcp_server.composer", "mcp_server.tools"):
        parent_pkg = __import__(parent_pkg_name, fromlist=[""])
        for mod_info in pkgutil.walk_packages(parent_pkg.__path__, prefix=f"{parent_pkg_name}."):
            try:
                mod = __import__(mod_info.name, fromlist=[""])
            except ImportError:
                continue
            leaks = {n for n in dir(mod) if n in BANNED_VARIANT_CONSTANTS}
            assert not leaks, (
                f"{mod_info.name} leaks fixed-taxonomy variant constant(s): {leaks}"
            )


def test_planner_engine_does_not_import_style_templates():
    """If _planner_engine.py still exists, it does NOT export STYLE_TEMPLATES."""
    try:
        from mcp_server.tools import _planner_engine
    except ImportError:
        return  # File was deleted entirely — that's fine
    public_names = {n for n in dir(_planner_engine) if not n.startswith("_")}
    assert "STYLE_TEMPLATES" not in public_names, (
        "mcp_server.tools._planner_engine still exposes STYLE_TEMPLATES — must be deleted"
    )
