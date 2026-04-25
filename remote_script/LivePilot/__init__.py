"""
LivePilot - Ableton Live 12 Remote Script.

Entry point for the ControlSurface. Ableton calls create_instance(c_instance)
when this script is selected in Preferences > Link, Tempo & MIDI.
"""

__version__ = "1.23.3"

from _Framework.ControlSurface import ControlSurface
from . import router
from .server import LivePilotServer
from . import utils        # noqa: F401  — shared helpers (get_track, get_device)
from . import transport    # noqa: F401  — registers transport handlers
from . import tracks       # noqa: F401  — registers track handlers
from . import clips        # noqa: F401  — registers clip handlers
from . import notes        # noqa: F401  — registers note handlers
from . import devices      # noqa: F401  — registers device handlers
from . import scenes       # noqa: F401  — registers scene handlers
from . import scales       # noqa: F401  — registers song scale handlers (12.0+)
from . import mixing       # noqa: F401  — registers mixing handlers
from . import browser      # noqa: F401  — registers browser handlers
from . import arrangement  # noqa: F401  — registers arrangement handlers
from . import diagnostics       # noqa: F401  — registers diagnostics handler
from . import follow_actions    # noqa: F401  — registers follow action handlers (12.0+, 12.2+)
from . import grooves           # noqa: F401  — registers groove pool handlers (11+)
from . import take_lanes        # noqa: F401  — registers take lane handlers (12.0+ read, 12.2+ write)
from . import clip_automation   # noqa: F401  — registers clip automation handlers
from . import simpler_sample    # noqa: F401  — registers replace_sample_native (12.4+)
from . import version_detect    # noqa: F401  — version detection


# ── Reload plumbing (BUG-B-reload, Batch 20) ──────────────────────────────
# Ableton keeps `sys.modules["LivePilot.*"]` cached across Control Surface
# toggles. Without intervention, edits to handler files don't take effect
# until a full Ableton restart.
#
# Fix: on every create_instance() except the first, re-discover every
# handler module on disk via pkgutil.iter_modules() and reload it. This
# side-steps two separate issues: (1) the old hardcoded _HANDLER_MODULES
# tuple that had to be manually updated for every new handler file, and
# (2) Ableton's embedded Python silently no-op'ing importlib.reload() on
# the package itself — a behavior confirmed empirically by observing
# that a module-level file write in __init__.py never fires across
# toggles, only at initial Live boot. pkgutil.iter_modules reads the
# filesystem directly and relies only on reloading leaf submodules
# (which Ableton handles correctly), so NEW handler files are picked up
# on the next toggle / TCP reload_handlers call.
#
# In addition, a `reload_handlers` TCP command is exposed so the dev
# loop becomes: edit source → sync → TCP reload_handlers → done. No
# more UI toggles required during iteration.
#
# Order matters:
#   1. Reload router first — clears _handlers so re-register is clean.
#   2. Reload utils next — every handler imports get_track/get_device
#      from it; must be fresh before handlers that depend on it reload.
#   3. Discover + reload everything else via pkgutil.

_FIRST_CREATE_INSTANCE = True

# Modules excluded from auto-reload. router is reloaded first (separately)
# because clearing its _handlers must precede re-register. server owns the
# TCP listener — reloading it mid-run would drop the socket.
_RELOAD_EXCLUDE = {"router", "server"}


def _force_reload_handlers(cs=None):
    """Re-discover and reload every handler submodule on disk.

    Uses pkgutil.iter_modules so NEW handler files added after Live boot
    are picked up on the next call without any hand-maintained tuple.
    Only touches leaf submodules — the one reload operation Ableton's
    embedded Python handles correctly. Reloading the package itself was
    tried and empirically no-ops in Ableton's Python.

    Order:
      1. Reload router → clears _handlers.
      2. Reload utils → every handler imports get_track/get_device from it.
      3. Discover + import/reload every other submodule. First-time imports
         fire @register once; reloads re-fire it after the router reset.
      4. Re-register reload_handlers_cmd (defined in __init__.py, not a
         handler module, so not covered by step 3).

    When ``cs`` is provided, reload exceptions log to the ControlSurface so
    a SyntaxError / NameError in an edited handler is surfaced in Live's
    status log instead of silently swallowed.
    """
    import importlib
    import pkgutil
    import sys as _sys

    def _log(msg):
        if cs is None:
            return
        try:
            cs.log_message("[LivePilot] " + msg)
        except Exception:
            pass

    try:
        importlib.reload(router)
    except Exception as exc:
        _log("reload(router) FAILED — %s: %s" % (type(exc).__name__, exc))

    try:
        importlib.reload(utils)
    except Exception as exc:
        _log("reload(utils) FAILED — %s: %s" % (type(exc).__name__, exc))

    # Invalidate caches so iter_modules sees newly-added files even if
    # an importer cached the previous directory listing.
    importlib.invalidate_caches()
    pkg = _sys.modules.get("LivePilot")
    if pkg is None or getattr(pkg, "__path__", None) is None:
        return

    discovered = reloaded = first_imported = 0
    for _finder, modname, _is_pkg in pkgutil.iter_modules(pkg.__path__):
        if modname in _RELOAD_EXCLUDE or modname == "utils":
            continue
        discovered += 1
        full_name = "LivePilot." + modname
        try:
            cached = _sys.modules.get(full_name)
            if cached is not None:
                importlib.reload(cached)
                reloaded += 1
            else:
                importlib.import_module(full_name)
                first_imported += 1
        except Exception as exc:
            _log("reload(%s) FAILED — %s: %s" % (
                full_name, type(exc).__name__, exc))

    # reload_handlers_cmd lives in __init__.py (not a handler module),
    # so the step-3 loop does not cover it. Re-register manually.
    router._handlers["reload_handlers"] = reload_handlers_cmd

    _log("reload complete — %d discovered (%d reloaded, %d first-imported)" % (
        discovered, reloaded, first_imported))


def reload_handlers_cmd(song, params):
    """TCP-accessible reload trigger. Lets automation refresh handlers
    without a UI Control Surface toggle — the core dev-loop improvement.
    Returns the handler count so the caller can assert before/after."""
    _force_reload_handlers(cs=None)
    return {
        "reloaded": True,
        "handler_count": len(router._handlers),
    }


# Register the TCP-triggered reload command for initial boot.
# _force_reload_handlers re-registers it after each reload cycle.
router._handlers["reload_handlers"] = reload_handlers_cmd


def create_instance(c_instance):
    """Factory function called by Ableton Live.

    Called once on initial Control Surface enable, AND every time the
    user toggles the Control Surface off and on. The reload path below
    makes the toggle behave like a fresh import — crucial for dev
    ergonomics when iterating on mixing.py / devices.py / etc.
    """
    global _FIRST_CREATE_INSTANCE
    if not _FIRST_CREATE_INSTANCE:
        _force_reload_handlers(cs=c_instance)
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
