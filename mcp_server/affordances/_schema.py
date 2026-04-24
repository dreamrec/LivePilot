"""Schema validator for affordance-device preset YAML files.

Enforces at test-time that every seed preset file is well-formed. The
runtime loader (``presets.py``) is tolerant of missing optional fields
so the product never crashes on a bad preset; this validator is the
pre-ship gate run by ``tests/test_affordance_presets.py``.

Schema:
    device_slug: str                    # REQUIRED — must match filename stem
    device_class_name: str              # REQUIRED — Ableton's class_name
    presets:                            # REQUIRED — dict[name → PresetRecord]
      <name>:
        description: str                # REQUIRED — human-readable
        param_overrides: dict           # REQUIRED — {name: number|bool|int}, ≥1 entry
        risk_notes: str                 # optional
        suggested_pairings: list[str]   # optional
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


_REQUIRED_TOPLEVEL = {"device_slug", "device_class_name", "presets"}
_REQUIRED_PER_PRESET = {"description", "param_overrides"}
_OPTIONAL_PER_PRESET = {"risk_notes", "suggested_pairings"}


def validate_preset_file(path: Path) -> list[str]:
    """Return a list of validation errors. Empty list = valid.

    Errors are human-readable one-liners suitable for test failure output.
    """
    errors: list[str] = []

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return [f"{path.name}: YAML parse error — {exc}"]

    if not isinstance(data, dict):
        return [
            f"{path.name}: top-level must be a mapping, "
            f"got {type(data).__name__}"
        ]

    missing = _REQUIRED_TOPLEVEL - set(data.keys())
    if missing:
        errors.append(
            f"{path.name}: missing required top-level fields {sorted(missing)}"
        )

    slug = data.get("device_slug")
    if slug is not None and not isinstance(slug, str):
        errors.append(f"{path.name}: device_slug must be a string")
    elif slug and slug != path.stem:
        errors.append(
            f"{path.name}: device_slug {slug!r} must match "
            f"filename stem {path.stem!r}"
        )

    class_name = data.get("device_class_name")
    if class_name is not None and not isinstance(class_name, str):
        errors.append(f"{path.name}: device_class_name must be a string")

    presets = data.get("presets")
    if presets is not None:
        if not isinstance(presets, dict):
            errors.append(f"{path.name}: presets must be a mapping")
        elif not presets:
            errors.append(f"{path.name}: presets dict is empty")
        else:
            for preset_name, preset in presets.items():
                errors.extend(_validate_preset(path.name, preset_name, preset))

    return errors


def _validate_preset(filename: str, name: str, preset: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(preset, dict):
        return [f"{filename}: preset {name!r} must be a mapping"]

    missing = _REQUIRED_PER_PRESET - set(preset.keys())
    if missing:
        errors.append(
            f"{filename}: preset {name!r} missing required fields {sorted(missing)}"
        )

    description = preset.get("description")
    if description is not None and not isinstance(description, str):
        errors.append(f"{filename}: preset {name!r} description must be a string")

    overrides = preset.get("param_overrides")
    if overrides is not None:
        if not isinstance(overrides, dict):
            errors.append(
                f"{filename}: preset {name!r} param_overrides must be a dict"
            )
        elif not overrides:
            errors.append(
                f"{filename}: preset {name!r} param_overrides is empty"
            )
        else:
            for k, v in overrides.items():
                if not isinstance(k, str):
                    errors.append(
                        f"{filename}: preset {name!r} param_overrides key "
                        f"{k!r} must be a string"
                    )
                if not isinstance(v, (int, float, bool)):
                    errors.append(
                        f"{filename}: preset {name!r} param_overrides value for "
                        f"{k!r} must be number|bool, got {type(v).__name__}"
                    )

    pairings = preset.get("suggested_pairings")
    if pairings is not None:
        if not isinstance(pairings, list):
            errors.append(
                f"{filename}: preset {name!r} suggested_pairings must be a list"
            )
        elif not all(isinstance(p, str) for p in pairings):
            errors.append(
                f"{filename}: preset {name!r} suggested_pairings entries "
                f"must be strings"
            )

    risk_notes = preset.get("risk_notes")
    if risk_notes is not None and not isinstance(risk_notes, str):
        errors.append(f"{filename}: preset {name!r} risk_notes must be a string")

    extras = set(preset.keys()) - _REQUIRED_PER_PRESET - _OPTIONAL_PER_PRESET
    if extras:
        errors.append(
            f"{filename}: preset {name!r} has unknown fields {sorted(extras)} "
            f"(allowed: {sorted(_REQUIRED_PER_PRESET | _OPTIONAL_PER_PRESET)})"
        )

    return errors
