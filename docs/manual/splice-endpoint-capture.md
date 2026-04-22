# Capturing Splice HTTPS Endpoints for the Sounds Plugin Bridge

LivePilot ships an HTTPS bridge for the Splice Sounds Plugin's
*Describe a Sound* and *Variations* features. These live on
`api.splice.com` over HTTPS, not on the local gRPC we wrap for sample
search/download. The bridge is ready, but the exact endpoint URLs have
to be observed once against the running plugin — this guide walks
through doing that with mitmproxy.

**Time required**: ~20-30 minutes, one-time per Splice API version.

## Why this is needed

Splice's local gRPC exposes ~40 RPCs for sample/collection/preset CRUD,
but the plugin-exclusive AI features (Describe a Sound, Variations,
Search with Sound) bypass gRPC entirely and call the cloud API with the
session token. The token rotates, so we fetch it fresh from
`GetSession` on each call — but the endpoint shapes themselves need
capture because Splice doesn't publish them.

## Prerequisites

- macOS 12+ or Windows 10 22H2+ (Splice's supported platforms)
- The Splice Sounds Plugin (beta) installed inside a DAW
- Homebrew (macOS) or pip (cross-platform)
- ~30 minutes

## Setup: install and trust mitmproxy

```bash
# macOS via Homebrew
brew install mitmproxy

# OR cross-platform via pip
pip install mitmproxy
```

Start the proxy once to generate a cert:

```bash
mitmweb --listen-port 8080
```

Visit `http://mitm.it` in a browser, download the CA cert, install it,
and mark it as trusted in Keychain (macOS) / cert store (Windows).

Now route the Splice Sounds Plugin's traffic through the proxy. On
macOS:

```bash
# System Settings → Network → Wi-Fi → Details → Proxies →
# Secure Web Proxy (HTTPS): 127.0.0.1 port 8080
# OR via CLI:
networksetup -setsecurewebproxy Wi-Fi 127.0.0.1 8080
```

## Capture: Describe a Sound

1. Open mitmweb (web UI at http://127.0.0.1:8081).
2. Launch your DAW, insert the Splice Sounds Plugin on any track.
3. In the plugin's search bar, type something like *"dark ambient pad
   with shimmer"* and press Enter.
4. Filter mitmproxy's flow list to `api.splice.com`.
5. Look for a POST (or GET) that fires on submit. Note:
   - The full URL (including any path version prefix like `/v2/` or
     `/ai/describe`)
   - The request method
   - The request body shape (JSON keys)
   - The response body shape

Example of what you might observe:

```
POST https://api.splice.com/v2/sounds/search/describe
Authorization: Bearer eyJhbGciOi...
Content-Type: application/json

{
  "description": "dark ambient pad with shimmer",
  "limit": 20,
  "bpm": 124,
  "key": "Am"
}
```

Record these values.

## Capture: Variations

1. In the Splice Sounds Plugin, find a sample and click the Variations
   button (on hover or in the detail view).
2. Watch mitmweb for the new flow — usually a POST to an endpoint
   containing `variations` or `generate`.
3. Note the URL template (it may include the `file_hash` as a path
   parameter: `/v2/samples/{file_hash}/variations`).
4. Record the request body shape — typically includes target_key,
   target_bpm, count.

## Apply the captured endpoints

Two options — pick one.

### Option A: JSON config file (recommended)

Create `~/.livepilot/splice.json`:

```json
{
  "base_url": "https://api.splice.com",
  "describe_endpoint": "/v2/sounds/search/describe",
  "variation_endpoint": "/v2/samples/{file_hash}/variations",
  "search_with_sound_endpoint": "/v2/sounds/search/by-audio",
  "timeout_sec": 30
}
```

LivePilot reads this on MCP server startup — restart the server after
editing.

### Option B: Environment variables (ephemeral)

```bash
export SPLICE_API_BASE_URL="https://api.splice.com"
export SPLICE_DESCRIBE_ENDPOINT="/v2/sounds/search/describe"
export SPLICE_VARIATION_ENDPOINT="/v2/samples/{file_hash}/variations"
# Then restart the MCP server so it picks up the env.
```

## Verify

Once configured, test from an MCP client:

```
splice_describe_sound("warm analog bass under 80bpm", limit=5)
```

If the endpoint is correct, you get back `samples` with metadata. If
not, you see an HTTP_ERROR with the status code — which tells you
whether the URL was wrong (404) or the body shape was off (400).

## Clean up

Don't leave the proxy on:

```bash
# macOS
networksetup -setsecurewebproxystate Wi-Fi off
```

And close mitmweb.

## Troubleshooting

- **401 Unauthorized** — the session token expired or isn't getting
  attached. The bridge fetches fresh from gRPC each call; verify
  `get_splice_credits` returns `connected: true`.
- **404 Not Found** — the URL is wrong. Try variants with/without
  version prefixes.
- **400 Bad Request** — the body shape is off. mitmproxy shows the
  error response body; look for hints there.
- **No traffic visible** — the plugin might be using certificate
  pinning. If so, mitmproxy can't intercept without bypassing the pin,
  which is more involved. File an issue rather than monkey-patching.

## Ethics note

This is LivePilot talking to your own Splice account, with your token,
from your machine. It's not scraping; it's using the same APIs the
Sounds Plugin uses. Splice can change these endpoints at any time —
when they do, re-run this capture.

## Related

- Bridge implementation: [`mcp_server/splice_client/http_bridge.py`](../../mcp_server/splice_client/http_bridge.py)
- MCP tools: `splice_describe_sound`, `splice_generate_variation`,
  `splice_search_with_sound` in
  [`mcp_server/sample_engine/tools.py`](../../mcp_server/sample_engine/tools.py)
- Splice's FAQ on Variations:
  https://support.splice.com/en/articles/12997523-how-to-use-variations-in-the-splice-sounds-plugin-now-in-beta
