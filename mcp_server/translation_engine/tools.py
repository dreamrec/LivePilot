"""Translation Engine MCP tools — 2 tools for playback robustness.

Each tool fetches data from Ableton via the shared connection,
then delegates to pure-computation critics.
"""

from __future__ import annotations

from mcp.server.fastmcp import Context

from ..server import mcp
from .critics import build_translation_report, run_all_translation_critics


# ── Helpers ─────────────────────────────────────────────────────────


def _fetch_translation_data(ctx: Context) -> dict:
    """Fetch mix snapshot data needed for translation analysis.

    Builds snapshot from real available data:
    - Spectrum from SpectralCache (direct access, not TCP)
    - Stereo width estimated from track pan values
    - Foreground detection from role inference
    """
    ableton = ctx.lifespan_context["ableton"]

    # Get spectral data directly from SpectralCache
    spectrum_bands = {}
    try:
        spectral = ctx.lifespan_context.get("spectral")
        if spectral and spectral.is_connected:
            spec_data = spectral.get("spectrum")
            if spec_data and isinstance(spec_data["value"], dict):
                spectrum_bands = spec_data["value"]
    except Exception:
        pass

    # Estimate stereo width from track pans via session info
    stereo_width = 0.0
    center_strength = 0.5
    has_foreground = True
    foreground_masked = False
    try:
        session_info = ableton.send_command("get_session_info", {})
        tracks = session_info.get("tracks", [])
        if tracks:
            # Pan may be at top level or nested under mixer.panning
            def _get_pan(t: dict) -> float:
                mixer = t.get("mixer")
                if isinstance(mixer, dict):
                    return abs(mixer.get("panning", 0.0))
                return abs(t.get("pan", 0.0))
            pan_values = [_get_pan(t) for t in tracks if not t.get("muted", False)]
            if pan_values:
                # Wider pans = more stereo width
                stereo_width = min(1.0, sum(pan_values) / max(len(pan_values), 1))
                # Center strength = proportion of tracks near center
                center_count = sum(1 for p in pan_values if p < 0.15)
                center_strength = center_count / max(len(pan_values), 1)

            # Simple foreground detection: at least one unmuted, non-quiet track
            has_foreground = any(not t.get("muted", False) for t in tracks)
    except Exception:
        pass

    return {
        "stereo_width": stereo_width,
        "center_strength": center_strength,
        "sub_energy": spectrum_bands.get("sub", 0.0),
        "low_energy": spectrum_bands.get("low", 0.0),
        "low_mid_energy": spectrum_bands.get("low_mid", 0.0),
        "high_energy": spectrum_bands.get("high", 0.0),
        "presence_energy": spectrum_bands.get("presence", 0.0),
        "has_foreground": has_foreground,
        "foreground_masked": foreground_masked,
    }


# ── MCP Tools ───────────────────────────────────────────────────────


@mcp.tool()
def check_translation(ctx: Context) -> dict:
    """Check playback robustness — mono safety, small speakers, harshness.

    Returns a full translation report with robustness classification
    (robust/fragile/critical), boolean safety flags, and suggested
    corrective moves.
    """
    mix_snapshot = _fetch_translation_data(ctx)
    report = build_translation_report(mix_snapshot)
    return report.to_dict()


@mcp.tool()
def get_translation_issues(ctx: Context) -> dict:
    """Get just the translation issues without the full report.

    Lighter than check_translation — returns only detected issues
    from the 5 playback robustness critics.
    """
    mix_snapshot = _fetch_translation_data(ctx)
    issues = run_all_translation_critics(mix_snapshot)
    return {
        "issues": [i.to_dict() for i in issues],
        "issue_count": len(issues),
    }
