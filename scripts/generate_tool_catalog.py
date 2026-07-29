#!/usr/bin/env python3
"""Generate tool catalog from live runtime metadata.

Produces a markdown tool catalog validated against mcp.list_tools().
This is the single source of truth — hand-edited catalogs are replaced.

Usage: python3 scripts/generate_tool_catalog.py > docs/manual/tool-catalog.md

Note (v1.17+): the canonical path is `tool-catalog.md` (used to be split
across `tool-catalog.md` hand-edited vs `tool-catalog-generated.md` auto.
The hand-edited copy drifted constantly, so we consolidated on a single
auto-generated file at the familiar filename).
"""

import asyncio
import inspect
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def get_tools() -> list[dict]:
    """Get all registered tools with metadata."""
    from mcp_server.server import mcp

    tools_raw = asyncio.run(mcp.list_tools())
    tools = []
    for t in tools_raw:
        # Get the module path to determine domain
        func = t.fn if hasattr(t, "fn") else None
        module = ""
        if func:
            module = func.__module__ if hasattr(func, "__module__") else ""

        # Get parameter names
        params = []
        if func:
            sig = inspect.signature(func)
            for name, param in sig.parameters.items():
                if name == "ctx":
                    continue
                required = param.default is inspect.Parameter.empty
                params.append({"name": name, "required": required})

        tools.append({
            "name": t.name,
            "description": t.description[:120] if hasattr(t, "description") and t.description else "",
            "module": module,
            "params": params,
        })

    return tools


def infer_domain(module: str) -> str:
    """Infer domain from module path using the same module-layout rule as
    ``scripts/sync_metadata.py``:
      - ``mcp_server.<X>.<...>``              → ``<X>``
      - ``mcp_server.tools.<Y>``              → ``<Y>``
    The display name is Title-Cased; underscores become spaces.
    """
    parts = module.split(".")
    if len(parts) < 2 or parts[0] != "mcp_server":
        return "Other"
    if parts[1] == "tools":
        domain_key = parts[2] if len(parts) > 2 else "other"
    else:
        domain_key = parts[1]
    return domain_key.replace("_", " ").title()


# --- docs/manual/index.md "Domain Map" section -----------------------------
#
# The per-domain tool COUNTS below are always derived live from the tool
# registry (see get_raw_domain_counts()). Layer membership, display names, and
# prose "Scope" descriptions can't be derived from the registry — they're
# curated here once per domain. When a brand-new domain appears with no entry
# in DOMAIN_LAYER/DOMAIN_SCOPE, generate_domain_map() raises instead of
# silently omitting a row (mirrors the fail-loud posture of sync_metadata.py).

# Display-name overrides for domain keys that don't Title-Case cleanly.
DOMAIN_DISPLAY_OVERRIDES = {
    "agent_os": "Agent OS",
    "midi_io": "MIDI I/O",
    "miditool": "MidiTool",
}

# domain_key -> layer number (1=Core Ableton Control, 2=Perception,
# 3=Creative Intelligence, 4=Personal Library Awareness).
DOMAIN_LAYER = {
    "devices": 1, "arrangement": 1, "transport": 1, "tracks": 1, "memory": 1,
    "clips": 1, "scenes": 1, "mixing": 1, "automation": 1, "composition": 1,
    "notes": 1, "scales": 1, "follow_actions": 1, "theory": 1, "grooves": 1,
    "take_lanes": 1, "generative": 1, "browser": 1, "harmony": 1,
    "midi_io": 1, "miditool": 1,

    "analyzer": 2, "perception": 2, "diagnostics": 2, "evaluation": 2,
    "listening": 2,

    "sample_engine": 3, "hook_hunter": 3, "atlas": 3, "agent_os": 3,
    "session_continuity": 3, "musical_intelligence": 3, "mix_engine": 3,
    "preview_studio": 3, "runtime": 3, "experiment": 3,
    "creative_constraints": 3, "sound_design": 3, "composer": 3,
    "semantic_moves": 3, "transition_engine": 3, "reference_engine": 3,
    "performance_engine": 3, "song_brain": 3, "stuckness_detector": 3,
    "wonder_mode": 3, "research": 3, "synthesis_brain": 3, "device_forge": 3,
    "motif": 3, "project_brain": 3, "planner": 3, "translation_engine": 3,
    "creative_director": 3, "audit": 3, "grader": 3,

    "user_corpus": 4,
}

LAYER_TITLES = {
    1: "Core Ableton Control",
    2: "Perception",
    3: "Creative Intelligence",
    4: "Personal Library Awareness",
}

# domain_key -> hand-curated one-line scope description for the manual table.
DOMAIN_SCOPE = {
    "devices": "Load by name/URI, insert native (12.3+), params, racks, chains, drum pads, plugins, presets, wavetable mod matrix, replace_sample (12.4+), `add_drum_rack_pad`, `verify_device_alive` (v1.16+)",
    "arrangement": "Timeline editing, arrangement notes, native clips (12.1.10+), cue points, recording, capture, `set_arrangement_automation_via_session_record` (v1.17+)",
    "transport": "Playback, tempo, time sig, loop, metronome, undo/redo, diagnostics, capture MIDI",
    "tracks": "Create MIDI/audio/return, delete, duplicate, arm, mute, solo, routing, sends, monitoring",
    "memory": "Save, recall, replay, session memory, list/favorite/delete, update",
    "clips": "Create, delete, duplicate, fire, stop, loop, launch mode, warp mode, pitch, color",
    "scenes": "Create, delete, duplicate, fire, name, color, per-scene tempo, follow actions",
    "mixing": "Volume, pan, sends, routing, meters, return tracks, mix snapshot",
    "automation": "Clip envelopes, 16 curve types, 15 recipes, spectral suggestions",
    "composition": "Section analysis, motif detection, emotional arc, form planning",
    "notes": "Add/get/remove/modify MIDI, transpose, duplicate, per-note probability",
    "scales": "Clip scales, song scales, scale modes, list available scales",
    "follow_actions": "Clip + scene follow actions, presets, type listing",
    "theory": "Harmony analysis, Roman numerals, scales, countermelody, transposition",
    "grooves": "Groove templates, per-clip groove, groove amount, groove params",
    "take_lanes": "Create, name, list, per-lane clips",
    "generative": "Euclidean rhythm, tintinnabuli, phase shift, additive process",
    "browser": "Search library, browse tree, load items",
    "harmony": "Tonnetz navigation, voice leading, neo-Riemannian classification",
    "midi_io": "Export/import .mid, offline analysis, piano roll extraction",
    "miditool": "Device install, generator registration, per-clip target mapping",

    "analyzer": "9-band spectrum (v1.17+), RMS, key detection, Simpler ops, warp markers, capture, FluCoMa mel/chroma/onset `[M4L]`",
    "perception": "Offline loudness, spectral analysis, reference comparison, metadata",
    "diagnostics": "Device/session health verification, test-note fire-and-forget",
    "evaluation": "Before/after evaluation with structured scoring",
    "listening": "Offline perceptual analysis of master-bus captures — `listen_capture` full report, `listen_ab` before/after comparison with evaluate_move-ready snapshots (v1.28+)",

    "sample_engine": "Multi-source search (Splice gRPC + browser + filesystem), Splice catalog hunt, downloads, previews, pack info, collections, presets, describe-a-sound (LIVE), variations (LIVE), http-diagnose (v1.17+)",
    "hook_hunter": "Hook detection, salience scoring, neglect detection, phrase impact",
    "atlas": "Search 5264 devices, suggest by intent, chain building, comparison, library scan, `atlas_pack_info`, `atlas_describe_chain` (free-text), `atlas_techniques_for_device` (reverse-lookup), `atlas_macro_fingerprint` (preset similarity), Pack-Atlas cross-pack tools (`atlas_transplant`, `atlas_extract_chain`, `atlas_cross_pack_chain`, `atlas_pack_aware_compose`, `atlas_demo_story`), hybrid-surface Layer B (`atlas_explore`, `atlas_audition`, `atlas_substitute`) — all v1.17+ unless noted; plus `extension_atlas_search` / `extension_atlas_get` / `extension_atlas_list` for user-local overlays (v1.23.0+)",
    "agent_os": "Session kernel, action ledger, capability state, routing, goal vectors, taste, turn budget",
    "session_continuity": "Creative threads, turn resolution, session story, anti-preferences",
    "musical_intelligence": "Phrase arc, impact scoring, comparison, rendering, grid analysis, snapshot",
    "mix_engine": "Critic-driven mix analysis, issue detection, move planning",
    "preview_studio": "Variant creation, preview rendering, comparison, commit, discard",
    "runtime": "Session kernel building, world model, capability, safety, resume intent, Live 12.4 probe-first tools (`probe_link_audio`, `probe_stem_workflow`)",
    "experiment": "Create, run, compare, commit, discard A/B experiment branches",
    "creative_constraints": "Constraint activation, reference-inspired variants",
    "sound_design": "Patch analysis, modulation planning, timbre scoring",
    "composer": "Prompt → multi-layer composition plan, sample augmentation, plan preview, branches, develop-mode apply, hybrid Ableton-Knowledge consultation",
    "semantic_moves": "Move listing, preview, application, next-best-move proposal",
    "transition_engine": "Transition classification, scoring, archetype planning",
    "reference_engine": "Reference profiling, principle distillation, gap analysis",
    "performance_engine": "Safety-constrained suggestions, safe moves, scene handoff",
    "song_brain": "Identity inference, sacred elements, drift monitoring",
    "stuckness_detector": "Momentum analysis, rescue classification, rescue workflows",
    "wonder_mode": "Diagnosis-driven variants, taste-aware ranking, session discard",
    "research": "Technique research, style tactics",
    "synthesis_brain": "Synth patch analysis, branch proposals, timbre fingerprint extraction",
    "device_forge": "Generate M4L devices from gen~ templates, install to browser",
    "motif": "Motif graph, motif transformation",
    "project_brain": "Project-level analysis, section purpose inference",
    "planner": "Gesture planning, arrangement planning",
    "translation_engine": "Cross-domain translation, issue detection",
    "creative_director": "Brief-compliance checking for a proposed tool call, hybrid-brief compilation from multiple concept packets",
    "audit": "Single-call §5 layer-precision audit (timbre + sequence + stereo + masking) for one track",
    "grader": "Rubric-based session evaluation — list rubrics, run one, run all",

    "user_corpus": "Plugin Knowledge Engine 4-phase pipeline. `corpus_setup_wizard`, `corpus_init`, `corpus_status`, `corpus_list_scanners`, `corpus_add_source`, `corpus_remove_source`, `corpus_scan` (file-level), `corpus_detect_plugins` (auval-aware), `corpus_canonicalize_plugins` (VST3-preferred dedup), `corpus_cluster_plugins` (vendor-batched research), `corpus_trim_plugin_identity` (deprioritization), `corpus_discover_manuals`, `corpus_research_targets`, `corpus_emit_synthesis_briefs`",
}


def domain_display_name(domain_key: str) -> str:
    return DOMAIN_DISPLAY_OVERRIDES.get(domain_key, domain_key.replace("_", " ").title())


def get_raw_domain_counts(tools: list[dict]) -> dict[str, int]:
    """Per-domain tool counts keyed by the raw snake_case domain (module dir/stem).

    Mirrors ``scripts/sync_metadata.py::get_domains()``'s domain-key derivation
    so the two never disagree about what a "domain" is.
    """
    counts: dict[str, int] = defaultdict(int)
    for t in tools:
        parts = t["module"].split(".")
        if len(parts) < 2 or parts[0] != "mcp_server":
            continue
        domain_key = parts[2] if parts[1] == "tools" and len(parts) > 2 else parts[1]
        if domain_key.startswith("_"):
            continue
        counts[domain_key] += 1
    return dict(counts)


DOMAIN_MAP_START = "<!-- DOMAIN_MAP:AUTO-GENERATED START -->"
DOMAIN_MAP_END = "<!-- DOMAIN_MAP:AUTO-GENERATED END -->"


def generate_domain_map(tools: list[dict] | None = None) -> str:
    """Render the docs/manual/index.md "Domain Map" body (layer tables only).

    Raises ValueError if a live domain has no DOMAIN_LAYER/DOMAIN_SCOPE entry
    (new domain shipped without a doc update) rather than silently omitting
    it — same fail-loud posture as the rest of sync_metadata.py.
    """
    if tools is None:
        tools = get_tools()
    counts = get_raw_domain_counts(tools)

    unmapped = sorted(set(counts) - set(DOMAIN_LAYER) - set(DOMAIN_SCOPE))
    if unmapped:
        raise ValueError(
            "generate_domain_map: domain(s) missing DOMAIN_LAYER/DOMAIN_SCOPE "
            f"entries in scripts/generate_tool_catalog.py: {', '.join(unmapped)}"
        )

    by_layer: dict[int, list[str]] = defaultdict(list)
    for domain_key in counts:
        by_layer[DOMAIN_LAYER[domain_key]].append(domain_key)

    total = sum(counts.values())
    lines = [DOMAIN_MAP_START, ""]
    lines.append(f"All {total} tools across {len(counts)} domains, in source-truth per-domain counts:")
    lines.append("")

    for layer_num in sorted(by_layer):
        domain_keys = sorted(by_layer[layer_num], key=lambda d: (-counts[d], d))
        layer_total = sum(counts[d] for d in domain_keys)
        lines.append(f"### {LAYER_TITLES[layer_num]} (Layer {layer_num} — {layer_total} tools)")
        lines.append("")
        lines.append("| Domain | # | Scope |")
        lines.append("|--------|:-:|-------|")
        for domain_key in domain_keys:
            lines.append(
                f"| {domain_display_name(domain_key)} | {counts[domain_key]} | {DOMAIN_SCOPE[domain_key]} |"
            )
        lines.append("")

    lines.append(DOMAIN_MAP_END)
    return "\n".join(lines).rstrip() + "\n"


def main():
    # The emitted markdown contains non-latin-1 glyphs ("→"); Windows
    # consoles/pipes default to cp1252 and crash with UnicodeEncodeError.
    # Belt-and-braces with the PYTHONIOENCODING env the sync_metadata
    # subprocess callers set (standing cp1252 rule for glyph-printing scripts).
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    if len(sys.argv) > 1 and sys.argv[1] == "--domain-map":
        sys.stdout.write(generate_domain_map())
        return

    tools = get_tools()
    total = len(tools)

    # Group by domain
    domains = defaultdict(list)
    for t in tools:
        domain = infer_domain(t["module"])
        domains[domain].append(t)

    print(f"# LivePilot — Full Tool Catalog (Generated)")
    print()
    print(f"{total} tools across {len(domains)} domains.")
    print()
    print("> Auto-generated from `mcp.list_tools()`. Do not hand-edit.")
    print("> Regenerate: `python3 scripts/generate_tool_catalog.py`")
    print()
    print("---")
    print()

    for domain in sorted(domains.keys()):
        tool_list = sorted(domains[domain], key=lambda t: t["name"])
        print(f"## {domain} ({len(tool_list)})")
        print()
        print("| Tool | Description |")
        print("|------|-------------|")
        for t in tool_list:
            desc = t["description"].split("\n")[0].strip()
            print(f"| `{t['name']}` | {desc} |")
        print()

    print(f"---")
    print(f"*Generated from {total} registered tools.*")


if __name__ == "__main__":
    main()
