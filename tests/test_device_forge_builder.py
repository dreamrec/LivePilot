"""Tests for Device Forge builder — .amxd binary generation."""

from __future__ import annotations

import json
import struct
import tempfile

import pytest

from mcp_server.device_forge.models import DeviceSpec, DeviceType, GenExprParam
from mcp_server.device_forge.builder import (
    build_patcher_json,
    build_amxd_binary,
    build_device,
    parse_amxd_header,
    ABLETON_USER_LIBRARY,
)


class TestBuildPatcherJson:
    def test_audio_effect_has_plugin_plugout(self):
        spec = DeviceSpec(name="Test", device_type=DeviceType.AUDIO_EFFECT, gen_code="out1 = in1;")
        patcher = build_patcher_json(spec)
        texts = [b["box"]["text"] for b in patcher["patcher"]["boxes"] if "text" in b["box"]]
        assert "plugin~" in texts
        assert "plugout~" in texts

    def test_audio_effect_has_gen_tilde(self):
        spec = DeviceSpec(name="Test", device_type=DeviceType.AUDIO_EFFECT, gen_code="out1 = in1 * 0.5;")
        patcher = build_patcher_json(spec)
        gen_boxes = [b for b in patcher["patcher"]["boxes"]
                     if b["box"].get("text", "").startswith("gen~")]
        assert len(gen_boxes) == 1
        gen_patcher = gen_boxes[0]["box"]["patcher"]
        assert gen_patcher["classnamespace"] == "dsp.gen"

    def test_gen_codebox_contains_user_code(self):
        spec = DeviceSpec(
            name="Test", device_type=DeviceType.AUDIO_EFFECT,
            gen_code="History fb(0);\nfb = tanh(in1 + fb * 0.5);\nout1 = fb;",
        )
        patcher = build_patcher_json(spec)
        gen_box = [b for b in patcher["patcher"]["boxes"]
                   if b["box"].get("text", "").startswith("gen~")][0]
        gen_patcher = gen_box["box"]["patcher"]
        codebox = [b for b in gen_patcher["boxes"]
                   if b["box"].get("maxclass") == "codebox"][0]
        assert "History fb(0)" in codebox["box"]["code"]

    def test_audio_effect_connections_exist(self):
        spec = DeviceSpec(name="Test", device_type=DeviceType.AUDIO_EFFECT, gen_code="out1 = in1;")
        patcher = build_patcher_json(spec)
        lines = patcher["patcher"]["lines"]
        assert len(lines) >= 3

    def test_params_create_live_dials(self):
        spec = DeviceSpec(
            name="Test", device_type=DeviceType.AUDIO_EFFECT,
            gen_code="Param freq(440);\nout1 = cycle(freq);",
            params=[GenExprParam(name="freq", default=440, min_val=20, max_val=20000, unit_style=3)],
        )
        patcher = build_patcher_json(spec)
        dials = [b for b in patcher["patcher"]["boxes"] if b["box"]["maxclass"] == "live.dial"]
        assert len(dials) == 1
        assert dials[0]["box"]["varname"] == "freq"

    def test_midi_effect_has_midiin_midiout(self):
        spec = DeviceSpec(name="Test MIDI", device_type=DeviceType.MIDI_EFFECT, gen_code="out1 = in1;")
        patcher = build_patcher_json(spec)
        texts = [b["box"]["text"] for b in patcher["patcher"]["boxes"] if "text" in b["box"]]
        assert "midiin" in texts
        assert "midiout" in texts

    def test_instrument_has_midiin_and_plugout(self):
        spec = DeviceSpec(name="Test Inst", device_type=DeviceType.INSTRUMENT, gen_code="out1 = cycle(440);")
        patcher = build_patcher_json(spec)
        texts = [b["box"]["text"] for b in patcher["patcher"]["boxes"] if "text" in b["box"]]
        assert "midiin" in texts
        assert "plugout~" in texts

    def test_safety_clip_appended(self):
        spec = DeviceSpec(name="Test", device_type=DeviceType.AUDIO_EFFECT, gen_code="out1 = in1 * 100;")
        patcher = build_patcher_json(spec)
        gen_box = [b for b in patcher["patcher"]["boxes"]
                   if b["box"].get("text", "").startswith("gen~")][0]
        gen_patcher = gen_box["box"]["patcher"]
        codebox = [b for b in gen_patcher["boxes"]
                   if b["box"].get("maxclass") == "codebox"][0]
        assert "clip" in codebox["box"]["code"].lower()


class TestBuildAmxdBinary:
    def test_magic_header(self):
        spec = DeviceSpec(name="Test", device_type=DeviceType.AUDIO_EFFECT, gen_code="out1 = in1;")
        data = build_amxd_binary(spec)
        assert data[:4] == b"ampf"

    def test_device_type_marker(self):
        spec = DeviceSpec(name="Test", device_type=DeviceType.AUDIO_EFFECT, gen_code="out1 = in1;")
        data = build_amxd_binary(spec)
        assert data[8:12] == b"aaaa"

    def test_meta_chunk(self):
        spec = DeviceSpec(name="Test", device_type=DeviceType.AUDIO_EFFECT, gen_code="out1 = in1;")
        data = build_amxd_binary(spec)
        assert data[12:16] == b"meta"
        assert struct.unpack("<I", data[20:24])[0] == 0  # unfrozen = 0

    def test_ptch_chunk(self):
        spec = DeviceSpec(name="Test", device_type=DeviceType.AUDIO_EFFECT, gen_code="out1 = in1;")
        data = build_amxd_binary(spec)
        assert data[24:28] == b"ptch"

    def test_no_mxc_for_unfrozen(self):
        """Unfrozen .amxd files have JSON directly at offset 32 — no mx@c wrapper."""
        spec = DeviceSpec(name="Test", device_type=DeviceType.AUDIO_EFFECT, gen_code="out1 = in1;")
        data = build_amxd_binary(spec)
        assert data[32:36] != b"mx@c"
        assert data[32:33] == b"{"  # JSON starts immediately

    def test_json_starts_at_offset_32(self):
        spec = DeviceSpec(name="Test", device_type=DeviceType.AUDIO_EFFECT, gen_code="out1 = in1;")
        data = build_amxd_binary(spec)
        assert data[32:33] == b"{"

    def test_json_is_valid(self):
        spec = DeviceSpec(name="Test", device_type=DeviceType.AUDIO_EFFECT, gen_code="out1 = in1;")
        data = build_amxd_binary(spec)
        patcher = json.loads(data[32:])
        assert "patcher" in patcher

    def test_ptch_size_matches(self):
        spec = DeviceSpec(name="Test", device_type=DeviceType.AUDIO_EFFECT, gen_code="out1 = in1;")
        data = build_amxd_binary(spec)
        ptch_size = struct.unpack("<I", data[28:32])[0]
        assert ptch_size == len(data) - 32

    def test_midi_effect_binary(self):
        spec = DeviceSpec(name="Test", device_type=DeviceType.MIDI_EFFECT, gen_code="out1 = in1;")
        data = build_amxd_binary(spec)
        assert data[8:12] == b"mmmm"


class TestBuildDevice:
    def test_writes_amxd_file(self):
        spec = DeviceSpec(name="Test Device", device_type=DeviceType.AUDIO_EFFECT, gen_code="out1 = in1;")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = build_device(spec, output_dir=tmpdir)
            assert path.exists()
            assert path.suffix == ".amxd"
            assert path.stat().st_size > 100

    def test_filename_is_safe(self):
        spec = DeviceSpec(name="Wonder: Chaos!", device_type=DeviceType.AUDIO_EFFECT, gen_code="out1 = in1;")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = build_device(spec, output_dir=tmpdir)
            assert path.name == "Wonder_Chaos.amxd"


class TestParseAmxdHeader:
    def test_round_trip(self):
        spec = DeviceSpec(name="Test", device_type=DeviceType.AUDIO_EFFECT, gen_code="out1 = in1;")
        data = build_amxd_binary(spec)
        header = parse_amxd_header(data)
        assert header["device_type"] == "audio_effect"
        assert header["ptch_size"] > 0
        assert header["frozen"] is False
        assert header["json_offset"] == 32


class TestAbletonUserLibrary:
    def test_path_is_reasonable(self):
        assert "Ableton" in str(ABLETON_USER_LIBRARY)
        assert "User Library" in str(ABLETON_USER_LIBRARY)
