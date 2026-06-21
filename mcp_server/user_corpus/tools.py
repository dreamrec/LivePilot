"""MCP tool wrappers for the user corpus builder + plugin knowledge engine.

Phase 1 tools (file scanner — see USER_CORPUS_GUIDE.md):
  corpus_init           — create ~/.livepilot/atlas-overlays/user/ + manifest.yaml
  corpus_add_source     — register a directory + scanner type
  corpus_remove_source  — unregister
  corpus_scan           — run scans (all sources, or one)
  corpus_status         — what's in the manifest + freshness
  corpus_list_scanners  — show available scanner types

Phase 2 tools (plugin knowledge engine — see PLUGIN_KNOWLEDGE_ENGINE.md):
  corpus_detect_plugins         — Phase 2.1+2.2: enumerate installed VST3/AU/VST2/AAX
  corpus_canonicalize_plugins   — dedupe inventory by vendor+name, prefer VST3
  corpus_cluster_plugins        — group by vendor → cluster manifest for efficient research
  corpus_discover_manuals       — Phase 2.3+2.4: find + extract local PDFs/HTML/etc.
  corpus_research_targets       — Phase 3: emit WebSearch task packet for the agent
  corpus_emit_synthesis_briefs  — Phase 4: emit sonnet-subagent brief for identity.yaml
  corpus_trim_plugin_identity   — slim a plugin's identity.yaml to lean overlay-required form
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from fastmcp import Context

from ..server import mcp
from .manifest import (
    DEFAULT_MANIFEST_PATH,
    DEFAULT_OUTPUT_ROOT,
    Manifest,
    Source,
    init_default_manifest,
    load_manifest,
    save_manifest,
)
from .runner import run_scan
from .scanner import list_scanners

from .plugin_engine.detector import (
    DetectedPlugin, default_plugin_dir, detect_installed_plugins,
)
from .plugin_engine.manual import (
    discover_manuals_for_plugin, extract_manual_text,
)
from .plugin_engine.research import (
    build_research_targets, build_synthesis_brief,
)


# ─── Vendor canonicalization helpers (used by corpus_canonicalize_plugins) ───
# Strips common vendor-suffix words ("DSP", "LLC", "GmbH", etc.) so different
# spellings of the same vendor ("Valhalla DSP, LLC" + "Valhalladsp") collapse
# to a stable canonical key.

_VENDOR_SUFFIX_WORDS = (
    "dsp", "llc", "inc", "gmbh", "ltd", "sas", "sa", "srl", "sl", "co", "corp",
    "corporation", "technologies", "technology", "sound", "sounds", "software",
    "audio", "labs", "lab", "studios", "studio", "records", "productions",
    "industries",
)


def _canon_vendor(vendor: str) -> str:
    """Canonical vendor key: lowercase + alphanum-only + iteratively strip
    suffix words at the END of the string (regardless of word boundary).

    "Valhalla DSP, LLC" → "valhalla"
    "Valhalladsp"       → "valhalla"
    "u-he"              → "uhe"
    """
    if not vendor:
        return "unknown"
    cleaned = re.sub(r"[^a-z0-9]+", "", vendor.lower())
    changed = True
    while changed:
        changed = False
        for s in _VENDOR_SUFFIX_WORDS:
            if cleaned.endswith(s) and len(cleaned) > len(s):
                cleaned = cleaned[: -len(s)]
                changed = True
                break
    return cleaned[:24] or "unknown"


def _vendor_score(v: str | None) -> float:
    """Higher score = prettier vendor display string. Used to pick the best
    representation across multi-format detections.

    Prefers strings with proper case + spaces ("Valhalla DSP, LLC") over
    bundle-id derivatives ("Valhalladsp")."""
    if not v:
        return -1
    return (
        sum(1 for c in v if c.isupper())
        + v.count(" ") * 2
        + v.count(",")
        + len(v) * 0.05
    )


# ─── corpus_init ─────────────────────────────────────────────────────────────


@mcp.tool()
def corpus_setup_wizard(ctx: Context) -> dict:
    """First-run setup — survey the user's filesystem for sensible scan candidates
    and return an approval packet for the agent to walk through with the user.

    Does NOT scan anything. Returns:
      - candidates: list of {category, path, file_count, sample_filenames,
                              description, recommended_default}
      - plugin_detection_offer: separate prompt for installed-plugin detection
      - instructions: how the agent should proceed (ask each, then add approved)
      - do_not_scan: paths that require explicit per-folder opt-in (e.g. .als projects)

    Categories surfaced (when present on this machine):
      - user_library_racks  — ~/Music/Ableton/User Library/Presets/*.adg
      - max_devices         — ~/Documents/Max <N>/Max for Live Devices/*.amxd
      - plugin_presets      — ~/Library/Audio/Presets/*.{aupreset,vstpreset,...}
      - samples_advisory    — sample folders (scanner not yet implemented)

    Personal .als project folders are NEVER auto-suggested (privacy-sensitive).
    """
    from .wizard import build_setup_proposal
    return build_setup_proposal()


@mcp.tool()
def corpus_init(ctx: Context) -> dict:
    """Initialize the user-corpus output directory + manifest.yaml.

    Creates ``~/.livepilot/atlas-overlays/user/`` (if missing) and writes a
    default manifest if one doesn't already exist. Idempotent: safe to call
    multiple times — preserves an existing manifest.

    Returns
    -------
    {manifest_path, output_root, sources, scanners_available, created: bool}
    """
    existed = DEFAULT_MANIFEST_PATH.exists()
    manifest = init_default_manifest(DEFAULT_MANIFEST_PATH)
    return {
        "manifest_path": str(DEFAULT_MANIFEST_PATH),
        "output_root": str(manifest.output_root),
        "sources": [s.id for s in manifest.sources],
        "scanners_available": list_scanners(),
        "created": not existed,
        "next_step": (
            "Add sources with corpus_add_source(...) "
            "then run corpus_scan() to build the corpus."
        ),
    }


# ─── corpus_add_source ───────────────────────────────────────────────────────


@mcp.tool()
def corpus_add_source(
    ctx: Context,
    source_id: str,
    type: str,
    path: str,
    recursive: bool = True,
    exclude_globs: list = None,
) -> dict:
    """Register a new scan source in the user manifest.

    Parameters
    ----------
    source_id      : unique short identifier, e.g. "my-projects". Used in
                     entity_id slugs and the namespace (user.<source_id>).
    type           : scanner type_id. Run corpus_list_scanners to see options.
                     Built-ins: "als", "adg", "amxd", "plugin-preset".
    path           : filesystem path to scan. May contain ``~``.
    recursive      : descend into subdirectories. Default True.
    exclude_globs  : list of glob patterns to skip (e.g. ["*Backup*"]).
    """
    if type not in list_scanners():
        return {
            "error": f"Unknown scanner type '{type}'.",
            "available_types": list_scanners(),
            "status": "error",
        }
    resolved = Path(path).expanduser()
    if not resolved.exists():
        return {
            "error": f"Path does not exist: {resolved}",
            "status": "error",
        }
    manifest = load_manifest(DEFAULT_MANIFEST_PATH)
    if manifest.find_source(source_id):
        return {
            "error": f"Source id '{source_id}' already exists.",
            "hint": "Use corpus_remove_source first if you want to redefine it.",
            "status": "error",
        }
    src = Source(
        id=source_id,
        type=type,
        path=path,
        recursive=recursive,
        exclude_globs=exclude_globs or [],
    )
    manifest.add_source(src)
    save_manifest(manifest, DEFAULT_MANIFEST_PATH)
    return {
        "added": {
            "source_id": source_id,
            "type": type,
            "path": str(resolved),
            "recursive": recursive,
        },
        "manifest_sources": [s.id for s in manifest.sources],
        "next_step": "Run corpus_scan() to index, or corpus_scan(source_id=...) to scan only this source.",
    }


# ─── corpus_remove_source ────────────────────────────────────────────────────


@mcp.tool()
def corpus_remove_source(ctx: Context, source_id: str) -> dict:
    """Remove a source from the manifest.

    Does NOT delete previously-written sidecars under the output root — those
    persist until you remove them manually. This makes redefining a source
    safe: removed → add → scan, no data loss.
    """
    manifest = load_manifest(DEFAULT_MANIFEST_PATH)
    removed = manifest.remove_source(source_id)
    if not removed:
        return {
            "error": f"No source with id '{source_id}' in manifest.",
            "available_sources": [s.id for s in manifest.sources],
            "status": "error",
        }
    save_manifest(manifest, DEFAULT_MANIFEST_PATH)
    return {
        "removed": source_id,
        "remaining_sources": [s.id for s in manifest.sources],
        "note": (
            "Sidecars under the output root are NOT auto-deleted. "
            "If you want a clean re-scan, remove the per-source subdirectory manually."
        ),
    }


# ─── corpus_scan ─────────────────────────────────────────────────────────────


@mcp.tool()
def corpus_scan(ctx: Context, source_id: str = "") -> dict:
    """Run scans on the user corpus.

    Parameters
    ----------
    source_id : optional. If non-empty, scan ONLY that source. Otherwise scan
                every source in the manifest.

    Returns
    -------
    {
      sources: [{source_id, type_id, files_scanned, files_skipped, files_errored,
                 errors, elapsed_sec}, ...],
      total_scanned, total_skipped, total_errored,
      output_root,
    }
    """
    manifest = load_manifest(DEFAULT_MANIFEST_PATH)
    if not manifest.sources:
        return {
            "error": "No sources in manifest.",
            "hint": "Add sources via corpus_add_source(...) first.",
            "status": "error",
        }
    if source_id and not manifest.find_source(source_id):
        return {
            "error": f"No source with id '{source_id}'.",
            "available_sources": [s.id for s in manifest.sources],
            "status": "error",
        }

    result = run_scan(
        manifest,
        only_source_id=source_id or None,
        update_manifest_path=DEFAULT_MANIFEST_PATH,
    )

    return {
        "sources": [
            {
                "source_id": s.source_id,
                "type_id": s.type_id,
                "files_scanned": s.files_scanned,
                "files_skipped": s.files_skipped,
                "files_errored": s.files_errored,
                "errors": s.errors[:20],  # cap for readability
                "elapsed_sec": s.elapsed_sec,
            }
            for s in result.sources
        ],
        "total_scanned": result.total_scanned,
        "total_skipped": result.total_skipped,
        "total_errored": result.total_errored,
        "output_root": str(manifest.output_root),
        "next_step": (
            "Restart the MCP server to load the new sidecars into the overlay "
            "index, then query via extension_atlas_search(namespace='user.<source_id>')."
        ),
    }


# ─── corpus_status ───────────────────────────────────────────────────────────


@mcp.tool()
def corpus_status(ctx: Context) -> dict:
    """Report manifest contents + freshness for each source."""
    manifest = load_manifest(DEFAULT_MANIFEST_PATH)
    sources_report = []
    for s in manifest.sources:
        resolved = s.resolved_path
        sources_report.append({
            "source_id": s.id,
            "type": s.type,
            "path": str(resolved),
            "exists": resolved.exists(),
            "recursive": s.recursive,
            "exclude_globs": s.exclude_globs,
            "last_scanned": s.last_scanned,
            "file_count": s.file_count,
        })
    return {
        "manifest_path": str(DEFAULT_MANIFEST_PATH),
        "output_root": str(manifest.output_root),
        "sources": sources_report,
        "scanners_available": list_scanners(),
    }


# ─── corpus_list_scanners ────────────────────────────────────────────────────


@mcp.tool()
def corpus_detect_plugins(
    ctx: Context,
    formats: list = None,
    persist: bool = True,
) -> dict:
    """Phase 2.1 + 2.2 — detect installed VST3 / AU / VST2 / AAX / LV2 plugins
    and extract identity metadata (vendor, version, unique_id, format) from
    each plugin's bundle without needing a DAW host.

    Parameters
    ----------
    formats : optional list of formats to restrict to, e.g. ["VST3", "AU"].
              Default = all formats found at OS-standard paths.
    persist : write the detected inventory to
              ~/.livepilot/atlas-overlays/user/plugins/_inventory.json (default True)

    Returns
    -------
    {plugins: [...], totals: {...}, inventory_path}
    """
    fmts = formats or None
    detected = detect_installed_plugins(formats=fmts)

    plugins_serialized = [p.to_dict() for p in detected]

    by_format: dict[str, int] = {}
    for p in detected:
        by_format[p.format] = by_format.get(p.format, 0) + 1

    inventory_path = None
    if persist:
        plugins_dir = DEFAULT_OUTPUT_ROOT / "plugins"
        plugins_dir.mkdir(parents=True, exist_ok=True)
        inventory_path = plugins_dir / "_inventory.json"
        inventory_path.write_text(
            json.dumps({
                "schema_version": 1,
                "plugins": plugins_serialized,
                "totals": by_format,
            }, indent=2, default=str),
            encoding="utf-8",
        )

    return {
        "plugins": plugins_serialized,
        "totals": {"all": len(detected), "by_format": by_format},
        "inventory_path": str(inventory_path) if inventory_path else None,
        "search_paths": [str(p) for p, _ in default_plugin_dir()],
    }


@mcp.tool()
def corpus_discover_manuals(
    ctx: Context,
    plugin_id: str = "",
    extract: bool = True,
    persist: bool = True,
) -> dict:
    """Phase 2.3 + 2.4 — find local manual files for a detected plugin and
    extract their text.

    Parameters
    ----------
    plugin_id : the plugin to search for (must already be in _inventory.json
                from corpus_detect_plugins). Required.
    extract   : also extract text from the top candidate (default True)
    persist   : write extracted text to
                ~/.livepilot/atlas-overlays/user/plugins/<plugin_id>/manual.txt

    Returns
    -------
    {plugin_id, candidates, extraction: {...}, manual_path}
    """
    if not plugin_id:
        return {
            "error": "plugin_id is required",
            "hint": "Run corpus_detect_plugins first, then pass a plugin_id from the result.",
            "status": "error",
        }
    inventory_path = DEFAULT_OUTPUT_ROOT / "plugins" / "_inventory.json"
    if not inventory_path.exists():
        return {
            "error": "No plugin inventory found.",
            "hint": "Run corpus_detect_plugins first.",
            "status": "error",
        }
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    matches = [p for p in inventory.get("plugins", []) if p["plugin_id"] == plugin_id]
    if not matches:
        return {
            "error": f"plugin_id '{plugin_id}' not found in inventory.",
            "available_count": len(inventory.get("plugins", [])),
            "status": "error",
        }
    plugin_dict = matches[0]
    plugin = DetectedPlugin(**{k: v for k, v in plugin_dict.items() if k in DetectedPlugin.__dataclass_fields__})

    candidates = discover_manuals_for_plugin(plugin)
    candidates_serialized = [
        {
            "path": c.path,
            "extension": c.extension,
            "size_kb": c.size_kb,
            "name_score": c.name_score,
            "location_score": c.location_score,
        }
        for c in candidates
    ]

    extraction_result = None
    manual_path = None
    if extract and candidates:
        top = candidates[0]
        extraction = extract_manual_text(plugin, top)
        extraction_result = {
            "source_path": extraction.source_path,
            "source_kind": extraction.source_kind,
            "char_count": extraction.char_count,
            "page_count": extraction.page_count,
            "section_count": len(extraction.sections),
            "section_titles": [s["title"] for s in extraction.sections][:30],
            "truncated": extraction.truncated,
            "error": extraction.error,
        }
        if persist and extraction.text and not extraction.error:
            plugin_dir = DEFAULT_OUTPUT_ROOT / "plugins" / plugin.plugin_id
            plugin_dir.mkdir(parents=True, exist_ok=True)
            manual_path = plugin_dir / "manual.txt"
            manual_path.write_text(extraction.text, encoding="utf-8")
            (plugin_dir / "manual_sections.json").write_text(
                json.dumps(extraction.sections, indent=2),
                encoding="utf-8",
            )

    return {
        "plugin_id": plugin_id,
        "plugin_identity": {
            "name": plugin.name, "vendor": plugin.vendor,
            "format": plugin.format, "version": plugin.version,
        },
        "candidates": candidates_serialized,
        "candidates_total": len(candidates),
        "extraction": extraction_result,
        "manual_path": str(manual_path) if manual_path else None,
    }


@mcp.tool()
def corpus_canonicalize_plugins(
    ctx: Context,
    skip_vendors: list = None,
    skip_name_prefixes: list = None,
) -> dict:
    """Dedupe the plugin inventory by canonical vendor + name; prefer VST3 as
    primary format; pick the prettiest vendor string across formats. Writes
    `plugins/_canonical.json` next to `_inventory.json`.

    The canonical inventory is what efficient Phase 3+4 research consumes —
    instead of running research separately on the AU and VST3 versions of the
    same plugin, the canonicalized record represents BOTH formats with
    `formats_available: [AU, VST3]` so a single identity.yaml covers both.

    Filtering:
      skip_vendors        — list of vendor names to drop (default: ["Apple",
                            "Splice"]) — exclude system AUs + utility apps
      skip_name_prefixes  — list of name-prefix patterns to drop (default:
                            ["Splice"]) — exclude installer/helper plugins

    Returns
    -------
    {canonical_count, formats_distribution, top_vendors, canonical_path}
    """
    inventory_path = DEFAULT_OUTPUT_ROOT / "plugins" / "_inventory.json"
    if not inventory_path.exists():
        return {
            "error": "No inventory found. Run corpus_detect_plugins first.",
            "status": "error",
        }
    skip_vendors_lower = {v.lower() for v in (skip_vendors or ["Apple", "Splice"])}
    skip_prefixes_lower = [p.lower() for p in (skip_name_prefixes or ["Splice"])]

    inv = json.loads(inventory_path.read_text(encoding="utf-8"))
    raw_plugins = inv.get("plugins", [])

    # Group raw plugins by (canonical_vendor, normalized_name)
    groups: dict = {}
    for p in raw_plugins:
        v_lc = (p.get("vendor") or "").lower()
        if not v_lc or v_lc in skip_vendors_lower:
            continue
        nm = (p.get("name") or "").lower()
        if any(nm.startswith(pre) for pre in skip_prefixes_lower):
            continue
        # Strip parenthetical role qualifiers so "Drambo" + "Drambo (Fx)" merge
        nm_norm = (
            nm.replace(" (instrument)", "").replace(" (instr)", "")
              .replace(" (fx)", "").replace(" (midi fx)", "")
              .replace(" (8 outs)", "").strip()
        )
        key = (_canon_vendor(p.get("vendor") or ""), nm_norm)
        groups.setdefault(key, []).append(p)

    canonical: list[dict] = []
    for (canon_v, name), entries in groups.items():
        # Sort: VST3 first, then AU, then others; within format, prettiest vendor
        entries.sort(key=lambda p: (
            0 if p.get("format") == "VST3" else 1 if p.get("format") == "AU" else 2,
            -_vendor_score(p.get("vendor") or ""),
        ))
        primary = dict(entries[0])
        # Pretty vendor across all entries (not just primary's)
        pretty_vendor = max(
            (e.get("vendor") for e in entries if e.get("vendor")),
            key=_vendor_score,
        )
        formats = sorted({e.get("format") for e in entries if e.get("format")})
        # Stable plugin_id: canon_v + primary's name
        primary["vendor"] = pretty_vendor
        primary["plugin_id"] = re.sub(
            r"[^a-z0-9]+", "-", f"{canon_v}-{primary.get('name', '')}".lower(),
        ).strip("-")
        primary["formats_available"] = formats
        canonical.append(primary)

    canonical.sort(key=lambda d: (d.get("vendor", ""), d.get("name", "")))

    canonical_path = DEFAULT_OUTPUT_ROOT / "plugins" / "_canonical.json"
    canonical_path.write_text(
        json.dumps(canonical, indent=2, default=str),
        encoding="utf-8",
    )

    # Report stats
    formats_dist: dict[str, int] = {}
    vendor_counts: dict[str, int] = {}
    for d in canonical:
        for f in d.get("formats_available") or []:
            formats_dist[f] = formats_dist.get(f, 0) + 1
        v = d.get("vendor") or "unknown"
        vendor_counts[v] = vendor_counts.get(v, 0) + 1

    top_vendors = sorted(vendor_counts.items(), key=lambda kv: -kv[1])[:15]
    return {
        "canonical_count": len(canonical),
        "raw_count": len(raw_plugins),
        "skipped_vendors": sorted(skip_vendors_lower),
        "skipped_name_prefixes": sorted(skip_prefixes_lower),
        "formats_distribution": formats_dist,
        "top_vendors": [{"vendor": v, "count": n} for v, n in top_vendors],
        "canonical_path": str(canonical_path),
    }


@mcp.tool()
def corpus_cluster_plugins(
    ctx: Context,
    min_cluster_size: int = 2,
) -> dict:
    """Group canonical plugins by vendor; return a cluster manifest the agent
    uses to dispatch Phase 3+4 research efficiently.

    For each cluster (vendor with >= min_cluster_size plugins) the agent runs
    ONE shared WebSearch pass + writes N identity yamls — vs N independent
    research passes for singletons. Cluster research lowers per-plugin token
    cost by 3-5x for vendors documented as a coherent product line.

    Returns
    -------
    {
      clusters:    [{vendor, plugin_count, plugin_ids: [...]}],
      singletons:  [{plugin_id, vendor, name}],
      total_plugins, cluster_count, singleton_count,
      identity_yaml_status: {covered: [ids], missing: [ids]},
    }
    """
    canonical_path = DEFAULT_OUTPUT_ROOT / "plugins" / "_canonical.json"
    if not canonical_path.exists():
        return {
            "error": "No canonical inventory. Run corpus_canonicalize_plugins first.",
            "status": "error",
        }
    canonical = json.loads(canonical_path.read_text(encoding="utf-8"))

    by_vendor: dict[str, list[dict]] = {}
    for d in canonical:
        v = d.get("vendor") or "unknown"
        by_vendor.setdefault(v, []).append(d)

    clusters: list[dict] = []
    singletons: list[dict] = []
    plugins_root = DEFAULT_OUTPUT_ROOT / "plugins"
    covered: list[str] = []
    missing: list[str] = []

    for vendor, items in sorted(by_vendor.items()):
        if len(items) >= min_cluster_size:
            clusters.append({
                "vendor": vendor,
                "plugin_count": len(items),
                "plugin_ids": [d.get("plugin_id") for d in items],
                "plugin_names": [d.get("name") for d in items],
                "research_strategy": (
                    "Run ONE shared WebSearch pass on this vendor's product line, "
                    "cache to _shared_research/<vendor-slug>/, then write N lean "
                    "identity yamls citing the shared cache."
                ),
            })
        else:
            for d in items:
                singletons.append({
                    "plugin_id": d.get("plugin_id"),
                    "vendor": vendor,
                    "name": d.get("name"),
                })
        for d in items:
            pid = d.get("plugin_id") or ""
            yaml_p = plugins_root / pid / "identity.yaml"
            if yaml_p.exists():
                covered.append(pid)
            else:
                missing.append(pid)

    # Sort clusters by size descending — largest research-payoff first
    clusters.sort(key=lambda c: -c["plugin_count"])

    return {
        "clusters": clusters,
        "singletons": singletons,
        "total_plugins": len(canonical),
        "cluster_count": len(clusters),
        "singleton_count": len(singletons),
        "identity_yaml_status": {
            "covered": covered,
            "missing": missing,
            "covered_count": len(covered),
            "missing_count": len(missing),
        },
        "next_step": (
            "For clusters: dispatch one sonnet subagent per cluster with the "
            "plugin_ids list, pointing each at corpus_emit_synthesis_briefs(plugin_ids=[...]). "
            "For singletons: batch ~5-7 per agent (no shared theme). Cap parallel "
            "agent count at 8."
        ),
    }


@mcp.tool()
def corpus_trim_plugin_identity(
    ctx: Context,
    plugin_id: str = "",
    research_priority: str = "low",
) -> dict:
    """Slim a plugin's identity.yaml to the lean overlay-required shape.

    Use when the user explicitly deprioritizes a plugin ("don't waste tokens
    on this one") OR when post-processing a Phase 4 batch where some plugins
    received deeper research than the user wants persisted. Keeps the file
    queryable via atlas_search but drops the long key_techniques /
    parameter_glossary / comparable_plugins sections.

    Result preserves: entity_id, entity_type, name, description, tags (with
    `research-priority:<level>` appended), artists, plugin_id, vendor, format,
    formats_available, sonic_fingerprint (capped at 400 chars).

    Result drops: reach_for, avoid, key_techniques, parameter_glossary,
    comparable_plugins, genre_affinity, producer_anchors, cache_provenance.

    Parameters
    ----------
    plugin_id          : the plugin to trim. Required.
    research_priority  : tag value: "low" / "medium" / "skip". Default "low".
    """
    if not plugin_id:
        return {"error": "plugin_id is required", "status": "error"}
    yaml_path = DEFAULT_OUTPUT_ROOT / "plugins" / plugin_id / "identity.yaml"
    if not yaml_path.exists():
        return {
            "error": f"No identity.yaml for plugin_id '{plugin_id}'",
            "status": "error",
        }
    import yaml as _yaml
    full = _yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    if not isinstance(full, dict):
        return {"error": "identity.yaml is not a dict", "status": "error"}

    original_size = yaml_path.stat().st_size

    slim = {
        "entity_id": full.get("entity_id", plugin_id),
        "entity_type": full.get("entity_type", "installed_plugin"),
        "name": full.get("name", ""),
        "description": (full.get("description") or "")[:200],
        # Filter out genre tags but keep core overlay-search signal; append research_priority
        "tags": (
            [t for t in (full.get("tags") or []) if not t.startswith("genre:")][:8]
            + [f"research-priority:{research_priority}"]
        ),
        "artists": full.get("artists") or [],
        "plugin_id": full.get("entity_id", plugin_id),
        "vendor": full.get("vendor", ""),
        "format": full.get("format", ""),
        "formats_available": full.get("formats_available") or [],
        "sonic_fingerprint": (full.get("sonic_fingerprint") or "")[:400],
        "research_priority": research_priority,
        "schema_version": full.get("schema_version", 1),
    }
    yaml_path.write_text(
        _yaml.dump(slim, sort_keys=False, default_flow_style=False, width=200, allow_unicode=True),
        encoding="utf-8",
    )
    return {
        "plugin_id": plugin_id,
        "size_before_bytes": original_size,
        "size_after_bytes": yaml_path.stat().st_size,
        "research_priority": research_priority,
        "yaml_path": str(yaml_path),
    }


@mcp.tool()
def corpus_research_targets(
    ctx: Context,
    plugin_id: str = "",
) -> dict:
    """Phase 3 — emit a structured WebSearch task packet for the agent to fulfill.

    This tool does NOT call the web. It returns the queries + cache locations
    + instructions; the Claude agent uses WebSearch + WebFetch + sonnet
    subagents to fulfill them.

    Returns
    -------
    The Phase 3 packet — see PLUGIN_KNOWLEDGE_ENGINE.md §"Research target packet".
    """
    if not plugin_id:
        return {"error": "plugin_id is required", "status": "error"}
    inventory_path = DEFAULT_OUTPUT_ROOT / "plugins" / "_inventory.json"
    if not inventory_path.exists():
        return {
            "error": "No inventory; run corpus_detect_plugins first.",
            "status": "error",
        }
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    matches = [p for p in inventory.get("plugins", []) if p["plugin_id"] == plugin_id]
    if not matches:
        return {"error": f"plugin_id '{plugin_id}' not in inventory.", "status": "error"}
    plugin = DetectedPlugin(**{k: v for k, v in matches[0].items() if k in DetectedPlugin.__dataclass_fields__})

    # Look for an extracted local manual to inform the packet
    manual_path = DEFAULT_OUTPUT_ROOT / "plugins" / plugin_id / "manual.txt"
    sections_path = DEFAULT_OUTPUT_ROOT / "plugins" / plugin_id / "manual_sections.json"
    local_manual = None
    if manual_path.exists():
        from .plugin_engine.manual import ManualExtraction
        sections = []
        if sections_path.exists():
            try:
                sections = json.loads(sections_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        local_manual = ManualExtraction(
            plugin_id=plugin_id, source_path=str(manual_path),
            source_kind=manual_path.suffix.lstrip(".") or "txt",
            text=manual_path.read_text(encoding="utf-8", errors="ignore"),
            char_count=manual_path.stat().st_size,
            sections=sections,
        )

    return build_research_targets(plugin, local_manual)


@mcp.tool()
def corpus_emit_synthesis_briefs(
    ctx: Context,
    plugin_ids: list = None,
) -> dict:
    """Phase 4 — emit sonnet-subagent briefs for plugin identity synthesis.

    For each requested plugin, builds a self-contained brief that an agent
    dispatches to a sonnet subagent (via the Agent tool) which writes one
    identity.yaml at the brief's output_path.

    Parameters
    ----------
    plugin_ids : list of plugin_ids to emit briefs for. If empty, emits for
                 every plugin in the inventory.

    Returns
    -------
    {briefs: [{plugin_id, brief, output_path}, ...], total}
    """
    inventory_path = DEFAULT_OUTPUT_ROOT / "plugins" / "_inventory.json"
    if not inventory_path.exists():
        return {"error": "Run corpus_detect_plugins first.", "status": "error"}
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    all_plugins = inventory.get("plugins", [])

    target_ids = set(plugin_ids) if plugin_ids else None
    briefs = []
    for plugin_dict in all_plugins:
        pid = plugin_dict.get("plugin_id")
        if target_ids is not None and pid not in target_ids:
            continue
        plugin = DetectedPlugin(**{k: v for k, v in plugin_dict.items() if k in DetectedPlugin.__dataclass_fields__})

        # Read any extracted manual + research cache that exist
        manual_path = DEFAULT_OUTPUT_ROOT / "plugins" / pid / "manual.txt"
        local_manual = None
        if manual_path.exists():
            from .plugin_engine.manual import ManualExtraction
            local_manual = ManualExtraction(
                plugin_id=pid, source_path=str(manual_path),
                source_kind="txt",
                text=manual_path.read_text(encoding="utf-8", errors="ignore"),
                char_count=manual_path.stat().st_size,
                sections=[],
            )
        research_root = DEFAULT_OUTPUT_ROOT / "plugins" / pid / "research"

        brief = build_synthesis_brief(plugin, local_manual, research_root if research_root.exists() else None)
        briefs.append({
            "plugin_id": pid,
            "brief": brief,
            "output_path": brief["output_path"],
        })

    return {
        "briefs": briefs,
        "total": len(briefs),
        "instruction": (
            "For each brief: dispatch one sonnet subagent (Agent tool with "
            "subagent_type='general-purpose', model='sonnet') passing the brief "
            "as context. The subagent reads brief['synthesis_inputs'] and writes "
            "the YAML at brief['output_path']. Cap parallel subagents at ~5 to "
            "avoid main-context bloat."
        ),
    }


@mcp.tool()
def corpus_list_scanners(ctx: Context) -> dict:
    """Enumerate registered scanner types and their supported file extensions.

    Useful for discovering what content types the corpus builder can handle on
    this install. Custom scanners registered by the user via @register_scanner
    show up here too.
    """
    from .scanner import SCANNERS
    out = {}
    for type_id, cls in SCANNERS.items():
        out[type_id] = {
            "extensions": cls.file_extensions,
            "output_subdir": cls.output_subdir,
            "schema_version": cls.schema_version,
        }
    return {"scanners": out, "count": len(out)}
