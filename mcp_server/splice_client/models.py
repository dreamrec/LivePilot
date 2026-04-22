"""Splice client data models — Python representations of Splice gRPC messages.

Models here mirror the proto messages under `protos/app_pb2.py`.
See `project_splice_subscription_model.md` for the two-pocket model
(daily samples vs Splice.com credits) that PlanKind classifies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ── Plan classification ──────────────────────────────────────────────────


class PlanKind(str, Enum):
    """Classification of Splice subscription plans.

    Splice returns `User.SoundsStatus` as a generic string (often just
    "subscribed"), so we classify tier via the `Features` map and numeric
    `SoundsPlan` id. See `project_splice_subscription_model.md`.

    - ABLETON_LIVE: $12.99/mo, 100 samples/day unmetered via Ableton drag-drop
      + 100 intro credits for Splice.com content. Sample downloads DO NOT
      cost credits on this plan — they deplete a daily counter.
    - SOUNDS_PLUS: legacy per-credit tiers (100/300/600/1000) + Creator+.
      Samples DO cost credits.
    - CREATOR: $12.99/mo legacy creator plan, 100 credits/mo.
    - FREE: anonymous or unconverted trial.
    - UNKNOWN: plan metadata absent — treat like SOUNDS_PLUS (safest).
    """

    ABLETON_LIVE = "ableton_live"
    SOUNDS_PLUS = "sounds_plus"
    CREATOR = "creator"
    CREATOR_PLUS = "creator_plus"
    FREE = "free"
    UNKNOWN = "unknown"

    @property
    def is_subscribed(self) -> bool:
        return self != PlanKind.FREE and self != PlanKind.UNKNOWN

    @property
    def has_daily_sample_quota(self) -> bool:
        """True iff sample downloads deplete a daily counter, not credits."""
        return self == PlanKind.ABLETON_LIVE


# Feature-flag keys we look for in `User.Features`. Splice sets these in
# the ValidateLogin response. Names are best-effort — Splice may rename
# them; the classifier tolerates missing keys.
_FEATURE_ABLETON_UNMETERED = "ableton_unmetered"
_FEATURE_ABLETON_LIVE_PLAN = "ableton_live_plan"
_FEATURE_UNMETERED = "unmetered_downloads"
_FEATURE_CREATOR_PLUS = "creator_plus"

# Numeric plan IDs we've observed. Splice uses `User.SoundsPlan` as a
# proprietary enum. These are inferred from the API responses and the
# public plan catalog.
_PLAN_ID_ABLETON_LIVE = {12, 13}      # possible IDs for the Ableton plan
_PLAN_ID_CREATOR_PLUS = {11}
_PLAN_ID_CREATOR = {1, 2, 3}
_PLAN_ID_FREE = {0}


def classify_plan(
    sounds_status: str,
    sounds_plan: int,
    features: Optional[dict[str, bool]] = None,
) -> PlanKind:
    """Classify the user's Splice plan from the ValidateLogin response.

    Priority order (most authoritative first):
      1. Feature flags — if `ableton_unmetered` etc. is set, trust it.
      2. Non-zero numeric plan IDs we recognize.
      3. Free-form status string heuristics — catches "subscribed",
         "ableton live plan", "creator plus", etc.
      4. Numeric 0 → FREE only when the status string doesn't
         contradict. (plan_id=0 alone with status="subscribed" is NOT
         free — it's just a plan we don't have a numeric ID for yet.)
      5. Fallback: UNKNOWN so callers keep the safe credit-floor default.
    """
    features = features or {}

    # Step 1: feature flags are authoritative
    if features.get(_FEATURE_ABLETON_UNMETERED) or features.get(_FEATURE_ABLETON_LIVE_PLAN):
        return PlanKind.ABLETON_LIVE
    if features.get(_FEATURE_UNMETERED):
        return PlanKind.ABLETON_LIVE
    if features.get(_FEATURE_CREATOR_PLUS):
        return PlanKind.CREATOR_PLUS

    # Step 2: recognized non-zero plan IDs
    if sounds_plan in _PLAN_ID_ABLETON_LIVE:
        return PlanKind.ABLETON_LIVE
    if sounds_plan in _PLAN_ID_CREATOR_PLUS:
        return PlanKind.CREATOR_PLUS
    if sounds_plan in _PLAN_ID_CREATOR:
        return PlanKind.CREATOR

    # Step 3: string heuristics — BEFORE the plan_id=0 FREE check, because
    # "subscribed" + plan_id=0 means "subscribed plan we don't recognize
    # numerically", NOT free.
    status_lower = (sounds_status or "").lower().strip()
    if "ableton" in status_lower:
        return PlanKind.ABLETON_LIVE
    if "creator" in status_lower and "plus" in status_lower:
        return PlanKind.CREATOR_PLUS
    if "creator" in status_lower:
        return PlanKind.CREATOR
    if status_lower in ("subscribed", "paid", "active", "sounds_plus", "sounds+"):
        # Generic "subscribed" is ambiguous — SOUNDS_PLUS is the safe
        # default because it keeps the credit floor on. The MCP tool
        # documents this.
        return PlanKind.SOUNDS_PLUS
    if status_lower in ("free", "trial", "unconverted"):
        return PlanKind.FREE

    # Step 4: numeric FREE path — only reached when status was silent
    if sounds_plan in _PLAN_ID_FREE:
        return PlanKind.FREE

    # Step 5: fallback
    if not status_lower:
        return PlanKind.FREE
    return PlanKind.UNKNOWN


# ── Sample & search ──────────────────────────────────────────────────────


@dataclass
class SpliceSample:
    """A sample from the Splice catalog or local library."""

    file_hash: str = ""
    filename: str = ""
    local_path: str = ""          # empty if not downloaded
    audio_key: str = ""           # lowercase: "c#", "a", "eb"
    chord_type: str = ""          # "major", "minor", ""
    bpm: int = 0
    duration_ms: int = 0
    genre: str = ""
    sample_type: str = ""         # "loop" or "oneshot"
    tags: list[str] = field(default_factory=list)
    provider_name: str = ""
    pack_uuid: str = ""
    popularity: int = 0
    is_premium: bool = False
    price: int = 0                # 0 ⇒ free regardless of plan
    preview_url: str = ""
    waveform_url: str = ""
    is_downloaded: bool = False

    @property
    def key_display(self) -> str:
        """Normalized key: 'c#' + 'minor' → 'C#m'."""
        if not self.audio_key:
            return ""
        key = self.audio_key[0].upper() + self.audio_key[1:]
        if self.chord_type.lower() in ("minor", "min"):
            key += "m"
        return key

    @property
    def duration_seconds(self) -> float:
        return self.duration_ms / 1000.0 if self.duration_ms else 0.0

    @property
    def is_free(self) -> bool:
        """True iff this sample costs no credits under any plan.

        Splice marks samples as free via `IsPremium == False` or `Price == 0`.
        This is orthogonal to plan: even a free-tier user can license these.
        """
        return (not self.is_premium) or self.price == 0

    def to_dict(self) -> dict:
        return {
            "file_hash": self.file_hash,
            "filename": self.filename,
            "local_path": self.local_path,
            "key": self.key_display,
            "audio_key_raw": self.audio_key,
            "chord_type": self.chord_type,
            "bpm": self.bpm,
            "duration": self.duration_seconds,
            "genre": self.genre,
            "sample_type": self.sample_type,
            "tags": self.tags,
            "provider": self.provider_name,
            "pack_uuid": self.pack_uuid,
            "popularity": self.popularity,
            "is_downloaded": self.is_downloaded,
            "is_premium": self.is_premium,
            "price": self.price,
            "is_free": self.is_free,
            "preview_url": self.preview_url,
        }


@dataclass
class SpliceSearchResult:
    """Result from a Splice catalog search."""

    total_hits: int = 0
    samples: list[SpliceSample] = field(default_factory=list)
    matching_tags: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "total_hits": self.total_hits,
            "sample_count": len(self.samples),
            "samples": [s.to_dict() for s in self.samples],
            "matching_tags": self.matching_tags,
        }


# ── Credits & plan ───────────────────────────────────────────────────────


@dataclass
class SpliceCredits:
    """User credit status plus plan classification.

    `plan` is the raw Splice `SoundsStatus` string (e.g. "subscribed").
    `plan_kind` is our classification — use this for gating decisions.
    `features` carries the full `Features` map so callers can check
    granular flags not yet modelled by PlanKind.
    """

    credits: int = 0
    username: str = ""
    plan: str = ""
    sounds_plan_id: int = 0
    features: dict[str, bool] = field(default_factory=dict)
    plan_kind: PlanKind = PlanKind.UNKNOWN
    user_uuid: str = ""

    def to_dict(self) -> dict:
        return {
            "credits": self.credits,
            "username": self.username,
            "plan": self.plan,
            "sounds_plan_id": self.sounds_plan_id,
            "plan_kind": self.plan_kind.value,
            "features": dict(self.features),
            "user_uuid": self.user_uuid,
        }


# ── Collections (Splice-side personal organization) ──────────────────────


@dataclass
class SpliceCollection:
    """A user-curated Collection (Likes, custom folders, Daily Picks bookmark)."""

    uuid: str = ""
    name: str = ""
    description: str = ""
    access: str = ""              # "public", "private"
    permalink: str = ""
    cover_url: str = ""
    sample_count: int = 0
    preset_count: int = 0
    pack_count: int = 0
    subscription_count: int = 0
    created_by_current_user: bool = False
    creator_username: str = ""
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "description": self.description,
            "access": self.access,
            "permalink": self.permalink,
            "sample_count": self.sample_count,
            "preset_count": self.preset_count,
            "pack_count": self.pack_count,
            "cover_url": self.cover_url,
            "owned_by_me": self.created_by_current_user,
            "creator": self.creator_username,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# ── Packs ────────────────────────────────────────────────────────────────


@dataclass
class SplicePack:
    """A sample pack (Splice `SamplePack` message)."""

    uuid: str = ""
    name: str = ""
    cover_url: str = ""
    genre: str = ""
    permalink: str = ""
    provider_name: str = ""

    def to_dict(self) -> dict:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "genre": self.genre,
            "permalink": self.permalink,
            "provider": self.provider_name,
            "cover_url": self.cover_url,
        }


# ── Presets ──────────────────────────────────────────────────────────────


@dataclass
class SplicePreset:
    """A Splice Instrument or VST/AU preset from the catalog."""

    uuid: str = ""
    file_hash: str = ""
    filename: str = ""
    local_path: str = ""
    tags: list[str] = field(default_factory=list)
    price: int = 0
    is_default: bool = False
    plugin_name: str = ""
    plugin_version: str = ""
    provider_name: str = ""
    pack_uuid: str = ""
    preview_url: str = ""
    purchased_at: int = 0

    @property
    def is_downloaded(self) -> bool:
        return bool(self.local_path)

    def to_dict(self) -> dict:
        return {
            "uuid": self.uuid,
            "file_hash": self.file_hash,
            "filename": self.filename,
            "local_path": self.local_path,
            "tags": self.tags,
            "price": self.price,
            "plugin_name": self.plugin_name,
            "plugin_version": self.plugin_version,
            "provider": self.provider_name,
            "pack_uuid": self.pack_uuid,
            "is_default": self.is_default,
            "is_downloaded": self.is_downloaded,
            "preview_url": self.preview_url,
        }
