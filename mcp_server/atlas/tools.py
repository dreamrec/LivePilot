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

    query:    natural language search — name, sonic character, use case, or genre
              Examples: "warm analog bass", "reverb", "808 kit", "granular"
    category: filter by category (all, instruments, audio_effects, midi_effects,
              max_for_live, drum_kits, plugins)
    limit:    max results (default 10)
    """
    atlas = _get_atlas()
    if atlas is None:
        return {"error": "Atlas not loaded. Run scan_full_library first.", "results": []}

    results = atlas.search(query, category=category, limit=limit)
    return {
        "query": query,
        "category": category,
        "count": len(results),
        "results": [
            {
                "id": r["device"].get("id", ""),
                "name": r["device"].get("name", ""),
                "uri": r["device"].get("uri", ""),
                "category": r["device"].get("category", ""),
                "sonic_description": r["device"].get("sonic_description", "")[:120],
                "character_tags": r["device"].get("character_tags", [])[:5],
                "enriched": r["device"].get("enriched", False),
                "score": r.get("score", 0),
            }
            for r in results
        ],
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

    role:  the musical role — "bass", "lead", "pad", "drums", "percussion", "texture"
    genre: target genre for style-appropriate choices
    """
    atlas = _get_atlas()
    if atlas is None:
        return {"error": "Atlas not loaded. Run scan_full_library first."}

    return atlas.chain_suggest(role, genre=genre)


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

    # ── Build per-role suggestions via atlas.suggest ─────────────
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
        per_role_suggestions.append({
            "role": role,
            "intent_used": intent,
            "suggestions": [
                {
                    "device_id": r["device"].get("id", ""),
                    "device_name": r["device"].get("name", ""),
                    "uri": r["device"].get("uri", ""),
                    "rationale": r.get("rationale", ""),
                    "recipe": r.get("recipe"),
                }
                for r in results
            ],
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
