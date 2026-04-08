"""Sound Design Engine MCP tools — 4 tools for timbral analysis and planning.

Each tool fetches data from Ableton via the shared connection,
then delegates to pure-computation modules.
"""

from __future__ import annotations

from mcp.server.fastmcp import Context

from ..server import mcp
from .models import (
    LayerStrategy,
    PatchBlock,
    PatchModel,
    SoundDesignState,
    TimbralGoalVector,
    VALID_BLOCK_TYPES,
)
from .critics import run_all_sound_design_critics
from .planner import plan_sound_design_moves


# ── Helpers ──────────────────────────────────────────────────────────


# Native Ableton devices whose internal blocks are known
_NATIVE_BLOCK_MAP: dict[str, list[tuple[str, str]]] = {
    # (block_type, label)
    "Wavetable": [
        ("oscillator", "Wavetable"),
        ("filter", "Wavetable"),
        ("envelope", "Wavetable"),
        ("lfo", "Wavetable"),
    ],
    "Operator": [
        ("oscillator", "Operator"),
        ("filter", "Operator"),
        ("envelope", "Operator"),
        ("lfo", "Operator"),
    ],
    "Analog": [
        ("oscillator", "Analog"),
        ("filter", "Analog"),
        ("envelope", "Analog"),
        ("lfo", "Analog"),
    ],
    "Drift": [
        ("oscillator", "Drift"),
        ("filter", "Drift"),
        ("envelope", "Drift"),
        ("lfo", "Drift"),
    ],
    "Simpler": [
        ("oscillator", "Simpler"),
        ("filter", "Simpler"),
        ("envelope", "Simpler"),
        ("lfo", "Simpler"),
    ],
    "Sampler": [
        ("oscillator", "Sampler"),
        ("filter", "Sampler"),
        ("envelope", "Sampler"),
        ("lfo", "Sampler"),
    ],
    "Collision": [
        ("oscillator", "Collision"),
        ("filter", "Collision"),
        ("envelope", "Collision"),
        ("lfo", "Collision"),
    ],
    "Tension": [
        ("oscillator", "Tension"),
        ("filter", "Tension"),
        ("envelope", "Tension"),
    ],
    "Electric": [
        ("oscillator", "Electric"),
        ("effect", "Electric"),
    ],
    "Saturator": [("saturation", "Saturator")],
    "Overdrive": [("saturation", "Overdrive")],
    "Pedal": [("saturation", "Pedal")],
    "Auto Filter": [("filter", "Auto Filter"), ("lfo", "Auto Filter")],
    "EQ Eight": [("filter", "EQ Eight")],
    "EQ Three": [("filter", "EQ Three")],
    "Chorus-Ensemble": [("spatial", "Chorus-Ensemble"), ("lfo", "Chorus-Ensemble")],
    "Chorus": [("spatial", "Chorus"), ("lfo", "Chorus")],
    "Phaser-Flanger": [("spatial", "Phaser-Flanger"), ("lfo", "Phaser-Flanger")],
    "Phaser": [("spatial", "Phaser"), ("lfo", "Phaser")],
    "Flanger": [("spatial", "Flanger"), ("lfo", "Flanger")],
    "Reverb": [("spatial", "Reverb")],
    "Delay": [("spatial", "Delay")],
    "Echo": [("spatial", "Echo"), ("lfo", "Echo")],
    "Corpus": [("effect", "Corpus")],
    "Erosion": [("effect", "Erosion")],
    "Frequency Shifter": [("effect", "Frequency Shifter")],
    "Redux": [("effect", "Redux")],
    "Grain Delay": [("spatial", "Grain Delay")],
    "Spectral Resonator": [("effect", "Spectral Resonator")],
    "Spectral Time": [("effect", "Spectral Time")],
    "Hybrid Reverb": [("spatial", "Hybrid Reverb")],
}


def _build_patch_model(track_index: int, track_info: dict, devices: list[dict]) -> PatchModel:
    """Build a PatchModel from track info and device list."""
    device_chain = [d.get("name", "Unknown") for d in devices]
    blocks: list[PatchBlock] = []
    opaque: list[str] = []

    for d in devices:
        name = d.get("name", "Unknown")
        if name in _NATIVE_BLOCK_MAP:
            for block_type, label in _NATIVE_BLOCK_MAP[name]:
                blocks.append(PatchBlock(
                    block_type=block_type,
                    device_name=label,
                    controllable=True,
                ))
        else:
            # Opaque third-party or unknown device
            opaque.append(name)
            blocks.append(PatchBlock(
                block_type="effect",
                device_name=name,
                controllable=False,
            ))

    # Infer roles from track name
    roles: list[str] = []
    track_name = track_info.get("name", "").lower()
    role_keywords = {
        "bass": "bass",
        "sub": "sub_anchor",
        "kick": "transient_layer",
        "drum": "transient_layer",
        "perc": "transient_layer",
        "pad": "texture_layer",
        "texture": "texture_layer",
        "lead": "lead",
        "vocal": "lead",
        "keys": "body_layer",
        "piano": "body_layer",
        "synth": "body_layer",
        "wide": "width_layer",
        "stereo": "width_layer",
    }
    for keyword, role in role_keywords.items():
        if keyword in track_name and role not in roles:
            roles.append(role)
    if not roles:
        roles.append("unknown")

    return PatchModel(
        track_index=track_index,
        device_chain=device_chain,
        roles=roles,
        blocks=blocks,
        opaque_blocks=opaque,
    )


def _build_layer_strategy(track_index: int, patch: PatchModel) -> LayerStrategy:
    """Build a basic LayerStrategy from the patch's inferred roles."""
    layers = LayerStrategy()
    for role in patch.roles:
        if role == "sub_anchor" and layers.sub_anchor is None:
            layers.sub_anchor = track_index
        elif role == "body_layer" and layers.body_layer is None:
            layers.body_layer = track_index
        elif role == "transient_layer" and layers.transient_layer is None:
            layers.transient_layer = track_index
        elif role == "texture_layer" and layers.texture_layer is None:
            layers.texture_layer = track_index
        elif role == "width_layer" and layers.width_layer is None:
            layers.width_layer = track_index
    return layers


def _fetch_sound_design_data(ctx: Context, track_index: int) -> dict:
    """Fetch data needed to build a SoundDesignState from Ableton."""
    ableton = ctx.lifespan_context["ableton"]

    track_info = ableton.send_command(
        "get_track_info", {"track_index": track_index}
    )

    # Get devices from track_info response (already included by Remote Script)
    devices: list[dict] = track_info.get("devices", [])

    return {
        "track_info": track_info,
        "devices": devices,
    }


# ── MCP Tools ────────────────────────────────────────────────────────


@mcp.tool()
def analyze_sound_design(ctx: Context, track_index: int) -> dict:
    """Build full sound design state and run all critics for a track.

    Returns the complete timbral analysis including patch model,
    layer strategy, all detected issues, and suggested moves.

    Args:
        track_index: Index of the track to analyze.
    """
    data = _fetch_sound_design_data(ctx, track_index)
    patch = _build_patch_model(track_index, data["track_info"], data["devices"])
    layers = _build_layer_strategy(track_index, patch)
    state = SoundDesignState(
        goal=TimbralGoalVector(),
        patch=patch,
        layers=layers,
    )
    issues = run_all_sound_design_critics(state)
    moves = plan_sound_design_moves(issues, state)

    return {
        "state": state.to_dict(),
        "issues": [i.to_dict() for i in issues],
        "suggested_moves": [m.to_dict() for m in moves],
        "issue_count": len(issues),
        "move_count": len(moves),
    }


@mcp.tool()
def get_sound_design_issues(ctx: Context, track_index: int) -> dict:
    """Run all sound design critics and return detected issues only.

    Lighter than analyze_sound_design — skips move planning.

    Args:
        track_index: Index of the track to analyze.
    """
    data = _fetch_sound_design_data(ctx, track_index)
    patch = _build_patch_model(track_index, data["track_info"], data["devices"])
    layers = _build_layer_strategy(track_index, patch)
    state = SoundDesignState(
        goal=TimbralGoalVector(),
        patch=patch,
        layers=layers,
    )
    issues = run_all_sound_design_critics(state)

    return {
        "issues": [i.to_dict() for i in issues],
        "issue_count": len(issues),
    }


@mcp.tool()
def plan_sound_design_move(ctx: Context, track_index: int) -> dict:
    """Get ranked move suggestions based on current sound design issues.

    Runs critics and planner, returns sorted moves with
    estimated impact and risk scores.

    Args:
        track_index: Index of the track to analyze.
    """
    data = _fetch_sound_design_data(ctx, track_index)
    patch = _build_patch_model(track_index, data["track_info"], data["devices"])
    layers = _build_layer_strategy(track_index, patch)
    state = SoundDesignState(
        goal=TimbralGoalVector(),
        patch=patch,
        layers=layers,
    )
    issues = run_all_sound_design_critics(state)
    moves = plan_sound_design_moves(issues, state)

    return {
        "moves": [m.to_dict() for m in moves],
        "move_count": len(moves),
        "issue_count": len(issues),
    }


@mcp.tool()
def get_patch_model(ctx: Context, track_index: int) -> dict:
    """Get the structural patch model for a track's device chain.

    Returns device chain, functional blocks, controllable vs opaque
    blocks, and inferred musical roles.

    Args:
        track_index: Index of the track to inspect.
    """
    data = _fetch_sound_design_data(ctx, track_index)
    patch = _build_patch_model(track_index, data["track_info"], data["devices"])

    return patch.to_dict()
