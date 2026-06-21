from __future__ import annotations

import json
import struct
from pathlib import Path

from scripts import build_pitch_glide_amxd


def _extract_amxd_json(path: Path) -> dict:
    data = path.read_bytes()
    ptch_idx = data.find(b"ptch")
    assert ptch_idx >= 0
    ptch_len = struct.unpack("<I", data[ptch_idx + 4 : ptch_idx + 8])[0]
    payload = data[ptch_idx + 8 : ptch_idx + 8 + ptch_len]
    return build_pitch_glide_amxd.extract_json(payload)


def test_pitch_glide_builder_outputs_mpe_midi_effect(tmp_path: Path):
    template = build_pitch_glide_amxd.find_template()
    out_amxd = tmp_path / "LivePilot_Pitch_Glide.amxd"
    out_maxpat = tmp_path / "LivePilot_Pitch_Glide.maxpat"

    build_pitch_glide_amxd.build(template, out_amxd, out_maxpat)

    patch = _extract_amxd_json(out_amxd)["patcher"]
    assert patch["is_mpe"] == 1
    assert patch["project"]["amxdtype"] == 1835887981
    assert any(
        box["box"].get("text") == "js livepilot_pitch_glide.js"
        for box in patch["boxes"]
    )
    assert any(
        box["box"].get("varname") == "Enabled"
        for box in patch["boxes"]
    )

    maxpat = json.loads(out_maxpat.read_text())
    assert maxpat["patcher"]["digest"] == "LivePilot Pitch Glide"
