"""Tests for the v1.21 minimal affordance preset library.

Covers: schema validation per seed file, loader resolution, missing
device/preset handling, and the configure_device compiler's preset
resolution path (preset → param_overrides + explicit-overrides-win merge).

Plan reference: docs/plans/v1.21-structural-plan.md §4.2,
docs/plans/v1.21-implementation-plan.md Task 4.3 + 4.4.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mcp_server.affordances import (
    resolve_preset, list_devices, list_presets, get_preset_metadata,
)
from mcp_server.affordances._schema import validate_preset_file


_SEED_DEVICE_SLUGS = {"reverb", "delay", "auto-filter"}
_AFFORDANCES_DEVICES = (
    Path(__file__).resolve().parent.parent
    / "mcp_server" / "affordances" / "devices"
)


class TestSchemaValidation:
    """Every seed YAML must validate cleanly at ship time — this is the
    pre-ship gate enforced at CI."""

    @pytest.mark.parametrize("slug", sorted(_SEED_DEVICE_SLUGS))
    def test_seed_file_validates(self, slug):
        path = _AFFORDANCES_DEVICES / f"{slug}.yaml"
        errors = validate_preset_file(path)
        assert errors == [], f"{slug}.yaml validation errors: {errors}"


class TestLoader:
    """Runtime loader happy paths + error cases. Loader is tolerant
    (returns None on any error) so production code never crashes."""

    def test_list_devices_returns_all_3_seed_slugs(self):
        devs = set(list_devices())
        assert _SEED_DEVICE_SLUGS.issubset(devs), (
            f"expected all seed slugs; got {sorted(devs)}"
        )

    def test_list_presets_for_reverb(self):
        presets = list_presets("reverb")
        assert "dub-cathedral" in presets

    def test_resolve_preset_reverb_dub_cathedral_returns_expected_keys(self):
        d = resolve_preset("reverb", "dub-cathedral")
        assert d is not None
        expected_keys = {"Decay Time", "Room Size", "Dry/Wet", "Predelay", "Diffusion"}
        assert set(d.keys()) == expected_keys, (
            f"expected {expected_keys}, got {set(d.keys())}"
        )

    def test_resolve_preset_unknown_device_returns_None(self):
        assert resolve_preset("nonexistent-device", "any") is None

    def test_resolve_preset_unknown_preset_returns_None(self):
        assert resolve_preset("reverb", "nonexistent-preset") is None

    def test_get_preset_metadata_includes_description_and_pairings(self):
        meta = get_preset_metadata("reverb", "dub-cathedral")
        assert meta is not None
        assert "description" in meta and meta["description"], (
            "dub-cathedral should have a non-empty description"
        )
        assert meta.get("suggested_pairings") == ["Echo", "Auto Filter"]

    def test_delay_16th_note_is_6_dotted_eighth(self):
        """Pin the Delay 16th Note value (dotted 8th = 6/16) in a test
        rather than relying on a YAML comment to keep the intent
        self-describing."""
        d = resolve_preset("delay", "ping-pong-dub")
        assert d is not None
        assert d["16th Note"] == 6


class TestConfigureDeviceCompilerPresetResolution:
    """The configure_device compiler must resolve `preset` into
    ``param_overrides``, and explicit ``param_overrides`` entries must
    win entry-by-entry on conflict (last-write-wins at dict-key granularity)."""

    def test_preset_alone_resolves_to_param_overrides(self):
        import mcp_server.semantic_moves  # noqa: F401 — registrations
        from mcp_server.semantic_moves import compiler as move_compiler
        from mcp_server.semantic_moves.registry import get_move

        move = get_move("configure_device")
        kernel = {
            "seed_args": {
                "track_index": 0,
                "device_index": 0,
                "device_slug": "reverb",
                "preset": "dub-cathedral",
            },
            "session_info": {},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        assert plan.executable, f"plan not executable: {plan.warnings}"
        batch = [s for s in plan.steps if s.tool == "batch_set_parameters"][0]
        params = batch.params["parameters"]
        names = {p["name_or_index"] for p in params}
        assert "Decay Time" in names
        assert "Room Size" in names
        # Wire format still enforced — each entry uses name_or_index not parameter_name.
        for entry in params:
            assert "name_or_index" in entry and "value" in entry

    def test_explicit_param_overrides_win_on_conflict(self):
        """Preset resolves first, explicit overrides merge on top —
        per-key last-write-wins."""
        import mcp_server.semantic_moves  # noqa: F401
        from mcp_server.semantic_moves import compiler as move_compiler
        from mcp_server.semantic_moves.registry import get_move

        move = get_move("configure_device")
        kernel = {
            "seed_args": {
                "track_index": 0,
                "device_index": 0,
                "device_slug": "reverb",
                "preset": "dub-cathedral",
                "param_overrides": {"Decay Time": 0.5},  # override ONE entry
            },
            "session_info": {},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        assert plan.executable, f"plan not executable: {plan.warnings}"
        batch = [s for s in plan.steps if s.tool == "batch_set_parameters"][0]
        by_name = {p["name_or_index"]: p["value"] for p in batch.params["parameters"]}
        # Explicit Decay Time wins over preset's 0.85
        assert by_name["Decay Time"] == 0.5
        # Preset's Room Size survives unchanged
        assert by_name["Room Size"] == 0.95

    def test_preset_without_device_slug_rejects(self):
        """v1.21 contract: `preset` requires `device_slug`. v1.22 adds
        auto-inference from class_name."""
        import mcp_server.semantic_moves  # noqa: F401
        from mcp_server.semantic_moves import compiler as move_compiler
        from mcp_server.semantic_moves.registry import get_move

        move = get_move("configure_device")
        kernel = {
            "seed_args": {
                "track_index": 0,
                "device_index": 0,
                "preset": "dub-cathedral",
                # device_slug missing
            },
            "session_info": {},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        assert not plan.executable
        joined = " ".join(plan.warnings).lower()
        assert "device_slug" in joined, (
            f"warning should mention device_slug; got: {plan.warnings}"
        )

    def test_preset_unknown_device_rejects_with_path_hint(self):
        """When device_slug points at a missing YAML, the warning
        should point at the expected file path."""
        import mcp_server.semantic_moves  # noqa: F401
        from mcp_server.semantic_moves import compiler as move_compiler
        from mcp_server.semantic_moves.registry import get_move

        move = get_move("configure_device")
        kernel = {
            "seed_args": {
                "track_index": 0,
                "device_index": 0,
                "device_slug": "nonexistent-slug",
                "preset": "any",
            },
            "session_info": {},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        assert not plan.executable
        joined = " ".join(plan.warnings)
        assert "nonexistent-slug" in joined, (
            f"warning should include the unknown slug for triage; "
            f"got: {plan.warnings}"
        )

    def test_back_compat_param_overrides_only_still_works(self):
        """Callers passing only `param_overrides` (no preset/device_slug)
        must work unchanged — the preset seed_args are additive."""
        import mcp_server.semantic_moves  # noqa: F401
        from mcp_server.semantic_moves import compiler as move_compiler
        from mcp_server.semantic_moves.registry import get_move

        move = get_move("configure_device")
        kernel = {
            "seed_args": {
                "track_index": 0,
                "device_index": 0,
                "param_overrides": {"Decay Time": 0.85, "Dry/Wet": 0.35},
            },
            "session_info": {},
            "mode": "improve",
        }
        plan = move_compiler.compile(move, kernel)
        assert plan.executable
        batch = [s for s in plan.steps if s.tool == "batch_set_parameters"][0]
        names = {p["name_or_index"] for p in batch.params["parameters"]}
        assert names == {"Decay Time", "Dry/Wet"}
