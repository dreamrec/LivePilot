from __future__ import annotations

import json

from mcp_server.lifecycle_log import lifecycle_event


def test_lifecycle_event_writes_jsonl(tmp_path, monkeypatch):
    log_path = tmp_path / "lifecycle.jsonl"
    monkeypatch.setenv("LIVEPILOT_LIFECYCLE_LOG", str(log_path))

    lifecycle_event("unit_test_event", detail="ok")

    records = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
    ]
    assert len(records) == 1
    assert records[0]["event"] == "unit_test_event"
    assert records[0]["detail"] == "ok"
    assert isinstance(records[0]["pid"], int)
