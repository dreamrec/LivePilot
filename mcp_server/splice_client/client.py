"""SpliceGRPCClient — connect to Splice desktop's local gRPC API.

Splice runs a gRPC server (Go binary) on localhost with TLS.
Port is dynamic (read from port.conf). Certs are self-signed.

This client wraps the full `proto.App` service surface:
  - Search / download / sample-info
  - Credits + plan classification (see models.PlanKind)
  - Collections (list, samples, add/remove items, create, update, delete)
  - Presets (purchased list, download, info, purchase)
  - Packs (info)
  - Imported samples (user's own directories indexed by Splice)
  - Convert to WAV (for non-WAV sources)
  - Preview URL fetching (zero-credit audition)

All methods are async. Graceful degradation when Splice is not running.

Plan-aware gating (see `project_splice_subscription_model.md`):
  - On the Ableton Live plan, sample downloads deplete a DAILY counter
    (100/day) rather than credits. `can_download_sample()` checks both
    the daily quota AND the credit floor, choosing the right budget for
    the user's actual plan.
  - Free samples (`Sample.IsPremium == False` or `Price == 0`) bypass
    gating entirely — they're free under any plan.
"""

from __future__ import annotations

import asyncio
import glob
import logging
import os
from dataclasses import dataclass
from typing import Optional

from .models import (
    PlanKind,
    SpliceCollection,
    SpliceCredits,
    SplicePack,
    SplicePreset,
    SpliceSample,
    SpliceSearchResult,
    classify_plan,
)
from .quota import DailyQuotaTracker, get_tracker

logger = logging.getLogger(__name__)

# Splice app support directory
_SPLICE_APP_SUPPORT = os.path.expanduser(
    "~/Library/Application Support/com.splice.Splice"
)

# Credit safety floor — never drain below this on credit-metered plans.
# Does NOT apply to the Ableton Live plan, which uses a daily counter.
CREDIT_HARD_FLOOR = 5

# Per-call gRPC timeouts. The previous implementation passed no timeout, so
# a hung Splice process could block the MCP event loop until gRPC's default
# (often infinite) deadline fired. Keep generous enough for cold searches
# but bounded enough that a dead socket fails the tool call, not the server.
SEARCH_TIMEOUT = 10.0
INFO_TIMEOUT = 5.0
CREDITS_TIMEOUT = 5.0
SYNC_TIMEOUT = 30.0
DOWNLOAD_TRIGGER_TIMEOUT = 5.0
COLLECTION_TIMEOUT = 10.0
PRESET_TIMEOUT = 10.0
CONVERT_TIMEOUT = 30.0


@dataclass
class DownloadDecision:
    """Result of pre-download gating logic.

    `allowed` — whether to proceed with the download.
    `reason` — human-readable explanation.
    `plan_kind` — plan classification used for the decision.
    `credits_remaining` / `quota_used` / `quota_remaining` — state snapshot.
    `gating_mode` — "free_sample", "daily_quota", "credit_floor", or "blocked".
    """

    allowed: bool
    reason: str
    plan_kind: PlanKind
    gating_mode: str
    credits_remaining: int = 0
    quota_used: int = 0
    quota_remaining: int = 0

    def to_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "plan_kind": self.plan_kind.value,
            "gating_mode": self.gating_mode,
            "credits_remaining": self.credits_remaining,
            "quota_used": self.quota_used,
            "quota_remaining": self.quota_remaining,
        }


def _try_import_grpc():
    """Import grpcio lazily — graceful degradation if not installed."""
    try:
        import grpc
        return grpc
    except ImportError:
        return None


def _try_import_protos():
    """Import generated protobuf stubs lazily."""
    try:
        from .protos import app_pb2, app_pb2_grpc
        return app_pb2, app_pb2_grpc
    except ImportError:
        return None, None


class SpliceGRPCClient:
    """Async gRPC client for Splice desktop's App service."""

    def __init__(self, quota_tracker: Optional[DailyQuotaTracker] = None):
        self.channel = None
        self.stub = None
        self.connected = False
        self._port: Optional[int] = None
        self._grpc = _try_import_grpc()
        self._pb2, self._pb2_grpc = _try_import_protos()
        self._quota = quota_tracker or get_tracker()
        # Cached plan state — refreshed on every explicit get_credits() call.
        self._cached_credits: Optional[SpliceCredits] = None

    @property
    def available(self) -> bool:
        """True if grpcio is installed and Splice app support exists."""
        return (
            self._grpc is not None
            and self._pb2 is not None
            and os.path.isdir(_SPLICE_APP_SUPPORT)
        )

    async def connect(self) -> bool:
        """Connect to Splice's local gRPC server. Returns True on success."""
        if not self.available:
            logger.info("Splice gRPC not available (grpcio missing or Splice not installed)")
            return False

        port = self._read_port()
        if not port:
            logger.info("Cannot read Splice port from port.conf")
            return False

        cert_pem = self._read_cert()
        if not cert_pem:
            logger.info("Cannot read Splice TLS certificate")
            return False

        try:
            grpc = self._grpc
            credentials = grpc.ssl_channel_credentials(root_certificates=cert_pem)
            self.channel = grpc.aio.secure_channel(
                f"127.0.0.1:{port}", credentials
            )
            self.stub = self._pb2_grpc.AppStub(self.channel)
            self._port = port
            self.connected = True
            logger.info(f"Connected to Splice gRPC on port {port}")
            return True
        except Exception as exc:
            logger.warning(f"Failed to connect to Splice: {exc}")
            self.connected = False
            return False

    async def disconnect(self):
        """Close the gRPC channel."""
        if self.channel:
            await self.channel.close()
            self.channel = None
            self.stub = None
            self.connected = False

    # ── Search ──────────────────────────────────────────────────────

    async def search_samples(
        self,
        query: str = "",
        key: str = "",
        chord_type: str = "",
        bpm_min: int = 0,
        bpm_max: int = 0,
        tags: Optional[list[str]] = None,
        genre: str = "",
        sample_type: str = "",
        sort: str = "",
        per_page: int = 20,
        page: int = 1,
        purchased_only: bool = False,
        collection_uuid: str = "",
        file_hash: str = "",
    ) -> SpliceSearchResult:
        """Search Splice catalog. Returns ranked results with full metadata.

        `collection_uuid` scopes search to a single user collection
        (e.g. "Likes", "bass") — pure taste signal when present.
        `file_hash` is a direct lookup for a single sample.
        """
        if not self.connected:
            return SpliceSearchResult()

        pb2 = self._pb2
        try:
            purchased = 0  # All
            if purchased_only:
                purchased = 1  # OnlyPurchased

            request = pb2.SearchSampleRequest(
                SearchTerm=query,
                Key=key.lower() if key else "",
                ChordType=chord_type,
                BPMMin=bpm_min,
                BPMMax=bpm_max,
                Tags=tags or [],
                Genre=genre,
                SampleType=sample_type,
                SortFn=sort,
                PerPage=per_page,
                Page=page,
                Purchased=purchased,
                CollectionUUID=collection_uuid,
                FileHash=file_hash,
            )
            response = await self.stub.SearchSamples(request, timeout=SEARCH_TIMEOUT)
            return self._parse_search_response(response)
        except Exception as exc:
            logger.warning(f"Splice search failed: {exc}")
            return SpliceSearchResult()

    def _parse_search_response(self, response) -> SpliceSearchResult:
        """Convert protobuf SearchSampleResponse to our models."""
        samples = []
        for s in response.Samples:
            samples.append(self._parse_sample(s))
        return SpliceSearchResult(
            total_hits=response.TotalHits,
            samples=samples,
            matching_tags=dict(response.MatchingTags),
        )

    def _parse_sample(self, s) -> SpliceSample:
        """Convert a single protobuf Sample to our model."""
        return SpliceSample(
            file_hash=s.FileHash,
            filename=s.Filename,
            local_path=s.LocalPath,
            audio_key=s.AudioKey,
            chord_type=s.ChordType,
            bpm=s.BPM,
            duration_ms=s.Duration,
            genre=s.Genre,
            sample_type=s.SampleType,
            tags=list(s.Tags),
            provider_name=s.ProviderName,
            pack_uuid=s.PackUUID,
            popularity=s.Popularity,
            is_premium=s.IsPremium,
            price=s.Price if hasattr(s, "Price") else 0,
            preview_url=s.PreviewURL,
            waveform_url=s.WaveformURL,
            is_downloaded=bool(s.LocalPath),
        )

    # ── Download ────────────────────────────────────────────────────

    async def decide_download(
        self,
        file_hash: str,
        sample: Optional[SpliceSample] = None,
    ) -> DownloadDecision:
        """Run plan-aware gating logic for a prospective download.

        The caller passes the `SpliceSample` when known (from a prior
        search); we use it to detect `is_free` and skip all gating.
        When not known we do NOT fetch the sample — that would waste
        a SampleInfo round-trip. Unknown samples default to paid.
        """
        if not self.connected:
            return DownloadDecision(
                allowed=False,
                reason="Splice desktop app not reachable",
                plan_kind=PlanKind.UNKNOWN,
                gating_mode="blocked",
            )

        # Fast path: free samples bypass every gate.
        if sample is not None and sample.is_free:
            return DownloadDecision(
                allowed=True,
                reason=(
                    "Sample is free (Price=0 or !IsPremium) — no credit or "
                    "quota cost under any plan."
                ),
                plan_kind=(
                    self._cached_credits.plan_kind
                    if self._cached_credits
                    else PlanKind.UNKNOWN
                ),
                gating_mode="free_sample",
            )

        # Refresh plan + credit state for this decision.
        credits = await self.get_credits()
        plan = credits.plan_kind

        if plan == PlanKind.ABLETON_LIVE:
            quota = self._quota.summary()
            if quota["at_limit"]:
                return DownloadDecision(
                    allowed=False,
                    reason=(
                        f"Daily quota hit ({quota['used_today']}/"
                        f"{quota['daily_limit']}). Resets at UTC midnight."
                    ),
                    plan_kind=plan,
                    gating_mode="daily_quota",
                    credits_remaining=credits.credits,
                    quota_used=quota["used_today"],
                    quota_remaining=quota["remaining_today"],
                )
            return DownloadDecision(
                allowed=True,
                reason=(
                    f"Ableton Live plan: {quota['remaining_today']} of "
                    f"{quota['daily_limit']} daily samples remain. Download "
                    "will NOT deplete your 80 Splice.com credits."
                ),
                plan_kind=plan,
                gating_mode="daily_quota",
                credits_remaining=credits.credits,
                quota_used=quota["used_today"],
                quota_remaining=quota["remaining_today"],
            )

        # Credit-metered plans (SOUNDS_PLUS, CREATOR, CREATOR_PLUS, UNKNOWN).
        # Keep the hard floor to avoid draining the monthly pool.
        can, remaining = await self.can_afford(1, budget=1)
        if not can:
            return DownloadDecision(
                allowed=False,
                reason=(
                    f"Credit safety floor hit (remaining={remaining}, "
                    f"floor={CREDIT_HARD_FLOOR}). Download would drain "
                    "your monthly allotment past the safe reserve."
                ),
                plan_kind=plan,
                gating_mode="credit_floor",
                credits_remaining=remaining,
            )
        return DownloadDecision(
            allowed=True,
            reason=(
                f"Credit-metered plan ({plan.value}): {remaining} credits "
                "available, safely above floor."
            ),
            plan_kind=plan,
            gating_mode="credit_floor",
            credits_remaining=remaining,
        )

    async def download_sample(
        self,
        file_hash: str,
        timeout: float = 30.0,
        sample: Optional[SpliceSample] = None,
    ) -> Optional[str]:
        """Download a sample by file_hash. Returns local path when complete.

        Plan-aware gating:
          - Free samples: always allowed, no counter update.
          - Ableton Live plan: increments daily quota, leaves credits alone.
          - Credit-metered plans: enforces CREDIT_HARD_FLOOR.

        Callers should prefer `decide_download()` first for a structured
        response that surfaces plan/quota state. This method is the
        imperative "go download it" path; the decision is repeated here
        defensively because a future caller might forget to gate.
        """
        if not self.connected:
            return None

        decision = await self.decide_download(file_hash, sample=sample)
        if not decision.allowed:
            logger.warning(
                "Splice download refused: %s (plan=%s, mode=%s)",
                decision.reason, decision.plan_kind.value, decision.gating_mode,
            )
            return None

        pb2 = self._pb2
        try:
            # Trigger download
            await self.stub.DownloadSample(
                pb2.DownloadSampleRequest(FileHash=file_hash),
                timeout=DOWNLOAD_TRIGGER_TIMEOUT,
            )
            # Wait for file to appear on disk
            local_path = await self._wait_for_download(file_hash, timeout)
        except Exception as exc:
            logger.warning(f"Splice download failed for {file_hash}: {exc}")
            return None

        if local_path is None:
            return None

        # Record against the daily quota IF this was a quota-metered download.
        # Free samples don't count; credit-metered samples are tracked by
        # Splice server-side (our credit count will reflect on next fetch).
        if decision.gating_mode == "daily_quota":
            try:
                self._quota.record_download(
                    file_hash=file_hash,
                    filename=os.path.basename(local_path),
                )
            except Exception as exc:
                logger.debug("quota record_download failed: %s", exc)

        return local_path

    async def _wait_for_download(
        self, file_hash: str, timeout: float,
    ) -> Optional[str]:
        """Poll SampleInfo until LocalPath is populated."""
        pb2 = self._pb2
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while loop.time() < deadline:
            try:
                response = await self.stub.SampleInfo(
                    pb2.SampleInfoRequest(FileHash=file_hash),
                    timeout=INFO_TIMEOUT,
                )
                if response.Sample.LocalPath:
                    return response.Sample.LocalPath
            except Exception as exc:
                logger.debug("_wait_for_download failed: %s", exc)
            await asyncio.sleep(0.5)
        logger.warning(f"Download timed out for {file_hash}")
        return None

    # ── Sample Info ─────────────────────────────────────────────────

    async def get_sample_info(self, file_hash: str) -> Optional[SpliceSample]:
        """Get metadata for a specific sample."""
        if not self.connected:
            return None

        pb2 = self._pb2
        try:
            response = await self.stub.SampleInfo(
                pb2.SampleInfoRequest(FileHash=file_hash),
                timeout=INFO_TIMEOUT,
            )
            return self._parse_sample(response.Sample)
        except Exception as exc:
            logger.warning(f"SampleInfo failed: {exc}")
            return None

    # ── Credits + Plan ──────────────────────────────────────────────

    async def get_credits(self) -> SpliceCredits:
        """Get current credit balance, plan, and feature-flag map."""
        if not self.connected:
            return SpliceCredits()

        pb2 = self._pb2
        try:
            response = await self.stub.ValidateLogin(
                pb2.ValidateLoginRequest(),
                timeout=CREDITS_TIMEOUT,
            )
            user = response.User
            features = dict(user.Features) if hasattr(user, "Features") else {}
            sounds_plan = (
                int(user.SoundsPlan) if hasattr(user, "SoundsPlan") else 0
            )
            uuid_str = str(user.UUID) if hasattr(user, "UUID") else ""
            plan_kind = classify_plan(
                sounds_status=user.SoundsStatus,
                sounds_plan=sounds_plan,
                features=features,
            )
            creds = SpliceCredits(
                credits=user.Credits,
                username=user.Username,
                plan=user.SoundsStatus,
                sounds_plan_id=sounds_plan,
                features=features,
                plan_kind=plan_kind,
                user_uuid=uuid_str,
            )
            self._cached_credits = creds
            return creds
        except Exception as exc:
            logger.warning(f"Credit check failed: {exc}")
            return SpliceCredits()

    async def can_afford(self, credits_needed: int, budget: int) -> tuple[bool, int]:
        """Check if we can afford `credits_needed` within `budget` for
        credit-metered plans.

        Returns (can_afford, credits_remaining). NOTE: does NOT consult the
        daily quota — callers on the Ableton Live plan should use
        `decide_download()` instead of `can_afford()`.
        """
        info = await self.get_credits()
        remaining = info.credits
        can = (
            remaining > CREDIT_HARD_FLOOR
            and credits_needed <= budget
            and credits_needed <= (remaining - CREDIT_HARD_FLOOR)
        )
        return can, remaining

    # ── Sync ────────────────────────────────────────────────────────

    async def sync_sounds(self) -> bool:
        """Trigger a full Splice library sync."""
        if not self.connected:
            return False
        pb2 = self._pb2
        try:
            await self.stub.SyncSounds(
                pb2.SyncSoundsRequest(),
                timeout=SYNC_TIMEOUT,
            )
            return True
        except Exception as exc:
            logger.debug("sync_sounds failed: %s", exc)
            return False

    # ── Collections ─────────────────────────────────────────────────

    def _parse_collection(self, c) -> SpliceCollection:
        creator_username = ""
        try:
            creator_username = c.Creator.Username
        except AttributeError:
            pass
        access_map = {0: "unspecified", 1: "private", 2: "public"}
        access = access_map.get(
            int(c.Access) if hasattr(c, "Access") else 0, "unspecified",
        )
        return SpliceCollection(
            uuid=c.UUID,
            name=c.Name,
            description=c.Description,
            access=access,
            permalink=c.Permalink,
            cover_url=c.CoverURL,
            sample_count=int(c.SampleCount),
            preset_count=int(c.PresetCount),
            pack_count=int(c.PackCount),
            subscription_count=int(c.SubscriptionCount),
            created_by_current_user=bool(c.CreatedByCurrentUser),
            creator_username=creator_username,
            created_at=c.CreatedAt,
            updated_at=c.UpdatedAt,
        )

    async def list_collections(
        self, page: int = 1, per_page: int = 50,
    ) -> tuple[int, list[SpliceCollection]]:
        """List the user's collections. Returns (total_count, collections)."""
        if not self.connected:
            return 0, []
        pb2 = self._pb2
        try:
            response = await self.stub.CollectionsList(
                pb2.CollectionsListRequest(Page=page, PerPage=per_page),
                timeout=COLLECTION_TIMEOUT,
            )
            total = int(response.TotalCount)
            collections = [self._parse_collection(c) for c in response.Collections]
            return total, collections
        except Exception as exc:
            logger.warning(f"CollectionsList failed: {exc}")
            return 0, []

    async def collection_samples(
        self, uuid: str, page: int = 1, per_page: int = 50,
    ) -> tuple[int, list[SpliceSample]]:
        """List samples inside a collection. Returns (total_hits, samples)."""
        if not self.connected:
            return 0, []
        pb2 = self._pb2
        try:
            response = await self.stub.CollectionListSamples(
                pb2.CollectionListSamplesRequest(
                    UUID=uuid, Page=page, PerPage=per_page,
                ),
                timeout=COLLECTION_TIMEOUT,
            )
            total = int(response.TotalHits)
            samples = [self._parse_sample(s) for s in response.Samples]
            return total, samples
        except Exception as exc:
            logger.warning(f"CollectionListSamples failed: {exc}")
            return 0, []

    async def add_to_collection(self, uuid: str, sample_hashes: list[str]) -> bool:
        """Add samples to a collection. Returns True on success."""
        if not self.connected or not sample_hashes:
            return False
        pb2 = self._pb2
        try:
            await self.stub.CollectionAddItems(
                pb2.CollectionAddItemsRequest(UUID=uuid, Samples=sample_hashes),
                timeout=COLLECTION_TIMEOUT,
            )
            return True
        except Exception as exc:
            logger.warning(f"CollectionAddItems failed: {exc}")
            return False

    async def remove_from_collection(
        self, uuid: str, sample_hashes: list[str],
    ) -> bool:
        """Remove samples from a collection."""
        if not self.connected or not sample_hashes:
            return False
        pb2 = self._pb2
        try:
            await self.stub.CollectionDeleteItems(
                pb2.CollectionDeleteItemsRequest(UUID=uuid, Samples=sample_hashes),
                timeout=COLLECTION_TIMEOUT,
            )
            return True
        except Exception as exc:
            logger.warning(f"CollectionDeleteItems failed: {exc}")
            return False

    async def create_collection(self, name: str) -> Optional[SpliceCollection]:
        """Create a new user collection. Returns the new Collection or None."""
        if not self.connected:
            return None
        pb2 = self._pb2
        try:
            response = await self.stub.CollectionAdd(
                pb2.CollectionAddRequest(Name=name),
                timeout=COLLECTION_TIMEOUT,
            )
            return self._parse_collection(response.Collection)
        except Exception as exc:
            logger.warning(f"CollectionAdd failed: {exc}")
            return None

    # ── Packs ───────────────────────────────────────────────────────

    async def get_pack_info(self, pack_uuid: str) -> Optional[SplicePack]:
        """Fetch metadata for a single sample pack."""
        if not self.connected:
            return None
        pb2 = self._pb2
        try:
            response = await self.stub.SamplePackInfo(
                pb2.SamplePackInfoRequest(UUID=pack_uuid),
                timeout=INFO_TIMEOUT,
            )
            p = response.Pack
            return SplicePack(
                uuid=p.UUID,
                name=p.Name,
                cover_url=p.CoverURL,
                genre=p.Genre,
                permalink=p.Permalink,
                provider_name=p.ProviderName,
            )
        except Exception as exc:
            logger.warning(f"SamplePackInfo failed: {exc}")
            return None

    # ── Presets ─────────────────────────────────────────────────────

    def _parse_preset(self, p) -> SplicePreset:
        return SplicePreset(
            uuid=p.UUID,
            file_hash=p.FileHash,
            filename=p.Filename,
            local_path=p.LocalPath,
            tags=list(p.Tags),
            price=int(p.Price),
            is_default=bool(p.IsDefault),
            plugin_name=p.PluginName,
            plugin_version=p.PluginVersion,
            provider_name=p.ProviderName,
            pack_uuid=p.Pack.UUID if hasattr(p, "Pack") else "",
            preview_url=p.PreviewURL,
            purchased_at=int(p.PurchasedAt) if hasattr(p, "PurchasedAt") else 0,
        )

    async def list_purchased_presets(
        self,
        page: int = 1,
        per_page: int = 50,
        sort: str = "",
        sort_order: str = "",
    ) -> tuple[int, list[SplicePreset]]:
        """List presets the user has purchased/owns."""
        if not self.connected:
            return 0, []
        pb2 = self._pb2
        try:
            response = await self.stub.PresetsListPurchased(
                pb2.PresetsListPurchasedRequest(
                    Page=page, PerPage=per_page,
                    SortFn=sort, SortOrder=sort_order,
                ),
                timeout=PRESET_TIMEOUT,
            )
            total = int(response.TotalHits)
            presets = [self._parse_preset(p) for p in response.Presets]
            return total, presets
        except Exception as exc:
            logger.warning(f"PresetsListPurchased failed: {exc}")
            return 0, []

    async def get_preset_info(
        self, uuid: str = "", file_hash: str = "", plugin_name: str = "",
    ) -> Optional[dict]:
        """Fetch metadata for a single preset."""
        if not self.connected:
            return None
        pb2 = self._pb2
        try:
            response = await self.stub.PresetInfo(
                pb2.PresetInfoRequest(
                    UUID=uuid, FileHash=file_hash, PluginName=plugin_name,
                ),
                timeout=PRESET_TIMEOUT,
            )
            return {
                "uuid": response.Preset.UUID,
                "file_hash": response.Preset.FileHash,
                "local_path": response.Preset.LocalPath,
            }
        except Exception as exc:
            logger.warning(f"PresetInfo failed: {exc}")
            return None

    async def download_preset(self, uuid: str) -> bool:
        """Trigger a preset download (uses credits)."""
        if not self.connected:
            return False
        pb2 = self._pb2
        try:
            await self.stub.PresetDownload(
                pb2.PresetDownloadRequest(UUID=uuid),
                timeout=PRESET_TIMEOUT,
            )
            return True
        except Exception as exc:
            logger.warning(f"PresetDownload failed: {exc}")
            return False

    # ── Convert to WAV ──────────────────────────────────────────────

    async def convert_to_wav(self, path: str) -> Optional[dict]:
        """Convert an audio file to PCM WAV via Splice's converter."""
        if not self.connected:
            return None
        pb2 = self._pb2
        try:
            response = await self.stub.ConvertToWav(
                pb2.ConvertToWavRequest(Path=path),
                timeout=CONVERT_TIMEOUT,
            )
            wav = response.WavFile
            return {
                "path": wav.Path,
                "channels": int(wav.Channels),
                "sample_rate": int(wav.SampleRate),
                "bit_depth": int(wav.BitDepth),
            }
        except Exception as exc:
            logger.warning(f"ConvertToWav failed: {exc}")
            return None

    # ── Connection Helpers ──────────────────────────────────────────

    def _read_port(self) -> Optional[int]:
        """Read Splice's current gRPC port from port.conf."""
        port_file = os.path.join(_SPLICE_APP_SUPPORT, "port.conf")
        if not os.path.isfile(port_file):
            return None
        try:
            with open(port_file) as f:
                content = f.read().strip()
            # Format: "127.0.0.1:56765" or just "56765"
            if ":" in content:
                return int(content.split(":")[-1])
            return int(content)
        except (ValueError, OSError):
            return None

    def _read_cert(self) -> Optional[bytes]:
        """Read Splice's self-signed TLS certificate."""
        # Search in user-specific directories
        patterns = [
            os.path.join(_SPLICE_APP_SUPPORT, ".certs", "cert.pem"),
            os.path.join(_SPLICE_APP_SUPPORT, "certs", "cert.pem"),
        ]
        # Also try user-specific paths
        user_patterns = glob.glob(
            os.path.join(_SPLICE_APP_SUPPORT, "users", "*", ".certs", "cert.pem")
        )
        patterns.extend(user_patterns)

        for path in patterns:
            if os.path.isfile(path):
                try:
                    with open(path, "rb") as f:
                        return f.read()
                except OSError:
                    continue
        return None
