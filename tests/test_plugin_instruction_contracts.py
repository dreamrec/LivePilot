"""Regression checks for Claude/Codex plugin operating instructions."""

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


def test_plugin_docs_use_analyzer_preflight_not_direct_master_load():
    plugin_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "livepilot").rglob("*.md")
    )

    assert "find_and_load_device(track_index=-1000" not in plugin_text
    assert "ensure_analyzer_on_master" in _read("livepilot/commands/mix.md")
    assert "ensure_analyzer_on_master" in _read("livepilot/commands/evaluate.md")


def test_beat_command_keeps_analyzer_after_master_chain():
    beat = _read("livepilot/commands/beat.md")

    assert beat.index("Set up master chain") < beat.index("Ensure analyzer last")


def test_semantic_move_improve_mode_is_described_as_compile_for_approval():
    core = _read("livepilot/skills/livepilot-core/SKILL.md")
    mix = _read("livepilot/commands/mix.md")

    assert "compile and execute the move" not in core
    assert "returns the compiled plan without executing it" in mix
    assert 'apply_semantic_move(mode="improve")' in core


def test_release_skill_has_current_counts_without_stale_subtotals():
    release = _read("livepilot/skills/livepilot-release/SKILL.md")
    core = _read("livepilot/skills/livepilot-core/SKILL.md")

    assert "All others: **292**" not in release
    assert "ALL 45" not in release
    assert "ALL 56" in release
    assert "120 enriched" in core
    assert "135 enriched" not in core


def test_sync_metadata_guards_core_skill_enriched_count():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "sync_metadata", ROOT / "scripts" / "sync_metadata.py"
    )
    assert spec and spec.loader
    sync_metadata = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sync_metadata)

    assert (
        "livepilot/skills/livepilot-core/SKILL.md"
        in sync_metadata.PROSE_CLAIM_FILES["enriched"]["files"]
    )
