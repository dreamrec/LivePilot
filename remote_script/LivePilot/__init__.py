"""
LivePilot - Ableton Live 12 Remote Script.

Entry point for the ControlSurface. Ableton calls create_instance(c_instance)
when this script is selected in Preferences > Link, Tempo & MIDI.
"""

__version__ = "1.10.7"

from _Framework.ControlSurface import ControlSurface
from . import router
from .server import LivePilotServer
from . import transport    # noqa: F401  — registers transport handlers
from . import tracks       # noqa: F401  — registers track handlers
from . import clips        # noqa: F401  — registers clip handlers
from . import notes        # noqa: F401  — registers note handlers
from . import devices      # noqa: F401  — registers device handlers
from . import scenes       # noqa: F401  — registers scene handlers
from . import mixing       # noqa: F401  — registers mixing handlers
from . import browser      # noqa: F401  — registers browser handlers
from . import arrangement  # noqa: F401  — registers arrangement handlers
from . import diagnostics       # noqa: F401  — registers diagnostics handler
from . import clip_automation   # noqa: F401  — registers clip automation handlers
from . import version_detect    # noqa: F401  — version detection


# ── Reload plumbing (BUG-B-reload, Batch 20) ──────────────────────────────
# Ableton keeps `sys.modules["LivePilot.*"]` cached across Control Surface
# toggles. Without intervention, edits to handler files don't take effect
# until a full Ableton restart — the toggle just re-instantiates the
# ControlSurface class without re-importing submodules.
#
# Fix: track whether this is the first create_instance call per
# interpreter lifetime. On subsequent calls, force-reload the router
# (which clears _handlers) and every handler module (which re-fires
# @register decorators with the updated code). Result: a Control Surface
# toggle now behaves like a fresh module reload, so live-editing mixing.py
# / devices.py / etc. and re-toggling is enough — no Ableton restart.

_FIRST_CREATE_INSTANCE = True

_HANDLER_MODULES = (
    transport, tracks, clips, notes, devices, scenes,
    mixing, browser, arrangement, diagnostics,
    clip_automation, version_detect,
)


def _force_reload_handlers():
    """Force Python to re-read the handler modules from disk.

    Called on every create_instance() except the first, so edits to
    handler files take effect via Control Surface toggle without
    restarting Ableton. Order matters: router first (clears _handlers),
    then each handler module (re-registers its @register decorators).
    """
    import importlib
    try:
        importlib.reload(router)
    except Exception:
        pass
    for mod in _HANDLER_MODULES:
        try:
            importlib.reload(mod)
        except Exception:
            # Don't block Ableton startup on a single bad reload —
            # the stale version will still work for that handler
            pass


def create_instance(c_instance):
    """Factory function called by Ableton Live.

    Called once on initial Control Surface enable, AND every time the
    user toggles the Control Surface off and on. The reload path below
    makes the toggle behave like a fresh import — crucial for dev
    ergonomics when iterating on mixing.py / devices.py / etc.
    """
    global _FIRST_CREATE_INSTANCE
    if not _FIRST_CREATE_INSTANCE:
        _force_reload_handlers()
    _FIRST_CREATE_INSTANCE = False
    return LivePilot(c_instance)


class LivePilot(ControlSurface):
    """Main ControlSurface that starts the LivePilot TCP server."""

    def __init__(self, c_instance):
        ControlSurface.__init__(self, c_instance)
        self._server = LivePilotServer(self)
        self._server.start()
        self.log_message("LivePilot v%s starting..." % __version__)
        self.show_message("LivePilot v%s starting..." % __version__)
        v = version_detect.version_string()
        self.log_message("LivePilot detected Ableton Live %s" % v)
        features = version_detect.get_api_features()
        enabled = [k for k, flag in features.items() if flag]
        if enabled:
            self.log_message("  Enabled features: %s" % ", ".join(enabled))

    def disconnect(self):
        """Called by Ableton when the script is unloaded."""
        if self._server:
            self._server.stop()
        self.log_message("LivePilot disconnected")
        ControlSurface.disconnect(self)
