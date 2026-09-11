"""Tuning System handlers must survive `Song.tuning_system` being None.

None is the DEFAULT state of every Live set — it means "no custom Tuning
System loaded, standard 12-TET" — not an error. All four handlers
dereferenced it unconditionally, so on an ordinary session:

    get_tuning_system -> 'NoneType' object has no attribute 'name'

i.e. the one tool that answers "is my tuning standard?" failed on every
session that was, in fact, standard. `has_feature("tuning_system")` cannot
catch it: that gates on Live >= 12.1 and says nothing about whether a tuning
system is loaded.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
REMOTE_ROOT = ROOT / "remote_script" / "LivePilot"

_POLLUTED = (
    "Live", "remote_script", "remote_script.LivePilot",
    "remote_script.LivePilot.utils", "remote_script.LivePilot.router",
    "remote_script.LivePilot.version_detect", "remote_script.LivePilot.scales",
)


@pytest.fixture(autouse=True)
def _cleanup():
    snap = {n: sys.modules.get(n) for n in _POLLUTED}
    yield
    for n, orig in snap.items():
        sys.modules.pop(n, None) if orig is None else sys.modules.__setitem__(n, orig)


def _load_scales():
    for n in _POLLUTED:
        sys.modules.pop(n, None)
    live = types.ModuleType("Live")

    class _App:
        get_major_version = lambda self: 12
        get_minor_version = lambda self: 4
        get_bugfix_version = lambda self: 5

    live.Application = types.SimpleNamespace(get_application=lambda: _App())
    sys.modules["Live"] = live
    pkg = types.ModuleType("remote_script"); pkg.__path__ = [str(ROOT / "remote_script")]
    sys.modules["remote_script"] = pkg
    lp = types.ModuleType("remote_script.LivePilot"); lp.__path__ = [str(REMOTE_ROOT)]
    sys.modules["remote_script.LivePilot"] = lp

    def _load(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
        return mod

    _load("remote_script.LivePilot.utils", REMOTE_ROOT / "utils.py")
    _load("remote_script.LivePilot.router", REMOTE_ROOT / "router.py")
    _load("remote_script.LivePilot.version_detect", REMOTE_ROOT / "version_detect.py")
    return _load("remote_script.LivePilot.scales", REMOTE_ROOT / "scales.py")


def _song(ts):
    return types.SimpleNamespace(tuning_system=ts)


class _TS:
    name = "Just Intonation"
    pseudo_octave_in_cents = 1200.0
    lowest_note = 0
    highest_note = 127
    reference_pitch = 440.0
    note_tunings = [0.0] * 12


def test_get_reports_12tet_instead_of_crashing():
    scales = _load_scales()
    out = scales.get_tuning_system(_song(None), {})
    assert out["loaded"] is False
    assert out["tuning"] == "12-TET"
    assert out["reference_pitch"] is None, "must not fabricate 440 Hz"
    assert out["note_tunings"] == []


def test_get_still_reports_a_loaded_system():
    scales = _load_scales()
    out = scales.get_tuning_system(_song(_TS()), {})
    assert out["loaded"] is True
    assert out["name"] == "Just Intonation"
    assert out["reference_pitch"] == 440.0


@pytest.mark.parametrize(
    "handler,params",
    [
        ("set_tuning_reference_pitch", {"reference_pitch": 432.0}),
        ("set_tuning_note", {"degree": 0, "cent_offset": 5.0}),
        ("reset_tuning_system", {}),
    ],
)
def test_mutators_explain_that_nothing_is_loaded(handler, params):
    scales = _load_scales()
    with pytest.raises(RuntimeError, match="No Tuning System is loaded"):
        getattr(scales, handler)(_song(None), params)


def test_mutators_still_work_when_one_is_loaded():
    scales = _load_scales()
    song = _song(_TS())
    assert scales.set_tuning_reference_pitch(song, {"reference_pitch": 432.0}) == {
        "reference_pitch": 432.0
    }
