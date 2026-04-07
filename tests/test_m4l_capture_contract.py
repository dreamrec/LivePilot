import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRIDGE_JS = ROOT / "m4l_device" / "livepilot_bridge.js"
MAXPAT = ROOT / "m4l_device" / "LivePilot_Analyzer.maxpat"


def test_capture_js_reports_absolute_file_path_and_stop_signal():
    text = BRIDGE_JS.read_text()

    assert "var capture_file_path = \"\";" in text
    assert 'outlet(1, "capture_start", capture_file_path, num_samples);' in text
    assert 'outlet(1, "capture_stop");' in text
    assert "function _to_posix_path(path)" in text
    assert '"file_path": _to_posix_path(written_path)' in text
    assert "capture_file_path = _join_path(_get_captures_dir(), capture_filename);" in text


def test_maxpat_contains_real_capture_recording_chain():
    data = json.loads(MAXPAT.read_text())
    boxes = {box["box"]["id"]: box["box"] for box in data["patcher"]["boxes"]}
    lines = [line["patchline"] for line in data["patcher"]["lines"]]

    assert boxes["obj-route-status"]["text"] == "route status key capture_start capture_stop"
    assert boxes["obj-capture-unpack"]["text"] == "unpack s i"
    assert boxes["obj-capture-trigger"]["text"] == "t b s"
    assert boxes["obj-capture-record-delay"]["text"] == "delay 20"
    assert boxes["obj-capture-open"]["text"] == "prepend open"
    assert boxes["obj-capture-record-on"]["text"] == "1"
    assert boxes["obj-capture-record-off"]["text"] == "0"
    assert boxes["obj-capture-rec"]["text"] == "sfrecord~ 2"

    edges = {
        (tuple(line["source"]), tuple(line["destination"]))
        for line in lines
    }
    assert (("obj-route-status", 2), ("obj-capture-unpack", 0)) in edges
    assert (("obj-capture-unpack", 0), ("obj-capture-trigger", 0)) in edges
    assert (("obj-capture-trigger", 1), ("obj-capture-open", 0)) in edges
    assert (("obj-capture-trigger", 0), ("obj-capture-record-delay", 0)) in edges
    assert (("obj-capture-record-delay", 0), ("obj-capture-record-on", 0)) in edges
    assert (("obj-capture-open", 0), ("obj-capture-rec", 0)) in edges
    assert (("obj-capture-record-on", 0), ("obj-capture-rec", 0)) in edges
    assert (("obj-route-status", 3), ("obj-capture-record-off", 0)) in edges
    assert (("obj-capture-record-off", 0), ("obj-capture-rec", 0)) in edges
    assert (("obj-1", 0), ("obj-capture-rec", 0)) in edges
    assert (("obj-1", 1), ("obj-capture-rec", 1)) in edges
