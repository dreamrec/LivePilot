"""Pack-Atlas Phase E — Demo Story.

Synthesizes a track-by-track narrative + production-sequence inference for a
demo .als sidecar.  Turns the 104 parsed demo files into interactive learning
artifacts.  All data from local JSON sidecars — no Live connection required.

Real sidecar schema (from Phase C appendix, 2026-04-27):
  Demo sidecars  (~/.livepilot/atlas-overlays/packs/_demo_parses/<slug>.json):
    top-level: {file, name, bpm, time_signature, scale, tracks, scenes}
    scale: {root_note: str, name: str}  — root_note is a STRING, cast to int
    bpm: float
    tracks[*]: {name, type, id, device_count, devices[{class, user_name,
                                                         params, macros}], routing}
    devices[*].macros: [{index, value}]  — NO name field in demo macros
    ReturnTrack type: "ReturnTrack"
    GroupTrack type:  "GroupTrack"

Demo macro entries have no names — macro names live in preset sidecars only.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

# Re-use path constants and loading helpers from Phase C — no duplication.
from .transplant import (
    DEMO_PARSES_ROOT,
    _load_demo_sidecar,
    _resolve_demo_slug,
    _PRODUCER_ANCHORS,
    _detect_producer_anchor,
)

# ─── Track-role classifier ────────────────────────────────────────────────────

# Device classes that indicate rhythmic content
_DRUM_CLASSES = {"DrumGroupDevice", "DrumRack"}
_DRUM_NAME_RE = re.compile(r"\b(drum|kick|snare|hat|perc|beat|rhythm|kit)\b", re.IGNORECASE)

# Device classes that are clearly utility/spatial (not harmonic content)
_SPATIAL_CLASSES = {"Reverb", "Delay", "Echo", "Chorus", "Phaser", "Flanger"}
_FX_BUS_CLASSES = {"Limiter", "Compressor2", "EQ8", "EquallyLoud", "GlueCompressor"}

# GroupDevice rack classes
_INSTRUMENT_GROUP = "InstrumentGroupDevice"
_AUDIO_EFFECT_GROUP = "AudioEffectGroupDevice"
_MIDI_EFFECT_CLASSES = {"MidiRandom", "MidiArpeggiator", "MidiChord", "MidiPitcher",
                        "MidiScale", "MidiVelocity"}


def _count_nonzero_macros(devices: list[dict]) -> int:
    """Count total non-zero macro values across all devices on a track."""
    total = 0
    for dev in devices:
        for m in dev.get("macros") or []:
            try:
                if float(str(m.get("value", "0"))) != 0.0:
                    total += 1
            except (ValueError, TypeError):
                pass
    return total


def _classify_track_role(track: dict, all_tracks: list[dict]) -> str:
    """Classify a track into one of six semantic roles.

    Returns one of:
      "harmonic-foundation" — primary harmonic/melodic source (most devices,
                              instrument rack, or lead MIDI track)
      "rhythmic-driver"     — drum rack or percussion-named track
      "texture"             — additional MIDI instrument layers (no drums)
      "spatial-glue"        — return/send tracks with reverb/delay
      "fx-bus"              — group/return tracks with bus processing
      "decoration"          — audio tracks with no MIDI clips, or minimal devices
    """
    t_type = track.get("type", "")
    t_name = track.get("name", "")
    devices = track.get("devices") or []
    device_count = track.get("device_count", 0)

    # Return tracks → spatial-glue or fx-bus
    if t_type == "ReturnTrack":
        device_classes = [d.get("class", "") for d in devices]
        if any(c in _SPATIAL_CLASSES for c in device_classes):
            return "spatial-glue"
        return "fx-bus"

    # Group tracks with only audio-effect rack → fx-bus
    if t_type == "GroupTrack":
        device_classes = [d.get("class", "") for d in devices]
        if all(c in {_AUDIO_EFFECT_GROUP} | _FX_BUS_CLASSES | _SPATIAL_CLASSES
               for c in device_classes if c):
            return "fx-bus"
        return "texture"

    # Check device classes
    device_classes = [d.get("class", "") for d in devices]

    # Drum rack → rhythmic-driver
    if any(c in _DRUM_CLASSES for c in device_classes):
        return "rhythmic-driver"

    # Name-based drum detection
    if _DRUM_NAME_RE.search(t_name):
        return "rhythmic-driver"

    # Audio track with no devices → decoration
    if t_type == "AudioTrack" and device_count == 0:
        return "decoration"

    # Audio track with only effects, no instruments → decoration
    if t_type == "AudioTrack":
        has_instrument = any(
            c in (_INSTRUMENT_GROUP, "Simpler", "Sampler", "Operator",
                  "Drift", "Wavetable", "AnalogSynth", "Tension", "Electric",
                  "Collision", "Mallet", "DrumGroupDevice")
            for c in device_classes
        )
        if not has_instrument:
            return "decoration"

    # MIDI track with instrument rack — figure out harmonic vs texture
    # Strategy: among all non-return, non-drum MIDI tracks, the one with
    # the most devices (and/or the first/longest named track) is harmonic-foundation.
    midi_instrument_tracks = [
        t for t in all_tracks
        if t.get("type") in ("MidiTrack", "GroupTrack")
        and t.get("type") != "ReturnTrack"
        and not _DRUM_NAME_RE.search(t.get("name", ""))
        and any(
            d.get("class", "") not in _DRUM_CLASSES
            and d.get("class", "") not in _MIDI_EFFECT_CLASSES
            for d in (t.get("devices") or [])
        )
    ]

    if not midi_instrument_tracks:
        return "texture"

    # First numbered track (e.g. "1-Pioneer Drone") is usually harmonic spine
    # Track with highest device_count is usually harmonic foundation
    max_devices = max(
        (t.get("device_count", 0) for t in midi_instrument_tracks),
        default=0,
    )

    # Check for numbered prefix — "1-" is harmonic anchor
    numbered_first = None
    for t in midi_instrument_tracks:
        if re.match(r"^1[-\s]", t.get("name", "")):
            numbered_first = t
            break

    # This track is harmonic-foundation if:
    # - it's the numbered-first track, OR
    # - it has the most devices among non-drum MIDI tracks
    if numbered_first and track.get("name") == numbered_first.get("name"):
        return "harmonic-foundation"
    if (not numbered_first
            and track.get("device_count", 0) == max_devices
            and max_devices > 0):
        return "harmonic-foundation"

    return "texture"


# ─── Macro signature builder ──────────────────────────────────────────────────

def _extract_macro_signature(track: dict) -> str:
    """Build a human-readable macro signature for a demo track.

    Demo macros lack names (per Phase C appendix — names only exist in preset
    sidecars).  We report the structural commitment pattern:
      - device class + user_name
      - how many non-zero macros are committed
      - top 3 non-zero macro index/value pairs

    Returns a concise prose string or empty string if no devices.
    """
    devices = track.get("devices") or []
    if not devices:
        return ""

    parts = []
    for dev in devices:
        cls = dev.get("class", "")
        uname = dev.get("user_name") or ""
        label = uname or cls or "device"

        macros = dev.get("macros") or []
        nonzero = [
            m for m in macros
            if _safe_float(m.get("value", "0")) != 0.0
        ]

        if nonzero:
            top3 = nonzero[:3]
            vals = ", ".join(
                f"M{m['index']}={int(round(_safe_float(m.get('value','0'))))}"
                for m in top3
            )
            if len(nonzero) > 3:
                vals += f" (+ {len(nonzero) - 3} more)"
            parts.append(f"{label}: {len(nonzero)} macros committed ({vals})")
        else:
            parts.append(f"{label}: all macros at default")

    return "; ".join(parts)


def _safe_float(v: Any) -> float:
    try:
        return float(str(v))
    except (ValueError, TypeError):
        return 0.0


# ─── Production sequence inference ───────────────────────────────────────────

def _infer_production_sequence(tracks: list[dict]) -> list[str]:
    """Infer the likely creation order + production decisions as narrative steps.

    Heuristics (per spec §E algorithm):
      1. Numbered prefix tracks ("1-", "2-") → creation order follows numbering
      2. Non-numbered tracks → assumed added in list order
      3. Return tracks → created after the tracks that send to them
      4. Tracks with many non-zero macros → "producer settled on specific values"
    """
    steps: list[str] = []

    regular = [t for t in tracks if t.get("type") not in ("ReturnTrack",)]
    returns = [t for t in tracks if t.get("type") == "ReturnTrack"]

    # Sort by numeric prefix if present
    def sort_key(t: dict) -> tuple[int, str]:
        m = re.match(r"^(\d+)[-\s]", t.get("name", ""))
        return (int(m.group(1)), t["name"]) if m else (999, t.get("name", ""))

    ordered = sorted(regular, key=sort_key)

    step_idx = 1
    for t in ordered:
        t_name = t.get("name", "Unknown")
        device_count = t.get("device_count", 0)
        devices = t.get("devices") or []
        cls_list = [d.get("class", "") for d in devices]
        uname_list = [d.get("user_name") or "" for d in devices]

        primary_dev = (uname_list[0] or cls_list[0]) if devices else "device"
        nonzero = _count_nonzero_macros(devices)

        if device_count == 0:
            steps.append(
                f"Step {step_idx}: '{t_name}' — audio source "
                f"(no devices; clip-based content)"
            )
        elif any(c in _DRUM_CLASSES for c in cls_list):
            steps.append(
                f"Step {step_idx}: '{t_name}' — rhythmic foundation "
                f"via {primary_dev}"
            )
        else:
            commit_note = (
                f" — {nonzero} macro(s) committed from default"
                if nonzero else " — macros at default (exploratory preset)"
            )
            steps.append(
                f"Step {step_idx}: '{t_name}' — {primary_dev}{commit_note}"
            )
        step_idx += 1

    if returns:
        return_names = ", ".join(t.get("name", "Return") for t in returns)
        steps.append(
            f"Step {step_idx}: Return tracks wired ({return_names}) — "
            "shared spatial processing applied across sends"
        )

    # Global macro note
    macro_committed = sum(
        _count_nonzero_macros(t.get("devices") or []) for t in regular
    )
    if macro_committed > 0:
        steps.append(
            f"Macro note: {macro_committed} total non-default macro values "
            "across tracks — these encode the producer's committed artistic decisions."
        )

    return steps


# ─── Learning path ────────────────────────────────────────────────────────────

def _suggest_learning_path(track_breakdown: list[dict]) -> list[str]:
    """Build a solo-each-then-add learning sequence.

    Start with harmonic-foundation, add layers in production order,
    end with spatial-glue / fx-bus returns.
    """
    path: list[str] = []

    # Separate by role priority
    foundation = [t for t in track_breakdown if t["role"] == "harmonic-foundation"]
    rhythmic = [t for t in track_breakdown if t["role"] == "rhythmic-driver"]
    textures = [t for t in track_breakdown if t["role"] == "texture"]
    decoration = [t for t in track_breakdown if t["role"] == "decoration"]
    spatial = [t for t in track_breakdown
               if t["role"] in ("spatial-glue", "fx-bus")]

    # Build ordered sequence
    ordered = foundation + rhythmic + textures + decoration

    if not ordered:
        return ["Open the demo and listen through once before deconstructing."]

    # Step 1: mute everything, listen to foundation solo
    first = ordered[0]
    path.append(
        f"Open the demo. Mute every track except '{first['name']}'. "
        f"Listen: this is the {first['role']} — {first['device_chain_summary']}."
    )

    # Add layers one by one
    cumulative = [first["name"]]
    for t in ordered[1:]:
        unmuted = "' + '".join(cumulative)
        path.append(
            f"Unmute '{t['name']}' (keep '{unmuted}' playing). "
            f"Role: {t['role']}. "
            f"Notice: {t['device_chain_summary']}."
        )
        cumulative.append(t["name"])

    # Final: add returns
    if spatial:
        return_names = "' and '".join(t["name"] for t in spatial)
        path.append(
            f"Enable the return tracks ('{return_names}'). "
            "Hear how shared spatial processing glues the layers together."
        )

    path.append(
        "Rebuild the sequence from scratch in a new set — this order "
        "is the producer's creation path."
    )

    return path


# ─── Chain summary builder ────────────────────────────────────────────────────

_MAX_CHAIN_DEPTH = 4  # matches transplant and extract_chain caps


def _build_chain_summary(devices: list[dict], _depth: int = 0) -> str:
    """Build a concise device-chain string from a track's device list.

    BUG-INT#2 fix: recurses into dev.chains (Schema A — nested) so that inner
    rack devices (e.g. InstrumentVector, Pedal, Erosion, Limiter inside an
    InstrumentGroupDevice) appear in the chain summary rather than being hidden
    behind the rack's top-level class name.

    Returns e.g.:
      "InstrumentGroupDevice (Saturn Ascends) [InstrumentVector → Pedal → Erosion → Limiter] → Delay"
    """
    if not devices:
        return "(no devices)"

    parts = []
    for dev in devices:
        cls = dev.get("class", "")
        uname = dev.get("user_name") or ""
        if uname and uname != cls:
            label = f"{cls} ({uname})"
        elif uname:
            label = uname
        elif cls:
            label = cls
        else:
            label = ""

        # Recurse into inner chains if present and within depth cap
        inner_parts: list[str] = []
        if _depth < _MAX_CHAIN_DEPTH:
            for chain in dev.get("chains") or []:
                for inner_dev in chain.get("devices") or []:
                    inner_cls = inner_dev.get("class", "")
                    inner_uname = inner_dev.get("user_name") or ""
                    if inner_uname and inner_uname != inner_cls:
                        inner_parts.append(f"{inner_cls} ({inner_uname})")
                    elif inner_uname:
                        inner_parts.append(inner_uname)
                    elif inner_cls:
                        inner_parts.append(inner_cls)
                    # One more level of nesting (depth+2) for racks inside racks
                    if _depth + 1 < _MAX_CHAIN_DEPTH:
                        for sub_chain in inner_dev.get("chains") or []:
                            for sub_dev in sub_chain.get("devices") or []:
                                sub_cls = sub_dev.get("class", "") or ""
                                sub_uname = sub_dev.get("user_name") or ""
                                inner_parts.append(sub_uname if sub_uname else sub_cls)

        if inner_parts:
            label = f"{label} [{' → '.join(inner_parts)}]"

        if label:
            parts.append(label)

    return " → ".join(parts) if parts else "(empty chain)"


# ─── Narrative synthesis ──────────────────────────────────────────────────────

_ROOT_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def _synthesize_narrative(
    demo_meta: dict,
    track_breakdown: list[dict],
    prod_sequence: list[str],
    depth: str,
) -> str:
    """Generate prose narrative about the demo.

    depth: "terse" | "standard" | "verbose"
    """
    name = demo_meta.get("name", "Demo")
    bpm = demo_meta.get("bpm", 0)
    scale = demo_meta.get("scale", "Unknown")
    track_count = demo_meta.get("track_count", 0)
    scene_count = demo_meta.get("scene_count", 0)

    # Detect producer anchor from entity_id
    entity_id = demo_meta.get("entity_id", "")
    producer_anchor = _detect_producer_anchor(entity_id, "", "packs")

    # Summarise roles
    role_counts: dict[str, int] = {}
    for t in track_breakdown:
        role_counts[t["role"]] = role_counts.get(t["role"], 0) + 1

    foundation_tracks = [t for t in track_breakdown if t["role"] == "harmonic-foundation"]
    rhythmic_tracks = [t for t in track_breakdown if t["role"] == "rhythmic-driver"]
    return_tracks = [t for t in track_breakdown if t["role"] in ("spatial-glue", "fx-bus")]

    if depth == "terse":
        lines = [
            f"{name} — {bpm:.0f} BPM, {scale}, {track_count} tracks.",
        ]
        if producer_anchor:
            lines.append(producer_anchor)
        if foundation_tracks:
            lines.append(
                f"Harmonic spine: {foundation_tracks[0]['name']} "
                f"({foundation_tracks[0]['device_chain_summary']})."
            )
        if rhythmic_tracks:
            lines.append(
                f"Rhythm: {rhythmic_tracks[0]['name']}."
            )
        lines.append(f"{len(prod_sequence)} production steps inferred. [SOURCE: agent-inference]")
        return " ".join(lines)

    if depth == "standard":
        intro = (
            f"'{name}' is a {bpm:.0f} BPM demo in {scale} with "
            f"{track_count} track{'s' if track_count != 1 else ''} "
            f"and {scene_count} scene{'s' if scene_count != 1 else ''}. "
        )
        if producer_anchor:
            intro += producer_anchor + " "
        if foundation_tracks:
            intro += (
                f"The harmonic spine is '{foundation_tracks[0]['name']}' "
                f"({foundation_tracks[0]['device_chain_summary']}). "
            )
        texture_count = role_counts.get("texture", 0)
        deco_count = role_counts.get("decoration", 0)
        if texture_count:
            intro += f"{texture_count} texture layer(s) build over the foundation. "
        if rhythmic_tracks:
            intro += (
                f"Rhythm comes from '{rhythmic_tracks[0]['name']}' "
                f"({rhythmic_tracks[0]['device_chain_summary']}). "
            )
        if return_tracks:
            return_names = ", ".join(f"'{t['name']}'" for t in return_tracks)
            intro += f"Spatial cohesion via return tracks: {return_names}. "
        intro += "[SOURCE: als-parse] [SOURCE: agent-inference]"
        return intro.strip()

    # verbose
    lines = [
        f"## Demo Analysis: {name}",
        f"",
        f"**{bpm:.0f} BPM · {scale} · {track_count} tracks · "
        f"{scene_count} scene{'s' if scene_count != 1 else ''}**",
        f"",
    ]
    if producer_anchor:
        lines += [
            "### Producer Vocabulary",
            "",
            producer_anchor,
            "",
        ]

    lines += ["### Track Architecture", ""]
    for t in track_breakdown:
        lines.append(
            f"- **{t['name']}** — *{t['role']}*: "
            f"{t['device_chain_summary']}. "
            f"{t.get('macro_signature', '')}"
        )

    lines += ["", "### Inferred Production Sequence", ""]
    for step in prod_sequence:
        lines.append(f"- {step}")

    lines += ["", f"*[SOURCE: als-parse] [SOURCE: agent-inference]*"]
    return "\n".join(lines)


# ─── Main entry point ─────────────────────────────────────────────────────────

def demo_story(
    demo_entity_id: str,
    focus_tracks: list[str] | None = None,
    detail_level: str = "standard",
) -> dict:
    """Generate track-by-track narrative + production-sequence for a demo.

    Called by the MCP tool wrapper in tools.py.  Separated for direct unit tests.

    Parameters
    ----------
    demo_entity_id : str
        Entity ID, e.g. "drone_lab__earth" or "drone-lab__earth".
    focus_tracks : list[str] | None
        Optional list of track names to include in breakdown (others omitted).
        None = include all tracks.
    detail_level : str
        "terse" | "standard" | "verbose" — controls narrative verbosity.

    Returns
    -------
    dict matching the spec return shape.
    """
    # ── 1. Load sidecar ───────────────────────────────────────────────────────
    sidecar = _load_demo_sidecar(demo_entity_id)
    if sidecar is None:
        # Enumerate real demo IDs from disk for a helpful error message
        _available: list[str] = []
        try:
            import pathlib
            _demo_root = pathlib.Path(DEMO_PARSES_ROOT)
            if _demo_root.exists():
                _jsons = sorted(_demo_root.glob("*.json"))
                _available = [p.stem for p in _jsons[:10]]
        except Exception:
            pass
        return {
            "error": (
                f"Demo sidecar not found for entity_id='{demo_entity_id}'. "
                "Check that the pack + demo slug exist under "
                f"~/.livepilot/atlas-overlays/packs/_demo_parses/."
            ),
            "entity_id": demo_entity_id,
            "available_demos": _available,
            "sources": [],
        }

    sidecar_path = _resolve_demo_slug(demo_entity_id)

    # ── 2. Extract metadata ───────────────────────────────────────────────────
    bpm = float(sidecar.get("bpm") or 120.0)
    scale_raw = sidecar.get("scale") or {}
    try:
        root_note_int = int(str(scale_raw.get("root_note", "0")))
    except (ValueError, TypeError):
        root_note_int = 0
    scale_name = scale_raw.get("name", "Major") or "Major"
    scale_str = f"{_ROOT_NAMES[root_note_int % 12]} {scale_name}"

    all_tracks = sidecar.get("tracks") or []
    scenes = sidecar.get("scenes") or []

    # ── 3. Build per-track breakdown ─────────────────────────────────────────
    track_breakdown: list[dict] = []
    for t in all_tracks:
        t_name = t.get("name", "Unnamed")
        t_type = t.get("type", "")

        # Focus filter — substring match on any token
        if focus_tracks and not any(tok.lower() in t_name.lower() for tok in focus_tracks):
            continue

        devices = t.get("devices") or []
        role = _classify_track_role(t, all_tracks)
        chain_summary = _build_chain_summary(devices)
        macro_sig = _extract_macro_signature(t)

        # Production decision prose
        primary_device = (devices[0] if devices else {})
        primary_cls = primary_device.get("class", "")
        primary_uname = primary_device.get("user_name") or ""
        nonzero = _count_nonzero_macros(devices)

        if t_type == "ReturnTrack":
            prod_decision = (
                f"{primary_cls} shared return — applies uniformly across all sends."
            )
        elif role == "harmonic-foundation":
            prod_decision = (
                f"{primary_uname or primary_cls} chosen as harmonic spine; "
                f"{nonzero} macro(s) committed to specific values, "
                "suggesting deliberate timbral targeting."
            )
        elif role == "rhythmic-driver":
            prod_decision = (
                f"Drum rack '{primary_uname or primary_cls}' provides rhythmic drive. "
                f"{nonzero} non-default macro values indicate custom tuning."
            )
        elif role == "texture":
            prod_decision = (
                f"'{primary_uname or t_name}' adds textural density. "
                + (f"{nonzero} macro(s) dialed in." if nonzero else
                   "Macros at default — exploratory layer.")
            )
        elif role == "decoration":
            prod_decision = (
                "Audio source or effects-only layer — provides colour rather than melodic content."
            )
        else:
            prod_decision = f"{role.replace('-', ' ').title()} role."

        # Narrative role (how it fits the overall piece)
        if role == "harmonic-foundation":
            narrative_role = "carries the harmonic spine; all other layers decorate this"
        elif role == "rhythmic-driver":
            narrative_role = "provides rhythmic pulse and groove engine"
        elif role == "texture":
            narrative_role = "adds timbral complexity and spectral density"
        elif role == "spatial-glue":
            narrative_role = "shared reverb/delay — glues layers into a single acoustic space"
        elif role == "fx-bus":
            narrative_role = "bus processing — shapes the collective output of routed tracks"
        elif role == "decoration":
            narrative_role = "decorative layer — accent or atmospherics"
        else:
            narrative_role = role

        track_breakdown.append({
            "name": t_name,
            "type": t_type,
            "role": role,
            "device_chain_summary": chain_summary,
            "macro_signature": macro_sig,
            "production_decision": prod_decision,
            "narrative_role": narrative_role,
        })

    # ── 4. Infer production sequence ─────────────────────────────────────────
    # Use all tracks (not just focus filtered) for sequence
    prod_sequence = _infer_production_sequence(all_tracks)

    # ── 5. Suggest learning path ──────────────────────────────────────────────
    learning_path = _suggest_learning_path(track_breakdown)

    # ── 6. Synthesize narrative ───────────────────────────────────────────────
    demo_meta = {
        "entity_id": demo_entity_id,
        "name": sidecar.get("name", demo_entity_id),
        "bpm": bpm,
        "scale": scale_str,
        "track_count": len(all_tracks),
        "scene_count": len(scenes),
    }
    narrative = _synthesize_narrative(demo_meta, track_breakdown, prod_sequence, detail_level)

    return {
        "demo": {
            "entity_id": demo_entity_id,
            "name": sidecar.get("name", demo_entity_id),
            "bpm": bpm,
            "scale": scale_str,
            "track_count": len(all_tracks),
            "scene_count": len(scenes),
        },
        "narrative": narrative,
        "track_breakdown": track_breakdown,
        "production_sequence_inference": prod_sequence,
        "suggested_learning_path": learning_path,
        "sources": [
            f"als-parse: {sidecar_path} [SOURCE: als-parse]",
            "agent-inference: role classification + narrative synthesis [SOURCE: agent-inference]",
        ],
    }
