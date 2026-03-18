"""
LivePilot - Command dispatch registry.

Handlers register themselves via the @register decorator.
dispatch() is called on the main thread to route commands.
"""

from .utils import (
    success_response,
    error_response,
    INDEX_ERROR,
    INVALID_PARAM,
    NOT_FOUND,
    INTERNAL,
)

# ── Handler registry ─────────────────────────────────────────────────────────

_handlers = {}


def register(command_type):
    """Decorator that registers a handler function for *command_type*."""
    def decorator(fn):
        _handlers[command_type] = fn
        return fn
    return decorator


# ── Dispatcher ───────────────────────────────────────────────────────────────

def dispatch(song, command):
    """Route a parsed command dict to the appropriate handler.

    Parameters
    ----------
    song : Live.Song.Song
        The current song instance.
    command : dict
        Must contain ``id`` (str), ``type`` (str), and optionally ``params`` (dict).

    Returns
    -------
    dict
        A success or error response envelope.
    """
    request_id = command.get("id", "unknown")
    cmd_type = command.get("type")
    params = command.get("params", {})

    if cmd_type is None:
        return error_response(request_id, "Missing 'type' field", INVALID_PARAM)

    # Built-in ping — no handler registration needed.
    if cmd_type == "ping":
        return success_response(request_id, {"pong": True})

    handler = _handlers.get(cmd_type)
    if handler is None:
        return error_response(
            request_id,
            "Unknown command type: %s" % cmd_type,
            NOT_FOUND,
        )

    try:
        result = handler(song, params)
        return success_response(request_id, result)
    except IndexError as exc:
        return error_response(request_id, str(exc), INDEX_ERROR)
    except ValueError as exc:
        return error_response(request_id, str(exc), INVALID_PARAM)
    except Exception as exc:
        return error_response(request_id, str(exc), INTERNAL)
