"""SpliceGRPCClient — connect to Splice desktop's local gRPC API.

Splice runs a gRPC server (Go binary) on localhost with TLS.
Port is dynamic (read from port.conf). Certs are self-signed.

This client provides: search, download, sample info, credit check.
All methods are async. Graceful degradation when Splice is not running.
"""

from __future__ import annotations

import asyncio
import glob
import logging
import os
from typing import Optional

from .models import SpliceCredits, SpliceSample, SpliceSearchResult

logger = logging.getLogger(__name__)

# Splice app support directory
_SPLICE_APP_SUPPORT = os.path.expanduser(
    "~/Library/Application Support/com.splice.Splice"
)

# Credit safety floor — never drain below this
CREDIT_HARD_FLOOR = 5


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

    def __init__(self):
        self.channel = None
        self.stub = None
        self.connected = False
        self._port: Optional[int] = None
        self._grpc = _try_import_grpc()
        self._pb2, self._pb2_grpc = _try_import_protos()

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
    ) -> SpliceSearchResult:
        """Search Splice catalog. Returns ranked results with full metadata."""
        if not self.connected:
            return SpliceSearchResult()

        pb2 = self._pb2
        try:
            # Build search request
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
            )
            response = await self.stub.SearchSamples(request)
            return self._parse_search_response(response)
        except Exception as exc:
            logger.warning(f"Splice search failed: {exc}")
            return SpliceSearchResult()

    def _parse_search_response(self, response) -> SpliceSearchResult:
        """Convert protobuf SearchSampleResponse to our models."""
        samples = []
        for s in response.Samples:
            samples.append(SpliceSample(
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
                preview_url=s.PreviewURL,
                waveform_url=s.WaveformURL,
                is_downloaded=bool(s.LocalPath),
            ))
        return SpliceSearchResult(
            total_hits=response.TotalHits,
            samples=samples,
            matching_tags=dict(response.MatchingTags),
        )

    # ── Download ────────────────────────────────────────────────────

    async def download_sample(
        self, file_hash: str, timeout: float = 30.0,
    ) -> Optional[str]:
        """Download a sample by file_hash. Returns local path when complete.

        Costs 1 credit. Enforces CREDIT_HARD_FLOOR defensively — refuses the
        download (returns None) if completing it would leave the user at or
        below the floor, regardless of what the caller requested. Callers
        should still gate on `can_afford` upstream for UX, but this guard
        closes the hole if a future caller forgets.
        """
        if not self.connected:
            return None

        # Defensive floor guard — do not rely on callers alone.
        can, remaining = await self.can_afford(1, budget=1)
        if not can:
            logger.warning(
                "Splice download blocked by credit floor guard "
                "(remaining=%s, floor=%s, file_hash=%s)",
                remaining, CREDIT_HARD_FLOOR, file_hash,
            )
            return None

        pb2 = self._pb2
        try:
            # Trigger download
            await self.stub.DownloadSample(
                pb2.DownloadSampleRequest(FileHash=file_hash)
            )
            # Wait for file to appear on disk
            return await self._wait_for_download(file_hash, timeout)
        except Exception as exc:
            logger.warning(f"Splice download failed for {file_hash}: {exc}")
            return None

    async def _wait_for_download(
        self, file_hash: str, timeout: float,
    ) -> Optional[str]:
        """Poll SampleInfo until LocalPath is populated."""
        pb2 = self._pb2
        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            try:
                response = await self.stub.SampleInfo(
                    pb2.SampleInfoRequest(FileHash=file_hash)
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
                pb2.SampleInfoRequest(FileHash=file_hash)
            )
            s = response.Sample
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
                is_downloaded=bool(s.LocalPath),
            )
        except Exception as exc:
            logger.warning(f"SampleInfo failed: {exc}")
            return None

    # ── Credits ─────────────────────────────────────────────────────

    async def get_credits(self) -> SpliceCredits:
        """Get current credit balance and user info."""
        if not self.connected:
            return SpliceCredits()

        pb2 = self._pb2
        try:
            response = await self.stub.ValidateLogin(
                pb2.ValidateLoginRequest()
            )
            return SpliceCredits(
                credits=response.User.Credits,
                username=response.User.Username,
                plan=response.User.SoundsStatus,
            )
        except Exception as exc:
            logger.warning(f"Credit check failed: {exc}")
            return SpliceCredits()

    async def can_afford(self, credits_needed: int, budget: int) -> tuple[bool, int]:
        """Check if we can afford credits_needed within budget.

        Returns (can_afford, credits_remaining).
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
            await self.stub.SyncSounds(pb2.SyncSoundsRequest())
            return True
        except Exception as exc:
            logger.debug("sync_sounds failed: %s", exc)
            return False
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
