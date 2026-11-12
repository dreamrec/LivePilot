"""Private subprocess entry point for bounded offline audio analysis."""
from __future__ import annotations

from contextlib import redirect_stdout
import importlib
import json
import sys

from .offline_analysis import OPERATIONS


def main():
    try:
        request = json.load(sys.stdin)
        operation = request["operation"]
        module_name = OPERATIONS[operation]
        # Third-party imports may print progress. Never mix that with the
        # single JSON response consumed by the parent process.
        with redirect_stdout(sys.stderr):
            # Load the registry in its canonical order. Importing a tool
            # module first can cycle through server -> taste tools -> listening
            # while listening's helpers are still only partially defined.
            importlib.import_module("mcp_server.server")
            module = importlib.import_module(module_name)
            fn = getattr(module, operation).__wrapped__
            result = fn(**request["arguments"])
    except ValueError as exc:
        result = {"error": str(exc), "code": "INVALID_PARAM"}
    except Exception as exc:
        result = {"error": f"Offline analysis failed: {exc}", "code": "INTERNAL"}
    sys.stdout.write(json.dumps(result))
    sys.stdout.flush()


if __name__ == "__main__":
    main()
