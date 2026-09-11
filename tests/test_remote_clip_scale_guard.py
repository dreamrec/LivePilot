"""Per-clip scale handlers must fail clearly when the LOM lacks the API.

`get_clip_scale` / `set_clip_scale` / `set_clip_scale_mode` were written
assuming Live 12 publishes per-clip scale (`Clip.root_note` / `scale_name` /
`scale_mode`) alongside the Song-level scale API. It does not. Verified on
Live 12.4.5: a MIDI clip's `dir()` contains no scale attribute of any kind,
so every call died with an opaque

    AttributeError: 'Clip' object has no attribute 'root_note'

which gave no hint that the capability was simply absent, nor that the
song-level tools do work. `has_feature("song_scale_api")` cannot catch it —
that is a version comparison against 12.0 gating a *different* capability.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
REMOTE_ROOT = ROOT / "remote_script" / "LivePilot"

_POLLUTED_MODULES = (
    "Live",
    "remote_script",
    "remote_script.LivePilot",
    "remote_script.LivePilot.utils",
    "remote_script.LivePilot.router",
    "remote_script.LivePilot.version_detect",
    "remote_script.LivePilot.clips",
)


@pytest.fixture(autouse=True)
def _cleanup_sys_modules():
    snapshot = {name: sys.modules.get(name) for name in _POLLUTED_MODULES}
    yield
    for name, original in snapshot.items():
        if original is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = original


def _load_clips_module():
    for name in _POLLUTED_MODULES:
        sys.modules.pop(name, None)

    live = types.ModuleType("Live")

    class _App:
        def get_major_version(self):
            return 12

        def get_minor_version(self):
            return 4

        def get_bugfix_version(self):
            return 5

    live.Application = types.SimpleNamespace(get_application=lambda: _App())
    sys.modules["Live"] = live

    remote_pkg = types.ModuleType("remote_script")
    remote_pkg.__path__ = [str(ROOT / "remote_script")]
    sys.modules["remote_script"] = remote_pkg

    live_pkg = types.ModuleType("remote_script.LivePilot")
    live_pkg.__path__ = [str(REMOTE_ROOT)]
    sys.modules["remote_script.LivePilot"] = live_pkg

    def _load(name: str, path: Path):
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module

    _load("remote_script.LivePilot.utils", REMOTE_ROOT / "utils.py")
    _load("remote_script.LivePilot.router", REMOTE_ROOT / "router.py")
    _load(
        "remote_script.LivePilot.version_detect",
        REMOTE_ROOT / "version_detect.py",
    )
    return _load("remote_script.LivePilot.clips", REMOTE_ROOT / "clips.py")


class _ClipWithoutScale:
    """Live 12.4.5's real Clip: no scale attributes whatsoever."""

    is_midi_clip = True


class _ClipWithScale:
    """A hypothetical future Live that does publish per-clip scale."""

    is_midi_clip = True
    root_note = 9
    scale_name = "Minor Blues"
    scale_mode = True


def _song(clip):
    slot = types.SimpleNamespace(has_clip=True, clip=clip)
    track = types.SimpleNamespace(clip_slots=[slot])
    return types.SimpleNamespace(tracks=[track], scale_names=["Major", "Minor Blues"])


ARGS = {"track_index": 0, "clip_index": 0}


@pytest.mark.parametrize(
    "handler,params",
    [
        ("get_clip_scale", ARGS),
        ("set_clip_scale", {**ARGS, "root_note": 9, "scale_name": "Minor Blues"}),
        ("set_clip_scale_mode", {**ARGS, "enabled": True}),
    ],
)
def test_absent_clip_scale_api_raises_actionable_error(handler, params):
    clips = _load_clips_module()
    fn = getattr(clips, handler)
    with pytest.raises(RuntimeError) as exc:
        fn(_song(_ClipWithoutScale()), params)
    message = str(exc.value)
    assert "not exposed" in message
    assert "set_song_scale" in message, "must point at the tool that does work"
    assert "12.4.5" in message, "must name the Live version actually measured"


def test_guard_is_transparent_when_the_api_exists():
    """The guard must not block a future Live that does publish it."""
    clips = _load_clips_module()
    result = clips.get_clip_scale(_song(_ClipWithScale()), ARGS)
    assert result == {"root_note": 9, "scale_mode": True, "scale_name": "Minor Blues"}


def test_guard_does_not_swallow_an_empty_slot():
    clips = _load_clips_module()
    song = _song(_ClipWithoutScale())
    song.tracks[0].clip_slots[0].has_clip = False
    with pytest.raises(ValueError, match="empty"):
        clips.get_clip_scale(song, ARGS)
