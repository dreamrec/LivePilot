"""Shared per-track signal fetchers — exercised via fake AbletonConnection."""

from __future__ import annotations

from mcp_server.audit import state


class _FakeAbleton:
    """Minimal AbletonConnection stand-in for testing fetcher helpers."""

    def __init__(self, responses: dict[str, dict | list]):
        self.responses = responses
        self.calls: list[tuple[str, dict]] = []

    def send_command(self, command: str, params: dict | None = None):
        self.calls.append((command, params or {}))
        result = self.responses.get(command)
        if isinstance(result, list):
            # support sequence of responses keyed by call order for the same command
            if not result:
                return None
            return result.pop(0)
        return result


# ── safe_call ───────────────────────────────────────────────────────


def test_safe_call_returns_response():
    fake = _FakeAbleton({"get_session_info": {"track_count": 4}})
    result = state.safe_call(fake, "get_session_info")
    assert result == {"track_count": 4}


def test_safe_call_swallows_exceptions():
    class _Boom:
        def send_command(self, *a, **kw):
            raise RuntimeError("network down")
    assert state.safe_call(_Boom(), "anything") is None


# ── fetch_notes_for_clips ───────────────────────────────────────────


def test_fetch_notes_returns_only_populated_slots():
    fake = _FakeAbleton({"get_notes": {"notes": [{"pitch": 60, "velocity": 100}]}})
    clip_slots = [
        {"index": 0, "has_clip": True},
        {"index": 1, "has_clip": False},
        {"index": 2, "has_clip": True},
    ]
    result = state.fetch_notes_for_clips(fake, track_index=0, clip_slots=clip_slots)
    assert len(result) == 2  # slots 0 + 2
    assert all("pitch" in n for clip in result for n in clip)


def test_fetch_notes_handles_empty_clip_slots_list():
    fake = _FakeAbleton({})
    assert state.fetch_notes_for_clips(fake, 0, []) == []
    assert state.fetch_notes_for_clips(fake, 0, None) == []


def test_fetch_notes_skips_when_command_returns_none():
    fake = _FakeAbleton({"get_notes": None})
    clip_slots = [{"index": 0, "has_clip": True}]
    assert state.fetch_notes_for_clips(fake, 0, clip_slots) == []


# ── has_clip_automation ─────────────────────────────────────────────


def test_has_clip_automation_true_when_envelopes_present():
    fake = _FakeAbleton({"get_clip_automation": {"envelopes": [{"target": "volume"}]}})
    clip_slots = [{"index": 0, "has_clip": True}]
    assert state.has_clip_automation(fake, 0, clip_slots) is True


def test_has_clip_automation_false_on_empty_track():
    fake = _FakeAbleton({})
    assert state.has_clip_automation(fake, 0, []) is False


def test_has_clip_automation_false_when_envelopes_empty():
    fake = _FakeAbleton({"get_clip_automation": {"envelopes": []}})
    clip_slots = [{"index": 0, "has_clip": True}]
    assert state.has_clip_automation(fake, 0, clip_slots) is False


def test_has_clip_automation_accepts_alt_response_key():
    """Response sometimes uses 'automation' instead of 'envelopes'."""
    fake = _FakeAbleton({"get_clip_automation": {"automation": [{"target": "pan"}]}})
    clip_slots = [{"index": 0, "has_clip": True}]
    assert state.has_clip_automation(fake, 0, clip_slots) is True


# ── count_wavetable_routings ────────────────────────────────────────


def test_count_wavetable_routings_skips_non_wavetable_devices():
    fake = _FakeAbleton({})  # never called because no Wavetable
    devices = [{"class_name": "Drift"}, {"class_name": "EQ Eight"}]
    assert state.count_wavetable_routings(fake, 0, devices) == 0


def test_count_wavetable_routings_sums_non_zero_amounts():
    fake = _FakeAbleton({"get_wavetable_mod_matrix": {"matrix": [
        {"source": "lfo1", "target": "filter", "amount": 0.5},
        {"source": "env2", "target": "pitch", "amount": 0.0},
        {"source": "lfo2", "target": "amp", "amount": 0.3},
    ]}})
    devices = [{"class_name": "Wavetable"}]
    assert state.count_wavetable_routings(fake, 0, devices) == 2


def test_count_wavetable_routings_handles_invalid_amount():
    fake = _FakeAbleton({"get_wavetable_mod_matrix": {"matrix": [
        {"source": "lfo1", "target": "filter", "amount": "bad"},
        {"source": "lfo2", "target": "pitch", "amount": 0.4},
    ]}})
    devices = [{"class_name": "Wavetable"}]
    assert state.count_wavetable_routings(fake, 0, devices) == 1


def test_count_wavetable_routings_handles_alt_response_key():
    fake = _FakeAbleton({"get_wavetable_mod_matrix": {"entries": [
        {"amount": 0.6}, {"amount": 0.0}
    ]}})
    devices = [{"class_name": "Wavetable"}]
    assert state.count_wavetable_routings(fake, 0, devices) == 1
