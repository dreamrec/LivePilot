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


_DEFAULT_CONFIG_PATH = os.path.expanduser("~/.livepilot/splice.json")


@dataclass
class SpliceHTTPConfig:
    """Endpoint configuration for the HTTPS bridge.

    Three sources, checked in order of precedence:
      1. Env vars (highest — useful for one-off tests / CI)
      2. JSON config file at `~/.livepilot/splice.json` (persistent user config)
      3. Built-in defaults (unverified guesses — WILL need updating when
         we capture real traffic)

    JSON config shape:
      {
        "base_url": "https://api.splice.com",
        "describe_endpoint": "/v1/...",
        "variation_endpoint": "/v1/variations/{file_hash}",
        "search_with_sound_endpoint": "/v1/...",
        "timeout_sec": 30.0,
        "max_retries": 2,
        "allow_unverified_endpoints": false
      }

    Any subset of keys is allowed; omitted keys fall through to defaults.
    """

    base_url: str = "https://api.splice.com"
    describe_endpoint: str = "/v1/describe"
    variation_endpoint: str = "/v1/variations/{file_hash}"
    search_with_sound_endpoint: str = "/v1/search-with-sound"
    timeout_sec: float = 30.0
    max_retries: int = 2
    # Whether any of the above values came from user config (file or env)
    # rather than the built-in defaults. Used by `is_user_configured`.
    _user_configured: bool = False

    @classmethod
    def from_env(cls, config_path: Optional[str] = None) -> "SpliceHTTPConfig":
        """Load config: defaults → JSON file → env vars.

        `config_path` override is test-only. Production always uses
        ~/.livepilot/splice.json (or skips the file silently if absent).
        """
        instance = cls()
        loaded_from_file = False

        # Layer 1: JSON file (persistent user config)
        path = config_path or _DEFAULT_CONFIG_PATH
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    for key in (
                        "base_url", "describe_endpoint", "variation_endpoint",
                        "search_with_sound_endpoint",
                    ):
                        if key in data and isinstance(data[key], str):
                            setattr(instance, key, data[key])
                            loaded_from_file = True
                    for key in ("timeout_sec",):
                        if key in data:
                            try:
                                setattr(instance, key, float(data[key]))
                                loaded_from_file = True
                            except (TypeError, ValueError):
                                logger.warning(
                                    "splice.json: %s must be a number", key,
                                )
                    for key in ("max_retries",):
                        if key in data:
                            try:
                                setattr(instance, key, int(data[key]))
                                loaded_from_file = True
                            except (TypeError, ValueError):
                                logger.warning(
                                    "splice.json: %s must be an integer", key,
                                )
                    if data.get("allow_unverified_endpoints"):
                        loaded_from_file = True
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning(
                    "Could not load %s: %s — falling back to defaults/env",
                    path, exc,
                )

        # Layer 2: env vars (override file/defaults)
        env_keys = (
            ("SPLICE_API_BASE_URL", "base_url", str),
            ("SPLICE_DESCRIBE_ENDPOINT", "describe_endpoint", str),
            ("SPLICE_VARIATION_ENDPOINT", "variation_endpoint", str),
            ("SPLICE_SEARCH_WITH_SOUND_ENDPOINT", "search_with_sound_endpoint", str),
            ("SPLICE_HTTP_TIMEOUT", "timeout_sec", float),
            ("SPLICE_HTTP_RETRIES", "max_retries", int),
        )
        env_configured = False
        for env_name, attr, cast in env_keys:
            if env_name in os.environ:
                try:
                    setattr(instance, attr, cast(os.environ[env_name]))
                    env_configured = True
                except (TypeError, ValueError) as exc:
                    logger.warning(
                        "Env %s has invalid value: %s", env_name, exc,
                    )

        instance._user_configured = (
            loaded_from_file
            or env_configured
            or os.environ.get("SPLICE_ALLOW_UNVERIFIED_ENDPOINTS") == "1"
        )
        return instance

    @property
    def is_user_configured(self) -> bool:
        """True when at least one endpoint URL has been overridden by the
        user (JSON config file or env var).

        Defaults are unverified guesses; callers check this before making
        requests so we don't silently hit non-existent endpoints.
        """
        return self._user_configured


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
