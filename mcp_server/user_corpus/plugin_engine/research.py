"""Phase 3 + 4 — Research target builder + Synthesis brief builder.

These don't call WebSearch or Anthropic directly. They emit STRUCTURED TASK
PACKETS that the Claude agent (in Claude Code) fulfills via WebSearch +
WebFetch + Agent dispatch (sonnet subagents). This keeps the corpus engine
portable + lets Claude Code's permission model gate every external call.

See docs/PLUGIN_KNOWLEDGE_ENGINE.md §"Why the agent-driven split".
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .detector import DetectedPlugin
from .manual import ManualExtraction


# ─── Phase 3: research target packet ────────────────────────────────────────


def build_research_targets(
    plugin: DetectedPlugin,
    local_manual: ManualExtraction | None = None,
    output_root: Path | None = None,
) -> dict:
    """Emit a structured packet of research queries for the agent to fulfill.

    The packet declares:
      - what we already know (identity + local manual presence)
      - what queries to run (manual_alt, technique_corpus, comparison)
      - where to cache results
      - what tool to call next (corpus_synthesize_plugin_identity)
    """
    name = plugin.name
    vendor = plugin.vendor or "unknown vendor"
    output_dir = (
        (output_root or _default_output_root()) / "plugins" / plugin.plugin_id / "research"
    )
    has_local_manual = bool(local_manual and local_manual.text and not local_manual.error)

    targets: list[dict] = []

    # Target 1: alternate / verified manual (always emit; even with local manual,
    # online may have a newer version)
    targets.append({
        "type": "manual_alt",
        "rationale": (
            "Verify local manual is current OR fetch one if no local manual exists"
            if has_local_manual else
            "No local manual found; locate the official PDF/web manual"
        ),
        "queries": _manual_queries(name, vendor),
        "priority": 1,
        "fetch_top_n": 1 if has_local_manual else 2,
    })

    # Target 2: technique corpus (recipes, sound design walkthroughs)
    targets.append({
        "type": "technique_corpus",
        "rationale": "Build a producer-oriented technique library — concrete recipes, sweet spots, common patches",
        "queries": _technique_queries(name, vendor),
        "priority": 2,
        "fetch_top_n": 5,
    })

    # Target 3: comparisons (when to reach for vs alternatives)
    targets.append({
        "type": "comparison",
        "rationale": "Determine when to reach for this plugin vs comparable alternatives",
        "queries": _comparison_queries(name, vendor),
        "priority": 3,
        "fetch_top_n": 3,
    })

    return {
        "plugin_id": plugin.plugin_id,
        "plugin_identity": {
            "name": name, "vendor": vendor, "format": plugin.format,
            "version": plugin.version, "unique_id": plugin.unique_id,
        },
        "local_manual_present": has_local_manual,
        "local_manual_path": local_manual.source_path if has_local_manual else None,
        "research_targets": targets,
        "cache_root": str(output_dir),
        "instructions": (
            "Use WebSearch + WebFetch to fulfill each target. For each query, "
            "cache the top result(s) under cache_root/<target_type>/<n>.txt + "
            "<n>_url.txt (the source URL). Stamp each cached file with a "
            "retrieval timestamp comment in the first line. Failures "
            "(no results, paywall, 404) are logged to cache_root/search_log.json "
            "and do not abort other targets."
        ),
        "next_step_tool": "corpus_emit_synthesis_briefs",
        "schema_version": 1,
    }


def _manual_queries(name: str, vendor: str) -> list[str]:
    out = [
        f'{vendor} {name} manual pdf',
        f'{vendor} {name} user guide',
    ]
    if vendor and vendor != "unknown vendor":
        out.append(f'site:{vendor.lower().split()[0]}.com {name} manual')
    return out


def _technique_queries(name: str, vendor: str) -> list[str]:
    return [
        f'{name} sound design tutorial',
        f'{name} bass patch',
        f'{name} pad evolving',
        f'{name} lead sound',
        f'{name} preset walkthrough',
        f'how to use {name}',
    ]


def _comparison_queries(name: str, vendor: str) -> list[str]:
    return [
        f'{name} vs alternatives review',
        f'{name} when to use',
        f'{name} pros cons',
    ]


# ─── Phase 4: synthesis brief ───────────────────────────────────────────────


def build_synthesis_brief(
    plugin: DetectedPlugin,
    local_manual: ManualExtraction | None = None,
    research_cache_root: Path | None = None,
    preset_examples: list[dict] | None = None,
    output_root: Path | None = None,
) -> dict:
    """Emit a self-contained brief for a sonnet subagent to write identity.yaml.

    The agent calls Anthropic-API (via Agent tool) with this brief. The brief
    contains all source data the subagent needs. The subagent writes one YAML
    at brief["output_path"].
    """
    out_root = output_root or _default_output_root()
    plugin_dir = out_root / "plugins" / plugin.plugin_id
    output_path = plugin_dir / "identity.yaml"

    # Manual extract — either full text (capped) or a sectioned digest
    manual_block: dict[str, Any] = {}
    if local_manual and local_manual.text and not local_manual.error:
        manual_block = {
            "source_path": local_manual.source_path,
            "source_kind": local_manual.source_kind,
            "char_count": local_manual.char_count,
            "page_count": local_manual.page_count,
            "section_titles": [s["title"] for s in (local_manual.sections or [])][:30],
            "text_preview": local_manual.text[:6000],   # first ~1000 words
        }

    # Research cache — list whatever's there as URLs + previews
    research_block: dict[str, Any] = {"available": False}
    if research_cache_root and Path(research_cache_root).exists():
        research_block = _summarize_research_cache(Path(research_cache_root))

    return {
        "plugin_id": plugin.plugin_id,
        "synthesis_inputs": {
            "identity": {
                "name": plugin.name, "vendor": plugin.vendor,
                "format": plugin.format, "version": plugin.version,
                "unique_id": plugin.unique_id,
            },
            "local_manual": manual_block,
            "research_cache": research_block,
            "preset_examples": (preset_examples or [])[:30],
        },
        "synthesis_schema": {
            # ── REQUIRED overlay fields (so the file is queryable via extension_atlas_search) ──
            "entity_id": "EXACTLY equal to plugin_id — required for overlay indexing",
            "entity_type": 'literal string "installed_plugin" — required for overlay indexing',
            "name": "human-readable plugin name (same as plugin's 'name' field)",
            "description": "ONE short paragraph (≤200 chars) used as the search-result summary; can be the first sentence of sonic_fingerprint",
            "tags": (
                "list of search tags — MUST include: 'installed-plugin', "
                "'vendor:<vendor-slug>', and EXACTLY ONE 'format:<primary>' tag — "
                "VST3 preferred when available, otherwise AU, otherwise AAX/VST2/CLAP/LV2. "
                "Do NOT emit multiple format:* tags — the full format list goes in "
                "'formats_available' for reference, but only the primary format is queryable. "
                "This avoids token waste and duplicate hits when a plugin ships in 4+ formats. "
                "Plus one 'genre:<slug>' per genre_affinity entry, one 'producer:<slug>' "
                "per producer_anchors entry, and any signature descriptors "
                "('shimmer-capable', 'self-sustaining', 'parallel-only', etc.)."
            ),
            "artists": "list of producer names from producer_anchors keys (overlay search ranks artist matches +50)",
            # ── Plugin-specific knowledge ──
            "sonic_fingerprint": "3-5 sentences describing what the plugin SOUNDS like + its signature character. Must reference concrete sonic qualities (warmth/grit/digital/analog/etc.), not just architecture.",
            "reach_for": "list of bullet points: when/why a producer would pick this plugin",
            "avoid": "list of bullet points: when this plugin is the wrong tool",
            "key_techniques": "list of producer-oriented recipes — each ideally citing specific parameter ranges or modulation routings",
            "parameter_glossary": "dict of dial → 1-line description, capped at 12 most important",
            "comparable_plugins": "list of {name, when_better} entries",
            "genre_affinity": "list of genre slugs (microhouse, dub_techno, hip_hop_boom_bap_lo_fi, etc.)",
            "producer_anchors": "list of {producer_name: rationale} entries — only cite when the research clearly supports the mapping",
        },
        "agent_instructions": (
            "Read synthesis_inputs in full. Write a YAML file at output_path "
            "matching synthesis_schema. The first 6 fields (entity_id, entity_type, "
            "name, description, tags, artists) are REQUIRED for the overlay loader "
            "to index the result — without them the file is unqueryable. "
            "Be concrete, not generic — every claim should be traceable to a "
            "specific sentence in manual or research_cache. Do not invent producer "
            "attributions; only cite anchors when the plugin's character clearly "
            "maps to a producer's documented sound. Cap output at ~3000 tokens."
        ),
        "output_path": str(output_path),
        "schema_version": 1,
    }


def _summarize_research_cache(root: Path) -> dict:
    """Walk a research/ cache dir and produce a manifest the brief can include."""
    if not root.exists():
        return {"available": False}
    entries: list[dict] = []
    for sub in sorted(root.iterdir()):
        if not sub.is_dir():
            continue
        for f in sorted(sub.glob("*.txt")):
            try:
                preview = f.read_text(encoding="utf-8", errors="ignore")[:2000]
            except OSError:
                preview = ""
            entries.append({
                "target_type": sub.name,
                "path": str(f),
                "preview": preview,
            })
    return {
        "available": bool(entries),
        "entry_count": len(entries),
        "entries": entries[:40],   # cap so the brief stays reasonable size
    }


def _default_output_root() -> Path:
    return Path.home() / ".livepilot" / "atlas-overlays" / "user"
