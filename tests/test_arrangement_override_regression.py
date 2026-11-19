"""#115: the lit Back to Arrangement indicator means Session override."""
from types import SimpleNamespace

from tests.test_remote_arrangement_clip_tools import (
    _FakeSong,
    _cleanup_sys_modules,  # noqa: F401 — restore the imported Remote Script doubles.
    _load_arrangement_module,
)


class StickyOverrideSong(_FakeSong):
    """Model Live retaining or reasserting Session override after a write."""

    @property
    def back_to_arranger(self):
        return True

    @back_to_arranger.setter
    def back_to_arranger(self, value):
        pass


def test_back_to_arranger_clears_session_override_and_reports_state():
    arr = _load_arrangement_module()
    song = _FakeSong([])
    assert song.back_to_arranger is True

    result = arr.back_to_arranger(song, {})

    assert song.back_to_arranger is False
    assert result['back_to_arranger'] is True  # Existing action acknowledgment.
    assert result['back_to_arranger_lit'] is False
    assert result['arrangement_active'] is True
    assert song.is_playing is False
    assert song.current_song_time == 13.0


def test_back_to_arranger_reports_override_that_remains_lit():
    arr = _load_arrangement_module()
    result = arr.back_to_arranger(StickyOverrideSong([]), {})
    assert result['back_to_arranger_lit'] is True
    assert result['arrangement_active'] is False


def test_force_arrangement_does_not_claim_success_when_override_remains():
    arr = _load_arrangement_module()
    song = StickyOverrideSong([])
    result = arr.force_arrangement(song, {'play': False})
    while isinstance(result, arr.DeferredResult):
        result = result.resume()
    assert result['stop_errors'] == []
    assert result['back_to_arranger_lit'] is True
    assert result['arrangement_active'] is False
    assert 'warning' in result


def test_session_record_clears_override_before_starting_and_firing(monkeypatch):
    arr = _load_arrangement_module()
    seen = []
    slot = SimpleNamespace(has_clip=True, clip=SimpleNamespace())
    track = SimpleNamespace(can_be_armed=True, clip_slots=[slot], arm=False)
    song = _FakeSong([track])
    song.tempo = 120
    song.record_mode = False

    def start():
        seen.append(('start', song.back_to_arranger, song.current_song_time))
        song.is_playing = True

    def fire():
        seen.append(('fire', song.back_to_arranger, song.current_song_time))
        # Firing the source clip is intentional and may re-light the button.
        song.back_to_arranger = True

    song.start_playing = start
    slot.fire = fire
    monkeypatch.setattr(arr, '_set_clip_automation_handler', lambda *_: {'ok': True})

    result = arr.arrangement_automation_via_session_record_start(song, {
        'track_index': 0,
        'target_beat': 32,
        'parameter_type': 'volume',
        'points': [{'time': 0, 'value': 0.5}],
    })

    assert seen == [('start', False, 32.0), ('fire', False, 32.0)]
    assert song.record_mode is True
    assert track.arm is True
    assert result['status'] == 'recording'
