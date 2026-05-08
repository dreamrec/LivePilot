"""Pure-computation §5 layer checks. No I/O — operates on fetched data.

Each check returns:
    {
        "severity": "pass" | "warn" | "fail" | "n/a",
        "summary": str,
        "issues": [{"code": str, "detail": str}, ...],
        "evidence": {...},
    }
"""

from __future__ import annotations

from statistics import mean, pstdev
from typing import Any


# ── Role inference ───────────────────────────────────────────────────

_ROLE_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("kick", ("kick", "kik", "bd", "bass drum", "808 kick")),
    ("snare", ("snare", "snr", "sd", "clap", "rim")),
    ("hat", ("hihat", "hi-hat", "hi hat", "hat", "hh", "open hh", "closed hh")),
    ("perc", ("perc", "tom", "shaker", "ride", "crash", "cym", "cowbell", "tamb", "conga")),
    ("bass", ("bass", "sub", "808", "bs ")),
    ("vox", ("vox", "vocal", "voc", "lead vocal", "vocoder")),
    ("lead", ("lead", "melody", "main", "hook", "topline", "arp")),
    ("pad", ("pad", "chord", "keys", "piano", "wurli", "rhodes", "string")),
    ("atmos", ("atmos", "drone", "wash", "texture", "ambient", "field")),
    ("fx", ("fx", "riser", "hit", "impact", "swoosh", "downer")),
)


def infer_role(track_name: str, devices: list[dict]) -> str:
    """Best-effort role inference from track name + first instrument class."""
    name = (track_name or "").lower()
    for role, kws in _ROLE_KEYWORDS:
        for kw in kws:
            if kw in name:
                return role
    # Fallback: look at the first instrument-class device
    for dev in devices or []:
        cls = (dev.get("class_name") or "").lower()
        if cls in ("drumgroup", "drumrack", "drum rack"):
            return "perc"
        if cls in ("simpler", "sampler"):
            return "perc"  # most common single-Simpler use
        if cls in ("operator", "wavetable", "drift", "analog", "poli", "meld", "tension", "collision"):
            return "lead"
    return "unknown"


# ── §5.1 Timbre via spectrum ─────────────────────────────────────────

# Loose role → expected spectrum-band dominance.
# Uses 7-band convention: SUB_LOW, LOW, LOW_MID, MID, PRESENCE, HIGH, AIR.
_ROLE_BAND_EXPECTATIONS: dict[str, tuple[str, ...]] = {
    "kick": ("SUB_LOW", "LOW", "MID"),
    "snare": ("MID", "PRESENCE", "HIGH"),
    "hat": ("PRESENCE", "HIGH", "AIR"),
    "perc": ("MID", "PRESENCE", "HIGH"),
    "bass": ("SUB_LOW", "LOW", "LOW_MID"),
    "pad": ("LOW_MID", "MID", "PRESENCE"),
    "lead": ("MID", "PRESENCE", "HIGH"),
    "atmos": ("LOW_MID", "MID", "PRESENCE", "HIGH"),
    "vox": ("MID", "PRESENCE", "HIGH"),
    "fx": ("PRESENCE", "HIGH", "AIR"),
}


def check_timbre(role: str, fingerprint: dict | None) -> dict:
    """§5.1 — does the layer's spectral shape match its role?"""
    if not fingerprint:
        return {
            "severity": "n/a",
            "summary": "No timbre fingerprint available (M4L bridge not connected or solo not run)",
            "issues": [],
            "evidence": {"source": "unavailable"},
        }
    bands = fingerprint.get("bands") or fingerprint.get("band_energy") or {}
    if not bands:
        return {
            "severity": "n/a",
            "summary": "Timbre fingerprint had no band energy",
            "issues": [],
            "evidence": {"source": "empty"},
        }
    expected = _ROLE_BAND_EXPECTATIONS.get(role)
    if not expected:
        return {
            "severity": "pass",
            "summary": f"Role '{role}' has no fixed band expectation",
            "issues": [],
            "evidence": {"bands": bands},
        }
    # Find dominant band(s) — top1 is the discriminator
    sorted_bands = sorted(bands.items(), key=lambda kv: kv[1], reverse=True)
    top2 = [b for b, _ in sorted_bands[:2]]
    expected_set = set(expected)
    if top2[0] in expected_set:
        return {
            "severity": "pass",
            "summary": f"{role} dominates {top2[0]} — within expected {expected}",
            "issues": [],
            "evidence": {"top2": top2, "expected": list(expected)},
        }
    if len(top2) > 1 and top2[1] in expected_set:
        return {
            "severity": "warn",
            "summary": f"{role}: dominant band {top2[0]} is off-role; expected {expected[0]} prominent",
            "issues": [{
                "code": "off_band_dominance",
                "detail": f"Top band is {top2[0]}; expected dominance in {expected}. Secondary band {top2[1]} is in range.",
            }],
            "evidence": {"top2": top2, "expected": list(expected)},
        }
    return {
        "severity": "fail",
        "summary": f"{role} should dominate {expected}; actually dominates {top2}",
        "issues": [{
            "code": "wrong_band_dominance",
            "detail": f"Sample/patch reads as {top2[0]}-dominant — wrong sample for {role}",
        }],
        "evidence": {"top2": top2, "expected": list(expected)},
    }


# ── §5.2 Sequence critique ───────────────────────────────────────────


def _collect_clip_notes(track_info: dict) -> list[dict]:
    """Pull notes from track_info; if not embedded, caller must fetch separately.

    Note: get_track_info does NOT include per-clip notes (only clip metadata).
    The audit_layer orchestrator fetches them via get_notes per clip.
    """
    return []


def check_sequence(role: str, notes_per_clip: list[list[dict]]) -> dict:
    """§5.2 — humanization, ghost notes, swing, variation."""
    if not notes_per_clip or all(not n for n in notes_per_clip):
        return {
            "severity": "n/a",
            "summary": "No notes on this track (no MIDI clips, or audio track)",
            "issues": [],
            "evidence": {"clip_count": len(notes_per_clip)},
        }
    issues: list[dict[str, str]] = []
    all_velocities: list[int] = []
    ghost_count = 0
    duration_set: set[float] = set()
    pitch_set: set[int] = set()
    total_notes = 0
    for notes in notes_per_clip:
        for n in notes:
            v = int(n.get("velocity", 100))
            all_velocities.append(v)
            if 25 <= v <= 45:
                ghost_count += 1
            duration_set.add(round(float(n.get("duration", 0)), 3))
            pitch_set.add(int(n.get("pitch", 60)))
            total_notes += 1

    if total_notes == 0:
        return {
            "severity": "n/a",
            "summary": "Clips exist but contain no notes",
            "issues": [],
            "evidence": {},
        }

    vel_stddev = pstdev(all_velocities) if len(all_velocities) > 1 else 0.0
    vel_mean = mean(all_velocities) if all_velocities else 0.0

    if vel_stddev < 3.0 and total_notes >= 4:
        issues.append({
            "code": "no_humanization",
            "detail": f"Velocities have stddev={vel_stddev:.1f} — robotic. Spread ±5-10 for organic feel.",
        })
    if role in ("snare", "hat", "perc") and ghost_count == 0 and total_notes >= 8:
        issues.append({
            "code": "no_ghost_notes",
            "detail": f"{role} has no ghost notes (vel 25-45). Add 16th-note ghosts at vel ~35 for groove.",
        })
    if len(duration_set) <= 1 and total_notes >= 4 and role in ("pad", "lead", "bass", "vox"):
        issues.append({
            "code": "uniform_durations",
            "detail": "All notes have identical duration. Vary durations for phrasing.",
        })
    if role in ("pad", "lead") and len(pitch_set) <= 2 and total_notes >= 4:
        issues.append({
            "code": "low_pitch_variety",
            "detail": f"{role} uses only {len(pitch_set)} pitch(es). Add melodic motion or chord extensions.",
        })

    severity = "pass" if not issues else ("warn" if len(issues) <= 1 else "fail")
    return {
        "severity": severity,
        "summary": (
            f"{total_notes} notes, vel µ={vel_mean:.0f}±{vel_stddev:.1f}, "
            f"ghosts={ghost_count}, durations={len(duration_set)}, pitches={len(pitch_set)}"
        ),
        "issues": issues,
        "evidence": {
            "total_notes": total_notes,
            "velocity_stddev": round(vel_stddev, 2),
            "velocity_mean": round(vel_mean, 1),
            "ghost_count": ghost_count,
            "duration_variants": len(duration_set),
            "pitch_variants": len(pitch_set),
        },
    }


# ── §5.3 Stereo image ────────────────────────────────────────────────


def check_stereo(role: str, track_info: dict) -> dict:
    """§5.3 — pan + bass-mono + width."""
    mixer = track_info.get("mixer", {})
    pan = float(mixer.get("panning", 0.0))
    issues: list[dict[str, str]] = []
    if role == "bass" and abs(pan) > 0.05:
        issues.append({
            "code": "panned_bass",
            "detail": f"Bass is panned {pan:+.2f}. Sub-bass should be center for translation.",
        })
    if role in ("kick", "snare") and abs(pan) > 0.15:
        issues.append({
            "code": "panned_drum_anchor",
            "detail": f"{role} panned {pan:+.2f} — drum anchors usually center.",
        })
    severity = "warn" if issues else "pass"
    return {
        "severity": severity,
        "summary": f"pan={pan:+.2f}",
        "issues": issues,
        "evidence": {"pan": pan},
    }


# ── §5.4 Masking (cross-track frequency collision) ──────────────────


def check_masking(track_index: int, masking_report: dict | None) -> dict:
    """§5.4 — pull this track's collisions out of the global masking report."""
    if not masking_report:
        return {
            "severity": "n/a",
            "summary": "No masking report available",
            "issues": [],
            "evidence": {},
        }
    entries = masking_report.get("masking", {}).get("entries", []) or []
    my_collisions = [
        e for e in entries
        if e.get("track_a") == track_index or e.get("track_b") == track_index
    ]
    if not my_collisions:
        return {
            "severity": "pass",
            "summary": "No detected masking collisions",
            "issues": [],
            "evidence": {"collision_count": 0},
        }
    issues = []
    for c in my_collisions:
        sev = c.get("severity", "warn")
        other = c.get("track_b") if c.get("track_a") == track_index else c.get("track_a")
        band = c.get("band") or c.get("frequency_band") or "?"
        issues.append({
            "code": "masking_collision",
            "detail": f"Frequency clash with track {other} in band {band} (severity={sev})",
        })
    severity = "fail" if any(c.get("severity") == "high" for c in my_collisions) else "warn"
    return {
        "severity": severity,
        "summary": f"{len(my_collisions)} masking collision(s) involving this track",
        "issues": issues,
        "evidence": {"collisions": my_collisions[:5]},  # cap response size
    }


# ── §5.5 Modulation/automation (mandatory by §4) ────────────────────

_INSTRUMENT_CLASSES = frozenset({
    "Drift", "Wavetable", "Operator",
    # Live's actual runtime class names diverge from user-facing brand names.
    # Verified live 2026-05-08 via load_browser_item:
    #   "Analog"  user → "UltraAnalog"        class
    #   "Meld"    user → "InstrumentMeld"     class
    #   "Poli"    user → "MxDeviceInstrument" class (M4L wrapper)
    # The user-facing strings ("Analog", "Poli", "Meld") never appear as
    # class_name in Live's output — they were aspirational but unmatched.
    # Keep them as no-ops in case future Live versions change the taxonomy
    # back, but the runtime class names below are what actually fires.
    "Analog", "Poli", "Meld",
    "UltraAnalog", "InstrumentMeld", "MxDeviceInstrument",
    "Tension", "Collision", "Electric",
    # Electric's actual runtime class is LoungeLizard (verified live 2026-05-08
    # while building the two-step session — Track 3 'Stabs' loaded with
    # query:Synths#Electric showed first_device_class='LoungeLizard').
    "LoungeLizard",
    # Sampler family — Live exposes multiple class names depending on
    # device generation. OriginalSimpler is the legacy Simpler core,
    # MultiSampler is the Sampler core. Verified against live sessions
    # 2026-05-01: Phantasm Pad → MultiSampler, Hihat 808 Close → OriginalSimpler.
    "Simpler", "OriginalSimpler", "Sampler", "MultiSampler",
    "DrumGroup", "DrumRack", "DrumGroupDevice",
    "InstrumentVector", "InstrumentRack",
})


def check_modulation(
    role: str,
    devices: list[dict],
    clip_automation_present: bool,
    wavetable_mod_routings: int,
) -> dict:
    """§5.5 + §4 — at least one modulation routing per layer.

    Counts active routings across the native '<dest> < <source>' parameter
    naming convention (Live's standard for mod routings on Simpler/Sampler/
    Drift/etc.) plus generic mod/lfo/env-amount params. Validated against
    Phantasm Pad (MultiSampler, Filt < Vel: 0.59, Filt < Key: 1.0) on a
    live session 2026-05-01.
    """
    routings = 0
    for dev in devices or []:
        cls = dev.get("class_name", "")
        if cls not in _INSTRUMENT_CLASSES:
            continue
        params = dev.get("parameters", []) or []
        # Build a lookup so we can gate "<dest> < <source>" on its
        # corresponding "On" toggle (e.g. Fe < Env only counts if Fe On=1).
        by_name: dict[str, float] = {}
        for p in params:
            by_name[(p.get("name") or "").lower()] = float(p.get("value", 0.0))

        for name, value in by_name.items():
            # Generic mod-amount conventions
            if any(tok in name for tok in (
                "lfo amount", "env amount", "mod amount", "fm amount",
                "osc mod", "ring mod",
            )):
                if abs(value) > 0.01:
                    routings += 1
                continue
            # Live's "<dest> < <source>" routing convention.
            # Examples: "Filt < Env", "Filt < Vel", "Filt < Key", "Filt < LFO",
            # "Vol < Vel", "Vol < LFO", "Pan < Rnd", "Pan < LFO",
            # "Pitch < LFO", "Pe < Env", "Fe < Env", "Time < Key".
            if " < " in name and abs(value) > 0.01:
                # Gate filter-envelope amount on Fe On
                if name in ("fe < env", "fil < env", "filt < env"):
                    if by_name.get("fe on", 1.0) < 0.5:
                        continue
                # Gate pitch-envelope amount on Pe On
                if name == "pe < env":
                    if by_name.get("pe on", 1.0) < 0.5:
                        continue
                # Gate LFO routings on L On (legacy Simpler) or L 1/2/3 On
                if "< lfo" in name:
                    lfo_on = (
                        by_name.get("l on", 0.0) > 0.5
                        or by_name.get("l 1 on", 0.0) > 0.5
                        or by_name.get("l 2 on", 0.0) > 0.5
                        or by_name.get("l 3 on", 0.0) > 0.5
                    )
                    if not lfo_on:
                        continue
                routings += 1

    routings += max(0, int(wavetable_mod_routings))
    automation = bool(clip_automation_present)

    issues: list[dict[str, str]] = []
    if role in ("pad", "lead", "bass", "atmos") and routings == 0 and not automation:
        issues.append({
            "code": "static_layer",
            "detail": f"§4 violation: {role} has 0 modulation routings AND no automation. Add LFO→filter, env→pitch, or clip automation.",
        })
        severity = "fail"
    elif routings == 0 and not automation:
        issues.append({
            "code": "no_movement",
            "detail": "Layer has no modulation or automation. Adds life via LFO/envelope or per-clip automation.",
        })
        severity = "warn"
    else:
        severity = "pass"

    return {
        "severity": severity,
        "summary": f"routings={routings}, automation={automation}",
        "issues": issues,
        "evidence": {"routings_count": routings, "automation_present": automation},
    }


# ── §5.6 Synth params (default-detection) ───────────────────────────

# Param name fragments that, if at exactly 0 or factory-default, indicate
# the user didn't program the source (§2 violation).
_SUSPICIOUS_AT_ZERO: tuple[str, ...] = (
    "fe < env",   # filter envelope amount
    "filt < env",
    "pe < env",   # pitch envelope amount
    "spread",
    "detune",
    "unison",
)

# Drift's defaults trip up the suspicious-at-zero approach because the
# synth ships with sensible non-zero values for the params we'd otherwise
# flag (Spread=0.10, Strength=0.05, Mod Matrix Amt 1=0.97, etc.). The
# user-engagement signals that DO move on programming are bipolar
# parameters at center (0.5 = no effect) and a small set of factory
# defaults. Verified against bare-default Drift loaded via load_browser_item
# 2026-05-08.
_DRIFT_FACTORY_FINGERPRINT: dict[str, float] = {
    # bipolar center = no effect
    "pitch mod amt 1": 0.5,
    "pitch mod amt 2": 0.5,
    "mod matrix amt 2": 0.5,
    "mod matrix amt 3": 0.5,
    "vel > vol": 0.5,
    # near-zero factory values
    "spread": 0.10,
    "strength": 0.05,
    "drift": 0.07,
    "thickness": 0.0,
    # high-amplitude factory values
    "lp mod amt 1": 0.97,
    "lp mod amt 2": 0.78,
    "lfo amt": 1.0,
}
# Tolerance for "user touched this param" — if any shaping param deviates
# from factory by more than this, treat it as engagement evidence.
_DRIFT_FACTORY_EPSILON: float = 0.04


def _drift_engagement_score(params: list[dict]) -> tuple[int, list[str]]:
    """Count Drift shaping params that DEVIATE from factory defaults.

    Returns (deviation_count, list_of_deviated_param_names).
    """
    deviations: list[str] = []
    for p in params or []:
        name = (p.get("name") or "").lower().strip()
        if name in _DRIFT_FACTORY_FINGERPRINT:
            factory = _DRIFT_FACTORY_FINGERPRINT[name]
            try:
                value = float(p.get("value", 0.0))
            except (TypeError, ValueError):
                continue
            if abs(value - factory) > _DRIFT_FACTORY_EPSILON:
                deviations.append(p.get("name", "?"))
    return len(deviations), deviations


def _check_drift_params(role: str, instrument: dict) -> dict:
    """Drift-specific §2 detection via factory-fingerprint deviation count.

    Drift's bipolar defaults (Mod Matrix Amt at 0.5, Vel>Vol at 0.5,
    Pitch Mod Amt at 0.5) plus low-amplitude factory values (Spread=0.10,
    Strength=0.05) escape the generic _SUSPICIOUS_AT_ZERO heuristic.
    Compare against a hand-captured factory fingerprint instead.
    """
    params = instrument.get("parameters", []) or []
    deviation_count, deviated = _drift_engagement_score(params)
    fingerprint_size = len(_DRIFT_FACTORY_FINGERPRINT)

    if role in ("kick", "snare", "hat", "perc"):
        return {
            "severity": "pass",
            "summary": f"Drift: simple-role ({role}) — engagement check skipped",
            "issues": [],
            "evidence": {
                "instrument_class": "Drift",
                "drift_engagement_deviations": deviation_count,
                "fingerprint_size": fingerprint_size,
                "suppressed_for_role": role,
            },
        }

    if role in ("pad", "lead", "bass") and deviation_count == 0:
        return {
            "severity": "fail",
            "summary": f"Drift: bare-default — 0 of {fingerprint_size} shaping params engaged",
            "issues": [{
                "code": "unprogrammed_instrument",
                "detail": (
                    "§2 violation: bare-default Drift on melodic-role track. "
                    "ZERO shaping params deviated from factory. Open Drift, "
                    "engage at least one of: pitch envelope (Pitch Mod Amt), "
                    "filter envelope (LP Mod Amt), velocity routing (Vel > Vol), "
                    "mod matrix (Mod Matrix Amt 2/3), or oscillator character "
                    "(Spread / Strength / Thickness / Drift)."
                ),
            }],
            "evidence": {
                "instrument_class": "Drift",
                "drift_engagement_deviations": deviation_count,
                "fingerprint_size": fingerprint_size,
                "deviated_params": deviated,
            },
        }

    severity = "pass" if deviation_count >= 2 else "warn" if deviation_count == 1 else "warn"
    if role in ("pad", "lead", "bass"):
        return {
            "severity": severity,
            "summary": f"Drift: {deviation_count}/{fingerprint_size} shaping params engaged",
            "issues": [],
            "evidence": {
                "instrument_class": "Drift",
                "drift_engagement_deviations": deviation_count,
                "fingerprint_size": fingerprint_size,
                "deviated_params": deviated,
            },
        }
    # Other roles (vox/atmos/lead/etc.): just report engagement, no opinion
    return {
        "severity": "pass",
        "summary": f"Drift: {deviation_count}/{fingerprint_size} shaping params engaged ({role})",
        "issues": [],
        "evidence": {
            "instrument_class": "Drift",
            "drift_engagement_deviations": deviation_count,
            "fingerprint_size": fingerprint_size,
            "deviated_params": deviated,
        },
    }


def check_params(role: str, devices: list[dict]) -> dict:
    """§5.6 + §2 — instrument programming, not just defaults."""
    if not devices:
        return {
            "severity": "n/a",
            "summary": "No devices on track",
            "issues": [],
            "evidence": {},
        }
    instrument = next(
        (d for d in devices if d.get("class_name") in _INSTRUMENT_CLASSES),
        None,
    )
    if not instrument:
        return {
            "severity": "n/a",
            "summary": "No native instrument on track (audio track or 3rd-party VST)",
            "issues": [],
            "evidence": {"first_device_class": devices[0].get("class_name")},
        }
    cls = instrument.get("class_name", "")

    # Drift escapes the generic suspicious-at-zero heuristic — its defaults
    # are non-zero (Spread=0.10, etc.) and bipolar (Vel>Vol=0.5). Use a
    # synth-specific factory-fingerprint instead.
    if cls == "Drift":
        return _check_drift_params(role, instrument)

    params = instrument.get("parameters", []) or []
    by_name = {(p.get("name") or "").lower(): float(p.get("value", 0.0)) for p in params}
    untouched: list[str] = []
    for p in params:
        name_l = (p.get("name") or "").lower()
        value = float(p.get("value", 0.0))
        for tok in _SUSPICIOUS_AT_ZERO:
            if tok in name_l and abs(value) < 0.001:
                # Gate envelope-amount params on their On toggle —
                # Fe < Env: 0 with Fe On: 0 is a deliberate choice, not laziness.
                if tok in ("fe < env", "filt < env"):
                    if by_name.get("fe on", 1.0) < 0.5:
                        break
                if tok == "pe < env":
                    if by_name.get("pe on", 1.0) < 0.5:
                        break
                untouched.append(p.get("name", "?"))
                break
    issues: list[dict[str, str]] = []
    # BUG-E (caught 2026-05-01 live test): kick/snare/hat/perc are simple
    # by design — single sample + minimal shaping is the correct creative
    # choice. Mirror the suppression that sound_design/tools.py applies
    # via _is_simple_role_track. Without this, every drum track flags
    # 4 default-shaping params (Spread/Detune/Pe<Env/Fe<Env) which is
    # noise the LLM has to re-evaluate.
    _SIMPLE_ROLES = ("kick", "snare", "hat", "perc")
    if role in _SIMPLE_ROLES:
        return {
            "severity": "pass",
            "summary": f"{cls}: simple-role ({role}) — default shaping params expected",
            "issues": [],
            "evidence": {
                "instrument_class": cls,
                "untouched_params": untouched[:8],
                "suppressed_for_role": role,
            },
        }
    if role in ("pad", "lead", "bass") and len(untouched) >= 3:
        issues.append({
            "code": "unprogrammed_instrument",
            "detail": (
                f"§2 violation: {cls} has {len(untouched)} key shaping params at 0/default "
                f"({', '.join(untouched[:5])}). Open the instrument and program envelopes/spread/detune."
            ),
        })
        severity = "fail"
    elif len(untouched) >= 4:
        issues.append({
            "code": "many_default_params",
            "detail": f"{cls}: {len(untouched)} shaping params at default. Likely not programmed.",
        })
        severity = "warn"
    else:
        severity = "pass"
    return {
        "severity": severity,
        "summary": f"{cls}: {len(params)} params, {len(untouched)} at suspect-default",
        "issues": issues,
        "evidence": {"instrument_class": cls, "untouched_params": untouched[:8]},
    }


# ── §5.7 Sample audition (Simpler/Sampler only) ─────────────────────


_SAMPLER_CLASSES = frozenset({"Simpler", "OriginalSimpler", "Sampler", "MultiSampler"})


def check_samples(role: str, devices: list[dict], slice_classifications: list[dict] | None) -> dict:
    """§5.7 — Simpler/Sampler sample-fit signals."""
    simpler = next(
        (d for d in devices if d.get("class_name") in _SAMPLER_CLASSES),
        None,
    )
    if not simpler:
        return {
            "severity": "n/a",
            "summary": "No Simpler/Sampler on track",
            "issues": [],
            "evidence": {},
        }
    issues: list[dict[str, str]] = []
    # Heuristic: Simpler default volume is -12 dB (memory: feedback_simpler_default_volume).
    # Read Volume param if present.
    params = simpler.get("parameters", []) or []
    vol = next((p for p in params if (p.get("name") or "").lower() == "volume"), None)
    if vol and float(vol.get("value", 0.0)) < -10.0 and role in ("pad", "lead", "bass", "vox"):
        issues.append({
            "code": "simpler_default_volume",
            "detail": f"Simpler Volume at {vol.get('value'):.1f} dB (default -12). Set to 0 for sustained roles.",
        })
    if slice_classifications:
        unclassified = sum(1 for s in slice_classifications if s.get("classification") in (None, "unknown"))
        if unclassified > 0:
            issues.append({
                "code": "unclassified_slices",
                "detail": f"{unclassified} slice(s) unclassified — programming drums by index without spectral check.",
            })
    severity = "warn" if issues else "pass"
    return {
        "severity": severity,
        "summary": f"Simpler/Sampler present; {len(issues)} issue(s)",
        "issues": issues,
        "evidence": {
            "has_volume_default": bool(vol and float(vol.get("value", 0.0)) < -10.0),
            "slice_count": len(slice_classifications) if slice_classifications else 0,
        },
    }


# ── §5.8 Effects chain coverage ─────────────────────────────────────

_EFFECT_CATEGORIES: dict[str, tuple[str, ...]] = {
    # Each entry must include both the user-facing display names AND Live's
    # actual runtime class_name (verified live 2026-05-08). The audit reads
    # device.class_name, not device.name, so missing class_names cause
    # silent false-negative coverage reports.
    "eq": ("EQ Eight", "Eq8", "EQ Three", "Eq3", "Channel EQ"),
    "compressor": (
        "Compressor", "Compressor2",  # legacy + modern class names
        "Glue Compressor", "GlueCompressor",
        "Compressor 2",                # display variant
        "Multiband Dynamics", "MultibandDynamics",
    ),
    "saturation": (
        "Saturator", "Overdrive", "Pedal", "Drive", "Roar",
        # M4L wrappers — Drive, Roar are M4L: class_name = MxDeviceAudioEffect
        # Skipped intentionally — too generic for class-name detection
    ),
    "spatial": (
        "Reverb", "Hybrid Reverb", "HybridReverb",
        "Echo", "Delay", "PingPongDelay",
        "Chorus-Ensemble", "Chorus2", "Chorus",
    ),
    "filter": ("Auto Filter", "AutoFilter", "AutoFilter2"),
}


def check_effects(role: str, devices: list[dict]) -> dict:
    """§5.8 — every track should have shaping FX, not just a bare instrument."""
    if not devices:
        return {"severity": "n/a", "summary": "No devices", "issues": [], "evidence": {}}
    classes = [d.get("class_name", "") for d in devices]
    coverage: dict[str, bool] = {}
    for cat, names in _EFFECT_CATEGORIES.items():
        coverage[cat] = any(c in names for c in classes)

    issues: list[dict[str, str]] = []
    # Roles where EQ + Comp are pretty much mandatory
    if role in ("kick", "snare", "bass", "vox", "lead") and not coverage["eq"]:
        issues.append({"code": "no_eq", "detail": f"{role} has no EQ. Carve frequencies for translation."})
    if role in ("bass", "vox", "lead") and not coverage["compressor"]:
        issues.append({"code": "no_compressor", "detail": f"{role} has no compressor. Glue dynamics."})
    if role in ("pad", "atmos", "vox", "lead") and not coverage["spatial"]:
        issues.append({"code": "no_space", "detail": f"{role} has no reverb/delay. Add depth."})
    severity = "warn" if issues else "pass"
    return {
        "severity": severity,
        "summary": f"effects: {sum(coverage.values())}/{len(coverage)} categories covered",
        "issues": issues,
        "evidence": {"coverage": coverage, "device_classes": classes},
    }


# ── Severity rollup + fix ranking ───────────────────────────────────

_SEVERITY_RANK = {"n/a": 0, "pass": 1, "warn": 2, "fail": 3}


def rollup_severity(checks: dict[str, dict]) -> str:
    """Highest severity across all checks."""
    worst = max((_SEVERITY_RANK.get(c.get("severity", "pass"), 1) for c in checks.values()), default=1)
    for k, v in _SEVERITY_RANK.items():
        if v == worst:
            return k
    return "pass"


_FIX_PRIORITY: dict[str, str] = {
    "wrong_band_dominance": "high",
    "static_layer": "high",
    "unprogrammed_instrument": "high",
    "panned_bass": "high",
    "masking_collision": "high",
    "no_eq": "medium",
    "no_compressor": "medium",
    "no_space": "medium",
    "no_humanization": "medium",
    "no_ghost_notes": "medium",
    "uniform_durations": "low",
    "low_pitch_variety": "medium",
    "no_movement": "medium",
    "many_default_params": "low",
    "simpler_default_volume": "high",
    "unclassified_slices": "medium",
    "panned_drum_anchor": "low",
}


def rank_fixes(checks: dict[str, dict]) -> list[dict[str, Any]]:
    """Flatten all issues into a ranked fix list."""
    fixes: list[dict[str, Any]] = []
    for check_name, result in checks.items():
        for issue in result.get("issues", []) or []:
            code = issue.get("code", "")
            fixes.append({
                "priority": _FIX_PRIORITY.get(code, "low"),
                "check": check_name,
                "code": code,
                "fix": issue.get("detail", ""),
            })
    rank_order = {"high": 0, "medium": 1, "low": 2}
    fixes.sort(key=lambda f: rank_order.get(f["priority"], 99))
    return fixes
