"""Node installer contracts for the Max for Live analyzer bundle."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

import pytest


NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node not available")
REPO = Path(__file__).resolve().parents[1]


def test_analyzer_installer_copies_device_and_sibling_bridge(tmp_path: Path):
    env = os.environ.copy()
    env["LIVEPILOT_ANALYZER_DIR"] = str(tmp_path / "Max Audio Effect")
    script = "const r=require('./installer/analyzer.js').installAnalyzer(); console.log(JSON.stringify(r));"
    subprocess.run(
        [NODE, "-e", script], cwd=REPO, env=env, check=True,
        text=True, capture_output=True,
    )

    destination = tmp_path / "Max Audio Effect"
    for filename in ("LivePilot_Analyzer.amxd", "livepilot_bridge.js"):
        assert (destination / filename).read_bytes() == (REPO / "m4l_device" / filename).read_bytes()


def test_analyzer_installer_is_noop_when_files_match(tmp_path: Path):
    env = os.environ.copy()
    env["LIVEPILOT_ANALYZER_DIR"] = str(tmp_path)
    script = "const m=require('./installer/analyzer.js'); m.installAnalyzer(); console.log(JSON.stringify(m.installAnalyzer()));"
    result = subprocess.run(
        [NODE, "-e", script], cwd=REPO, env=env, check=True,
        text=True, capture_output=True,
    )
    assert '"changed":false' in result.stdout
