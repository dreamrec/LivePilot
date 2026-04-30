"""Atlas MCP tools — search, suggest, compare, and scan the device database.

6 tools for the atlas domain.
"""

from __future__ import annotations

import json
import os
import time

from fastmcp import Context

from ..server import mcp


def _get_ableton(ctx: Context):
    return ctx.lifespan_context["ableton"]


def _get_atlas():
    """Get the global AtlasManager instance, loading lazily if needed.

    Uses the thread-safe singleton helper — concurrent FastMCP tool calls no
    longer race on the check-then-set, and the atlas auto-reloads from disk
    if device_atlas.json's mtime advanced (e.g. after scan_full_library).
    """
    from . import get_atlas
    try:
        return get_atlas()
    except FileNotFoundError:
        return None


@mcp.tool()
def atlas_search(ctx: Context, query: str, category: str = "all", limit: int = 10) -> dict:
    """Search the device atlas for instruments, effects, kits, or plugins.

    Searches BOTH:
      1. The bundled factory atlas (5,264 devices across 33 packs)
      2. The user-local overlay corpus (~/.livepilot/atlas-overlays/) — including
         user-scanned Max devices, racks, plugin presets, and AI-synthesized
         plugin identity yamls. This is the wiring that lets LivePilot reason
         over the user's PERSONAL library, not just Ableton's defaults.

    query:    natural language search — name, sonic character, use case, or genre
              Examples: "warm analog bass", "reverb", "808 kit", "granular",
                        "my arpeggiator", "the polyrhythmic sequencer in my user library"
    category: filter by category (all, instruments, audio_effects, midi_effects,
              max_for_live, drum_kits, plugins). For user-corpus content, pass
              "all" — overlay entity_types are surfaced regardless of category.
    limit:    max combined results (default 10). Per-source limits are split
              proportionally; factory + user content interleave by score.
    """
    atlas = _get_atlas()
    factory_results = []
    if atlas is not None:
        factory_results = atlas.search(query, category=category, limit=limit)

    # Also search user-local overlay namespaces (v1.23.6+). All non-bundled
    # namespaces (user, m4l-devices, elektron, etc.) get queried — the overlay
    # system stores everything from corpus_scan + corpus_emit_synthesis_briefs +
    # the v1.23.0 extension overlays here.
    overlay_results = []
    try:
        from .overlays import get_overlay_index
        idx = get_overlay_index()
        # Search all non-`packs` namespaces; `packs` is already in the bundled atlas
        for ns in idx.list_namespaces():
            if ns == "packs":
                continue
            overlay_results.extend(idx.search(query, namespace=ns, limit=limit))
    except Exception:  # noqa: BLE001 — never fail atlas_search over an overlay glitch
        pass

    # Allocate the result budget so the user corpus actually surfaces alongside
    # the factory atlas — split limit roughly 50/50 when both sources have hits.
    # If only one source has results, it gets the full limit.
    has_factory = len(factory_results) > 0
    has_overlay = len(overlay_results) > 0
    if has_factory and has_overlay:
        factory_budget = (limit + 1) // 2   # rounds up — factory gets the extra slot
        overlay_budget = limit // 2
    elif has_factory:
        factory_budget = limit
        overlay_budget = 0
    else:
        factory_budget = 0
        overlay_budget = limit

    results: list[dict] = [
        {
            "id": r["device"].get("id", ""),
            "name": r["device"].get("name", ""),
            "uri": r["device"].get("uri", ""),
            "category": r["device"].get("category", ""),
            "sonic_description": r["device"].get("sonic_description", "")[:120],
            "character_tags": r["device"].get("character_tags", [])[:5],
            "enriched": r["device"].get("enriched", False),
            "score": r.get("score", 0),
            "source": "factory_atlas",
        }
        for r in factory_results[:factory_budget]
    ]
    for entry in overlay_results[:overlay_budget]:
        results.append({
            "id": entry.entity_id,
            "name": entry.name,
            "uri": "",  # overlay entries don't have Live browser URIs — caller resolves via search_browser
            "category": entry.entity_type,
            "sonic_description": (entry.description or "")[:120],
            "character_tags": list(entry.tags)[:5],
            "enriched": True,
            "score": 0,  # overlay search has its own ranking; surfaced with no factory-comparable score
            "source": f"user_overlay:{entry.namespace}",
        })

    return {
        "query": query,
        "category": category,
        "count": len(results),
        "factory_count": len(factory_results),
        "overlay_count": len(overlay_results),
        "results": results,
    }


@mcp.tool()
def atlas_device_info(ctx: Context, device_id: str) -> dict:
    """Get complete atlas knowledge about a device — parameters, recipes, pairings, gotchas.

    device_id: the atlas ID or device name (e.g., "drift", "Compressor", "808_core_kit")
    """
    atlas = _get_atlas()
    if atlas is None:
        return {"error": "Atlas not loaded. Run scan_full_library first."}

    entry = atlas.lookup(device_id)
    if entry is None:
        return {"error": f"Device '{device_id}' not found in atlas", "suggestion": "Use atlas_search to find devices"}
    return entry


@mcp.tool()
def atlas_suggest(
    ctx: Context,
    intent: str,
    genre: str = "",
    energy: str = "medium",
    key: str = "",
) -> dict:
    """Suggest devices for a production intent.

    intent: what you're trying to achieve — "warm bass", "crispy hi-hats", "evolving texture"
    genre:  target genre for better recommendations
    energy: low/medium/high — affects sonic character suggestions
    key:    musical key context (e.g., "Cm") for tuned percussion suggestions
    """
    atlas = _get_atlas()
    if atlas is None:
        return {"error": "Atlas not loaded. Run scan_full_library first."}

    results = atlas.suggest(intent, genre=genre, energy=energy)
    return {
        "intent": intent,
        "genre": genre,
        "energy": energy,
        "suggestions": [
            {
                "device_id": r["device"]["id"],
                "device_name": r["device"]["name"],
                "uri": r["device"].get("uri", ""),
                "rationale": r["rationale"],
                "recipe": r.get("recipe"),
            }
            for r in results
        ],
    }


@mcp.tool()
def atlas_chain_suggest(ctx: Context, role: str, genre: str = "") -> dict:
    """Suggest a full device chain for a track role.

    Searches BOTH the bundled factory atlas AND user-local overlay namespaces
    (e.g., m4l-devices, elektron, user). User-corpus devices (PEACH, Particle-Reverb,
    te.drone, etc.) are surfaced when their tags match the role+genre keywords.

    role:  the musical role — "bass", "lead", "pad", "drums", "percussion", "texture"
    genre: target genre for style-appropriate choices
    """
    atlas = _get_atlas()
    if atlas is None:
        return {"error": "Atlas not loaded. Run scan_full_library first."}

    factory_result = atlas.chain_suggest(role, genre=genre)

    # Also search user-local overlay namespaces for devices that match this role+genre.
    # Merge any hits as additional overlay_suggestions on top of the factory chain.
    overlay_suggestions = []
    try:
        from .overlays import get_overlay_index
        idx = get_overlay_index()
        # Build a query from role + genre keywords
        query_parts = [role]
        if genre:
            query_parts.append(genre)
        query = " ".join(query_parts)

        for ns in idx.list_namespaces():
            if ns == "packs":
                continue
            hits = idx.search(query, namespace=ns, limit=5)
            for entry in hits:
                overlay_suggestions.append({
                    "namespace": entry.namespace,
                    "entity_id": entry.entity_id,
                    "name": entry.name,
                    "description": (entry.description or "")[:120],
                    "tags": list(entry.tags)[:5],
                    "source": f"user_overlay:{entry.namespace}",
                    "note": "Load via search_browser or extension_atlas_get; no Live URI.",
                })
    except Exception:  # noqa: BLE001 — never fail chain_suggest over an overlay glitch
        pass

    result = dict(factory_result)
    result["overlay_suggestions"] = overlay_suggestions
    result["factory_count"] = len(factory_result.get("chain", []))
    result["overlay_count"] = len(overlay_suggestions)
    return result


@mcp.tool()
def atlas_compare(ctx: Context, device_a: str, device_b: str, role: str = "") -> dict:
    """Compare two devices — strengths, weaknesses, and recommendation for a role.

    device_a: first device name or ID
    device_b: second device name or ID
    role:     optional role context (e.g., "bass", "pad")
    """
    atlas = _get_atlas()
    if atlas is None:
        return {"error": "Atlas not loaded. Run scan_full_library first."}

    return atlas.compare(device_a, device_b, role=role)


@mcp.tool()
def atlas_describe_chain(
    ctx: Context,
    description: str,
    genre: str = "",
    limit_per_role: int = 3,
) -> dict:
    """Free-text describe-a-chain: "a granular pad that sounds like Tim Hecker"
    → device chain proposal.

    The mirror of `splice_describe_sound` for the device library. Where
    `atlas_chain_suggest(role, genre)` takes structured inputs, this takes
    a free-form sentence and proposes a chain by:

      1. Parsing role hints from the description ("bass", "pad", "lead",
         "percussion", "drum", "texture", "vocal", "keys")
      2. Parsing aesthetic hints (artist names → `artist-vocabularies.md`,
         genre names → `genre-vocabularies.md`, character words → atlas tags)
      3. Searching the atlas with those terms
      4. Proposing the top devices per role with brief rationale

    This does NOT autoload anything — it returns a proposal the caller can
    review, adjust, then execute with `load_browser_item` + a chain of FX.

    description: free text. Examples:
        "a granular pad that sounds like Tim Hecker"
        "warm analog bass for minimal techno, deep and dubby"
        "chopped vocal melody, Akufen-style microhouse"
        "brittle mallet percussion with long reverb, Stars of the Lid territory"
    genre:       optional genre bias if the description is genre-agnostic
    limit_per_role: max devices to suggest per detected role (default 3)

    Returns {description, detected_roles, detected_aesthetic,
             per_role_suggestions: [...], chain_proposal: [...]}.
    """
    atlas = _get_atlas()
    if atlas is None:
        return {"error": "Atlas not loaded. Run scan_full_library first."}
    if not description or not description.strip():
        return {"error": "description is required"}

    desc_lower = description.lower().strip()

    # ── Detect roles ──────────────────────────────────────────────
    ROLE_KEYWORDS = {
        "bass":       ["bass", "sub", "808", "low end", "bottom"],
        "lead":       ["lead", "melody", "topline", "hook"],
        "pad":        ["pad", "texture", "atmosphere", "atmos", "drone", "ambient"],
        "keys":       ["keys", "piano", "rhodes", "wurli", "wurly", "chord"],
        "percussion": ["percussion", "perc", "shaker", "conga", "claves", "tambourine"],
        "drums":      ["drums", "drum kit", "kick", "snare", "hat", "hi-hat", "hihat", "break"],
        "vocal":      ["vocal", "vox", "voice", "chop", "chant"],
        "fx":         ["fx", "riser", "downlifter", "sweep", "whoosh", "impact"],
    }
    detected_roles = []
    for role, keywords in ROLE_KEYWORDS.items():
        if any(k in desc_lower for k in keywords):
            detected_roles.append(role)
    if not detected_roles:
        detected_roles = ["pad"]  # sensible default

    # ── Detect aesthetic / artist cues ────────────────────────────
    ARTIST_TO_TAGS = {
        "villalobos":     ["minimal_techno", "deep_minimal"],
        "hawtin":         ["minimal_techno", "deep_minimal"],
        "plastikman":     ["minimal_techno"],
        "basic channel":  ["dub_techno", "dub"],
        "rhythm and sound": ["dub_techno", "dub"],
        "voigt":          ["ambient", "dub_techno"],
        "gas":            ["ambient"],
        "basinski":       ["ambient", "drone"],
        "stars of the lid": ["ambient", "drone", "modern_classical"],
        "hecker":         ["ambient", "drone", "experimental"],
        "aphex":          ["idm", "experimental"],
        "autechre":       ["idm", "experimental"],
        "dilla":          ["hip_hop", "lo_fi"],
        "burial":         ["dubstep", "uk_garage", "ambient"],
        "akufen":         ["microhouse"],
        "isolee":         ["microhouse", "deep_house"],
        "henke":          ["minimal_techno", "experimental"],
        "monolake":       ["minimal_techno", "experimental"],
        "tycho":          ["synthwave", "electronica"],
        "boards of canada": ["downtempo", "lo_fi"],
    }
    CHARACTER_TAGS = [
        "warm", "cold", "bright", "dark", "lush", "thin", "fat", "metallic",
        "granular", "glitch", "gritty", "clean", "wet", "dry", "resonant",
        "breathy", "analog", "digital", "vintage", "modern", "organic", "synthetic",
    ]
    GENRE_KEYWORDS = [
        "microhouse", "minimal", "techno", "house", "deep house", "ambient",
        "drone", "idm", "experimental", "dubstep", "dnb", "drum and bass",
        "hip hop", "hip-hop", "lo-fi", "lo fi", "lofi", "trap", "garage",
        "dub techno", "dub", "jazz", "classical", "cinematic", "synthwave",
        "vaporwave", "ambient techno", "deep minimal",
    ]
    detected_aesthetic = []
    for artist, tags in ARTIST_TO_TAGS.items():
        if artist in desc_lower:
            detected_aesthetic.extend(tags)
    for tag in CHARACTER_TAGS:
        if f" {tag}" in f" {desc_lower}":
            detected_aesthetic.append(tag)
    for g in GENRE_KEYWORDS:
        if g in desc_lower:
            detected_aesthetic.append(g.replace(" ", "_").replace("-", "_"))
    if genre:
        detected_aesthetic.append(genre.lower())
    # Dedupe preserving order
    seen = set()
    detected_aesthetic = [
        t for t in detected_aesthetic
        if not (t in seen or seen.add(t))
    ]

    # ── Build per-role suggestions via atlas.suggest + overlay search ─
    # Load overlay index once for all role iterations (graceful no-op on failure)
    _overlay_idx = None
    try:
        from .overlays import get_overlay_index
        _overlay_idx = get_overlay_index()
    except Exception:  # noqa: BLE001
        pass

    per_role_suggestions = []
    for role in detected_roles:
        # Build an intent string that combines role + aesthetic cues
        intent_parts = [role]
        intent_parts.extend(detected_aesthetic[:3])  # top 3 aesthetic tags
        intent = " ".join(intent_parts)
        results = atlas.suggest(
            intent=intent,
            genre=(detected_aesthetic[0] if detected_aesthetic else genre),
            energy="medium",
            limit=int(limit_per_role),
        )
        factory_suggestions = [
            {
                "device_id": r["device"].get("id", ""),
                "device_name": r["device"].get("name", ""),
                "uri": r["device"].get("uri", ""),
                "rationale": r.get("rationale", ""),
                "recipe": r.get("recipe"),
                "source": "factory_atlas",
            }
            for r in results
        ]

        # Query overlay namespaces for matching user-corpus devices
        overlay_hits = []
        if _overlay_idx is not None:
            try:
                for ns in _overlay_idx.list_namespaces():
                    if ns == "packs":
                        continue
                    hits = _overlay_idx.search(intent, namespace=ns, limit=limit_per_role)
                    for entry in hits:
                        overlay_hits.append({
                            "device_id": entry.entity_id,
                            "device_name": entry.name,
                            "uri": "",
                            "rationale": (entry.description or "")[:120],
                            "recipe": None,
                            "source": f"user_overlay:{entry.namespace}",
                        })
            except Exception:  # noqa: BLE001
                pass

        per_role_suggestions.append({
            "role": role,
            "intent_used": intent,
            "suggestions": factory_suggestions + overlay_hits,
            "factory_count": len(factory_suggestions),
            "overlay_count": len(overlay_hits),
        })

    # ── Propose a simple chain from the highest-ranked suggestions ─
    chain_proposal = []
    position = 0
    for role_block in per_role_suggestions:
        if not role_block["suggestions"]:
            continue
        top = role_block["suggestions"][0]
        chain_proposal.append({
            "position": position,
            "role": role_block["role"],
            "device_name": top["device_name"],
            "device_id": top["device_id"],
            "uri": top["uri"],
            "why": top["rationale"],
        })
        position += 1

    # ── Cross-reference aesthetic to the vocabulary files ──────────
    next_steps = []
    if any("villalobos" in desc_lower or a in detected_aesthetic for a in
           ("microhouse", "deep_minimal", "minimal_techno", "dub_techno",
            "ambient", "drone", "idm", "experimental")):
        next_steps.append(
            "Cross-reference "
            "`livepilot/skills/livepilot-core/references/artist-vocabularies.md` "
            "and `genre-vocabularies.md` for deeper aesthetic guidance."
        )
    if not detected_aesthetic:
        next_steps.append(
            "No aesthetic or genre cues detected. If the description "
            "should have matched, add it to the ARTIST_TO_TAGS map or "
            "provide genre= explicitly."
        )
    next_steps.append(
        "Call `atlas_techniques_for_device(device_id)` on any proposal "
        "to see what techniques reference it."
    )

    return {
        "description": description,
        "detected_roles": detected_roles,
        "detected_aesthetic": detected_aesthetic,
        "per_role_suggestions": per_role_suggestions,
        "chain_proposal": chain_proposal,
        "next_steps": next_steps,
    }


@mcp.tool()
def atlas_techniques_for_device(ctx: Context, device_id: str) -> dict:
    """Reverse-lookup: what techniques / principles reference this device?

    Answers questions like "what can I do with Granulator III?" by returning
    every technique across the knowledge base that mentions this device —
    the device's own `signature_techniques`, sample-manipulation principles
    that use it, sound-design-deep.md references. Complements
    `atlas_device_info` (which returns the device's own curated fields) by
    showing the device's OUTWARD connections — how it fits into techniques
    that weren't written from the device's perspective.

    device_id: atlas ID (e.g. "granulator_iii", "simpler", "analog"). Use
               `atlas_search` or `atlas_device_info` to discover IDs.

    Returns {device_id, technique_count, techniques: [...]}, where each
    technique entry has:
      - technique: short name (e.g. "Vocal micro-chop (Akufen)")
      - description: one-line
      - aesthetic: list of aesthetic/genre tags
      - source: where this technique lives (`atlas/<id>`,
                `sample-techniques.md`, `sound-design-deep.md`)
      - kind: signature_technique | sample_technique | sound_design_principle

    Index is auto-generated from the knowledge base; regenerate via the
    companion script when adding new techniques (rare — most additions
    happen through enrichment YAMLs, which the index reads directly).
    """
    import json, os
    index_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "device_techniques_index.json",
    )
    if not os.path.isfile(index_path):
        return {
            "error": "device_techniques_index.json not found",
            "hint": "regenerate via the post-v1.17 reverse-index builder script",
        }
    try:
        with open(index_path, "r") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        return {"error": f"Failed to load index: {exc}"}

    if not device_id:
        # Return a summary of indexed devices
        devices = data.get("devices", {})
        return {
            "indexed_device_count": len(devices),
            "total_cross_references": data.get("entry_count", 0),
            "devices": sorted(devices.keys()),
            "hint": "Pass a device_id for per-device techniques",
        }

    entries = data.get("devices", {}).get(device_id)
    if entries is None:
        return {
            "device_id": device_id,
            "technique_count": 0,
            "techniques": [],
            "hint": (
                "No techniques indexed for this device. Try a different ID "
                "or use `atlas_search` to find the correct one. Devices "
                "with no cross-references either haven't been enriched yet "
                "or aren't referenced in any technique doc."
            ),
        }

    return {
        "device_id": device_id,
        "technique_count": len(entries),
        "techniques": entries,
    }


@mcp.tool()
def atlas_pack_info(ctx: Context, pack_name: str = "") -> dict:
    """Inspect a single Ableton pack — device list + enrichment coverage.

    pack_name: the pack name (e.g., "Drone Lab", "Core Library",
               "Creative Extensions", "Inspired by Nature"). Case-insensitive.
               Pass an empty string to get the full list of packs known to
               the atlas with device counts.

    Returns {pack, device_count, enriched_count, devices[...]} for a
    specific pack, or {packs: [...]} when called with no name.

    Use this to answer questions like "what's in Drone Lab?" or "how
    much of Creative Extensions do we have aesthetic knowledge about?"
    """
    atlas = _get_atlas()
    if atlas is None:
        return {"error": "Atlas not loaded. Run scan_full_library first."}

    if not pack_name:
        return {"packs": atlas.list_packs()}

    return atlas.pack_info(pack_name)


@mcp.tool()
def scan_full_library(
    ctx: Context,
    force: bool = False,
    max_per_category: int = 5000,
) -> dict:
    """Scan the full Ableton browser and rebuild the device atlas.

    Walks every category (instruments, audio_effects, midi_effects, max_for_live,
    drums, plugins, packs) and records every loadable item with its URI.
    Results are merged with curated enrichments and saved to device_atlas.json.

    force: if True, rescan even if atlas already exists (default False)
    max_per_category: ceiling per category (default 5000). The previous
        hardcoded 1000 cap silently truncated large categories — for
        example, the samples category alone has ~22,000 items per the
        browser tree, so the reported count "1000 samples" was wrong by
        a factor of 22 (BUG-2026-04-22 #12). Raise this if your library
        is huge; lower it for fast smoke scans.

    Returns a stats dict including `truncated_categories` listing any
    category that hit the cap (so callers know the count is a lower
    bound rather than the true total).
    """
    from .scanner import normalize_scan_results
    from .enrichments import load_enrichments, merge_enrichments
    from . import AtlasManager, USER_ATLAS_DIR, USER_ATLAS_PATH

    # v1.22.0: scans always write to the user atlas path, never the
    # bundled baseline. The user-data directory is created on demand
    # so a brand-new install (no ~/.livepilot/ at all) still works.
    # Enrichments are read from the bundled package (same as before —
    # they're authored in-repo).
    atlas_dir = os.path.dirname(os.path.abspath(__file__))
    enrichments_dir = os.path.join(atlas_dir, "enrichments")
    USER_ATLAS_DIR.mkdir(parents=True, exist_ok=True)
    atlas_path = str(USER_ATLAS_PATH)

    if not force and os.path.exists(atlas_path):
        age = time.time() - os.path.getmtime(atlas_path)
        if age < 86400:
            # Reload if not already loaded
            import mcp_server.atlas as atlas_mod
            if atlas_mod._atlas_instance is None:
                atlas_mod._atlas_instance = AtlasManager(atlas_path)
            return {
                "status": "already_exists",
                "age_hours": round(age / 3600, 1),
                "device_count": atlas_mod._atlas_instance.device_count,
                "message": "Atlas is recent. Use force=True to rescan.",
            }

    # Scan browser
    ableton = _get_ableton(ctx)
    raw = ableton.send_command("scan_browser_deep", {"max_per_category": max_per_category})

    # Normalize
    devices = normalize_scan_results(raw)

    # Detect truncation: per-category count == cap means we likely hit it.
    truncated_categories = []
    if isinstance(raw, dict):
        per_cat = raw.get("counts") or raw.get("stats") or {}
        if isinstance(per_cat, dict):
            for cat, count in per_cat.items():
                try:
                    if int(count) >= max_per_category:
                        truncated_categories.append(cat)
                except (TypeError, ValueError):
                    continue

    # Load and merge enrichments
    enrichments = load_enrichments(enrichments_dir)
    devices = merge_enrichments(devices, enrichments)

    # Count stats
    stats: dict = {"total_devices": len(devices)}
    for device in devices:
        cat = device.get("category", "other")
        stats[cat] = stats.get(cat, 0) + 1
    stats["enriched_devices"] = sum(1 for d in devices if d.get("enriched"))

    # Read the actual running Live version from the session rather than
    # hardcoding "12.3.6" — the hardcoded string was baking last year's
    # version into every new user's atlas until they forced a rescan.
    try:
        session_info = ableton.send_command("get_session_info", {}) or {}
        live_version = session_info.get("live_version", "unknown")
    except Exception:
        live_version = "unknown"

    # Build atlas
    atlas_data = {
        "version": "2.0.0",
        "live_version": live_version,
        "scanned_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "stats": stats,
        "max_per_category": max_per_category,
        "truncated_categories": truncated_categories,
        "devices": devices,
        "packs": [],
    }

    # Atomic write: tmp + rename. Same pattern as PersistentJsonStore. Previous
    # version used open(atlas_path, "w") + json.dump with no fsync, so a crash
    # mid-write produced a truncated JSON file that the next AtlasManager init
    # silently read as empty-dict — devices vanished from memory.
    tmp_path = atlas_path + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(atlas_data, f, indent=2)
        f.flush()
        try:
            os.fsync(f.fileno())
        except OSError:
            # fsync may be unavailable on some filesystems/Windows paths —
            # best-effort; the rename below is still atomic on POSIX.
            pass
    os.replace(tmp_path, atlas_path)

    # Invalidate singleton so next get_atlas() picks up the new file.
    import mcp_server.atlas as atlas_mod
    atlas_mod.invalidate_atlas()

    return {
        "status": "scanned",
        "device_count": len(devices),
        "enriched_count": stats["enriched_devices"],
        "stats": stats,
        "atlas_path": atlas_path,
    }


@mcp.tool()
def reload_atlas(ctx: Context) -> dict:
    """Force the atlas to re-read device_atlas.json from disk.

    Useful after an out-of-band rebuild (e.g. a manual edit to the JSON file,
    or a scan that crashed before invalidating the cache). The next search /
    suggest / compare call will see the fresh data. No-op if the atlas has
    never been loaded — the first real call will load it fresh anyway.
    """
    from . import invalidate_atlas, get_atlas
    invalidate_atlas()
    atlas = get_atlas()
    return {
        "reloaded": True,
        "device_count": atlas.device_count if atlas else 0,
    }


# ─────────────────────────────────────────────────────────────────────────
# v1.23.0: User-local atlas overlays (extension_atlas_*)
#
# These tools surface the OverlayIndex populated by load_overlays() at
# server boot from ~/.livepilot/atlas-overlays/<namespace>/. Independent
# of the existing atlas_* tools, which are tightly coupled to the device
# schema (URIs, packs, categories). Per spec §5.3.
# ─────────────────────────────────────────────────────────────────────────


def _serialize_overlay_entry(entry) -> dict:
    """Serialize an OverlayEntry to a JSON-safe dict for MCP tool returns."""
    return {
        "namespace": entry.namespace,
        "entity_type": entry.entity_type,
        "entity_id": entry.entity_id,
        "name": entry.name,
        "description": entry.description,
        "tags": entry.tags,
        "artists": entry.artists,
        "requires_box": entry.requires_box,
        "body": entry.body,
    }


@mcp.tool()
def extension_atlas_search(ctx: Context, query: str,
                           namespace: str = "",
                           entity_type: str = "",
                           limit: int = 10) -> dict:
    """Search user-local atlas overlays under ~/.livepilot/atlas-overlays/.

    Use this for content from extension namespaces (e.g., 'elektron', 'prophet') —
    NOT for the main Ableton device atlas (use atlas_search for that).

    query:       case-insensitive substring; matches against entity_id (highest weight),
                 name, tags/artists, description (lowest weight).
    namespace:   restrict to one namespace (e.g., 'elektron'); empty = search all.
    entity_type: restrict to one entity_type (e.g., 'signature_chain'); empty = all.
    limit:       maximum results to return.
    """
    from .overlays import get_overlay_index
    idx = get_overlay_index()
    ns = namespace or None
    et = entity_type or None
    matches = idx.search(query, namespace=ns, entity_type=et, limit=limit)
    return {
        "query": query,
        "namespace": namespace or None,
        "entity_type": entity_type or None,
        "count": len(matches),
        "results": [_serialize_overlay_entry(e) for e in matches],
    }


@mcp.tool()
def extension_atlas_get(ctx: Context, namespace: str, entity_id: str) -> dict:
    """Fetch a single overlay entry by namespace + entity_id.

    Returns the full entry including the original YAML body so callers can read
    arbitrary extension-specific fields (architecture, requires_machines,
    requires_firmware, sources, etc.).

    If the entry has a `requires_firmware` field, surface it to the user before
    recommending the chain (per spec §7) — e.g., "this needs Monomachine OS 1.32+".
    """
    from .overlays import get_overlay_index
    idx = get_overlay_index()
    entry = idx.get(namespace, entity_id)
    if entry is None:
        return {
            "error": f"entity '{entity_id}' not found in namespace '{namespace}'",
            "suggestion": "Use extension_atlas_search to find available entries, "
                          "or extension_atlas_list to see installed namespaces."
        }
    return _serialize_overlay_entry(entry)


@mcp.tool()
def extension_atlas_list(ctx: Context, namespace: str = "") -> dict:
    """Enumerate user-local overlay namespaces and their entity_type counts.

    With no namespace: returns full list of namespaces and per-type counts.
    With a namespace: returns just the entity_types present in that namespace.
    """
    from .overlays import get_overlay_index
    idx = get_overlay_index()
    if namespace:
        return {
            "namespace": namespace,
            "entity_types": idx.list_entity_types(namespace),
        }
    return {
        "namespaces": idx.list_namespaces(),
        "counts": idx.stats(),
    }


@mcp.tool()
def atlas_macro_fingerprint(
    ctx: Context,
    source_pack_slug: str = "",
    source_preset_path: str = "",
    source_live_track: int = -1,
    source_live_device: int = -1,
    rack_class_filter: str = "",
    pack_filter: list = None,
    top_k: int = 8,
    min_named_macros: int = 3,
    similarity_threshold: float = 0.4,
) -> dict:
    """Find presets with similar macro state to the source — 'more like this' search.

    Source must be a known corpus preset (via source_pack_slug + source_preset_path).
    Live-device source via source_live_track/source_live_device is stubbed and returns
    an error; only the corpus path works currently (as of v1.23.4).

    Similarity is computed as:
      0.6 × macro-name-overlap-ratio  (synonym-aware: 'Filter Control' ≈ 'Filter Cutoff')
    + 0.4 × (1 − mean value distance)

    Parameters
    ----------
    source_pack_slug     : Pack directory name, e.g. "drone-lab".
    source_preset_path   : Sidecar filename stem, e.g.
                           "instruments_laboratory_razor-wire-drone".
                           Use underscores for directory separators (matches
                           the sidecar naming convention from als_deep_parse.py).
    source_live_track    : Track index in the live session (0-based). Used only
                           when source_pack_slug is empty.
    source_live_device   : Device index on that track. Used only when
                           source_pack_slug is empty.
    rack_class_filter    : Filter candidates by rack class. One of:
                           "InstrumentGroupDevice", "AudioEffectGroupDevice",
                           "DrumGroupDevice", "MidiEffectGroupDevice".
                           Empty string = all classes.
    pack_filter          : Optional list of pack slugs to restrict the candidate
                           scan (e.g. ["drone-lab", "mood-reel"]).
    top_k                : Maximum number of matches to return (default 8).
    min_named_macros     : Require source to have at least this many
                           producer-named macros; also applied to candidates.
                           Below this floor the fingerprint is too weak to be
                           useful (default 3).
    similarity_threshold : Drop matches below this score (default 0.4).

    Returns
    -------
    {
        "source": {
            "pack_slug": str,
            "preset_path": str,
            "rack_class": str,
            "macros_named": [{"index", "name", "value"}, ...],
            "fingerprint_strength": "strong" | "moderate" | "weak"
        },
        "matches": [
            {
                "pack_slug": str,
                "preset_path": str,
                "preset_name": str,
                "rack_class": str,
                "similarity_score": float,
                "matching_macros": [{"name_overlap", "value_distance", ...}, ...],
                "rationale": str
            },
            ...
        ],
        "sources": ["adg-parse: N sidecars across M packs"]
    }

    Citation tags: [SOURCE: adg-parse] for all preset data, [SOURCE: agent-inference]
    for rationale prose.
    """
    # BUG-EDGE#1: coerce string args that MCP may pass as strings
    try:
        top_k = int(top_k) if top_k is not None else 8
    except (ValueError, TypeError):
        top_k = 8
    try:
        min_named_macros = int(min_named_macros) if min_named_macros is not None else 3
    except (ValueError, TypeError):
        min_named_macros = 3
    try:
        similarity_threshold = float(similarity_threshold) if similarity_threshold is not None else 0.4
    except (ValueError, TypeError):
        similarity_threshold = 0.4

    from .macro_fingerprint import (
        _extract_fingerprint,
        _compute_similarity,
        _generate_rationale,
        _fingerprint_strength,
        _load_preset_sidecar,
        _iter_all_preset_sidecars,
        PRESET_PARSES_ROOT,
    )
    import json as _json
    from pathlib import Path as _Path

    # User-corpus rack sidecar root: ~/.livepilot/atlas-overlays/user/racks/_parses/<id>.json
    USER_RACK_PARSES_ROOT = _Path.home() / ".livepilot" / "atlas-overlays" / "user" / "racks" / "_parses"

    def _load_user_rack_sidecar(entity_id: str) -> dict | None:
        """Load a user-corpus rack sidecar by entity_id. Returns None if absent."""
        p = USER_RACK_PARSES_ROOT / f"{entity_id}.json"
        if not p.exists():
            return None
        try:
            return _json.loads(p.read_text())
        except (OSError, _json.JSONDecodeError):
            return None

    def _iter_user_rack_sidecars():
        """Yield (namespace_slug, preset_path_slug, sidecar_dict) for user rack parses."""
        if not USER_RACK_PARSES_ROOT.exists():
            return
        for sidecar_path in sorted(USER_RACK_PARSES_ROOT.glob("*.json")):
            try:
                sidecar = _json.loads(sidecar_path.read_text())
            except (OSError, _json.JSONDecodeError):
                continue
            yield "user", sidecar_path.stem, sidecar

    # Overlay namespace IDs that pack_filter may contain — separate from pack slugs.
    # We'll resolve these to the user-rack sidecar iterator instead of the factory iterator.
    _OVERLAY_NAMESPACE_IDS = {"user", "m4l-devices", "elektron"}

    # ── 1. Resolve source fingerprint ─────────────────────────────────────────

    source_sidecar: dict | None = None
    source_pack_resolved = source_pack_slug
    source_path_resolved = source_preset_path

    if source_pack_slug and source_preset_path:
        # Check if source_pack_slug is an overlay namespace (user rack corpus)
        if source_pack_slug in _OVERLAY_NAMESPACE_IDS:
            source_sidecar = _load_user_rack_sidecar(source_preset_path)
            if source_sidecar is None:
                slug_attempt = source_preset_path.replace("/", "_")
                source_sidecar = _load_user_rack_sidecar(slug_attempt)
                if source_sidecar is not None:
                    source_path_resolved = slug_attempt
            if source_sidecar is None:
                available = (
                    [p.stem for p in sorted(USER_RACK_PARSES_ROOT.glob("*.json"))[:10]]
                    if USER_RACK_PARSES_ROOT.exists()
                    else []
                )
                return {
                    "error": (
                        f"User-corpus rack sidecar not found: {source_pack_slug}/{source_preset_path}.json. "
                        f"Expected under {USER_RACK_PARSES_ROOT}."
                    ),
                    "available_user_rack_sidecars": available,
                    "hint": "Run corpus_scan to generate user-corpus rack sidecars.",
                }
        else:
            # Corpus path: load from bundled _preset_parses
            source_sidecar = _load_preset_sidecar(source_pack_slug, source_preset_path)
            if source_sidecar is None:
                # Try converting "/" separators to "_"
                slug_attempt = source_preset_path.replace("/", "_")
                source_sidecar = _load_preset_sidecar(source_pack_slug, slug_attempt)
                if source_sidecar is not None:
                    source_path_resolved = slug_attempt
            if source_sidecar is None:
                return {
                    "error": (
                        f"Sidecar not found: {source_pack_slug}/{source_preset_path}.json. "
                        "Check that the pack slug and preset path match the _preset_parses "
                        "directory layout. Use underscores as separators, e.g. "
                        "'instruments_laboratory_razor-wire-drone'."
                    ),
                    "hint": (
                        f"Available files in {source_pack_slug}: "
                        + ", ".join(
                            p.stem
                            for p in sorted(
                                (PRESET_PARSES_ROOT / source_pack_slug).glob("*.json")
                            )[:10]
                        )
                        if (PRESET_PARSES_ROOT / source_pack_slug).is_dir()
                        else "pack directory not found"
                    ),
                }

    elif source_live_track >= 0 and source_live_device >= 0:
        # TODO(Phase D follow-up): live-Live path — reads macro names/values from
        # a running Ableton session via the get_device_parameters MCP tool.
        # Not implemented in this release; corpus path is fully operational.
        return {
            "error": (
                "Live-device source path is not yet implemented (Phase D follow-up). "
                "Please use source_pack_slug + source_preset_path to query from the "
                "corpus instead."
            ),
            "hint": (
                "To use a live device as the source, save the rack as a .adg preset "
                "via Ableton's browser and re-run als_deep_parse.py to generate a "
                "sidecar, then reference it by pack_slug + preset_path."
            ),
        }
    else:
        return {
            "error": (
                "Provide either (source_pack_slug + source_preset_path) for corpus "
                "lookup, or (source_live_track + source_live_device) for a live "
                "device source."
            )
        }

    # ── 2. Build source fingerprint ───────────────────────────────────────────

    source_fp = _extract_fingerprint(source_sidecar)
    n_named_source = len(source_fp)

    if n_named_source < min_named_macros:
        named_display = [
            m for m in source_sidecar.get("macros", [])
            if m.get("name", "") and not m["name"].startswith("Macro ")
        ]
        return {
            "error": (
                f"Source preset has only {n_named_source} producer-named macro(s) "
                f"(min_named_macros={min_named_macros}). "
                "Fingerprint is too weak for reliable matching."
            ),
            "source_named_macros": [m["name"] for m in named_display],
            "suggestion": (
                "Lower min_named_macros, or choose a source preset with more "
                "producer-named macros."
            ),
        }

    # ── 3. Scan candidates ────────────────────────────────────────────────────

    pack_whitelist = set(pack_filter) if pack_filter else None

    # Split pack_whitelist into overlay namespaces vs. bundled pack slugs so
    # pack_filter=["user"] scans user rack sidecars, not bundled _preset_parses.
    overlay_whitelist = (
        {ns for ns in pack_whitelist if ns in _OVERLAY_NAMESPACE_IDS}
        if pack_whitelist else None
    )
    bundled_whitelist = (
        {slug for slug in pack_whitelist if slug not in _OVERLAY_NAMESPACE_IDS}
        if pack_whitelist else None
    )

    candidates_scanned = 0
    packs_seen: set[str] = set()
    scored: list[tuple[float, str, str, dict, list[dict]]] = []

    # Decide which iterators to run based on pack_filter contents:
    # - No filter → run both bundled + user-rack
    # - Filter with only overlay namespaces → run only user-rack
    # - Filter with only bundled slugs → run only bundled
    # - Mixed → run both, each filtered to its respective whitelist
    run_bundled = (pack_whitelist is None) or bool(bundled_whitelist)
    run_user_racks = (pack_whitelist is None) or bool(overlay_whitelist)

    def _scan_candidates(iterator):
        nonlocal candidates_scanned
        for cand_pack, cand_slug, cand_sidecar in iterator:
            # Skip the source itself
            if (cand_pack == source_pack_resolved
                    and cand_slug == source_path_resolved):
                continue

            # Rack class filter
            if rack_class_filter:
                if cand_sidecar.get("rack_class", "") != rack_class_filter:
                    continue

            # Candidate must also have enough named macros
            cand_fp = _extract_fingerprint(cand_sidecar)
            if len(cand_fp) < min_named_macros:
                continue

            candidates_scanned += 1
            packs_seen.add(cand_pack)

            score, matched = _compute_similarity(source_fp, cand_fp)
            if score >= similarity_threshold:
                scored.append((score, cand_pack, cand_slug, cand_sidecar, matched))

    if run_bundled:
        def _bundled_iter():
            for cand_pack, cand_slug, cand_sidecar in _iter_all_preset_sidecars():
                if bundled_whitelist and cand_pack not in bundled_whitelist:
                    continue
                yield cand_pack, cand_slug, cand_sidecar
        _scan_candidates(_bundled_iter())

    if run_user_racks:
        try:
            _scan_candidates(_iter_user_rack_sidecars())
        except Exception:  # noqa: BLE001 — never fail over a missing user-rack corpus
            pass

    # Sort descending by score
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:top_k]

    # ── 4. Format matches ─────────────────────────────────────────────────────

    matches_out = []
    for score, cand_pack, cand_slug, cand_sidecar, matched in top:
        rationale = _generate_rationale(
            source_pack=source_pack_resolved,
            source_name=source_sidecar.get("name", ""),
            cand_pack=cand_pack,
            cand_name=cand_sidecar.get("name", ""),
            matching_macros=matched,
        )
        matches_out.append({
            "pack_slug": cand_pack,
            "preset_path": cand_slug,
            "preset_name": cand_sidecar.get("name", ""),
            "rack_class": cand_sidecar.get("rack_class", ""),
            "similarity_score": score,
            "matching_macros": matched[:5],  # show up to 5; see total_matching_macros for full count
            "total_matching_macros": len(matched),
            "rationale": rationale,  # [SOURCE: agent-inference]
        })

    # ── 5. Format source block ────────────────────────────────────────────────

    source_macros_named = [
        {
            "index": m.get("index"),
            "name": m.get("name"),
            "value": m.get("value"),
        }
        for m in source_sidecar.get("macros", [])
        if m.get("name", "") and not m["name"].startswith("Macro ")
    ]

    overlay_count = sum(
        1 for _, cand_pack, _slug, _sd, _m in top
        if cand_pack in _OVERLAY_NAMESPACE_IDS
    )
    factory_match_count = len(matches_out) - overlay_count

    return {
        "source": {
            "pack_slug": source_pack_resolved,
            "preset_path": source_path_resolved,
            "rack_class": source_sidecar.get("rack_class", ""),
            "macros_named": source_macros_named,
            "fingerprint_strength": _fingerprint_strength(n_named_source),
        },
        "matches": matches_out,
        "candidates_scanned": candidates_scanned,
        "factory_count": factory_match_count,
        "overlay_count": overlay_count,
        "sources": [
            f"adg-parse: {candidates_scanned} candidate sidecars across "
            f"{len(packs_seen)} packs/namespaces [SOURCE: adg-parse]",
            f"user-corpus: {'checked' if run_user_racks else 'skipped'} "
            f"(~/.livepilot/atlas-overlays/user/racks/_parses/)",
        ],
    }


@mcp.tool()
def atlas_transplant(
    ctx: Context,
    source_namespace: str,
    source_entity_id: str,
    source_track_or_preset: str = "",
    target_bpm: float = 0.0,
    target_scale_root: int = -1,
    target_scale_name: str = "",
    target_aesthetic: str = "",
    preserve_macro_ratios: bool = True,
    preserve_pitch_intervals: bool = True,
    explanation_depth: str = "standard",
) -> dict:
    """Adapt a structure from one musical context to another (Pack-Atlas Phase C).

    Takes a demo project, preset chain, or workflow recipe from the Pack-Atlas
    corpus and translates it to a new musical context (different BPM, scale,
    aesthetic register).  Returns a structured plan with executable tool calls
    — agent applies the plan via load_browser_item, set_device_parameter,
    set_clip_pitch, etc.  No Live connection required; all data from local
    JSON sidecars.

    Parameters
    ----------
    source_namespace : str
        Namespace to look up the source entity.  Use "packs" for demo projects
        and Factory Pack presets; "m4l-devices" for M4L vendor devices;
        "elektron" for Elektron signature chains.

    source_entity_id : str
        Entity identifier.  For demo projects use the form "pack-slug__demo-slug"
        or "pack_slug__demo_slug" (hyphens and underscores are normalised).
        Examples: "drone_lab__earth", "drone-lab__emergent-planes",
        "mood-reel__mood-reel-demo".
        For pack presets (with source_track_or_preset): use the pack slug,
        e.g. "drone_lab".

    source_track_or_preset : str, optional
        Sub-selector within a demo or pack.  For pack presets: the preset
        file path slug such as "instruments_laboratory_razor-wire-drone"
        (underscores or hyphens both accepted).  Omit when targeting the
        whole demo project.

    target_bpm : float, optional
        Target BPM.  Pass 0.0 to keep source BPM.

    target_scale_root : int, optional
        Target scale root note as MIDI pitch-class (0=C, 1=C#, … 11=B).
        Pass -1 to keep source root.

    target_scale_name : str, optional
        Target scale mode name.  Supported: "Major", "Minor", "Dorian",
        "Phrygian", "Mixolydian", "Lydian", "Locrian".  Empty string = keep
        source mode.

    target_aesthetic : str, optional
        Free-text aesthetic descriptor.  Used to detect aesthetic-incompatible
        devices and drive REPLACE decisions.  Examples: "mood-reel cinematic",
        "inspired_by_nature tree_tone", "lo-fi dusty tape", "clean orchestral".

    preserve_macro_ratios : bool, default True
        When True, non-default macro values from the source are carried forward
        as normalised ratios [0-1] even when the target has different raw ranges.

    preserve_pitch_intervals : bool, default True
        When True, pitch interval relationships within each voice are preserved
        and only a global transposition is applied (scale shift stays parallel).

    explanation_depth : str, default "standard"
        Controls verbosity of the reasoning_artifact field.
        "terse"    — 1-2 sentence summary.
        "standard" — 1 paragraph with key decisions enumerated.
        "verbose"  — full per-decision narrative with producer-vocabulary
                     anchors where applicable.

    Returns
    -------
    dict with keys:
        source           — source musical context (bpm, scale, tracks_summary)
        target           — target context (bpm, scale, aesthetic)
        translation_plan — list of per-element decisions with executable_steps
        reasoning_artifact — prose explanation of the plan
        warnings         — list of caution strings (BPM ratio, missing sidecars)
        sources          — citation list with [SOURCE: als-parse | adg-parse |
                           agent-inference] tags

    Example
    -------
    atlas_transplant(
        source_namespace="packs",
        source_entity_id="drone_lab__earth",
        target_bpm=130,
        target_scale_root=5,   # F
        target_scale_name="Minor",
        target_aesthetic="mood-reel cinematic",
        explanation_depth="standard"
    )
    """
    from .transplant import transplant as _transplant

    # Normalise optional params — FastMCP passes typed defaults

    # BUG-EDGE#4: target_bpm may arrive as a string (e.g. "130.0") when the MCP
    # client serialises the value.  Cast to float BEFORE the > 0 comparison to
    # avoid TypeError: '>' not supported between instances of 'str' and 'int'.
    resolved_bpm = None
    if target_bpm:
        try:
            fbpm = float(target_bpm)
            if fbpm > 0:
                resolved_bpm = fbpm
        except (ValueError, TypeError):
            pass  # invalid string — treat as unset

    # BUG-EDGE#7: out-of-range root (e.g. 99) must be rejected; -1 is the
    # "keep source" sentinel and resolves to None (not passed to inner function).
    if target_scale_root is not None and not (0 <= target_scale_root <= 11):
        if target_scale_root != -1:
            return {
                "error": (
                    f"target_scale_root={target_scale_root} is out of range. "
                    "Valid values: 0–11 (pitch-class, C=0 … B=11), or -1 to keep source root."
                ),
                "status": "error",
            }
        resolved_root = None  # -1 sentinel → keep source
    else:
        resolved_root = int(target_scale_root) if target_scale_root is not None and target_scale_root >= 0 else None

    return _transplant(
        source_namespace=source_namespace,
        source_entity_id=source_entity_id,
        source_track_or_preset=source_track_or_preset,
        target_bpm=resolved_bpm,
        target_scale_root=resolved_root,
        target_scale_name=target_scale_name,
        target_aesthetic=target_aesthetic,
        preserve_macro_ratios=preserve_macro_ratios,
        preserve_pitch_intervals=preserve_pitch_intervals,
        explanation_depth=explanation_depth,
    )


@mcp.tool()
def atlas_demo_story(
    ctx: Context,
    demo_entity_id: str,
    focus_tracks: list = None,
    detail_level: str = "standard",
) -> dict:
    """Generate a track-by-track narrative + production-sequence for a demo .als (Pack-Atlas Phase E).

    Turns the 104 parsed demo files into interactive learning artifacts.  Reads
    from local JSON sidecars — no Live connection required.

    Parameters
    ----------
    demo_entity_id : str
        Entity ID for the demo.  Use the form "pack_slug__demo_slug" or the
        hyphenated variant — both are normalised.
        Examples: "drone_lab__earth", "drone-lab__emergent-planes",
        "mood_reel__the_killer_awaits_gmin_135_bpm".

    focus_tracks : list of str, optional
        Narrow the track_breakdown to only these track names (exact or fuzzy
        matched).  Pass None (default) to include all tracks.

    detail_level : str, default "standard"
        Controls narrative verbosity.
        "terse"    — 2-3 sentence summary.
        "standard" — 1 paragraph narrative + structured breakdown.
        "verbose"  — full markdown narrative with producer-vocabulary anchors,
                     track architecture table, production sequence, learning path.

    Returns
    -------
    dict with keys:
        demo              — {entity_id, name, bpm, scale, track_count, scene_count}
        narrative         — prose synthesis of the demo [SOURCE: als-parse,
                            agent-inference]
        track_breakdown   — list of per-track dicts:
                            {name, type, role, device_chain_summary,
                             macro_signature, production_decision, narrative_role}
        production_sequence_inference  — ordered list of inferred creation steps
        suggested_learning_path        — solo-each-then-add sequence for study
        sources           — citation list with [SOURCE: als-parse | agent-inference]
        error             — (only on failure) error message

    Track roles:
        "harmonic-foundation" — primary instrument/melodic source
        "rhythmic-driver"     — drum rack or percussion-named track
        "texture"             — additional instrument layers
        "spatial-glue"        — return tracks with reverb/delay
        "fx-bus"              — group/return tracks with bus processing
        "decoration"          — audio sources or effects-only layers

    Example
    -------
    atlas_demo_story(
        demo_entity_id="drone_lab__earth",
        detail_level="verbose"
    )
    """
    from .demo_story import demo_story as _demo_story
    return _demo_story(
        demo_entity_id=demo_entity_id,
        focus_tracks=list(focus_tracks) if focus_tracks else None,
        detail_level=detail_level,
    )


@mcp.tool()
def atlas_extract_chain(
    ctx: Context,
    demo_entity_id: str,
    track_name: str,
    target_track_index: int = -1,
    parameter_fidelity: str = "exact",
) -> dict:
    """Rebuild a specific demo track's device chain as an executable plan (Pack-Atlas Phase E).

    Reads from local JSON sidecars — no Live connection required for planning.
    Always returns a dry-run plan (executed: false).  Execute the plan manually
    via the listed MCP tool calls (load_browser_item, insert_device,
    set_device_parameter) or pass target_track_index >= 0 to target an existing
    track in the returned plan.

    Parameters
    ----------
    demo_entity_id : str
        Entity ID for the demo, e.g. "drone_lab__emergent_planes".

    track_name : str
        Name of the track to extract.  Fuzzy matched (case-insensitive substring,
        token match).  Example: "Mindless Self-Encounters", "Pioneer Drone",
        "mindless" (partial match accepted).

    target_track_index : int, default -1
        Target track in the current project.  -1 = plan includes a new-track
        creation step.  >= 0 = plan targets the existing track at that index.
        (Phase E ships dry-run only — use the plan to drive manual execution.)

    parameter_fidelity : str, default "exact"
        Controls how many parameters are included in set_device_parameter steps.
        "exact"          — emit set_device_parameter for every non-default macro
        "approximate"    — top 5 macros by deviation from zero (most production-
                           meaningful committed values)
        "structure-only" — chain topology only; no parameter steps

    Returns
    -------
    dict with keys:
        source         — {demo, track, track_type, device_count, device_chain}
                         device_chain: [{class, user_name, chain_depth, macros?}]
        execution_plan — list of action dicts.  Action types:
                         "create_midi_track" | "create_audio_track" |
                         "target_existing_track" |
                         "load_browser_item" | "insert_device" |
                         "set_device_parameter" | "manual_rebuild"
        executed       — always False (Phase E is dry-run only)
        parameter_fidelity — echoed back
        warnings       — list of caution strings (unknown classes, unnamed racks)
        sources        — citation list
        error          — (only on failure) error message with available_tracks

    Citation tags: [SOURCE: als-parse] for sidecar data, [SOURCE: agent-inference]
    for step generation logic.

    Example
    -------
    atlas_extract_chain(
        demo_entity_id="drone_lab__emergent_planes",
        track_name="Mindless Self-Encounters",
        target_track_index=-1,
        parameter_fidelity="approximate"
    )
    """
    from .extract_chain import extract_chain as _extract_chain
    return _extract_chain(
        demo_entity_id=demo_entity_id,
        track_name=track_name,
        target_track_index=target_track_index,
        parameter_fidelity=parameter_fidelity,
    )


@mcp.tool()
def atlas_pack_aware_compose(
    ctx: Context,
    aesthetic_brief: str,
    target_bpm: float = 0.0,
    target_scale: str = "",
    track_count: int = 6,
    pack_diversity: str = "coherent",
) -> dict:
    """Bootstrap a project with pack-coherent track selection given an aesthetic brief (Pack-Atlas Phase F).

    Parses the aesthetic brief against the artist/genre vocabulary files and the pack
    atlas overlay, builds a pack cohort (which Factory Packs best serve this brief),
    selects real presets from the corpus for each track role via macro-fingerprint
    similarity, and returns a full executable plan.

    Parameters
    ----------
    aesthetic_brief : str
        Free-text aesthetic description.
        Examples: "dub-techno spectral drone bed monolake henke",
                  "BoC pastoral decayed pad", "footwork breakcore",
                  "orchestral dread Mica Levi".

    target_bpm : float, optional
        Target project BPM. Pass 0.0 to omit.

    target_scale : str, optional
        Target scale string, e.g. "Cmin", "Fmaj", "Fmin". Pass "" to omit.

    track_count : int, default 6
        Number of tracks to propose.

    pack_diversity : str, default "coherent"
        "coherent"  — all tracks from packs aligned to the brief's aesthetic.
        "eclectic"  — deliberately spans conflicting aesthetics (Eclectic Mode
                      reasoning: picks packs whose anti_patterns conflict,
                      explains tension_resolution in reasoning_artifact).

    Returns
    -------
    dict with keys:
        brief_analysis : {
            primary_aesthetic: str,
            secondary_aesthetics: list[str],
            anchor_producers: list[str],
            anchor_genres: list[str],
            pack_cohort: list[str]  # Factory Pack slugs
        }
        track_proposal : list of {
            track_name: str,
            role: str,                # e.g. "harmonic-foundation"
            preset: str,              # "pack-slug/preset-path-slug"
            preset_name: str,
            rationale: str            # [SOURCE: adg-parse | agent-inference]
        }
        suggested_routing : list[str]  # routing hints + cross-pack workflow refs
        executable_steps  : list[dict] # create_track + load_browser_item + set_device_parameter
        sources           : list[str]  # citation list
        reasoning_artifact: dict       # only present in eclectic mode

    Citation tags: [SOURCE: adg-parse] for corpus preset data,
    [SOURCE: artist-vocabularies.md] / [SOURCE: genre-vocabularies.md] for
    vocabulary lookups, [SOURCE: cross_pack_workflow.yaml] for routing hints,
    [SOURCE: agent-inference] for role/step generation.

    Integrations (Phase F uses C+D+E):
    - Phase D: _extract_fingerprint + _fingerprint_strength for preset selection
    - Phase E: _emit_execution_steps step structure for executable plan
    - Phase C: transplant aesthetic-replace rules (via target_scale/customize_aesthetic)

    Example
    -------
    atlas_pack_aware_compose(
        aesthetic_brief="dub-techno spectral drone bed monolake",
        target_bpm=130,
        track_count=4
    )
    """
    from .pack_aware_compose import pack_aware_compose as _pack_aware_compose, _coerce_float, _coerce_int

    # BUG-EDGE#2/#3: coerce before the > 0 comparison to avoid TypeError on string inputs
    _bpm = _coerce_float(target_bpm, 0.0)
    resolved_bpm = _bpm if _bpm and _bpm > 0 else None
    _track_count = _coerce_int(track_count, 6)
    return _pack_aware_compose(
        aesthetic_brief=aesthetic_brief,
        target_bpm=resolved_bpm,
        target_scale=target_scale,
        track_count=_track_count,
        pack_diversity=pack_diversity,
    )


@mcp.tool()
def atlas_cross_pack_chain(
    ctx: Context,
    workflow_entity_id: str,
    target_track_index: int = -1,
    customize_aesthetic: dict = None,
) -> dict:
    """Execute a cross-pack signature recipe step-by-step (Pack-Atlas Phase F).

    Reads a cross_pack_workflow entry from the Pack-Atlas overlay, parses its
    signal_flow body into structured actions, and returns a dry-run execution log.
    All 15 cross-pack workflow recipes are supported.

    Parameters
    ----------
    workflow_entity_id : str
        Entity ID of the workflow. Use underscores or hyphens interchangeably.
        Examples:
          "dub_techno_spectral_drone_bed"   (HDG → PitchLoop89 → ConvReverb → AutoFilter)
          "boc_decayed_pad"                  (Tree Tone → Bad Speaker → Echo → Reverb)
          "mica_levi_orchestral_dread"       (Strings → Bass Clarinet → AutoPan → ConvReverb)
          "henke_full_granular_chain"
          "footwork_breakcore_drum_chain"
        Use atlas_cross_pack_chain(workflow_entity_id="") with an invalid ID to
        see the list of available workflows in the error.available_workflows field.

    target_track_index : int, default -1
        -1 = dry run. All steps returned with result: "dry-run".
        >= 0 = plan targets an existing track at that index (still dry-run in Phase F;
               live execution gated on Remote Script connection).

    customize_aesthetic : dict, optional
        Optional aesthetic-shift parameters. Supported keys:
        - "target_scale": str — insert set_song_scale step (e.g. "Fmin")
        - "target_bpm": float — insert set_tempo step
        - "transpose_semitones": float — shift numeric pitch parameter values

    Returns
    -------
    dict with keys:
        workflow : {
            entity_id: str,
            name: str,
            packs_used: list[str],
            description: str,
            when_to_reach: str,
            gotcha: str
        }
        executed_steps : list of {
            step: int,
            action: str,          # load_browser_item | insert_device |
                                  # set_device_parameter | fire_clip |
                                  # set_track_send | manual_step |
                                  # set_song_scale | set_tempo
            device_name: str?,
            parameter_name: str?,
            value: float?,
            raw_text: str,        # original signal_flow line
            result: "dry-run",
            target_track_index: int?  # only when target_track_index >= 0
        }
        warnings : list[str]     # gotcha + avoid text from workflow YAML
        sources  : list[str]     # citation list
        error    : str           # only on failure; also has available_workflows

    Signal-flow verb → action mapping:
      "load" / "open" / "import"   → load_browser_item
      "insert" / "add"             → insert_device
      "set" / "tweak" / "configure"→ set_device_parameter
      "fire" / "play" / "trigger"  → fire_clip
      "chain" / "route" / "→"      → set_track_send
      anything else                → manual_step

    Citation tags: [SOURCE: cross_pack_workflow.yaml] for workflow YAML data,
    [SOURCE: agent-inference] for parsing logic.

    Example
    -------
    atlas_cross_pack_chain(
        workflow_entity_id="dub_techno_spectral_drone_bed",
        target_track_index=-1
    )
    """
    from .cross_pack_chain import cross_pack_chain as _cross_pack_chain

    return _cross_pack_chain(
        workflow_entity_id=workflow_entity_id,
        target_track_index=target_track_index,
        customize_aesthetic=customize_aesthetic or {},
    )
