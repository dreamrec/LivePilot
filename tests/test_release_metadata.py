"""Release metadata checks for plugin manifest parity and checklist coverage."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_release_checklist_references_both_plugin_manifests():
    source = (ROOT / "livepilot" / "skills" / "livepilot-release" / "SKILL.md").read_text()
    assert "livepilot/.Codex-plugin/plugin.json" in source
    assert "livepilot/.claude-plugin/plugin.json" in source


def test_claude_doc_mentions_codex_primary_and_claude_mirror():
    source = (ROOT / "CLAUDE.md").read_text()
    assert "livepilot/.Codex-plugin/plugin.json" in source
    assert "livepilot/.claude-plugin/plugin.json" in source
