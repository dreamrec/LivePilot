"""HTTPS bridge for Splice plugin-exclusive features.

The Splice Sounds Plugin (beta) ships two capabilities that are NOT on the
local gRPC service:
  - **Describe a Sound** — natural-language search ("dark ambient pad
    with shimmer")
  - **Variations** — generate unique re-keyed / re-tempo'd versions of
    any sample

Both call `api.splice.com` over HTTPS, authenticated with the session
token we can read from the local gRPC `GetSession` RPC.

This module is *scaffolding* — it builds the auth flow, endpoint URLs,
response parsing, and retry/timeout plumbing so that capturing the real
endpoint shapes (via mitmproxy against the running plugin) is a matter
of updating the URL templates rather than rebuilding infrastructure.

## How to go from scaffolding to working tool

1. Run mitmproxy in transparent mode against the Splice Sounds Plugin
   while it makes a Describe a Sound or Variations request.
2. Capture the real endpoint URL, request body shape, and response body.
3. Drop the values into `SpliceHTTPConfig` defaults or via env vars:
     - `SPLICE_API_BASE_URL` (default: https://api.splice.com)
     - `SPLICE_DESCRIBE_ENDPOINT` (default: /v1/describe)
     - `SPLICE_VARIATION_ENDPOINT` (default: /v1/variations/{file_hash})
4. Run `splice_describe_sound("dark pad")` — done.

Until step 4 is complete, the MCP tools return a clear, actionable error
rather than pretending to work. Zero cheats.

## Why token-based instead of embedding the plugin

The plugin's authentication flow uses Splice's OAuth session tokens.
These rotate periodically — hardcoding them wouldn't work. Reading from
`GetSession` RPC means we always use the current session, tied to the
user's currently-logged-in Splice desktop app.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ── Configuration ─────────────────────────────────────────────────────


@dataclass
class SpliceHTTPConfig:
    """Endpoint configuration for the HTTPS bridge.

    All fields have env-var overrides so a dev can swap them for testing
    without code changes. Defaults are best-guesses based on Splice's
    public URL conventions — they WILL need updating when we capture real
    traffic. That's expected.
    """

    base_url: str = "https://api.splice.com"
    describe_endpoint: str = "/v1/describe"
    variation_endpoint: str = "/v1/variations/{file_hash}"
    search_with_sound_endpoint: str = "/v1/search-with-sound"
    timeout_sec: float = 30.0
    max_retries: int = 2

    @classmethod
    def from_env(cls) -> "SpliceHTTPConfig":
        """Load config from env vars, falling back to defaults."""
        return cls(
            base_url=os.environ.get("SPLICE_API_BASE_URL", cls.base_url),
            describe_endpoint=os.environ.get(
                "SPLICE_DESCRIBE_ENDPOINT", cls.describe_endpoint,
            ),
            variation_endpoint=os.environ.get(
                "SPLICE_VARIATION_ENDPOINT", cls.variation_endpoint,
            ),
            search_with_sound_endpoint=os.environ.get(
                "SPLICE_SEARCH_WITH_SOUND_ENDPOINT",
                cls.search_with_sound_endpoint,
            ),
            timeout_sec=float(os.environ.get("SPLICE_HTTP_TIMEOUT", cls.timeout_sec)),
            max_retries=int(os.environ.get("SPLICE_HTTP_RETRIES", cls.max_retries)),
        )

    @property
    def is_user_configured(self) -> bool:
        """True when at least one endpoint URL has been overridden by env var.

        Defaults are unverified guesses; callers check this before making
        requests so we don't silently hit non-existent endpoints.
        """
        return (
            "SPLICE_API_BASE_URL" in os.environ
            or "SPLICE_DESCRIBE_ENDPOINT" in os.environ
            or "SPLICE_VARIATION_ENDPOINT" in os.environ
            or "SPLICE_SEARCH_WITH_SOUND_ENDPOINT" in os.environ
            or os.environ.get("SPLICE_ALLOW_UNVERIFIED_ENDPOINTS") == "1"
        )


# ── Auth token fetch ─────────────────────────────────────────────────


async def fetch_session_token(grpc_client) -> Optional[str]:
    """Fetch the current Splice session token from the local gRPC.

    The `GetSession` RPC returns an `Auth` object with a `Token` field —
    this is the bearer we attach to `api.splice.com` requests. The token
    rotates periodically so we always fetch fresh rather than caching.
    """
    if not grpc_client or not getattr(grpc_client, "connected", False):
        return None
    pb2 = getattr(grpc_client, "_pb2", None)
    if pb2 is None:
        return None
    try:
        response = await grpc_client.stub.GetSession(
            pb2.GetSessionRequest(), timeout=5.0,
        )
        return str(response.Auth.Token) if response.Auth else None
    except Exception as exc:
        logger.warning("GetSession RPC failed: %s", exc)
        return None


# ── HTTP client ───────────────────────────────────────────────────────


@dataclass
class SpliceHTTPError(Exception):
    """Structured error for HTTPS-bridge calls."""

    code: str
    message: str
    endpoint: str = ""
    status_code: int = 0

    def __str__(self) -> str:
        return f"[{self.code}] {self.message} ({self.endpoint})"

    def to_dict(self) -> dict:
        return {
            "ok": False,
            "error": self.message,
            "code": self.code,
            "endpoint": self.endpoint,
            "status_code": self.status_code,
        }


class SpliceHTTPBridge:
    """Low-level HTTPS client for Splice cloud APIs.

    Attaches the bearer token, retries on 5xx, applies a total timeout.
    Thread-safe — each request builds its own opener. Synchronous network
    calls run in an executor from the async wrappers.
    """

    def __init__(
        self,
        config: Optional[SpliceHTTPConfig] = None,
        grpc_client=None,
    ):
        self.config = config or SpliceHTTPConfig.from_env()
        self.grpc_client = grpc_client

    async def _request(
        self,
        method: str,
        path: str,
        body: Optional[dict] = None,
        query: Optional[dict] = None,
    ) -> Any:
        token = await fetch_session_token(self.grpc_client)
        if token is None:
            raise SpliceHTTPError(
                code="NO_AUTH",
                message=(
                    "Could not fetch Splice session token via GetSession RPC. "
                    "Is the Splice desktop app running and logged in?"
                ),
                endpoint=path,
            )

        url = self.config.base_url.rstrip("/") + path
        if query:
            import urllib.parse
            qs = urllib.parse.urlencode(query)
            url = f"{url}?{qs}"

        data_bytes = None
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "LivePilot/1.15 (+splice-http-bridge)",
        }
        if body is not None:
            data_bytes = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"

        loop = asyncio.get_running_loop()
        last_err = None
        for attempt in range(1 + max(0, self.config.max_retries)):
            try:
                return await loop.run_in_executor(
                    None,
                    self._perform_sync_request,
                    url, method, data_bytes, headers,
                )
            except SpliceHTTPError as exc:
                last_err = exc
                # Retry only on 5xx / network. 4xx is terminal.
                if exc.status_code and exc.status_code < 500:
                    raise
            await asyncio.sleep(min(2 ** attempt, 5))
        assert last_err is not None
        raise last_err

    def _perform_sync_request(self, url, method, data_bytes, headers):
        try:
            req = urllib.request.Request(
                url, data=data_bytes, headers=headers, method=method,
            )
            context = ssl.create_default_context()
            with urllib.request.urlopen(
                req, timeout=self.config.timeout_sec, context=context,
            ) as resp:
                raw = resp.read()
                content_type = resp.headers.get("Content-Type", "")
                if "application/json" in content_type:
                    return json.loads(raw.decode("utf-8"))
                return {"raw": raw.decode("utf-8", errors="replace")}
        except urllib.error.HTTPError as exc:
            raise SpliceHTTPError(
                code="HTTP_ERROR",
                message=f"HTTP {exc.code}: {exc.reason}",
                endpoint=url,
                status_code=exc.code,
            )
        except urllib.error.URLError as exc:
            raise SpliceHTTPError(
                code="NETWORK_ERROR",
                message=f"Network error: {exc.reason}",
                endpoint=url,
                status_code=0,
            )
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise SpliceHTTPError(
                code="DECODE_ERROR",
                message=f"Response decode failed: {exc}",
                endpoint=url,
            )

    # ── Tool-facing helpers ──────────────────────────────────────────

    async def describe_sound(
        self,
        description: str,
        bpm: Optional[int] = None,
        key: Optional[str] = None,
        limit: int = 20,
    ) -> dict:
        """Natural-language sample search.

        Returns a dict with keys: `samples` (list of sample metadata),
        `total_hits`, plus whatever Splice echoes back. Shape is best-effort
        until we capture real traffic — see module docstring.
        """
        if not self.config.is_user_configured:
            raise SpliceHTTPError(
                code="ENDPOINT_NOT_CONFIGURED",
                message=(
                    "Describe a Sound endpoint is unverified. Set "
                    "SPLICE_DESCRIBE_ENDPOINT (or SPLICE_ALLOW_UNVERIFIED_"
                    "ENDPOINTS=1) once you've captured the real URL via "
                    "mitmproxy against the Sounds Plugin."
                ),
                endpoint=self.config.describe_endpoint,
            )
        body = {
            "description": description,
            "limit": int(limit),
        }
        if bpm is not None:
            body["bpm"] = int(bpm)
        if key:
            body["key"] = key
        return await self._request("POST", self.config.describe_endpoint, body=body)

    async def generate_variation(
        self,
        file_hash: str,
        target_key: Optional[str] = None,
        target_bpm: Optional[int] = None,
        count: int = 1,
    ) -> dict:
        """Generate AI variations of a sample.

        Returns a dict with keys: `variations` (list), `credits_spent`.
        Shape is best-effort until captured — see module docstring.
        """
        if not self.config.is_user_configured:
            raise SpliceHTTPError(
                code="ENDPOINT_NOT_CONFIGURED",
                message=(
                    "Variations endpoint is unverified. Set "
                    "SPLICE_VARIATION_ENDPOINT (or SPLICE_ALLOW_UNVERIFIED_"
                    "ENDPOINTS=1) once you've captured the real URL via "
                    "mitmproxy against the Sounds Plugin."
                ),
                endpoint=self.config.variation_endpoint,
            )
        path = self.config.variation_endpoint.format(file_hash=file_hash)
        body: dict = {"count": max(1, int(count))}
        if target_key:
            body["target_key"] = target_key
        if target_bpm is not None:
            body["target_bpm"] = int(target_bpm)
        return await self._request("POST", path, body=body)

    async def search_with_sound(
        self,
        audio_path: str,
        limit: int = 20,
    ) -> dict:
        """Sample-reference search — find catalog samples similar to a file.

        Encodes the file as a multipart POST. Wiring waits on a real
        endpoint capture; the upload shape is the most uncertain part
        of the bridge.
        """
        if not self.config.is_user_configured:
            raise SpliceHTTPError(
                code="ENDPOINT_NOT_CONFIGURED",
                message=(
                    "Search with Sound endpoint is unverified. Set "
                    "SPLICE_SEARCH_WITH_SOUND_ENDPOINT (or SPLICE_ALLOW_"
                    "UNVERIFIED_ENDPOINTS=1) once you've captured the real "
                    "URL via mitmproxy against the Sounds Plugin."
                ),
                endpoint=self.config.search_with_sound_endpoint,
            )
        # Multipart upload — reserved for the real-capture wiring.
        raise SpliceHTTPError(
            code="NOT_YET_IMPLEMENTED",
            message=(
                "search_with_sound multipart upload wiring is pending real-"
                "endpoint capture. File a follow-up when the Describe a "
                "Sound endpoint has been mapped — similar shape is likely."
            ),
            endpoint=self.config.search_with_sound_endpoint,
        )
