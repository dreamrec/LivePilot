"""Tests for Device Forge models — pure data, no I/O."""

from __future__ import annotations

import pytest

from mcp_server.device_forge.models import (
    DeviceType,
    DeviceSpec,
    GenExprParam,
    GenExprTemplate,
)


class TestDeviceType:
    def test_audio_effect_values(self):
        dt = DeviceType.AUDIO_EFFECT
        assert dt.ampf_marker == b"aaaa"
        assert dt.meta_value == 7
        assert dt.title == "Max Audio Effect"
        assert dt.required_io == ("plugin~", "plugout~")

    def test_midi_effect_values(self):
        dt = DeviceType.MIDI_EFFECT
        assert dt.ampf_marker == b"mmmm"
        assert dt.title == "Max MIDI Effect"
        assert dt.required_io == ("midiin", "midiout")

    def test_instrument_values(self):
        dt = DeviceType.INSTRUMENT
        assert dt.ampf_marker == b"iiii"
        assert dt.title == "Max Instrument"
        assert dt.required_io == ("midiin", "plugout~")


class TestGenExprParam:
    def test_defaults(self):
        p = GenExprParam(name="freq")
        assert p.name == "freq"
        assert p.default == 0.5
        assert p.min_val == 0.0
        assert p.max_val == 1.0
        assert p.unit_style == 1  # float

    def test_to_genexpr(self):
        p = GenExprParam(name="freq", default=440, min_val=20, max_val=20000)
        code = p.to_genexpr()
        assert "Param freq" in code
        assert "440" in code

    def test_to_live_dial_json(self):
        p = GenExprParam(name="Cutoff", default=1000, min_val=20, max_val=20000, unit_style=3)
        dial = p.to_live_dial_json(obj_id="obj-p1", rect=[10, 10, 44, 48])
        assert dial["box"]["maxclass"] == "live.dial"
        assert dial["box"]["parameter_enable"] == 1
        sa = dial["box"]["saved_attribute_attributes"]["valueof"]
        assert sa["parameter_mmin"] == 20
        assert sa["parameter_mmax"] == 20000


class TestGenExprTemplate:
    def test_creation(self):
        t = GenExprTemplate(
            template_id="lorenz",
            name="Lorenz Attractor",
            description="Chaotic modulation source",
            category="chaos",
            code="History x(0.1);\nout1 = x;",
            params=[GenExprParam(name="speed", default=0.001)],
        )
        assert t.template_id == "lorenz"
        assert "History" in t.code

    def test_to_dict(self):
        t = GenExprTemplate(
            template_id="test",
            name="Test",
            description="desc",
            category="test",
            code="out1 = in1;",
            params=[],
        )
        d = t.to_dict()
        assert d["template_id"] == "test"
        assert "code" not in d  # to_dict should not expose raw code


class TestDeviceSpec:
    def test_audio_effect_spec(self):
        spec = DeviceSpec(
            name="My Effect",
            device_type=DeviceType.AUDIO_EFFECT,
            description="Test effect",
            gen_code="out1 = in1 * 0.5;",
            params=[GenExprParam(name="gain", default=0.5)],
        )
        assert spec.name == "My Effect"
        assert spec.device_type == DeviceType.AUDIO_EFFECT

    def test_safe_filename(self):
        spec = DeviceSpec(
            name="Wonder: Chaos Mod!",
            device_type=DeviceType.AUDIO_EFFECT,
            gen_code="out1 = in1;",
        )
        assert spec.safe_filename == "Wonder_Chaos_Mod.amxd"
