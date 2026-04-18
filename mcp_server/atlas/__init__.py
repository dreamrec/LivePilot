"""Device Atlas v2 — indexed in-memory device knowledge base.

Loads a JSON atlas file and builds indexes for fast lookup, search,
suggestion, chain building, and device comparison.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional


class AtlasManager:
    """In-memory device atlas with indexed lookups."""

    def __init__(self, atlas_path: str):
        with open(atlas_path, "r") as f:
            data = json.load(f)

        self._meta = data.get("meta", {})
        self._devices: List[Dict[str, Any]] = data.get("devices", [])

        # ── Build indexes ───────────────────────────────────────────
        self._by_id: Dict[str, Dict[str, Any]] = {}
        self._by_name: Dict[str, Dict[str, Any]] = {}  # lowercase key
        self._by_uri: Dict[str, Dict[str, Any]] = {}
        self._by_category: Dict[str, List[Dict[str, Any]]] = {}
        self._by_tag: Dict[str, List[Dict[str, Any]]] = {}
        self._by_genre: Dict[str, List[Dict[str, Any]]] = {}

        for dev in self._devices:
            dev_id = dev.get("id", "")
            dev_name = dev.get("name", "")
            dev_uri = dev.get("uri", "")
            dev_category = dev.get("category", "")

            if dev_id:
                self._by_id[dev_id] = dev
            if dev_name:
                self._by_name[dev_name.lower()] = dev
            if dev_uri:
                self._by_uri[dev_uri] = dev

            # Category index
            if dev_category:
                self._by_category.setdefault(dev_category, []).append(dev)

            # Tag index
            for tag in dev.get("tags", []):
                self._by_tag.setdefault(tag.lower(), []).append(dev)

            # Genre index (primary + secondary)
            for genre in dev.get("genres", {}).get("primary", []):
                self._by_genre.setdefault(genre.lower(), []).append(dev)
            for genre in dev.get("genres", {}).get("secondary", []):
                self._by_genre.setdefault(genre.lower(), []).append(dev)

    # ── Properties ──────────────────────────────────────────────────

    @property
    def version(self) -> str:
        return self._meta.get("version", "unknown")

    @property
    def device_count(self) -> int:
        return len(self._devices)

    @property
    def stats(self) -> Dict[str, Any]:
        categories: Dict[str, int] = {}
        for dev in self._devices:
            cat = dev.get("category", "unknown")
            categories[cat] = categories.get(cat, 0) + 1
        return {
            "version": self.version,
            "device_count": self.device_count,
            "categories": categories,
            "index_sizes": {
                "by_id": len(self._by_id),
                "by_name": len(self._by_name),
                "by_uri": len(self._by_uri),
                "by_category": len(self._by_category),
                "by_tag": len(self._by_tag),
                "by_genre": len(self._by_genre),
            },
        }

    # ── Lookup ──────────────────────────────────────────────────────

    def lookup(self, name_or_id: str) -> Optional[Dict[str, Any]]:
        """Exact match by ID, name (case-insensitive), or URI. Returns None on miss."""
        # Try ID first
        if name_or_id in self._by_id:
            return self._by_id[name_or_id]
        # Try name (case-insensitive)
        lower = name_or_id.lower()
        if lower in self._by_name:
            return self._by_name[lower]
        # Try URI
        if name_or_id in self._by_uri:
            return self._by_uri[name_or_id]
        return None

    # ── Search ──────────────────────────────────────────────────────

    def search(
        self, query: str, category: str = "all", limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Multi-signal search scoring across name, tags, use_cases, genre, description."""
        if not query:
            return []

        query_lower = query.lower()
        query_words = query_lower.split()
        results: List[Dict[str, Any]] = []

        # BUG-B39: the real atlas scanner emits "instruments" /
        # "audio_effects" but older callers and test fixtures sometimes
        # pass the singular "instrument" / "effect". Build a tolerant
        # category alias set so both forms work.
        _CAT_ALIASES = {
            "instrument": {"instrument", "instruments"},
            "instruments": {"instrument", "instruments"},
            "effect": {"effect", "effects", "audio_effects"},
            "effects": {"effect", "effects", "audio_effects"},
            "audio_effect": {"effect", "effects", "audio_effects",
                             "audio_effect"},
            "audio_effects": {"effect", "effects", "audio_effects",
                              "audio_effect"},
        }
        allowed_cats = (
            _CAT_ALIASES.get(category, {category})
            if category != "all" else None
        )

        for dev in self._devices:
            # Category filter
            if allowed_cats is not None and dev.get("category", "") not in allowed_cats:
                continue

            score = 0
            dev_name = dev.get("name", "")
            dev_name_lower = dev_name.lower()

            # Name scoring. BUG-B41 fix: dropped weight dramatically
            # (was 100 exact / 50 substring) so a device literally
            # named "Bass" no longer blows past character-tag matches
            # for a sonic query like "warm analog bass". An exact name
            # match is still the strongest single signal, but a device
            # with 2+ matching character-tags now beats a name-only
            # accident.
            if dev_name_lower == query_lower:
                score += 45  # was 100
            elif query_lower in dev_name_lower:
                score += 20  # was 50
            else:
                # Partial: any query word present in name — small signal
                for word in query_words:
                    if len(word) >= 3 and word in dev_name_lower:
                        score += 5

            # Tag scoring — prefer enriched character_tags.
            # BUG-B40 / B41: also read character_tags so enriched devices
            # actually compete with name-based matches.
            dev_tags = [
                t.lower() for t in (
                    dev.get("character_tags") or dev.get("tags", [])
                )
            ]
            # BUG-B41: bumped to 35pts per tag so multi-tag matches beat
            # a single substring-name match.
            for word in query_words:
                if word in dev_tags:
                    score += 35
                # Partial tag match (word appears as substring in a tag)
                else:
                    for tag in dev_tags:
                        if word in tag:
                            score += 10
                            break

            # Use case scoring: 25pts per match
            for use_case in dev.get("use_cases", []):
                use_lower = use_case.lower()
                for word in query_words:
                    if word in use_lower:
                        score += 25
                        break

            # Genre scoring: 20pts primary, 10pts secondary.
            # BUG-B40: also read genre_affinity (enriched field).
            genres = dev.get("genre_affinity") or dev.get("genres", {}) or {}
            for genre in genres.get("primary", []):
                if query_lower in genre.lower() or genre.lower() in query_lower:
                    score += 20
            for genre in genres.get("secondary", []):
                if query_lower in genre.lower() or genre.lower() in query_lower:
                    score += 10

            # Description keyword scoring: 15pts.
            # BUG-B40: prefer sonic_description when present.
            description = (
                dev.get("sonic_description") or dev.get("description", "")
            ).lower()
            for word in query_words:
                if len(word) >= 3 and word in description:
                    score += 15

            if score > 0:
                results.append({"device": dev, "score": score})

        # Sort by score descending, then by name for stability
        results.sort(key=lambda r: (-r["score"], r["device"].get("name", "")))
        return results[:limit]

    # ── Suggest ─────────────────────────────────────────────────────

    def suggest(
        self,
        intent: str,
        genre: str = "",
        energy: str = "medium",
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Suggest devices for an intent, returning ranked list with rationale and recipe."""
        # Use search to find candidates
        search_query = intent
        if genre:
            search_query = f"{intent} {genre}"
        candidates = self.search(search_query, limit=limit * 2)

        results = []
        for candidate in candidates[:limit]:
            dev = candidate["device"]
            dev_name = dev.get("name", "")
            dev_category = dev.get("category", "")
            dev_tags = dev.get("tags", [])
            dev_sweet_spot = dev.get("sweet_spot", "")

            # Build rationale
            rationale_parts = []
            if dev_category:
                rationale_parts.append(f"{dev_name} is a {dev_category}")
            if dev_tags:
                rationale_parts.append(f"suited for {', '.join(dev_tags[:3])}")
            if genre:
                primary_genres = dev.get("genres", {}).get("primary", [])
                if any(genre.lower() in g.lower() for g in primary_genres):
                    rationale_parts.append(f"commonly used in {genre}")
            rationale = " — ".join(rationale_parts) if rationale_parts else f"{dev_name} matches your intent"

            # Build recipe
            recipe = {}
            if dev_sweet_spot:
                recipe["sweet_spot"] = dev_sweet_spot
            recipe["energy"] = energy
            key_params = dev.get("key_parameters", [])
            if key_params:
                recipe["start_with"] = key_params[:3]

            results.append({
                "device": dev,
                "rationale": rationale,
                "recipe": recipe,
            })

        return results

    # ── Chain Suggest ───────────────────────────────────────────────

    def chain_suggest(
        self, role: str, genre: str = ""
    ) -> Dict[str, Any]:
        """Suggest a device chain for a given role (e.g., 'bass', 'lead', 'pad').

        BUG-B39 fix: the old code passed category="instrument" (singular)
        and category="effect" to self.search(), but the atlas stores
        devices with category="instruments" / "audio_effects" (plural).
        Every filtered search missed and the chain came back empty.
        """
        chain: List[Dict[str, Any]] = []
        position = 0

        # Determine chain structure based on role
        role_lower = role.lower()

        # Stage 1: Instrument (if the role implies one)
        instrument_intents = {
            "bass": "bass synthesizer",
            "lead": "lead synthesizer",
            "pad": "pad synthesizer",
            "keys": "keyboard instrument",
            "drums": "drum machine",
            "vocal": "vocal",
        }

        intent = instrument_intents.get(role_lower, role_lower)
        search_q = f"{intent} {genre}" if genre else intent

        # Find instrument — atlas category is "instruments" (plural)
        instrument_candidates = self.search(search_q, category="instruments", limit=3)
        if instrument_candidates:
            best = instrument_candidates[0]["device"]
            chain.append({
                "position": position,
                "device": best,
                "reason": f"Primary {role} instrument",
            })
            position += 1

        # Stage 2: Effects — atlas category is "audio_effects"
        effect_stages = [
            ("eq", f"Shape the {role} tone"),
            ("compression", f"Control {role} dynamics"),
            ("reverb", f"Add space to {role}"),
        ]

        for effect_type, reason in effect_stages:
            effect_q = f"{effect_type} {genre}" if genre else effect_type
            effect_candidates = self.search(
                effect_q, category="audio_effects", limit=2,
            )
            if effect_candidates:
                best = effect_candidates[0]["device"]
                chain.append({
                    "position": position,
                    "device": best,
                    "reason": reason,
                })
                position += 1

        return {
            "role": role,
            "genre": genre,
            "chain": chain,
        }

    # ── Compare ─────────────────────────────────────────────────────

    def compare(
        self, device_a: str, device_b: str, role: str = ""
    ) -> Dict[str, Any]:
        """Compare two devices side-by-side with a recommendation."""
        dev_a = self.lookup(device_a)
        dev_b = self.lookup(device_b)

        if not dev_a:
            return {"error": f"Device not found: {device_a}"}
        if not dev_b:
            return {"error": f"Device not found: {device_b}"}

        def _summarize(dev: Dict[str, Any]) -> Dict[str, Any]:
            # BUG-B40 fix: enriched atlas entries use character_tags /
            # sonic_description / genre_affinity — the old _summarize
            # looked for "tags" / "description" / "genres" which are
            # the UN-enriched raw scanner fields. We prefer enriched
            # fields, fall back to raw when enrichment is absent.
            return {
                "name": dev.get("name", ""),
                "category": dev.get("category", ""),
                "tags": dev.get("character_tags") or dev.get("tags", []),
                "genres": dev.get("genre_affinity") or dev.get("genres", {}),
                "use_cases": dev.get("use_cases", []),
                "description": (
                    dev.get("sonic_description")
                    or dev.get("description", "")
                ),
                "cpu_weight": dev.get("cpu_weight", "unknown"),
                "sweet_spot": dev.get("sweet_spot", ""),
                "enriched": dev.get("enriched", False),
            }

        summary_a = _summarize(dev_a)
        summary_b = _summarize(dev_b)

        # Recommendation logic: score each for the role.
        # BUG-B40: scorer also reads the enriched field names.
        score_a = 0
        score_b = 0
        if role:
            role_lower = role.lower()
            for uc in dev_a.get("use_cases", []):
                if role_lower in uc.lower():
                    score_a += 20
            for uc in dev_b.get("use_cases", []):
                if role_lower in uc.lower():
                    score_b += 20
            # Tag scoring — prefer character_tags (enriched)
            a_tags = dev_a.get("character_tags") or dev_a.get("tags", [])
            b_tags = dev_b.get("character_tags") or dev_b.get("tags", [])
            for tag in a_tags:
                if role_lower in tag.lower():
                    score_a += 10
            for tag in b_tags:
                if role_lower in tag.lower():
                    score_b += 10

        if score_a > score_b:
            recommendation = f"{summary_a['name']} is better suited for {role}" if role else f"{summary_a['name']} scores higher"
        elif score_b > score_a:
            recommendation = f"{summary_b['name']} is better suited for {role}" if role else f"{summary_b['name']} scores higher"
        else:
            recommendation = "Both devices are equally suited" + (f" for {role}" if role else "")

        return {
            "device_a": summary_a,
            "device_b": summary_b,
            "recommendation": recommendation,
        }


# ── Module-level lazy loader ───────────────────────────────────────
#
# Thread-safe via services.singletons.Singleton. The previous check-then-set
# pattern raced under FastMCP concurrency (two handlers could both construct
# AtlasManager) and never refreshed the in-memory index after a rebuild of
# device_atlas.json on disk. The Singleton helper handles both.
#
# The ``_atlas_instance`` module attribute is preserved for backward
# compatibility with call sites that read it directly (atlas/tools.py),
# but new code should call ``get_atlas()`` / ``invalidate_atlas()`` instead.

from pathlib import Path
from ..services.singletons import Singleton

ATLAS_PATH = Path(__file__).parent / "device_atlas.json"

_atlas_instance: Optional[AtlasManager] = None  # kept for legacy imports


def _build_atlas() -> AtlasManager:
    return AtlasManager(str(ATLAS_PATH))


_atlas_holder = Singleton(_build_atlas)


def get_atlas() -> AtlasManager:
    """Thread-safe accessor. Re-reads device_atlas.json if its mtime advanced."""
    global _atlas_instance
    instance = _atlas_holder.get(reload_if_newer=ATLAS_PATH)
    _atlas_instance = instance   # keep legacy attribute in sync
    return instance


def invalidate_atlas() -> None:
    """Force the next get_atlas() to re-read device_atlas.json from disk."""
    global _atlas_instance
    _atlas_holder.invalidate()
    _atlas_instance = None


def _load_atlas() -> AtlasManager:
    """Legacy shim — kept so atlas/tools.py still works. Prefer get_atlas()."""
    return get_atlas()
