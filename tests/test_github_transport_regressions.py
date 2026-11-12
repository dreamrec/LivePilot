"""#104: model transport writes that Live applies on a later main-thread tick."""
import importlib
from types import SimpleNamespace

import pytest

from tests.test_remote_arrangement_clip_tools import _load_arrangement_module


class QueuedSong:
    def __init__(self, playing=False):
        self.is_playing = playing
        self._time = 385.0
        self.marker = 49.0
        self.loop = False
        self.tracks = []
        self.back_to_arranger = False
        self.pending = []
        self.stops = 0
        self.starts = 0

    @property
    def current_song_time(self):
        return self._time

    @current_song_time.setter
    def current_song_time(self, value):
        self.pending.append(lambda: setattr(self, '_time', value))

    def tick(self):
        pending, self.pending = self.pending, []
        for fn in pending:
            fn()

    def stop_playing(self):
        self.stops += 1
        def stop():
            self.is_playing = False
            self._time = self.marker
        self.pending.append(stop)

    def start_playing(self):
        self.starts += 1
        def start():
            self.is_playing = True
            self._time = self.marker
        self.pending.append(start)

    def continue_playing(self):
        self.starts += 1
        cursor = self._time
        def start():
            self.is_playing = True
            self._time = cursor
        self.pending.append(start)


def settle(result, song, deferred_type):
    for _ in range(10):
        if not isinstance(result, deferred_type):
            return result
        song.tick()
        result = result.resume()
    pytest.fail('transport operation never completed')


@pytest.mark.parametrize('playing', [False, True])
@pytest.mark.parametrize('play', [False, True])
@pytest.mark.parametrize('target', [0.0, 4.0, 192.0])
def test_force_arrangement_keeps_requested_position_across_live_ticks(playing, play, target):
    arr = _load_arrangement_module()
    song = QueuedSong(playing)
    result = settle(arr.force_arrangement(song, {'beat_time': target, 'play': play}),
                    song, arr.DeferredResult)
    assert result['position'] == target
    assert result['is_playing'] is play
    assert song.current_song_time == target
    assert song.stops == int(playing and not play)
    assert song.starts == int(play and not playing)


def test_repeated_stop_preserves_user_cursor():
    _load_arrangement_module()
    transport = importlib.import_module('remote_script.LivePilot.transport')
    song = QueuedSong(False)
    transport.stop_playback(song, {})
    song.tick()
    assert song.stops == 0
    assert song.current_song_time == 385


def test_stopped_cue_jump_updates_continue_cursor():
    arr = _load_arrangement_module()
    transport = importlib.import_module('remote_script.LivePilot.transport')
    song = QueuedSong(False)
    cue = SimpleNamespace(time=192, jump=lambda: setattr(song, 'marker', 192))
    song.cue_points = [cue]
    result = settle(arr.jump_to_cue(song, {'cue_index': 0}), song, arr.DeferredResult)
    transport.continue_playback(song, {})
    song.tick()
    assert result['position'] == 192
    assert song.current_song_time == 192
    assert song.is_playing


def test_router_maps_deferred_failures_to_original_request():
    arr = _load_arrangement_module()
    router = importlib.import_module('remote_script.LivePilot.router')
    def fail():
        raise ValueError('bad seek')
    router._handlers['delayed_failure'] = lambda song, params: arr.DeferredResult(fail)
    result = router.dispatch(None, {'id': 'seek-1', 'type': 'delayed_failure'})
    response = result.resume()
    assert response['id'] == 'seek-1'
    assert response['ok'] is False
    assert response['error']['code'] == 'INVALID_PARAM'


def test_server_waits_for_deferred_main_thread_work_before_reply():
    arr = _load_arrangement_module()
    remote_server = importlib.import_module('remote_script.LivePilot.server')
    import queue
    import threading
    song = QueuedSong(False)
    callbacks = []
    cs = SimpleNamespace(song=lambda: song,
                         schedule_message=lambda delay, callback: callbacks.append(callback))
    server = remote_server.LivePilotServer(cs)
    responses = queue.Queue()
    state = SimpleNamespace(lock=threading.Lock(), cancelled=False, committed=False)
    server._command_queue.put(({'id': 'seek', 'type': 'force_arrangement',
                                'params': {'beat_time': 192}}, responses, state))
    server._process_next_command()
    assert responses.empty()
    while callbacks:
        song.tick()
        callbacks.pop(0)()
    response = responses.get_nowait()
    assert response['ok']
    assert response['result']['position'] == 192
    assert response['result']['is_playing']


def test_old_server_hot_reload_fails_before_transport_mutation(monkeypatch):
    arr = _load_arrangement_module()
    server = importlib.import_module('remote_script.LivePilot.server')
    monkeypatch.setattr(server.LivePilotServer, 'supports_deferred_results', False)
    song = QueuedSong(True)
    with pytest.raises(RuntimeError, match='Ableton restart'):
        arr.force_arrangement(song, {'beat_time': 192})
    assert not song.pending
    assert song.stops == 0
