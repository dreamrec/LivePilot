"""Plugin Knowledge Engine — detects installed plugins, extracts identity from
their bundles, finds + extracts manuals, and emits research / synthesis briefs
for the agent to fulfill via WebSearch + sonnet subagents.

See docs/PLUGIN_KNOWLEDGE_ENGINE.md for the full architecture.

Public API:
    from mcp_server.user_corpus.plugin_engine import (
        detect_installed_plugins, discover_manuals_for_plugin,
        extract_manual_text, build_research_targets,
        build_synthesis_brief, default_plugin_dir,
    )
"""
from __future__ import annotations

from .detector import (
    detect_installed_plugins,
    default_plugin_dir,
    DetectedPlugin,
)
from .manual import (
    discover_manuals_for_plugin,
    extract_manual_text,
    ManualCandidate,
    ManualExtraction,
)
from .research import build_research_targets, build_synthesis_brief

__all__ = [
    "detect_installed_plugins",
    "default_plugin_dir",
    "DetectedPlugin",
    "discover_manuals_for_plugin",
    "extract_manual_text",
    "ManualCandidate",
    "ManualExtraction",
    "build_research_targets",
    "build_synthesis_brief",
]
