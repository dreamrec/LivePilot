"""Three v1.25 atlas knowledge-surface tools — agent-callable mid-design.

  atlas_explore     — refined per-role candidate query (wraps AtlasResolver)
  atlas_audition    — full sidecar dump for one URI (signature_techniques +
                      producer-curated macro values + related demos + curated ADGs)
  atlas_substitute  — anti-tag-driven swap (used after analyze_sound_design or
                      analyze_mix flags an issue with a chosen layer)

Imported and registered via @mcp.tool() decorators in atlas/tools.py.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ── Anti-tag → character-tag inversion map ──────────────────────────
#
# Maps a free-text "anti" descriptor to (excluded_tags, preferred_tags).
# Used by atlas_substitute. Keys are lowercased; matched as substring of the
# caller's anti_tag string so "too bright" and "bright" both resolve.

_ANTI_TAG_MAP: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "bright":     (("bright", "high", "shimmer", "airy"), ("warm", "dark", "muted", "vintage")),
    "harsh":      (("harsh", "aggressive", "distorted"), ("smooth", "soft", "clean")),
    "aggressive": (("harsh", "aggressive", "punchy"),  ("soft", "warm", "subtle")),
    "sparse":     (("minimal", "sparse", "thin"),     ("dense", "lush", "thick", "wide")),
    "thin":       (("thin", "minimal"),               ("thick", "fat", "dense", "wide")),
    "muddy":      (("muddy", "low_mid"),              ("clear", "open", "defined")),
    "clean":      (("clean", "pristine"),             ("dirty", "saturated", "vintage", "lo-fi")),
    "dark":       (("dark", "muted"),                 ("bright", "shimmer", "airy")),
    "warm":       (("warm", "vintage"),               ("clean", "modern", "digital")),
    "static":     (("static", "single_layer"),        ("evolving", "modulated", "movement")),
    "generic":    (("generic", "default"),            ("character", "unique", "signature")),
}


def _resolve_anti_tags(anti_tag: str) -> tuple[list[str], list[str]]:
    """Return (excluded_tags, preferred_tags) for an anti-tag string.

    Substring-matches the caller's anti_tag string against keys in the map;
    aggregates all hits. "too bright and harsh" → matches "bright" + "harsh".
    Empty input returns ([], []) — caller should treat that as no-op.
    """
    excluded: list[str] = []
    preferred: list[str] = []
    s = (anti_tag or "").lower()
    for key, (excl, pref) in _ANTI_TAG_MAP.items():
        if key in s:
            for t in excl:
                if t not in excluded:
                    excluded.append(t)
            for t in pref:
                if t not in preferred:
                    preferred.append(t)
    return excluded, preferred


# ── Tech-index lookup ───────────────────────────────────────────────


@lru_cache(maxsize=1)
def _load_device_techniques_index() -> dict[str, list[dict]]:
    """Lazy-load the device_techniques_index.json sidecar.

    Returns the inner `devices` dict keyed by device id/slug, or {} on miss.
    """
    path = Path(__file__).parent / "device_techniques_index.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("devices") or {}
    except (OSError, json.JSONDecodeError) as exc:
        logger.debug("device_techniques_index load failed: %s", exc)
        return {}


def _lookup_techniques(device: dict) -> list[dict]:
    """Find signature_techniques entries for a device.

    Tries device id first (matches the index key), then name slug.
    Returns the list of {technique, description, aesthetic, kind} dicts;
    empty list on miss.
    """
    if not device:
        return []
    index = _load_device_techniques_index()
    if not index:
        return []
    dev_id = (device.get("id") or "").lower()
    if dev_id and dev_id in index:
        return list(index[dev_id])
    name_slug = (device.get("name") or "").lower().replace(" ", "_")
    if name_slug and name_slug in index:
        return list(index[name_slug])
    return []


# ── Tool implementations ────────────────────────────────────────────


def explore(
    *,
    atlas: Any,
    role: str,
    mood: str = "",
    genre: str = "",
    artists: Optional[list[str]] = None,
    n: int = 5,
    avoid_uris: Optional[list[str]] = None,
    cohort_constraint: Optional[list[str]] = None,
) -> dict:
    """atlas_explore implementation — wraps AtlasResolver.resolve_for_role.

    Returns a structured dict (not raw dataclass) so MCP serialization is clean.
    Falls through gracefully when atlas is missing — empty `candidates` plus a
    `reasoning` line that says why.
    """
    if atlas is None:
        return {
            "candidates": [],
            "cohort_hint": None,
            "reasoning": "atlas not loaded — no candidates available",
        }

    from ..composer.framework.atlas_resolver import AtlasResolver

    resolver = AtlasResolver(atlas=atlas)
    candidates = resolver.resolve_for_role(
        role=role,
        genre=genre,
        mood=mood,
        artist_refs=list(artists or []),
        avoid=[],
        cohort_constraint=list(cohort_constraint or []) or None,
        excluded_uris=set(avoid_uris or []) or None,
        n=n,
    )

    cohort_hint: Optional[str] = None
    if cohort_constraint:
        cohort_hint = cohort_constraint[0]
    elif candidates:
        # Most-frequent pack across top candidates
        packs = [c.in_pack for c in candidates if c.in_pack]
        if packs:
            cohort_hint = max(set(packs), key=packs.count)

    reasoning_bits: list[str] = []
    if cohort_constraint:
        reasoning_bits.append(f"cohort-constrained to: {', '.join(cohort_constraint)}")
    if mood:
        reasoning_bits.append(f"mood: {mood}")
    if genre:
        reasoning_bits.append(f"genre: {genre}")
    if not candidates:
        reasoning_bits.append(f"no candidates matched role '{role}'")

    return {
        "candidates": [asdict(c) for c in candidates],
        "cohort_hint": cohort_hint,
        "reasoning": "; ".join(reasoning_bits) or f"role '{role}' resolved",
    }


def audition(*, atlas: Any, uri: str) -> dict:
    """atlas_audition implementation — full sidecar dump for a single URI.

    Joins atlas device record + device_techniques_index entries +
    preset_resolver curated macros (when pack is known and device user_name
    matches a sidecar). Best-effort on every join — missing data returns
    empty fields rather than failing the whole call.
    """
    if atlas is None:
        return {"error": "atlas not loaded", "uri": uri}
    if not uri:
        return {"error": "uri is required", "uri": uri}

    device = atlas.lookup(uri) if hasattr(atlas, "lookup") else None
    if not device:
        return {
            "error": "device not found in atlas",
            "uri": uri,
            "hint": "URI may be a runtime browser URI (FileId-keyed). Try atlas_explore to find the canonical atlas URI.",
        }

    techniques = _lookup_techniques(device)
    pack = device.get("pack")
    user_name = device.get("name") or ""

    producer_macros: list[dict] = []
    curated_adg_paths: list[str] = []
    if pack and user_name:
        try:
            from .preset_resolver import resolve_preset_for_device
            preset_match = resolve_preset_for_device(
                pack_slug=pack,
                device_class=device.get("class") or "",
                device_user_name=user_name,
            )
            if preset_match.get("found"):
                # macro_names is {idx: name}; surface as a list ordered by index
                names = preset_match.get("macro_names") or {}
                for idx in sorted(names.keys()):
                    producer_macros.append({
                        "index": idx,
                        "name": names[idx],
                        "source_preset": preset_match.get("preset_name"),
                    })
                if preset_match.get("preset_file"):
                    curated_adg_paths.append(preset_match["preset_file"])
        except Exception as exc:
            logger.debug("audition: preset_resolver failed: %s", exc)

    return {
        "uri": uri,
        "name": user_name,
        "id": device.get("id", ""),
        "pack": pack,
        "category": device.get("category", ""),
        "character_tags": list(device.get("character_tags") or device.get("tags") or []),
        "signature_techniques": techniques,
        "producer_macros": producer_macros,
        "curated_adg_paths": curated_adg_paths,
        "enriched": bool(device.get("enriched")),
        # Related demos: defer until v1.25.x reverse-index lands; explicit empty
        # so callers can rely on the field's presence.
        "related_demos": [],
    }


def substitute(
    *,
    atlas: Any,
    current_uri: str,
    anti_tag: str,
    n: int = 3,
) -> dict:
    """atlas_substitute implementation — anti-tag-driven candidate swap.

    Looks up the current device's role/category/tags, derives an excluded-tag
    set from the anti_tag string, and returns N alternatives that:
      - share role/category with the current pick
      - do NOT carry any excluded character_tag
      - are scored by AtlasResolver with the excluded names on the avoid list
    """
    if atlas is None:
        return {"error": "atlas not loaded"}
    if not current_uri:
        return {"error": "current_uri is required"}

    current = atlas.lookup(current_uri) if hasattr(atlas, "lookup") else None
    if not current:
        return {
            "error": "current device not found in atlas",
            "current_uri": current_uri,
        }

    excluded_tags, preferred_tags = _resolve_anti_tags(anti_tag)
    if not excluded_tags:
        return {
            "error": f"unrecognized anti_tag '{anti_tag}'",
            "supported_anti_tags": sorted(_ANTI_TAG_MAP.keys()),
        }

    # Derive a role tag from the current device's character_tags. Prefer the
    # most-specific role term (kick/snare/hat/bass/pad/lead/atmos) over generic.
    current_tags_lower = [
        str(t).lower() for t in (current.get("character_tags") or current.get("tags") or [])
    ]
    role_priority = ("kick", "snare", "hihat", "hi-hat", "hat", "perc",
                     "bass", "pad", "lead", "atmos", "vocal", "fx", "spectral")
    role_tag = next((t for t in role_priority if t in current_tags_lower), "")
    role = role_tag or current.get("category") or "unknown"

    # Collect candidates from the same role tag, filter out any carrying an
    # excluded character_tag.
    by_tag = getattr(atlas, "_by_tag", {}) or {}
    role_candidates: list[dict] = []
    seen: set[str] = set()
    for dev in by_tag.get(role_tag.lower(), []) if role_tag else []:
        uri = dev.get("uri") or ""
        if not uri or uri in seen or uri == current_uri:
            continue
        dev_tags = [str(t).lower() for t in (dev.get("character_tags") or dev.get("tags") or [])]
        if any(excl in dev_tags for excl in excluded_tags):
            continue
        seen.add(uri)
        role_candidates.append(dev)

    # Score the survivors via AtlasResolver and pick top N
    from ..composer.framework.atlas_resolver import AtlasResolver

    resolver = AtlasResolver(atlas=atlas)
    scored: list[tuple[float, dict]] = []
    for dev in role_candidates:
        score, reasoning = resolver._score(
            dev,
            role=role if role in {
                "kick", "snare", "hat", "perc", "clap",
                "bass", "pad", "lead", "atmos", "vocal_chop", "fx", "spectral",
            } else "",
            genre="",
            mood=" ".join(preferred_tags),
            artist_refs=[],
            avoid=[],
        )
        scored.append((score, AtlasResolver._to_candidate(dev, score, reasoning, source="atlas").__dict__))

    scored.sort(key=lambda x: -x[0])
    alternatives = [c for _, c in scored[:n]]

    return {
        "current_uri": current_uri,
        "current_name": current.get("name", ""),
        "anti_tag": anti_tag,
        "excluded_tags": excluded_tags,
        "preferred_tags": preferred_tags,
        "alternatives": alternatives,
        "reasoning": (
            f"Excluded tags {excluded_tags} from candidates sharing role '{role}'. "
            f"Boosted candidates whose character_tags overlap preferred tags {preferred_tags}."
        ),
    }
