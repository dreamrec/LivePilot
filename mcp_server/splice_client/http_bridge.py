"""HTTPS bridge for Splice plugin-exclusive features.

The Splice desktop app and its plugin ship capabilities that are NOT on
the local gRPC service. They route through a single GraphQL endpoint:

  - **Describe a Sound / keyword search** — GraphQL operation
    `SamplesSearch` with `semantic` + `rephrase` flags. One operation
    serves both modes via variable toggles.
  - **Variations** — GraphQL operation `AssetSimilarSoundsQuery`. A
    recommender lookup ("find similar catalog samples"), not AI audio
    synthesis.

Both authenticated with the bearer JWT we can read from the local gRPC
`GetSession` RPC. Both captured 2026-04-22 via mitmproxy against
Splice desktop v5.4.9 + Ableton 12.4 on macOS.

## Endpoint config

  - Base URL: `https://surfaces-graphql.splice.com`
  - Path: `/graphql`
  - Auth: `Authorization: Bearer <JWT>` (via gRPC GetSession)
  - Content-type: `application/json`
  - Body: `{operationName, variables, query}`
  - User-Agent: LivePilot default (override via env var if Cloudflare
    blocks — mimic `Splice Baelish/darwin/arm64/arm64 5.4.9/...`)

## GraphQL query location

The full query strings live under `graphql_queries/*.graphql` and are
loaded lazily at module-import. One file per operation.

## Explicitly NOT wired

Search-with-Sound (drag-audio reference search) was removed 2026-04-22
— user handles this directly in Splice's UI. The capture recipe is
preserved at `docs/2026-04-22-splice-https-capture-recipe.md` for any
future session that wants to resurrect the tool.
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
        "base_url": "https://surfaces-graphql.splice.com",
        "describe_endpoint": "/graphql",
        "variation_endpoint": "/graphql",
        "timeout_sec": 30.0,
        "max_retries": 2,
        "allow_unverified_endpoints": false
      }

    Any subset of keys is allowed; omitted keys fall through to defaults.
    """

    # Captured from Splice desktop v5.4.9 via mitmproxy on 2026-04-22.
    base_url: str = "https://surfaces-graphql.splice.com"
    describe_endpoint: str = "/graphql"  # GraphQL SamplesSearch operation
    variation_endpoint: str = "/graphql"  # GraphQL AssetSimilarSoundsQuery
    # Mimic the desktop client UA when Cloudflare complains.
    user_agent: str = "LivePilot/1.16 (+splice-http-bridge)"
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

        Historically this was the gate for all describe/variation tools
        because defaults were unverified. As of 2026-04-22 the describe
        endpoint is verified (GraphQL `surfaces-graphql.splice.com`), so
        `describe_sound` no longer gates on this. Variation and
        search-with-sound still do, because their GraphQL operations
        haven't been captured yet.
        """
        return self._user_configured

    @property
    def describe_verified(self) -> bool:
        """True when the describe endpoint is at its known-working value
        OR the user has explicitly overridden it."""
        return (
            self.base_url == "https://surfaces-graphql.splice.com"
            and self.describe_endpoint == "/graphql"
        ) or self._user_configured

    @property
    def variation_verified(self) -> bool:
        """True when the variation endpoint is at its known-working
        value (the captured AssetSimilarSoundsQuery path) OR the user
        has explicitly overridden it. Captured 2026-04-22."""
        return (
            self.base_url == "https://surfaces-graphql.splice.com"
            and self.variation_endpoint == "/graphql"
        ) or self._user_configured


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


# ── GraphQL query loading ────────────────────────────────────────────


_QUERY_DIR = os.path.join(os.path.dirname(__file__), "graphql_queries")
_QUERY_CACHE: dict[str, str] = {}


def _load_graphql_query(name: str) -> str:
    """Load a `.graphql` file from `graphql_queries/` lazily (cached).

    Separating the 5800-char SamplesSearch query into its own file keeps
    the Python source readable and lets GraphQL-aware tools (IDE syntax
    highlighting, schema-based linters) treat it as a first-class query.

    Raises FileNotFoundError with a clear message if the query hasn't
    been captured yet.
    """
    if name in _QUERY_CACHE:
        return _QUERY_CACHE[name]

    path = os.path.join(_QUERY_DIR, f"{name}.graphql")
    if not os.path.isfile(path):
        raise FileNotFoundError(
            f"GraphQL query '{name}' not found at {path}. "
            f"Capture it via mitmproxy against the Splice desktop app "
            f"(see docs/2026-04-22-splice-https-capture-recipe.md) and "
            f"save the captured `query` string to the .graphql file."
        )

    with open(path, "r", encoding="utf-8") as f:
        query = f.read()
    _QUERY_CACHE[name] = query
    return query


def _flatten_sample_item(it: dict) -> dict:
    """Turn a single Splice GraphQL SampleAsset item into the flat shape
    LivePilot's tools surface. Shared between SamplesSearch.items[] and
    similarSounds[] — both queries return identically-shaped items.
    """
    if not isinstance(it, dict):
        return {}
    tag_labels = [
        t.get("label", "") for t in (it.get("tags") or [])
        if isinstance(t, dict)
    ]
    # Pack info (items have optional `parents` or can be PackAsset-shaped)
    pack_name = None
    parents = it.get("parents") or {}
    if isinstance(parents, dict):
        pitems = parents.get("items") or []
        if pitems and isinstance(pitems[0], dict):
            pack_name = pitems[0].get("name")
    return {
        "uuid": it.get("uuid"),
        "name": it.get("name"),
        "bpm": it.get("bpm"),
        "key": it.get("key"),
        "duration": it.get("duration"),
        "instrument": it.get("instrument"),
        "asset_category": it.get("asset_category_slug"),
        "chord_type": it.get("chord_type"),
        "tags": tag_labels,
        "liked": bool(it.get("liked")),
        "licensed": bool(it.get("licensed")),
        "pack_name": pack_name,
        "files": it.get("files") or [],
    }


def _check_graphql_errors(raw) -> None:
    """Raise SpliceHTTPError if the GraphQL response has top-level errors.

    Splice returns errors as a top-level `errors: [...]` array alongside
    or instead of `data:`. A 200 response can still carry a logical
    error, so every parser must check.
    """
    if not isinstance(raw, dict):
        return
    if raw.get("errors"):
        errs = raw["errors"]
        first = errs[0] if isinstance(errs, list) and errs else errs
        msg = (first.get("message") if isinstance(first, dict) else str(first))
        raise SpliceHTTPError(
            code="GRAPHQL_ERROR",
            message=f"Splice GraphQL error: {msg}",
            endpoint="/graphql",
        )


def _parse_samples_search(raw: dict) -> dict:
    """Normalize the SamplesSearch GraphQL response into a flat shape.

    GraphQL shape: { data: { assetsSearch: { items: [...],
                    tag_summary: [...], rephrased_query_string, ... } } }
    Flat shape:    { samples: [...], total_hits, rephrased_query_string,
                     tag_summary, raw }
    """
    if not isinstance(raw, dict):
        return {"samples": [], "total_hits": 0, "raw": raw}
    _check_graphql_errors(raw)

    data = raw.get("data") or {}
    page = data.get("assetsSearch") or {}
    items = page.get("items") or []

    samples = [_flatten_sample_item(it) for it in items if isinstance(it, dict)]

    pm = page.get("pagination_metadata") or {}
    rm = page.get("response_metadata") or {}
    return {
        "samples": samples,
        "total_hits": rm.get("records") or len(samples),
        "total_pages": pm.get("totalPages"),
        "current_page": pm.get("currentPage"),
        "rephrased_query_string": page.get("rephrased_query_string"),
        "tag_summary": [
            {"label": (ts.get("tag") or {}).get("label"),
             "count": ts.get("count")}
            for ts in (page.get("tag_summary") or [])
            if isinstance(ts, dict)
        ],
        "raw": page,
    }


def _parse_similar_sounds(raw: dict) -> dict:
    """Normalize the AssetSimilarSoundsQuery GraphQL response.

    GraphQL shape: { data: { similarSounds: [SampleAsset, ...] } }
    Flat shape:    { similar_samples: [...], count }

    Note: Splice calls this the "Variations" feature in the UI, but the
    underlying semantics are "find catalog samples similar to this one" —
    not "generate new audio variants". No target-key / target-BPM inputs
    are supported; the API returns whatever the recommender picks.
    """
    if not isinstance(raw, dict):
        return {"similar_samples": [], "count": 0, "raw": raw}
    _check_graphql_errors(raw)

    data = raw.get("data") or {}
    sims = data.get("similarSounds") or []
    if not isinstance(sims, list):
        return {"similar_samples": [], "count": 0, "raw": sims}

    samples = [_flatten_sample_item(it) for it in sims if isinstance(it, dict)]
    return {
        "similar_samples": samples,
        "count": len(samples),
        "raw": sims,
    }


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
            "User-Agent": self.config.user_agent,
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
        rephrase: bool = True,
    ) -> dict:
        """Natural-language sample search via the GraphQL SamplesSearch
        operation (captured 2026-04-22).

        Splice's `SamplesSearch` operation serves both keyword AND
        semantic/describe search from a single endpoint. We set
        `semantic=1` + `rephrase=True` for describe-style queries.
        The server echoes `rephrased_query_string` in the response
        which tells us what the describe engine actually searched for.

        Returns a dict with keys:
          - `samples`: list of clean sample-metadata dicts (uuid, name,
            bpm, key, tags, duration, …)
          - `total_hits`: response record count (from pagination metadata)
          - `rephrased_query_string`: what Splice rephrased the query to
          - `tag_summary`: list of {label, count} for faceted filtering
          - `raw`: the full GraphQL `data` block for debugging

        Raises SpliceHTTPError on auth failure, network issues, or
        GraphQL-level errors.
        """
        if not self.config.describe_verified:
            raise SpliceHTTPError(
                code="ENDPOINT_NOT_CONFIGURED",
                message=(
                    "Describe endpoint points at an unverified URL. "
                    "Reset to defaults, or set SPLICE_API_BASE_URL + "
                    "SPLICE_DESCRIBE_ENDPOINT to match real Splice "
                    "graphql surface (see http_bridge.py docstring)."
                ),
                endpoint=f"{self.config.base_url}{self.config.describe_endpoint}",
            )

        query = _load_graphql_query("samples_search")
        variables: dict = {
            "query": str(description),
            "limit": int(limit),
            "order": "DESC",
            "sort": "relevance",
            "semantic": 1,
            "rephrase": bool(rephrase),
            "extract_filters": False,
            "includeSubscriberOnlyResults": False,
            "tags": [],
            "tags_exclude": [],
            "attributes": [],
            "bundled_content_daws": [],
            "legacy": True,
        }
        if bpm is not None:
            variables["bpm"] = str(int(bpm))
        if key:
            variables["key"] = str(key)

        body = {
            "operationName": "SamplesSearch",
            "variables": variables,
            "query": query,
        }

        raw = await self._request("POST", self.config.describe_endpoint, body=body)
        return _parse_samples_search(raw)

    async def generate_variation(
        self,
        uuid: str,
        is_legacy: bool = True,
    ) -> dict:
        """Find catalog samples similar to a given sample ("Variations").

        Captured 2026-04-22: Splice's "Variations" right-click menu item
        fires the GraphQL `AssetSimilarSoundsQuery` with just `uuid` +
        `isLegacy`. Returns up to 10 similar samples. The name
        "generate_variation" is a slight misnomer — this is a
        recommender lookup, not AI-synthesis of new audio — but it
        matches Splice's user-facing "Variations" label.

        uuid:      the source sample's catalog uuid (as returned by
                   `splice_describe_sound` or gRPC `SearchSamples`)
        is_legacy: match how Splice's own client sets it (true for
                   pre-catalog-v2 samples; leave as default)

        Returns `{similar_samples: [...], count}` — each sample has the
        same flat shape as `splice_describe_sound` items.
        """
        if not self.config.variation_verified:
            raise SpliceHTTPError(
                code="ENDPOINT_NOT_CONFIGURED",
                message=(
                    "Variation endpoint points at an unverified URL. "
                    "Reset config to defaults so the captured "
                    "surfaces-graphql.splice.com/graphql endpoint is used."
                ),
                endpoint=f"{self.config.base_url}{self.config.variation_endpoint}",
            )
        if not uuid or not isinstance(uuid, str):
            raise SpliceHTTPError(
                code="INVALID_UUID",
                message="uuid must be a non-empty string",
                endpoint=self.config.variation_endpoint,
            )
        query = _load_graphql_query("asset_similar_sounds")
        body = {
            "operationName": "AssetSimilarSoundsQuery",
            "variables": {
                "uuid": uuid,
                "isLegacy": bool(is_legacy),
            },
            "query": query,
        }
        raw = await self._request("POST", self.config.variation_endpoint, body=body)
        return _parse_similar_sounds(raw)

    # NOTE: `search_with_sound` method removed 2026-04-22. User does
    # audio-reference search in-Splice manually. Capture recipe is at
    # docs/2026-04-22-splice-https-capture-recipe.md if anyone wants to
    # resurrect it.
