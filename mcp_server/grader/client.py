"""Mechanical rubric grader.

Phase 1 — §7.3 layer accumulation only. Each check is a pure function of
session state, returning the same shape used by `mcp_server/audit/checks.py`:

    {
        "id": str,
        "passed": bool,
        "severity": "pass" | "warn" | "fail" | "n/a",
        "summary": str,
        "issues": [{"code": str, "detail": str, "track_index": int | None}, ...],
        "evidence": {...},
    }

`evaluate(rubric_id, state)` aggregates per-criterion results into a Verdict.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable

from mcp_server.audit import checks as audit_checks
from mcp_server.audit.checks import infer_role


_TRACK_COUNT_WARN = 8
_TRACK_COUNT_FAIL = 12

_BURIED_THRESHOLD = 0.15
_GHOST_KEYWORDS: tuple[str, ...] = ("ghost", "_g ", "_g_", " gh ", "gh_")

_ROLE_VOLUME_BANDS: dict[str, tuple[float, float]] = {
    "kick":    (0.60, 0.85),
    "bass":    (0.60, 0.85),
    "snare":   (0.55, 0.80),
    "hat":     (0.40, 0.70),
    "perc":    (0.40, 0.65),
    "lead":    (0.50, 0.80),
    "vox":     (0.55, 0.85),
    "pad":     (0.25, 0.50),
    "atmos":   (0.25, 0.45),
    "fx":      (0.30, 0.70),
    "unknown": (0.30, 0.80),
}

# Banned-default detection uses (class_name, name) FINGERPRINTS rather than
# class names alone. Live's runtime class taxonomy doesn't match user-facing
# brand names — surveyed live in 2026-05-08 with load_browser_item:
#   Drift  → class="Drift",              name="Drift"           (native)
#   Analog → class="UltraAnalog",        name="Analog"          (native)
#   Meld   → class="InstrumentMeld",     name="Meld"            (native)
#   Poli   → class="MxDeviceInstrument", name="Poli"            (M4L wrapper)
# The fingerprint approach catches all four; the previous flat-set approach
# only caught Drift.
_BANNED_DEFAULT_FINGERPRINTS: frozenset[tuple[str, str]] = frozenset({
    ("drift", "drift"),
    ("ultraanalog", "analog"),
    ("instrumentmeld", "meld"),
    ("mxdeviceinstrument", "poli"),
})
_BANNED_DEFAULT_ROLES: frozenset[str] = frozenset({"bass", "pad", "lead"})
_SUBTRACTIVE_EXCEPTION_KEYWORDS: tuple[str, ...] = ("subtractive", "analog sub", "_sub_synth")

# Instrument-class set used by the modulation-presence guard (Fix #2).
# Includes Live's actual runtime class names, not user-facing brand names.
_INSTRUMENT_CLASSES: frozenset[str] = frozenset({
    "operator", "wavetable", "drift",
    "ultraanalog",          # Analog
    "instrumentmeld",       # Meld
    "mxdeviceinstrument",   # Poli + every other M4L instrument
    "tension", "collision",
    "simpler", "originalsimpler", "sampler", "multisampler",
    "electric", "loungelizard",   # Electric → LoungeLizard runtime class
    "drumgroup", "drumrack", "drum rack", "drumgroupdevice",
    "instrumentgroupdevice", "instrumentrack",
})

_MODULATION_REQUIRED_ROLES: frozenset[str] = frozenset({"bass", "pad", "lead", "vox", "atmos"})


def _is_ghost(name: str) -> bool:
    n = (name or "").lower()
    return any(kw in n for kw in _GHOST_KEYWORDS)


def _track_volume(track: dict) -> float | None:
    mixer = track.get("mixer") or {}
    vol = mixer.get("volume")
    return float(vol) if vol is not None else None


def _check_track_count_within_limit(state: dict) -> dict:
    tracks = list(state.get("tracks") or [])
    n = len(tracks)
    if n <= _TRACK_COUNT_WARN:
        severity = "pass"
        summary = f"{n} tracks — within sustainable range (≤{_TRACK_COUNT_WARN})"
        issues: list[dict] = []
    elif n < _TRACK_COUNT_FAIL:
        severity = "warn"
        summary = f"{n} tracks — approaching §7.3 ceiling (warn at >{_TRACK_COUNT_WARN}, fail at ≥{_TRACK_COUNT_FAIL})"
        issues = [{
            "code": "track_count_high",
            "detail": f"{n} tracks present. Consider deleting 1–{n - _TRACK_COUNT_WARN} weakest layers before adding more.",
            "track_index": None,
        }]
    else:
        severity = "fail"
        summary = f"{n} tracks — exceeds §7.3 ceiling (≥{_TRACK_COUNT_FAIL}). 5–6 great layers > {n} mediocre."
        issues = [{
            "code": "track_count_exceeded",
            "detail": f"{n} tracks present. §7.3 demands fewer, better layers — delete the weakest until ≤{_TRACK_COUNT_WARN}.",
            "track_index": None,
        }]
    return {
        "id": "track_count_within_limit",
        "passed": severity in ("pass", "warn"),
        "severity": severity,
        "summary": summary,
        "issues": issues,
        "evidence": {"track_count": n, "warn_threshold": _TRACK_COUNT_WARN, "fail_threshold": _TRACK_COUNT_FAIL},
    }


def _check_no_extreme_buried_track(state: dict) -> dict:
    tracks = list(state.get("tracks") or [])
    buried_non_ghost: list[dict] = []
    buried_ghost: list[dict] = []
    for t in tracks:
        vol = _track_volume(t)
        if vol is None or vol >= _BURIED_THRESHOLD:
            continue
        entry = {"index": t.get("index"), "name": t.get("name"), "volume": round(vol, 3)}
        if _is_ghost(t.get("name") or ""):
            buried_ghost.append(entry)
        else:
            buried_non_ghost.append(entry)

    if not buried_non_ghost:
        return {
            "id": "no_extreme_buried_track",
            "passed": True,
            "severity": "pass",
            "summary": (
                "No buried tracks below 0.15"
                if not buried_ghost
                else f"{len(buried_ghost)} buried track(s) all ghost-tagged — OK"
            ),
            "issues": [],
            "evidence": {"buried_non_ghost": [], "buried_ghost": buried_ghost},
        }

    return {
        "id": "no_extreme_buried_track",
        "passed": False,
        "severity": "fail",
        "summary": f"{len(buried_non_ghost)} non-ghost track(s) at volume < {_BURIED_THRESHOLD} — delete or feature them",
        "issues": [
            {
                "code": "extreme_buried_track",
                "detail": f"Track '{e['name']}' at volume {e['volume']}. §7.3: delete it or feature it, don't bury it.",
                "track_index": e["index"],
            }
            for e in buried_non_ghost
        ],
        "evidence": {"buried_non_ghost": buried_non_ghost, "buried_ghost": buried_ghost, "threshold": _BURIED_THRESHOLD},
    }


def _check_role_volume_hierarchy(state: dict) -> dict:
    tracks = list(state.get("tracks") or [])
    out_of_band: list[dict] = []
    in_band_count = 0
    skipped_unknown = 0
    for t in tracks:
        vol = _track_volume(t)
        if vol is None:
            continue
        role = infer_role(t.get("name") or "", t.get("devices") or [])
        # No role inferred → no expected band → skip. Live's default fader
        # is 0.85 (unity); applying any band to unrecognised tracks fires
        # false positives on every fresh project.
        if role == "unknown":
            skipped_unknown += 1
            continue
        band = _ROLE_VOLUME_BANDS.get(role) or _ROLE_VOLUME_BANDS["unknown"]
        if band[0] <= vol <= band[1]:
            in_band_count += 1
            continue
        out_of_band.append({
            "index": t.get("index"),
            "name": t.get("name"),
            "role": role,
            "volume": round(vol, 3),
            "band": [band[0], band[1]],
            "direction": "above" if vol > band[1] else "below",
        })

    if not out_of_band:
        if in_band_count == 0 and skipped_unknown > 0:
            summary = f"No role-tagged tracks to check ({skipped_unknown} skipped as unknown role)"
        else:
            summary = f"All {in_band_count} role-tagged track(s) within role volume band"
            if skipped_unknown:
                summary += f" ({skipped_unknown} unknown-role skipped)"
        return {
            "id": "role_volume_hierarchy",
            "passed": True,
            "severity": "pass",
            "summary": summary,
            "issues": [],
            "evidence": {
                "in_band": in_band_count,
                "out_of_band": [],
                "skipped_unknown": skipped_unknown,
            },
        }

    return {
        "id": "role_volume_hierarchy",
        "passed": True,  # advisory — flag, don't block
        "severity": "warn",
        "summary": (
            f"{len(out_of_band)} role-tagged track(s) outside role volume band (advisory)"
            + (f" ({skipped_unknown} unknown-role skipped)" if skipped_unknown else "")
        ),
        "issues": [
            {
                "code": "role_volume_off_band",
                "detail": (
                    f"Track '{e['name']}' (role={e['role']}) at volume {e['volume']} — "
                    f"{e['direction']} expected band {e['band']}. "
                    f"{'Pad/atmos shouldn’t dominate.' if e['direction'] == 'above' and e['role'] in ('pad', 'atmos') else ''}"
                    f"{'Anchor role too quiet — should carry.' if e['direction'] == 'below' and e['role'] in ('kick', 'bass', 'vox') else ''}"
                ).strip(),
                "track_index": e["index"],
            }
            for e in out_of_band
        ],
        "evidence": {
            "in_band": in_band_count,
            "out_of_band": out_of_band,
            "skipped_unknown": skipped_unknown,
        },
    }


def _first_instrument_device(devices: list[dict]) -> dict | None:
    for d in devices or []:
        cls = (d.get("class_name") or "").lower()
        if cls in _INSTRUMENT_CLASSES:
            return d
    return None


def _is_banned_default_fingerprint(device: dict) -> bool:
    """Match (class_name, name) against the banned-default fingerprint set.

    Fires only when both class AND device-display-name match a banned synth's
    default-loaded state. A preset-applied device has device.name set to the
    preset stem, so it falls out of the fingerprint set automatically.
    """
    cls = (device.get("class_name") or "").strip().lower()
    name = (device.get("name") or "").strip().lower()
    return (cls, name) in _BANNED_DEFAULT_FINGERPRINTS


def _is_subtractive_exception(track_name: str) -> bool:
    n = (track_name or "").lower()
    return any(kw in n for kw in _SUBTRACTIVE_EXCEPTION_KEYWORDS)


def _check_no_banned_default_instruments(state: dict) -> dict:
    tracks = list(state.get("tracks") or [])
    violations: list[dict] = []
    skipped_exceptions: list[dict] = []
    for t in tracks:
        role = infer_role(t.get("name") or "", t.get("devices") or [])
        if role not in _BANNED_DEFAULT_ROLES:
            continue
        instr = _first_instrument_device(t.get("devices") or [])
        if not instr:
            continue
        if not _is_banned_default_fingerprint(instr):
            continue
        entry = {
            "index": t.get("index"),
            "name": t.get("name"),
            "role": role,
            "class_name": instr.get("class_name"),
            "device_name": instr.get("name"),
        }
        if _is_subtractive_exception(t.get("name") or ""):
            skipped_exceptions.append(entry)
        else:
            violations.append(entry)

    if not violations:
        return {
            "id": "no_banned_default_instruments",
            "passed": True,
            "severity": "pass",
            "summary": (
                "No banned-default synths on melodic-role tracks"
                if not skipped_exceptions
                else f"All banned-default loads explicitly tagged as subtractive ({len(skipped_exceptions)} skipped)"
            ),
            "issues": [],
            "evidence": {"violations": [], "subtractive_exceptions": skipped_exceptions},
        }

    return {
        "id": "no_banned_default_instruments",
        "passed": False,
        "severity": "fail",
        "summary": f"{len(violations)} melodic-role track(s) using banned-default synth (§1)",
        "issues": [
            {
                "code": "banned_default_instrument",
                "detail": (
                    f"Track '{v['name']}' (role={v['role']}) starts with default-loaded "
                    f"{v['class_name']}. §1: hunt the library — atlas_search, search_browser, "
                    "or sample-based / granular / physical-modeling source. "
                    "Tag track name with 'subtractive' if this is a deliberate analog choice."
                ),
                "track_index": v["index"],
            }
            for v in violations
        ],
        "evidence": {"violations": violations, "subtractive_exceptions": skipped_exceptions},
    }


def _check_melodic_layers_have_motion(state: dict) -> dict:
    """§4 — every melodic/harmonic layer should have ≥1 form of motion.

    State must populate per track:
        - modulation_count: int  (sum of mod-matrix non-zero entries)
        - has_clip_automation: bool

    Tracks missing both keys are reported as `unknown` and the check
    degrades to n/a if no track has either signal.
    """
    tracks = list(state.get("tracks") or [])
    static_tracks: list[dict] = []
    moving_tracks: list[dict] = []
    unknown_tracks: list[dict] = []

    for t in tracks:
        role = infer_role(t.get("name") or "", t.get("devices") or [])
        if role not in _MODULATION_REQUIRED_ROLES:
            continue
        mod_count = t.get("modulation_count")
        has_auto = t.get("has_clip_automation")
        if mod_count is None and has_auto is None:
            unknown_tracks.append({
                "index": t.get("index"), "name": t.get("name"), "role": role,
            })
            continue
        has_motion = (mod_count or 0) > 0 or bool(has_auto)
        entry = {
            "index": t.get("index"),
            "name": t.get("name"),
            "role": role,
            "modulation_count": mod_count or 0,
            "has_clip_automation": bool(has_auto),
        }
        (moving_tracks if has_motion else static_tracks).append(entry)

    n_checked = len(moving_tracks) + len(static_tracks)

    if n_checked == 0:
        return {
            "id": "melodic_layers_have_motion",
            "passed": True,
            "severity": "n/a",
            "summary": (
                "No melodic-role tracks present"
                if not unknown_tracks
                else f"Modulation data missing for {len(unknown_tracks)} melodic-role track(s)"
            ),
            "issues": [],
            "evidence": {"moving": [], "static": [], "unknown": unknown_tracks},
        }

    if not static_tracks:
        return {
            "id": "melodic_layers_have_motion",
            "passed": True,
            "severity": "pass",
            "summary": f"All {n_checked} melodic-role layer(s) have modulation or automation",
            "issues": [],
            "evidence": {"moving": moving_tracks, "static": [], "unknown": unknown_tracks},
        }

    return {
        "id": "melodic_layers_have_motion",
        "passed": True,
        "severity": "warn",
        "summary": (
            f"{len(static_tracks)} of {n_checked} melodic-role layer(s) static "
            "(no modulation routings, no clip automation)"
        ),
        "issues": [
            {
                "code": "static_melodic_layer",
                "detail": (
                    f"Track '{t['name']}' (role={t['role']}) has 0 modulation routings "
                    "and no clip automation. §4: add LFO routing, mod-matrix entry, or "
                    "automation curve. Static MIDI at default velocity ≈ 'didn't try'."
                ),
                "track_index": t["index"],
            }
            for t in static_tracks
        ],
        "evidence": {"moving": moving_tracks, "static": static_tracks, "unknown": unknown_tracks},
    }


def _aggregate_per_track(
    *,
    criterion_id: str,
    state: dict,
    args_for_track: Callable[[dict, dict, str], tuple | None],
    check_fn: Callable[..., dict],
    pass_summary: str,
) -> dict:
    """Run an audit check function per track, aggregate into one verdict.

    args_for_track(state, track, role) returns the args tuple for check_fn,
    or None to skip the track entirely. The audit check's own n/a returns
    are filtered out at aggregation time so they don't drag down the result.
    """
    tracks = list(state.get("tracks") or [])
    per_track: list[dict] = []
    for t in tracks:
        role = infer_role(t.get("name") or "", t.get("devices") or [])
        args = args_for_track(state, t, role)
        if args is None:
            continue
        try:
            result = check_fn(*args)
        except Exception as exc:
            per_track.append({
                "track_index": t.get("index"),
                "name": t.get("name"),
                "role": role,
                "severity": "n/a",
                "summary": f"check failed: {type(exc).__name__}",
                "issues": [],
                "evidence": {},
            })
            continue
        per_track.append({
            "track_index": t.get("index"),
            "name": t.get("name"),
            "role": role,
            **result,
        })

    actionable = [r for r in per_track if r["severity"] != "n/a"]

    if not actionable:
        return {
            "id": criterion_id,
            "passed": True,
            "severity": "n/a",
            "summary": "No checkable tracks (data missing or no applicable role)",
            "issues": [],
            "evidence": {"per_track": per_track},
        }

    has_fail = any(r["severity"] == "fail" for r in actionable)
    has_warn = any(r["severity"] == "warn" for r in actionable)

    if has_fail:
        rubric_severity, passed = "fail", False
    elif has_warn:
        rubric_severity, passed = "warn", True
    else:
        rubric_severity, passed = "pass", True

    issues: list[dict] = []
    for r in actionable:
        if r["severity"] in ("warn", "fail"):
            for issue in r.get("issues") or []:
                issues.append({
                    "code": issue.get("code", ""),
                    "detail": f"Track '{r['name']}' (role={r['role']}): {issue.get('detail', '')}",
                    "track_index": r["track_index"],
                })

    n_pass = sum(1 for r in actionable if r["severity"] == "pass")
    n_warn = sum(1 for r in actionable if r["severity"] == "warn")
    n_fail = sum(1 for r in actionable if r["severity"] == "fail")
    summary = (
        pass_summary
        if rubric_severity == "pass"
        else f"{len(actionable)} checked: {n_pass} pass, {n_warn} warn, {n_fail} fail"
    )

    return {
        "id": criterion_id,
        "passed": passed,
        "severity": rubric_severity,
        "summary": summary,
        "issues": issues,
        "evidence": {"per_track": per_track},
    }


def _check_timbre_per_track(state: dict) -> dict:
    return _aggregate_per_track(
        criterion_id="timbre_per_track",
        state=state,
        args_for_track=lambda s, t, role: (role, t.get("fingerprint")),
        check_fn=audit_checks.check_timbre,
        pass_summary="All checked tracks have role-appropriate spectral shape",
    )


def _check_sequence_per_track(state: dict) -> dict:
    return _aggregate_per_track(
        criterion_id="sequence_per_track",
        state=state,
        args_for_track=lambda s, t, role: (role, t.get("notes_per_clip") or []),
        check_fn=audit_checks.check_sequence,
        pass_summary="All MIDI tracks meet sequence bar (humanization + ghosts + variation)",
    )


def _check_stereo_per_track(state: dict) -> dict:
    return _aggregate_per_track(
        criterion_id="stereo_per_track",
        state=state,
        args_for_track=lambda s, t, role: (role, t),
        check_fn=audit_checks.check_stereo,
        pass_summary="No anti-pattern panning detected",
    )


def _check_masking_per_track(state: dict) -> dict:
    masking_report = state.get("masking_report")
    return _aggregate_per_track(
        criterion_id="masking_per_track",
        state=state,
        args_for_track=lambda s, t, role: (t.get("index"), masking_report) if masking_report else None,
        check_fn=audit_checks.check_masking,
        pass_summary="No detected cross-track masking collisions",
    )


def _modulation_args(state: dict, track: dict, role: str) -> tuple | None:
    """Skip tracks that have no instrument-class device.

    `audit_checks.check_modulation` returns 'no_movement' on empty-device
    tracks because routings=0 — but there's nothing on the track to
    modulate. Audio tracks, FX-only buses, and fresh empty tracks are
    not candidates for §4. Pre-filter here.
    """
    devices = track.get("devices") or []
    if _first_instrument_device(devices) is None:
        return None
    return (
        role,
        devices,
        bool(track.get("has_clip_automation")),
        int(track.get("wavetable_mod_routings", 0)),
    )


def _check_modulation_per_track(state: dict) -> dict:
    return _aggregate_per_track(
        criterion_id="modulation_per_track",
        state=state,
        args_for_track=_modulation_args,
        check_fn=audit_checks.check_modulation,
        pass_summary="All instrument tracks have ≥1 modulation routing or automation",
    )


def _check_params_per_track(state: dict) -> dict:
    return _aggregate_per_track(
        criterion_id="params_per_track",
        state=state,
        args_for_track=lambda s, t, role: (role, t.get("devices") or []),
        check_fn=audit_checks.check_params,
        pass_summary="All instrument tracks show evidence of parameter programming (§2)",
    )


def _check_effects_per_track(state: dict) -> dict:
    return _aggregate_per_track(
        criterion_id="effects_per_track",
        state=state,
        args_for_track=lambda s, t, role: (role, t.get("devices") or []),
        check_fn=audit_checks.check_effects,
        pass_summary="Required effects categories present per role",
    )


_RUBRICS: dict[str, list[Callable[[dict], dict]]] = {
    "layer_accumulation": [
        _check_track_count_within_limit,
        _check_no_extreme_buried_track,
        _check_role_volume_hierarchy,
    ],
    "default_preset_check": [
        _check_no_banned_default_instruments,
    ],
    "modulation_presence": [
        _check_melodic_layers_have_motion,
    ],
    "layer_precision": [
        _check_timbre_per_track,
        _check_sequence_per_track,
        _check_stereo_per_track,
        _check_masking_per_track,
        _check_modulation_per_track,
        _check_params_per_track,
        _check_effects_per_track,
    ],
    "sound_design_depth": [
        _check_params_per_track,
    ],
}


def evaluate(rubric_id: str, state: dict[str, Any]) -> dict[str, Any]:
    """Run all checks for a rubric, return aggregated verdict.

    Raises KeyError if rubric_id is unknown.
    """
    checks = _RUBRICS[rubric_id]
    results = [check(state) for check in checks]
    blocking_failed = any(
        not r["passed"] and r["severity"] == "fail" for r in results
    )
    return {
        "rubric_id": rubric_id,
        "passed": not blocking_failed,
        "criteria": results,
    }


def list_rubrics() -> list[str]:
    return list(_RUBRICS.keys())
