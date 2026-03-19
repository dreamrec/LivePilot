"""
LivePilot - Ableton Live 12 Remote Script.

Entry point for the ControlSurface. Ableton calls create_instance(c_instance)
when this script is selected in Preferences > Link, Tempo & MIDI.
"""

__version__ = "1.8.2"

from _Framework.ControlSurface import ControlSurface
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


def create_instance(c_instance):
    """Factory function called by Ableton Live."""
    return LivePilot(c_instance)


class LivePilot(ControlSurface):
    """Main ControlSurface that starts the LivePilot TCP server."""

    def __init__(self, c_instance):
        ControlSurface.__init__(self, c_instance)
        self._server = LivePilotServer(self)
        self._server.start()
        self.log_message("LivePilot v1.8.1 initialized")
        self.show_message("LivePilot: Listening on port 9878")

    def disconnect(self):
        """Called by Ableton when the script is unloaded."""
        if self._server:
            self._server.stop()
        self.log_message("LivePilot disconnected")
        ControlSurface.disconnect(self)
