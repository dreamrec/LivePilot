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
    STATE_ERROR,
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

    if params is None:
        params = {}
    elif not isinstance(params, dict):
        return error_response(
            request_id,
            "'params' must be an object/dict",
            INVALID_PARAM,
        )

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
        if isinstance(result, dict) and "error" in result:
            return error_response(
                request_id,
                result["error"],
                result.get("code", INTERNAL),
            )
        return success_response(request_id, result)
    except KeyError as exc:
        # Missing required parameter — report as INVALID_PARAM, not INTERNAL
        return error_response(
            request_id,
            "Missing required parameter: %s" % str(exc),
            INVALID_PARAM,
        )
    except IndexError as exc:
        return error_response(request_id, str(exc), INDEX_ERROR)
    except ValueError as exc:
        return error_response(request_id, str(exc), INVALID_PARAM)
    except RuntimeError as exc:
        return error_response(request_id, str(exc), STATE_ERROR)
    except Exception as exc:
        return error_response(request_id, str(exc), INTERNAL)
