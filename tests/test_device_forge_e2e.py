"""End-to-end test: generate .amxd, verify binary format, verify JSON patcher."""

from __future__ import annotations

import json
import struct
import tempfile
from pathlib import Path

from mcp_server.device_forge.models import DeviceSpec, DeviceType, GenExprParam
from mcp_server.device_forge.builder import build_device, parse_amxd_header
from mcp_server.device_forge.templates import get_template, TEMPLATES


class TestTemplateToDevice:
    def test_lorenz_to_device(self):
        """Build a device from the lorenz template and verify the full binary."""
        t = get_template("lorenz_attractor")
        spec = DeviceSpec(
            name="Wonder Chaos",
            device_type=DeviceType.AUDIO_EFFECT,
            gen_code=t.code,
            description="Lorenz attractor modulation source",
            params=t.params,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = build_device(spec, output_dir=tmpdir)

            assert path.exists()
            data = path.read_bytes()
            assert len(data) > 200

            # Valid header
            header = parse_amxd_header(data)
            assert header["device_type"] == "audio_effect"

            # Valid JSON
            patcher = json.loads(data[32:])
            assert "patcher" in patcher

            # Has gen~ with codebox
            gen_boxes = [b for b in patcher["patcher"]["boxes"]
                         if b["box"].get("text", "").startswith("gen~")]
            assert len(gen_boxes) == 1

            gen_sub = gen_boxes[0]["box"]["patcher"]
            assert gen_sub["classnamespace"] == "dsp.gen"

            # Codebox has safety clipping
            codeboxes = [b for b in gen_sub["boxes"]
                         if b["box"].get("maxclass") == "codebox"]
            assert len(codeboxes) == 1
            assert "clip" in codeboxes[0]["box"]["code"].lower()

    def test_karplus_strong_has_params(self):
        """KS device should have live.dial parameters."""
        t = get_template("karplus_strong")
        spec = DeviceSpec(
            name="KS String",
            device_type=DeviceType.AUDIO_EFFECT,
            gen_code=t.code,
            params=t.params,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = build_device(spec, output_dir=tmpdir)
            data = path.read_bytes()
            patcher = json.loads(data[32:])

            dials = [b for b in patcher["patcher"]["boxes"]
                     if b["box"]["maxclass"] == "live.dial"]
            assert len(dials) == len(t.params)


class TestAllTemplatesProduceValidDevices:
    def test_all_templates(self):
        """Every template should produce a valid .amxd when built."""
        with tempfile.TemporaryDirectory() as tmpdir:
            for tid, template in TEMPLATES.items():
                spec = DeviceSpec(
                    name=f"Test_{tid}",
                    device_type=DeviceType.AUDIO_EFFECT,
                    gen_code=template.code,
                    params=template.params,
                )
                path = build_device(spec, output_dir=tmpdir)
                assert path.exists(), f"Failed to build {tid}"
                data = path.read_bytes()
                assert data[:4] == b"ampf", f"{tid} missing ampf header"

                # JSON should be parseable
                patcher = json.loads(data[32:])
                assert "patcher" in patcher, f"{tid} has no patcher key"

                # Binary sizes should be consistent
                ptch_size = struct.unpack("<I", data[28:32])[0]
                assert ptch_size == len(data) - 32, f"{tid} ptch size mismatch"


class TestInstrumentDevice:
    def test_instrument_from_phase_distortion(self):
        """Build an instrument from the phase distortion template."""
        t = get_template("phase_distortion")
        spec = DeviceSpec(
            name="PD Synth",
            device_type=DeviceType.INSTRUMENT,
            gen_code=t.code,
            params=t.params,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = build_device(spec, output_dir=tmpdir)
            data = path.read_bytes()
            assert data[8:12] == b"iiii"

            patcher = json.loads(data[32:])
            texts = [b["box"]["text"] for b in patcher["patcher"]["boxes"] if "text" in b["box"]]
            assert "midiin" in texts
            assert "plugout~" in texts


class TestMidiEffect:
    def test_midi_effect_device(self):
        spec = DeviceSpec(
            name="MIDI Pass",
            device_type=DeviceType.MIDI_EFFECT,
            gen_code="out1 = in1;",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = build_device(spec, output_dir=tmpdir)
            data = path.read_bytes()
            assert data[8:12] == b"mmmm"
            header = parse_amxd_header(data)
            assert header["device_type"] == "midi_effect"
