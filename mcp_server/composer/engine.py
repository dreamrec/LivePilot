"""Backward-compat shim — engine has moved to full/engine.py.

Existing code that imports from ``mcp_server.composer.engine`` continues
to work unchanged. New code should import from
``mcp_server.composer.full.engine`` directly.

This shim sets ``__file__`` to the real implementation path so that any
code doing ``open(engine.__file__).read()`` sees the actual source.
"""
import sys as _sys
import importlib as _importlib

# Ensure full.engine is loaded
_full = _importlib.import_module("mcp_server.composer.full.engine")

# Re-export everything
from .full.engine import *  # noqa: F401, F403
from .full.engine import ComposerEngine, CompositionResult  # explicit re-export

# Point __file__ at the real implementation so source-inspection tests work
__file__ = _full.__file__
